"""
OBS Ders Kayıt Motoru — API uyumlu versiyon.
claudeai2-optimal.py mantığının sınıf tabanlı, event-driven adaptasyonu.
Zamanlama hassasiyeti korunur (busy-wait, Date header geçişi vb.).
"""

import time
import threading
import queue
import subprocess
import sys
import ctypes
import os
import socket
from email.utils import parsedate_to_datetime
from dataclasses import dataclass, field
from typing import Optional, Callable

import requests
import requests.adapters


class OptimizedHTTPAdapter(requests.adapters.HTTPAdapter):
    """Socket seviyesinde TCP optimizasyonları uygulayan HTTP adapter.

    - TCP_NODELAY: Nagle algoritmasını devre dışı bırak (küçük paketler hemen gönderilir)
    - SO_KEEPALIVE: OS seviyesinde TCP keepalive (bağlantı timeout'unu önler)
    - TCP_QUICKACK (Linux): Gecikmeli ACK'ları devre dışı bırak → RTT 5-15ms düşer
    """

    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        if hasattr(self.poolmanager, 'connection_pool_kw'):
            opts = list(self.poolmanager.connection_pool_kw.get('socket_options', []))
            opts.append((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1))
            opts.append((socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1))
            if sys.platform == "linux":
                opts.append((socket.IPPROTO_TCP, 12, 1))  # TCP_QUICKACK
            self.poolmanager.connection_pool_kw['socket_options'] = opts


OBS_URL = "https://obs.itu.edu.tr/api/ders-kayit/v21"
OBS_BASE = "https://obs.itu.edu.tr"

HATA_KODLARI = {
    "VAL02": "Kayıt dönemi henüz açılmadı",
    "VAL03": "Bu ders zaten alınmış",
    "VAL06": "Kontenjan dolu",
    "VAL09": "Ders çakışması var",
    "VAL16": "Debounce (sunucu <3sn'de tekrarı yok saydı)",
    "VAL22": "Yükseltmeye alınan ders çakışması",
}


@dataclass
class CalibrationData:
    server_offset: float = 0.0
    rtt_one_way: float = 0.003
    ntp_offset: float = 0.0


class RegistrationEngine:
    """Tek kullanımlık kayıt motoru. Her kayıt oturumu için yeni instance oluştur."""

    def __init__(
        self,
        token: str,
        ecrn_list: list[str],
        scrn_list: list[str] | None = None,
        kayit_saati: str = "",
        max_deneme: int = 60,
        retry_aralik: float = 3.0,
        gecikme_buffer: float = 0.005,
        dry_run: bool = False,
    ):
        self.token = token
        self.ecrn_list = list(ecrn_list)
        self.scrn_list = list(scrn_list or [])
        self.kayit_saati = kayit_saati
        self.max_deneme = max_deneme
        self.retry_aralik = retry_aralik
        self.gecikme_buffer = gecikme_buffer
        self.dry_run = dry_run

        self._events: queue.Queue = queue.Queue()
        self._cancelled = threading.Event()
        self._running = False
        self._phase = "idle"
        self._current_attempt = 0
        self._calibration: Optional[CalibrationData] = None
        self._cal_samples: list[tuple[float, float, float, str]] = []  # (offset, rtt, timestamp, source)
        self._crn_results: dict[str, dict] = {}
        self._trigger_time: Optional[float] = None

        # Session
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        adapter = OptimizedHTTPAdapter(
            pool_connections=1, pool_maxsize=5, max_retries=0,
        )
        self.session.mount("https://", adapter)

    # ── Event emitter ──

    def _emit(self, event_type: str, data: dict | None = None):
        self._events.put({
            "type": event_type,
            "data": data or {},
            "timestamp": time.time(),
        })

    def _log(self, msg: str, level: str = "info"):
        self._emit("log", {"message": msg, "level": level})

    def get_events(self) -> list[dict]:
        events = []
        while not self._events.empty():
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                break
        return events

    # ── State ──

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def current_attempt(self) -> int:
        return self._current_attempt

    @property
    def calibration(self) -> Optional[CalibrationData]:
        return self._calibration

    @property
    def crn_results(self) -> dict:
        return self._crn_results

    @property
    def trigger_time(self) -> Optional[float]:
        return self._trigger_time

    def cancel(self):
        self._cancelled.set()
        self._log("İptal edildi", "warning")

    def _best_calibration(self) -> Optional[CalibrationData]:
        """Tüm ölçüm havuzundan en düşük RTT'li sample'ı seç (en güvenilir offset)."""
        if not self._cal_samples:
            return self._calibration
        # En düşük RTT = en yüksek güvenilirlik
        best = min(self._cal_samples, key=lambda s: s[1])
        return CalibrationData(
            server_offset=best[0],
            rtt_one_way=best[1] / 2,
            ntp_offset=self._calibration.ntp_offset if self._calibration else 0.0,
        )

    def _add_sample(self, offset: float, rtt: float, source: str):
        """Kalibrasyon ölçüm havuzuna yeni sample ekle. Max 20 tutar, eski/kötü olanları atar."""
        self._cal_samples.append((offset, rtt, time.time(), source))
        # Havuzu 20 ile sınırla: en kötü RTT'lileri at
        if len(self._cal_samples) > 20:
            self._cal_samples.sort(key=lambda s: s[1])
            self._cal_samples = self._cal_samples[:20]

    def _set_phase(self, phase: str):
        self._phase = phase
        self._emit("state", {"phase": phase, "running": self._running})

    # ── RTT Ölçümü ──

    def _rtt_olc(self, n: int = 5) -> float:
        rtts = []
        for _ in range(n):
            t0 = time.perf_counter()
            try:
                self.session.head(OBS_BASE, timeout=5, allow_redirects=False)
            except Exception:
                continue
            rtts.append(time.perf_counter() - t0)
        if not rtts:
            return 0.010
        rtts.sort()
        return rtts[len(rtts) // 2]

    # ── NTP (bilgilendirme) ──

    def _ntp_offset(self) -> float:
        if sys.platform == "win32":
            try:
                result = subprocess.run(
                    ["w32tm", "/stripchart", "/computer:time.windows.com",
                     "/dataonly", "/samples:3"],
                    capture_output=True, text=True, timeout=15,
                )
                offsets = []
                for line in result.stdout.strip().split("\n"):
                    if "," in line and "s" in line:
                        try:
                            val = line.split(",")[1].strip().rstrip("s").strip()
                            offsets.append(float(val))
                        except (ValueError, IndexError):
                            continue
                if offsets:
                    offsets.sort()
                    return offsets[len(offsets) // 2]
            except Exception:
                pass
        try:
            import ntplib
            c = ntplib.NTPClient()
            resp = c.request("pool.ntp.org", version=3, timeout=5)
            return resp.offset
        except Exception:
            pass
        return 0.0

    # ── Sunucu Offset Ölçümü (Date Header Geçişi) ──

    def calibrate(self, source: str = "manual") -> CalibrationData:
        self._set_phase("calibrating")
        self._log("Sunucu saati ölçülüyor...")

        # Bağlantıyı ısıt
        try:
            self.session.head(OBS_BASE, timeout=10, allow_redirects=False)
        except Exception as e:
            self._log(f"Bağlantı hatası: {e}", "error")
            ntp = self._ntp_offset()
            self._calibration = CalibrationData(server_offset=ntp, rtt_one_way=0.010, ntp_offset=ntp)
            return self._calibration

        medyan_rtt = self._rtt_olc(5)
        poll_aralik = max(0.002, min(medyan_rtt / 2, 0.050))
        max_poll = int(2.0 / poll_aralik)

        self._log(f"RTT: {medyan_rtt*1000:.0f}ms → poll: {poll_aralik*1000:.0f}ms")

        offsets = []
        for gecis_no in range(3):
            if self._cancelled.is_set():
                break
            try:
                r = self.session.head(OBS_BASE, timeout=10, allow_redirects=False)
            except Exception:
                break

            son_date = r.headers.get("Date", "")
            if not son_date:
                self._log("Date header yok!", "warning")
                break

            if gecis_no == 0:
                self._log(f"Sunucu: {son_date}")

            for _ in range(max_poll):
                t0_pc = time.perf_counter()
                t_utc = time.time()
                try:
                    r = self.session.head(OBS_BASE, timeout=5, allow_redirects=False)
                except Exception:
                    time.sleep(poll_aralik)
                    continue
                rtt = time.perf_counter() - t0_pc

                yeni = r.headers.get("Date", "")
                if yeni and yeni != son_date:
                    server_ts = parsedate_to_datetime(yeni).timestamp()
                    offset = (t_utc + rtt / 2) - server_ts
                    offsets.append((offset, rtt))
                    self._log(f"Geçiş #{gecis_no+1}: RTT={rtt*1000:.0f}ms, offset={offset*1000:+.0f}ms")
                    break
                time.sleep(poll_aralik)

            if offsets:
                en_iyi = min(o[1] for o in offsets)
                if en_iyi < medyan_rtt * 0.8 and gecis_no >= 1:
                    break

        # NTP (bilgilendirme)
        ntp_off = self._ntp_offset()

        if offsets:
            # Tüm geçişleri havuza ekle
            for off, rtt in offsets:
                self._add_sample(off, rtt, source)

            offsets.sort(key=lambda x: x[1])
            best_offset, best_rtt = offsets[0]
            tek_yon = best_rtt / 2
            self._calibration = CalibrationData(
                server_offset=best_offset,
                rtt_one_way=tek_yon,
                ntp_offset=ntp_off,
            )
            yon = "İLERİDE" if best_offset > 0 else "GERİDE"
            self._log(f"Sonuç: {abs(best_offset*1000):.0f}ms {yon} (±{tek_yon*1000:.0f}ms) [havuz: {len(self._cal_samples)} ölçüm]")
        else:
            self._log("Date geçişi yakalanamadı → NTP fallback", "warning")
            self._calibration = CalibrationData(
                server_offset=ntp_off,
                rtt_one_way=medyan_rtt / 2,
                ntp_offset=ntp_off,
            )

        self._emit("calibration", {
            "server_offset_ms": self._calibration.server_offset * 1000,
            "rtt_one_way_ms": self._calibration.rtt_one_way * 1000,
            "rtt_full_ms": self._calibration.rtt_one_way * 2000,
            "ntp_offset_ms": ntp_off * 1000,
            "server_ntp_diff_ms": (self._calibration.server_offset - ntp_off) * 1000,
            "accuracy_ms": self._calibration.rtt_one_way * 1000,
            "source": source,
        })
        return self._calibration

    # ── Hafif Kalibrasyon (bekleme sırasında periyodik) ──

    def _quick_calibrate(self, source: str = "auto") -> CalibrationData | None:
        """Hafif kalibrasyon: 1 Date geçişi + 3 RTT örneği. ~2-3 saniye sürer."""
        try:
            medyan_rtt = self._rtt_olc(3)
            poll_aralik = max(0.002, min(medyan_rtt / 2, 0.050))
            max_poll = int(2.0 / poll_aralik)

            r = self.session.head(OBS_BASE, timeout=5, allow_redirects=False)
            son_date = r.headers.get("Date", "")
            if not son_date:
                return None

            for _ in range(max_poll):
                if self._cancelled.is_set():
                    return None
                t0_pc = time.perf_counter()
                t_utc = time.time()
                try:
                    r = self.session.head(OBS_BASE, timeout=5, allow_redirects=False)
                except Exception:
                    time.sleep(poll_aralik)
                    continue
                rtt = time.perf_counter() - t0_pc

                yeni = r.headers.get("Date", "")
                if yeni and yeni != son_date:
                    server_ts = parsedate_to_datetime(yeni).timestamp()
                    offset = (t_utc + rtt / 2) - server_ts
                    tek_yon = rtt / 2

                    # Havuza ekle
                    self._add_sample(offset, rtt, source)

                    # En iyi ölçümü havuzdan seç
                    best = self._best_calibration()
                    if best:
                        self._calibration = best

                    prev_ntp = self._calibration.ntp_offset if self._calibration else 0.0

                    self._emit("calibration", {
                        "server_offset_ms": self._calibration.server_offset * 1000,
                        "rtt_one_way_ms": self._calibration.rtt_one_way * 1000,
                        "rtt_full_ms": self._calibration.rtt_one_way * 2000,
                        "ntp_offset_ms": prev_ntp * 1000,
                        "server_ntp_diff_ms": (self._calibration.server_offset - prev_ntp) * 1000,
                        "accuracy_ms": self._calibration.rtt_one_way * 1000,
                        "source": source,
                    })
                    self._log(f"⚡ Hızlı kal: ölçüm={offset*1000:+.0f}ms/{rtt*1000:.0f}ms → en iyi: {self._calibration.server_offset*1000:+.0f}ms/{self._calibration.rtt_one_way*1000:.0f}ms [havuz:{len(self._cal_samples)}]")
                    return self._calibration
                time.sleep(poll_aralik)

            return None
        except Exception as e:
            self._log(f"Hızlı kalibrasyon hatası: {e}", "warning")
            return None

    # ── Prewarm ──

    def _prewarm(self, head_only: bool = False):
        try:
            self.session.head(OBS_BASE, timeout=10, allow_redirects=False)
            if not head_only:
                self.session.post(OBS_URL, json={"ECRN": ["00000"], "SCRN": []}, timeout=10)
            self._log("Bağlantı hazır" + (" (HEAD only)" if head_only else ""))
        except Exception as e:
            self._log(f"Prewarm hatası: {e}", "warning")

    # ── PreparedRequest ──

    def _build_request(self, ecrn_list: list[str]) -> requests.PreparedRequest:
        req = requests.Request(
            method="POST", url=OBS_URL,
            json={"ECRN": ecrn_list, "SCRN": self.scrn_list},
        )
        return self.session.prepare_request(req)

    # ── Dry-Run Simülasyonu ──

    def _kayit_yap_dry_run(self):
        """DRY RUN: Gerçek sunucuya dummy CRN ile istek atarak zamanlama doğruluğunu analiz eder."""
        kalan = list(self.ecrn_list)

        for crn in kalan:
            self._crn_results[crn] = {"status": "pending", "message": "Bekliyor (DRY RUN)"}

        self._log("═══════════════════════════════════", "warning")
        self._log("🧪 DRY RUN — Zamanlama Analizi", "warning")
        self._log("═══════════════════════════════════", "warning")

        hedef = self._saat_to_epoch(self.kayit_saati)

        # 1. Gerçek sunucuya dummy istek at — zamanlama ölçümü
        self._log("🎯 Gerçek sunucuya test isteği gönderiliyor (dummy CRN: 00000)...")
        t0_wall = time.time()
        t0_perf = time.perf_counter()
        try:
            resp = self.session.post(OBS_URL, json={"ECRN": ["00000"], "SCRN": []}, timeout=10)
            t1_wall = time.time()
            t1_perf = time.perf_counter()
            rtt_ms = (t1_perf - t0_perf) * 1000
            gonderim_wall = t0_wall
            varis_tahmini = t0_wall + (t1_perf - t0_perf) / 2  # RTT/2 = sunucu varış tahmini
            hedef_fark_ms = (gonderim_wall - hedef) * 1000
            varis_fark_ms = (varis_tahmini - hedef) * 1000

            self._log(f"📊 HTTP {resp.status_code} | RTT: {rtt_ms:.0f}ms")
            self._log("─────────────────────────────────")
            self._log(f"📤 İstek gönderim (yerel saat): hedef {hedef_fark_ms:+.0f}ms")
            self._log(f"📥 Tahmini varış (yerel saat): hedef {varis_fark_ms:+.0f}ms")

            # Sunucu perspektifine dönüştür (offset = yerel - sunucu)
            if self._calibration:
                offset_ms = self._calibration.server_offset * 1000
                sunucu_gonderim_ms = hedef_fark_ms - offset_ms
                sunucu_varis_ms = varis_fark_ms - offset_ms
                self._log(f"🎯 Sunucu perspektifi: gönderim {sunucu_gonderim_ms:+.0f}ms, varış {sunucu_varis_ms:+.0f}ms")
            else:
                sunucu_varis_ms = varis_fark_ms

            # Sunucu Date header'ından gerçek sunucu saati doğrulaması
            server_date = resp.headers.get("Date", "")
            if server_date:
                try:
                    server_ts = parsedate_to_datetime(server_date).timestamp()
                    server_hedef_fark = (server_ts - hedef) * 1000
                    self._log(f"🕐 Sunucu Date header: hedef {server_hedef_fark:+.0f}ms (1sn granülarite)")
                except Exception:
                    pass

            # Değerlendirme (sunucu perspektifinden)
            if abs(sunucu_varis_ms) <= 50:
                self._log(f"✅ MÜKEMMEL — Sunucuya ±50ms içinde ulaştı ({sunucu_varis_ms:+.0f}ms)")
            elif abs(sunucu_varis_ms) <= 200:
                self._log(f"👍 İYİ — Sunucuya ±200ms içinde ulaştı ({sunucu_varis_ms:+.0f}ms)")
            elif sunucu_varis_ms < -200:
                self._log(f"⚠️ ERKEN — İstek sunucuya {abs(sunucu_varis_ms):.0f}ms erken ulaştı (VAL02 riski)", "warning")
            else:
                self._log(f"⚠️ GEÇ — İstek sunucuya {sunucu_varis_ms:.0f}ms geç ulaştı (kontenjan kaçırma riski)", "warning")

            self._log("─────────────────────────────────")

            # Kalibrasyon verileriyle karşılaştır
            if self._calibration:
                cal = self._calibration
                self._log(f"📐 Kalibrasyon: offset={cal.server_offset*1000:+.0f}ms, RTT(tek yön)={cal.rtt_one_way*1000:.0f}ms")
                teorik_sunucu_varis = sunucu_gonderim_ms + cal.rtt_one_way * 1000
                self._log(f"📐 Teorik sunucu varış: hedef {teorik_sunucu_varis:+.0f}ms (sunucu saati)")

        except Exception as e:
            self._log(f"❌ Test isteği hatası: {e}", "error")

        self._log("─────────────────────────────────")

        # 2. Sonuçları simüle et (gerçek kayıtta ne olacağını göster)
        self._log("🧪 CRN sonuçları simüle ediliyor...")
        for deneme in range(1, min(self.max_deneme, 4) + 1):
            if not kalan or self._cancelled.is_set():
                break
            self._current_attempt = deneme
            if deneme <= 2:
                for crn in kalan:
                    self._crn_results[crn] = {"status": "debounce", "message": "DRY RUN: Sistem henüz açılmadı"}
                self._emit("crn_update", {"results": dict(self._crn_results)})
                time.sleep(0.1)
            else:
                for crn in list(kalan):
                    self._crn_results[crn] = {"status": "success", "message": "DRY RUN: Simüle edilmiş başarı"}
                    kalan.remove(crn)
                self._emit("crn_update", {"results": dict(self._crn_results)})
                break

        basarili = len(self.ecrn_list) - len(kalan)
        self._log(f"🧪 DRY RUN TAMAMLANDI — {basarili}/{len(self.ecrn_list)} simüle başarı")

    # ── Kayıt Döngüsü ──

    def _kayit_yap(self):
        kalan = list(self.ecrn_list)
        basarili = []
        basarisiz = {}
        aralik = self.retry_aralik

        # CRN sonuçlarını başlat
        for crn in kalan:
            self._crn_results[crn] = {"status": "pending", "message": "Bekliyor"}

        prepped = self._build_request(kalan)
        ilk = True
        crn_degisti = False

        for deneme in range(1, self.max_deneme + 1):
            if not kalan or self._cancelled.is_set():
                break

            self._current_attempt = deneme
            t0 = time.perf_counter()

            if not ilk:
                if crn_degisti:
                    prepped = self._build_request(kalan)
                    crn_degisti = False

            try:
                resp = self.session.send(prepped, timeout=10)
            except requests.exceptions.RequestException as e:
                self._log(f"Bağlantı hatası: {e}", "error")
                time.sleep(aralik)
                ilk = False
                continue

            ms = (time.perf_counter() - t0) * 1000
            tag = "İLK İSTEK" if ilk else f"D{deneme}"
            self._log(f"{tag} → {ms:.0f}ms | HTTP {resp.status_code}")
            ilk = False

            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", "5"))
                self._log(f"RATE LIMIT! {wait}sn bekleniyor...", "warning")
                aralik = min(max(aralik * 3, 1.0), 5.0)
                time.sleep(wait)
                continue

            if resp.status_code in (401, 403):
                self._log(f"HTTP {resp.status_code} — Token geçersiz!", "error")
                break

            tum_val02 = True

            if resp.status_code == 200:
                data = resp.json()
                for item in (data.get("ecrnResultList") or []):
                    crn = item.get("crn")
                    sc = item.get("statusCode")
                    rc = item.get("resultCode")
                    rd = item.get("resultData")

                    if rc not in ("VAL02", "VAL16"):
                        tum_val02 = False

                    if sc == 0:
                        self._log(f"✅ {crn} → BAŞARILI!")
                        self._crn_results[crn] = {"status": "success", "message": "Kayıt başarılı"}
                        if crn in kalan:
                            kalan.remove(crn)
                            basarili.append(crn)
                            crn_degisti = True

                    elif rc == "VAL03":
                        self._log(f"✅ {crn} → Zaten alınmış")
                        self._crn_results[crn] = {"status": "already", "message": "Zaten kayıtlı"}
                        if crn in kalan:
                            kalan.remove(crn)
                            basarili.append(crn)
                            crn_degisti = True

                    elif rc == "VAL02":
                        if deneme <= 2:
                            self._log(f"⏳ {crn} → Sistem henüz açılmadı")

                    elif rc == "VAL16":
                        if deneme <= 2:
                            self._log(f"⚠️ {crn} → Debounce")
                        self._crn_results[crn] = {"status": "debounce", "message": "Debounce — tekrar denenecek"}

                    elif rc == "VAL06":
                        self._log(f"🚫 {crn} → KONTENJAN DOLU", "error")
                        self._crn_results[crn] = {"status": "full", "message": "Kontenjan dolu"}
                        if crn in kalan:
                            kalan.remove(crn)
                            basarisiz[crn] = "Kontenjan dolu"
                            crn_degisti = True

                    elif rc == "VAL09":
                        self._log(f"⚠️ {crn} → Çakışma", "warning")
                        self._crn_results[crn] = {"status": "conflict", "message": "Ders çakışması"}
                        if crn in kalan:
                            kalan.remove(crn)
                            basarisiz[crn] = "Çakışma"
                            crn_degisti = True

                    elif rc == "VAL22":
                        d = rd.get("yukseltmeyeAlinanDers", "?") if rd else "?"
                        self._log(f"📚 {crn} → Yükseltme çakışması: {d}", "warning")
                        self._crn_results[crn] = {"status": "upgrade", "message": f"Yükseltme: {d}"}
                        if crn in kalan:
                            kalan.remove(crn)
                            basarisiz[crn] = f"Yükseltme: {d}"
                            crn_degisti = True
                    else:
                        desc = HATA_KODLARI.get(rc, rc)
                        self._log(f"❌ {crn} → {desc}", "error")
                        self._crn_results[crn] = {"status": "error", "message": desc}

                self._emit("crn_update", {"results": dict(self._crn_results)})
            else:
                tum_val02 = False
                self._log(f"HTTP {resp.status_code}: {resp.text[:200]}", "error")

            if kalan and deneme < self.max_deneme:
                if tum_val02:
                    time.sleep(self.retry_aralik)
                else:
                    time.sleep(0.05)

        # Özet
        self._log(f"Başarılı: {len(basarili)}/{len(self.ecrn_list)}")
        if basarisiz:
            for c, s in basarisiz.items():
                self._log(f"  Başarısız: {c} — {s}", "error")
        if kalan:
            self._log(f"  Kalan: {kalan}", "warning")

    # ── Saat yardımcısı ──

    @staticmethod
    def _saat_to_epoch(saat_str: str) -> float:
        """HH:MM:SS → bugünün epoch float (Türkiye saati, sunucu timezone'undan bağımsız)."""
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo  # Python <3.9 fallback
        h, m, s = map(int, saat_str.split(":"))
        tz = ZoneInfo("Europe/Istanbul")
        now = datetime.now(tz)
        target = now.replace(hour=h, minute=m, second=s, microsecond=0)
        return target.timestamp()

    # ── Sistem Optimizasyonları ──

    def _set_timer_resolution(self, high_res: bool):
        """Timer çözünürlüğünü optimize et (Windows: 1ms, Linux: native ~1ms)."""
        if sys.platform == "win32":
            try:
                winmm = ctypes.WinDLL("winmm", use_last_error=True)
                if high_res:
                    winmm.timeBeginPeriod(1)
                    self._log("⚡ Windows timer çözünürlüğü: 1ms")
                else:
                    winmm.timeEndPeriod(1)
            except Exception:
                pass
        elif high_res:
            self._log("⚡ Linux timer: ~1ms native")

    def _boost_priority(self):
        """Process ve thread önceliğini yükselt (cross-platform)."""
        if sys.platform == "win32":
            try:
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.GetCurrentProcess()
                kernel32.SetPriorityClass(handle, 0x80)  # HIGH_PRIORITY_CLASS
                thread_handle = kernel32.GetCurrentThread()
                kernel32.SetThreadPriority(thread_handle, 2)  # THREAD_PRIORITY_HIGHEST
                self._log("⚡ Process/thread önceliği yükseltildi")
            except Exception:
                pass
        else:
            # Linux / Cloud Run (root olarak çalışır)
            opts = []
            try:
                os.nice(-10)
                opts.append("nice=-10")
            except (PermissionError, OSError):
                pass
            try:
                os.sched_setaffinity(0, {0})
                opts.append("cpu=0")
            except (AttributeError, OSError):
                pass
            if opts:
                self._log(f"⚡ Linux optimizasyonları: {', '.join(opts)}")

    # ── Ana orkestratör (thread içinde çalışır) ──

    def run(self):
        """Tam kayıt akışı: token kontrol → kalibrasyon → ısınma → bekleme → kayıt."""
        self._running = True
        self._set_timer_resolution(True)
        self._boost_priority()

        try:
            if self.dry_run:
                self._log("═══════════════════════════════════", "warning")
                self._log("🧪 DRY RUN MODU — Gerçek kayıt yapılMAyacak", "warning")
                self._log("═══════════════════════════════════", "warning")

            # 0. Token geçerlilik kontrolü
            self._set_phase("token_check")
            self._log("🔑 Token kontrol ediliyor...")
            token_result = self.test_token()
            if not token_result["valid"]:
                self._log(f"❌ Token geçersiz: {token_result['message']}", "error")
                self._log("Lütfen OBS'den yeni token alıp tekrar deneyin.", "error")
                return
            self._log("✅ Token geçerli")

            if self._cancelled.is_set():
                return

            # 1. Kalibrasyon
            self._set_phase("calibrating")
            cal = self.calibrate(source="initial")
            if self._cancelled.is_set():
                return

            # 2. Ilk ısınma (POST dahil)
            self._prewarm(head_only=False)

            # 3. Tetik zamanı (havuzdaki en iyi ölçüme göre)
            hedef = self._saat_to_epoch(self.kayit_saati)
            best = self._best_calibration()
            tetik = hedef + best.server_offset - best.rtt_one_way + self.gecikme_buffer
            self._trigger_time = tetik

            kalan_sn = tetik - time.time()
            self._log(f"Tetik: {self.kayit_saati} +{self.gecikme_buffer*1000:.0f}ms | {kalan_sn:.1f}s kaldı")

            self._emit("countdown", {"trigger_time": tetik, "remaining": kalan_sn})

            if kalan_sn < -5:
                self._log("Hedef zaman geçti! Hemen başlıyorum...", "warning")
                self._set_phase("registering")
                if self.dry_run:
                    self._kayit_yap_dry_run()
                else:
                    self._kayit_yap()
                return

            # 4. Bekleme döngüsü (sürekli kalibrasyon ile)
            self._set_phase("waiting")
            prewarm2 = False
            keepalive_5s = False
            final_cal_done = False
            last_recal_time = time.time()
            RECAL_INTERVAL = 30  # her X saniyede hafif kalibrasyon
            FINAL_CAL_WINDOW = 45  # son tam kalibrasyon bu saniyede başlar
            FINAL_CAL_MIN = 15  # bundan yakın olursa zaten yapma
            recal_count = 0

            def _recalc_trigger():
                """Havuzdaki en iyi ölçüme göre tetik zamanını yeniden hesapla."""
                best = self._best_calibration()
                if best:
                    return hedef + best.server_offset - best.rtt_one_way + self.gecikme_buffer
                return tetik

            while not self._cancelled.is_set():
                now = time.time()
                kalan = tetik - now

                # Countdown event (her saniye)
                self._emit("countdown", {"trigger_time": tetik, "remaining": kalan})

                # ── Periyodik hafif kalibrasyon (>25sn kala, her 30sn) ──
                if kalan > 25 and (now - last_recal_time) >= RECAL_INTERVAL:
                    recal_count += 1
                    self._log(f"🔄 Periyodik kalibrasyon #{recal_count}...")
                    self._quick_calibrate(source="auto")
                    eski_tetik = tetik
                    tetik = _recalc_trigger()
                    self._trigger_time = tetik
                    fark = (tetik - eski_tetik) * 1000
                    if abs(fark) > 1:
                        self._log(f"🔄 Tetik güncellendi: {fark:+.0f}ms kayma (en iyi RTT: {self._calibration.rtt_one_way*1000:.0f}ms)")
                    kalan = tetik - time.time()
                    last_recal_time = now

                # ── Son TAM kalibrasyon (35-45sn kala) ──
                if not final_cal_done and FINAL_CAL_MIN < kalan <= FINAL_CAL_WINDOW:
                    self._log("🎯 Son tam kalibrasyon başlıyor...")
                    self.calibrate(source="final")
                    eski_tetik = tetik
                    tetik = _recalc_trigger()
                    self._trigger_time = tetik
                    fark = (tetik - eski_tetik) * 1000
                    best = self._best_calibration()
                    self._log(f"🎯 Son kalibrasyon tamam → tetik farkı: {fark:+.0f}ms | en iyi: offset={best.server_offset*1000:+.0f}ms RTT={best.rtt_one_way*1000:.0f}ms [havuz:{len(self._cal_samples)}]")
                    kalan = tetik - time.time()
                    self._emit("countdown", {"trigger_time": tetik, "remaining": kalan})
                    final_cal_done = True
                    # Final sonrası bağlantıyı tekrar ısıt
                    self._prewarm(head_only=True)
                    prewarm2 = True

                # ── Bağlantı canlı tutma (10s ve 5s kala) ──
                if not prewarm2 and 0 < kalan <= 10:
                    self._prewarm(head_only=True)
                    prewarm2 = True
                elif prewarm2 and not keepalive_5s and 4.5 < kalan <= 5.5:
                    # 5s kala ikinci keepalive
                    keepalive_5s = True
                    try:
                        self.session.head(OBS_BASE, timeout=3, allow_redirects=False)
                    except Exception:
                        pass

                # ── Busy-wait (son 50ms — perf_counter ile yüksek çözünürlük) ──
                if kalan <= 0.05:
                    pc_tetik = time.perf_counter() + (tetik - time.time())
                    while time.perf_counter() < pc_tetik:
                        pass
                    break

                # ── Kademeli uyku (gereksiz wakeup'ları minimize et) ──
                if kalan <= 0.5:
                    time.sleep(max(0, kalan - 0.05))
                elif kalan <= 5:
                    time.sleep(0.005)
                else:
                    time.sleep(min(1.0, kalan - 5))

            if self._cancelled.is_set():
                return

            # 5. KAYIT
            self._set_phase("registering")
            fark_ms = (time.time() - hedef) * 1000
            best = self._best_calibration()
            self._log(f"BAŞLIYOR! (hedef farkı: {fark_ms:+.0f}ms) [offset={best.server_offset*1000:+.0f}ms RTT={best.rtt_one_way*1000:.0f}ms havuz:{len(self._cal_samples)}]")
            if self.dry_run:
                self._kayit_yap_dry_run()
            else:
                self._kayit_yap()

        except Exception as e:
            self._log(f"Beklenmeyen hata: {e}", "error")
        finally:
            self._set_timer_resolution(False)
            self._set_phase("done")
            self._emit("done", {"results": dict(self._crn_results)})
            self._running = False  # MUST be last — poll_engine_events checks this flag

    # ── Token testi ──

    def test_token(self) -> dict:
        try:
            r = self.session.post(OBS_URL, json={"ECRN": ["00000"], "SCRN": []}, timeout=10)
            if r.status_code == 200:
                return {"valid": True, "status_code": 200, "message": "Token geçerli"}
            elif r.status_code in (401, 403):
                return {"valid": False, "status_code": r.status_code, "message": "Token geçersiz veya süresi dolmuş"}
            else:
                return {"valid": True, "status_code": r.status_code, "message": f"Sunucu yanıtı: {r.status_code}"}
        except Exception as e:
            return {"valid": False, "status_code": 0, "message": str(e)}
