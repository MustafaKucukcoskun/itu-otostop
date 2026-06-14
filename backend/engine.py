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
import gc
from collections import deque
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
    - TCP_SLOW_START_AFTER_IDLE=0 (Linux): Boşta kaldıktan sonra cwnd reset'ini önler
    """

    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        if hasattr(self.poolmanager, 'connection_pool_kw'):
            opts = list(self.poolmanager.connection_pool_kw.get('socket_options', []))
            opts.append((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1))
            opts.append((socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1))
            if sys.platform == "linux":
                opts.append((socket.IPPROTO_TCP, 12, 1))  # TCP_QUICKACK
                opts.append((socket.IPPROTO_TCP, 23, 0))  # TCP_SLOW_START_AFTER_IDLE=0
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
    obs_clock_offset: float = 0.0       # OBS-NTP saat farkı (sn)
    obs_clock_uncertainty: float = 0.025 # OBS saat belirsizliği (sn)


class TrendAnalyzer:
    """Ofset ve RTT değerlerinin trend analizini yapar."""
    def __init__(self, window_size=10):
        self.window_size = window_size
        self.data_points = deque(maxlen=window_size)  # [(timestamp, value), ...]
    
    def add_measurement(self, timestamp, value):
        """Yeni ölçüm ekle"""
        self.data_points.append((timestamp, value))
    
    def calculate_linear_trend(self):
        """Lineer regresyonla trend hesapla: y = mx + b"""
        if len(self.data_points) < 2:
            return 0.0, 0.0  # slope, intercept
        
        n = len(self.data_points)
        timestamps = [point[0] for point in self.data_points]
        values = [point[1] for point in self.data_points]
        
        # Lineer regresyon: y = mx + b
        sum_x = sum(timestamps)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(timestamps, values))
        sum_x_sq = sum(x * x for x in timestamps)
        
        denominator = n * sum_x_sq - sum_x * sum_x
        if denominator == 0:
            return 0.0, sum_y / n
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n
        
        return slope, intercept
    
    def predict_value_at_time(self, future_timestamp):
        """Belirli bir zamanda değerin ne olacağını tahmin et"""
        slope, intercept = self.calculate_linear_trend()
        return slope * future_timestamp + intercept


class ChangeDetector:
    """Anlamlı değişiklikleri tespit eder."""
    def __init__(self, threshold=0.050, min_window=3):
        self.threshold = threshold  # 50ms değişiklik eşik değeri
        self.min_window = min_window
        self.values = deque(maxlen=10)
    
    def add_value(self, value):
        """Yeni değeri ekle"""
        self.values.append(value)
    
    def detect_significant_change(self):
        """Anlamlı değişiklik olup olmadığını kontrol et"""
        if len(self.values) < self.min_window:
            return False
        
        # Son iki değre arasındaki fark
        if len(self.values) >= 2:
            recent_change = abs(self.values[-1] - self.values[-2])
            return recent_change > self.threshold
        
        return False
    
    def calculate_average_change(self):
        """Ortalama değişim miktarını hesapla"""
        if len(self.values) < 2:
            return 0.0
        
        changes = [abs(self.values[i+1] - self.values[i]) 
                   for i in range(len(self.values)-1)]
        return sum(changes) / len(changes) if changes else 0.0


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
        dry_run: bool = False,
    ):
        self.token = token
        self.ecrn_list = list(ecrn_list)
        self.scrn_list = list(scrn_list or [])
        self.kayit_saati = kayit_saati
        self.max_deneme = max_deneme
        self.retry_aralik = retry_aralik
        self._measurement_buffer = 0.025  # ölçüm tabanlı buffer (başlangıç)
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

        # Ölçüm tabanlı zamanlama
        self._last_ntp_delay: Optional[float] = None  # Son NTP delay (sn)
        # Cloud Run kalibrasyon sonuçları (2026-02-15, 5000 ölçüm, europe-west1)
        # OBS saati NTP'ye göre +1.5ms ileri, σ=4.08ms (95% CI: ±8.0ms)
        # OBS-NTP saat farkının manuel düzeltmesi. 0 = varsayım yok (OBS≈NTP, ölçümle teyitli).
        # Hardcoded erken bias TEHLİKELİ: tetiği sunucu açılmadan atabilir (VAL02). Büyük OBS
        # sapması zaten calibrate()'te Date offset ile dinamik yakalanıyor; bu yalnız küçük
        # (±RTT/2) artığın manuel düzeltmesi — ölçemediğimiz sürece 0 (buffer'ın σ_obs'u kapsar).
        self._obs_clock_offset: float = 0.0
        self._obs_clock_uncertainty: float = 0.00408  # OBS saat belirsizliği σ (sn) — buffer için

        # Yeni geliştirme özellikleri
        self._trend_analyzer = TrendAnalyzer(window_size=10)
        self._change_detector = ChangeDetector(threshold=0.050)  # 50ms eşik
        self._target_time: Optional[float] = None  # Hedef zamanı sakla
        self._last_val02_delay: float = 0.0  # VAL02 log spam önleyici
        self._cal_samples_chrono: list[tuple[float, float, float, str]] = []  # Kronolojik sıralı kopya

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

    def _apply_advanced_protection(self, calculated_trigger: float, target_time: float) -> float:
        """Tetik zamanını güvenli pencereye sıkıştır.

        Hedef: Paketin sunucuya varış zamanı [target + 0ms, target + 50ms]
        Risk: Erken varış → VAL02 + 3sn ceza
        Risk: Geç varış → kontenjan dolar
        """
        protected_trigger = calculated_trigger

        # ALT SINIR: En erken gönderim zamanı.
        # Paket sunucuya RTT/2 sonra ulaşır; offset ölçüm hatası ±RTT/2 olabilir.
        # 1ms güvenlik payı ile VAL02 riskini minimize et.
        # RTT tek yön (~24ms) zaten doğal güvenlik tamponu sağlar.
        min_safe_time = target_time + 0.001
        if protected_trigger < min_safe_time:
            delay_ms = (min_safe_time - protected_trigger) * 1000
            if abs(delay_ms - self._last_val02_delay) > 1:  # Sadece değişince logla
                self._log(f"🔒 VAL02 koruma: tetik {delay_ms:+.0f}ms geciktirildi (hard floor: hedef+1ms)", "info")
                self._last_val02_delay = delay_ms
            protected_trigger = min_safe_time

        # ÜST SINIR: 200ms sonra kontenjan dolmuş olabilir.
        latest_allowed = target_time + 0.200
        if protected_trigger > latest_allowed:
            self._log(f"⚠️ Geç varış koruması: {(protected_trigger - latest_allowed)*1000:.0f}ms öne çekildi", "warning")
            protected_trigger = latest_allowed

        return protected_trigger

    def _add_sample(self, offset: float, rtt: float, source: str):
        """Kalibrasyon ölçüm havuzuna yeni sample ekle. Max 20 tutar, eski/kötü olanları atar."""
        # Outlier filtresi: mevcut en iyi offset'ten 200ms+ sapan ölçümleri reddet
        if self._cal_samples:
            best_offset = min(self._cal_samples, key=lambda s: s[1])[0]
            deviation = abs(offset - best_offset)
            if deviation > 0.200:  # 200ms eşik
                self._log(
                    f"⚡ Outlier filtrelendi: {offset*1000:+.0f}ms "
                    f"(en iyi: {best_offset*1000:+.0f}ms, sapma: {deviation*1000:.0f}ms)"
                )
                return  # Havuza ekleme

        sample = (offset, rtt, time.time(), source)
        self._cal_samples.append(sample)
        self._cal_samples_chrono.append(sample)  # Kronolojik kopya (sıralama bozulmaz)
        # Havuzu 20 ile sınırla: en kötü RTT'lileri at
        if len(self._cal_samples) > 20:
            self._cal_samples.sort(key=lambda s: s[1])
            self._cal_samples = self._cal_samples[:20]
        # Kronolojik listeyi de 20 ile sınırla (eski olanları at)
        if len(self._cal_samples_chrono) > 20:
            self._cal_samples_chrono = self._cal_samples_chrono[-20:]

    def _update_trend_analysis(self):
        """Trend analizini güncelle."""
        if self._calibration:
            current_offset = self._calibration.server_offset
            current_time = time.time()
            
            # Ofset trend analizi
            self._trend_analyzer.add_measurement(current_time, current_offset)
            
            # Anlamlı değişiklik var mı kontrol et
            self._change_detector.add_value(current_offset)
            if self._change_detector.detect_significant_change():
                self._log(f"📈 Anlamlı ofset değişikliği tespit edildi: {current_offset*1000:+.0f}ms", "info")

    def _predict_offset_at_target_time(self, target_time: float) -> float:
        """Hedef zamanda ofsetin ne olacağını tahmin et."""
        if len(self._trend_analyzer.data_points) >= 2:
            predicted_offset = self._trend_analyzer.predict_value_at_time(target_time)
            return predicted_offset
        # Yeterli veri yoksa mevcut en iyi ofseti kullan
        best = self._best_calibration()
        return best.server_offset if best else 0.0

    def _set_phase(self, phase: str):
        self._phase = phase
        self._emit("state", {"phase": phase, "running": self._running})

    # ── RTT Ölçümü ──

    def _rtt_olc(self, n: int = 5) -> float:
        rtts = []
        for _ in range(n):
            t0 = time.perf_counter()
            try:
                # POST isteği ile RTT ölçümü (gerçek kayıt isteği gibi)
                self.session.post(OBS_URL, json={"ECRN": ["00000"], "SCRN": []}, timeout=10)
            except Exception:
                continue
            rtts.append(time.perf_counter() - t0)
        if not rtts:
            return 0.010
        rtts.sort()
        return rtts[len(rtts) // 2]

    # ── RTT İstatistikleri ──

    def _rtt_stats(self, n: int = 10) -> dict:
        """RTT istatistikleri: median, jitter (std dev), min, max."""
        rtts = []
        for _ in range(n):
            if self._cancelled.is_set():
                break
            t0 = time.perf_counter()
            try:
                # POST isteği ile RTT ölçümü (gerçek kayıt isteği gibi)
                self.session.post(OBS_URL, json={"ECRN": ["00000"], "SCRN": []}, timeout=10)
            except Exception:
                continue
            rtts.append(time.perf_counter() - t0)
        if not rtts:
            return {"median": 0.010, "jitter": 0.005, "min": 0.010, "max": 0.010, "count": 0, "trend": 0.0}

        # Trend hesabını sıralama ÖNCESİ yap (kronolojik sıra korunmalı)
        trend = 0.0
        if len(rtts) >= 2:
            trend = rtts[-1] - rtts[0]  # Kronolojik: son ölçüm - ilk ölçüm

        rtts.sort()
        count = len(rtts)
        median = rtts[count // 2]
        mean = sum(rtts) / count
        variance = sum((r - mean) ** 2 for r in rtts) / count
        jitter = variance ** 0.5

        return {"median": median, "jitter": jitter, "min": rtts[0], "max": rtts[-1], "count": count, "trend": trend}

    # ── Hassas Zamanlama ──

    def _calculate_measurement_based_buffer(self, cal: CalibrationData, rtt_jitter: float) -> float:
        """Tamamen ölçüme dayalı buffer hesaplama.

        Formül:
          buffer = N × √(σ_ntp² + σ_rtt² + σ_obs² + σ_asimetri²)

        Her σ gerçek ölçüm verisinden hesaplanır.
        N = güven seviyesi (2 = %97.7 güvenilirlik)
        """
        GUVEN_SEVIYESI = 2.0  # N: 2=%97.7, 3=%99.9

        # σ_ntp: NTP ölçüm hassasiyeti (delay/2)
        ntp_delay = self._last_ntp_delay or 0.008
        sigma_ntp = ntp_delay / 2  # tipik: ~4ms

        # σ_rtt: Ağ RTT değişkenliği (ölçülen jitter)
        sigma_rtt = rtt_jitter  # tipik: ~1-3ms

        # σ_obs: OBS sunucu saat farkı belirsizliği
        sigma_obs = self._obs_clock_uncertainty  # kalibrasyon yoksa 25ms

        # σ_asimetri: RTT gidiş-dönüş asimetrisi
        # Araştırma: tipik asimetri %10-30, min RTT en simetrik
        sigma_asimetri = cal.rtt_one_way * 0.15  # tipik: ~3-4ms

        # Toplam belirsizlik (bağımsız hata kaynakları → karekök toplam)
        sigma_total = (sigma_ntp**2 + sigma_rtt**2 + sigma_obs**2 + sigma_asimetri**2) ** 0.5

        # Buffer = N × σ_total
        buffer = GUVEN_SEVIYESI * sigma_total

        # Minimum: 5ms (kesinlikle sıfır olmasın)
        buffer = max(buffer, 0.005)

        self._log(
            f"⚖️ Buffer hesabı: "
            f"σ_ntp={sigma_ntp*1000:.1f}ms, "
            f"σ_rtt={sigma_rtt*1000:.1f}ms, "
            f"σ_obs={sigma_obs*1000:.1f}ms, "
            f"σ_asim={sigma_asimetri*1000:.1f}ms "
            f"→ σ_total={sigma_total*1000:.1f}ms "
            f"→ buffer={buffer*1000:.1f}ms (N={GUVEN_SEVIYESI})"
        )

        return buffer

    # ── NTP Kalibrasyon (birincil offset kaynağı) ──

    def _ntp_calibrate(self, servers: list[str] | None = None) -> tuple[float, float] | None:
        """NTP sunucusundan ms-hassasiyetinde offset ve delay ölç.

        NTP offset = sunucu_saati - yerel_saat.
        Pozitif: NTP sunucusu ileride, negatif: geride.

        Returns: (offset_seconds, delay_seconds) veya None
        """
        import ntplib
        servers = servers or [
            "time.google.com",      # Google — Cloud Run ile aynı altyapı
            "time.cloudflare.com",  # Cloudflare — düşük RTT
            "pool.ntp.org",         # Global NTP havuzu
        ]

        best_result = None
        for server in servers:
            try:
                client = ntplib.NTPClient()
                resp = client.request(server, version=3, timeout=3)
                # En düşük delay = en doğru ölçüm
                if best_result is None or resp.delay < best_result[1]:
                    best_result = (resp.offset, resp.delay)
            except Exception:
                continue
        if best_result:
            self._last_ntp_delay = best_result[1]
        return best_result

    def _ntp_offset(self) -> float:
        """Geriye uyumluluk: sadece offset döner."""
        result = self._ntp_calibrate()
        return result[0] if result else 0.0

    # ── Sunucu Offset Ölçümü (NTP birincil + Date doğrulama) ──

    def _measure_date_offset(self) -> float | None:
        """Date header geçişi ile offset ölç (sadece cross-validation için).

        Date header 1sn hassasiyetinde → ±500ms gürültü içerir.
        Bu yüzden sadece NTP sonucunu doğrulamak için kullanılır.
        """
        try:
            medyan_rtt = self._rtt_olc(3)
            poll_aralik = max(0.002, min(medyan_rtt / 2, 0.050))
            max_poll = int(2.0 / poll_aralik)

            r = self.session.head(OBS_BASE, timeout=5, allow_redirects=False)
            son_date = r.headers.get("Date", "")
            if not son_date:
                return None

            self._log(f"Sunucu: {son_date}")

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
                    self._log(f"Date geçişi: RTT={rtt*1000:.0f}ms, offset={offset*1000:+.0f}ms (±{rtt*500:.0f}ms — transition)")
                    return offset
                time.sleep(poll_aralik)

            return None
        except Exception:
            return None

    def calibrate(self, source: str = "manual") -> CalibrationData:
        """NTP birincil offset kaynağı, Date header cross-validation."""
        self._set_phase("calibrating")
        self._log("Sunucu saati ölçülüyor...")

        # 1. Bağlantıyı ısıt
        try:
            self.session.post(OBS_URL, json={"ECRN": ["00000"], "SCRN": []}, timeout=10)
        except Exception as e:
            self._log(f"POST bağlantısı hatası: {e}, HEAD ile deniyor...", "warning")
            try:
                self.session.head(OBS_BASE, timeout=10, allow_redirects=False)
            except Exception as e2:
                self._log(f"HEAD bağlantısı da başarısız: {e2}", "error")
                ntp_off = self._ntp_offset()
                self._calibration = CalibrationData(server_offset=-ntp_off, rtt_one_way=0.010, ntp_offset=ntp_off)
                return self._calibration

        # 2. RTT ölçümü (OBS'ye gerçek POST ile)
        medyan_rtt = self._rtt_olc(5)
        self._log(f"RTT: {medyan_rtt*1000:.0f}ms → tek yön: {medyan_rtt*500:.0f}ms")

        # 3. NTP ile hassas offset ölçümü (birincil)
        ntp_result = self._ntp_calibrate()
        ntp_offset_raw = ntp_result[0] if ntp_result else None
        ntp_delay = ntp_result[1] if ntp_result else None

        # 4. Date header ile cross-validation
        date_offset = self._measure_date_offset()

        # 5. Offset seçimi
        if ntp_offset_raw is not None:
            # NTP offset: sunucu_saati - yerel_saat (pozitif = sunucu ileride)
            # Biz yerel - sunucu istiyoruz → işareti çevir
            server_offset = -ntp_offset_raw
            accuracy = ntp_delay / 2 if ntp_delay else medyan_rtt / 2

            yon = "İLERİDE" if server_offset > 0 else "GERİDE"
            self._log(
                f"🎯 NTP offset: {abs(server_offset*1000):.1f}ms {yon} "
                f"(delay: {(ntp_delay or 0)*1000:.0f}ms, hassasiyet: ±{accuracy*1000:.0f}ms)"
            )

            # Date header ile cross-validation — KRİTİK güvenlik kontrolü.
            # NTP-Date çelişkisi, OBS'nin NTP-senkron OLMADIĞINI gösterir (OBS tarihsel
            # olarak ~2sn geriydeydi). Bu durumda NTP'ye güvenmek tetik'i sunucu açılmadan
            # ATAR → VAL02 + 3sn ceza → kontenjan biter (FELAKET). Date offset, transition
            # tekniğiyle GERÇEK OBS saatini ölçer (NTP-senkron varsaymaz, ±~RTT/2 hassasiyet).
            if date_offset is not None:
                diff = server_offset - date_offset  # ≈ OBS'nin NTP'den sapması
                if abs(diff) > 0.100:
                    # Tek Date ölçümü gürültülü olabilir → ikinci ölçümle TEYİT et,
                    # ancak öyle NTP'yi ez (yanlış override de erken/geç atışa yol açar).
                    date_offset2 = self._measure_date_offset()
                    if date_offset2 is not None and abs(server_offset - date_offset2) > 0.100:
                        confirmed = (date_offset + date_offset2) / 2
                        self._log(
                            f"🚨 OBS NTP-senkron DEĞİL! NTP-Date farkı {diff*1000:+.0f}ms "
                            f"(2 ölçümle teyit edildi). NTP yanıltıcı → gerçek OBS saatini "
                            f"(Date offset {confirmed*1000:+.0f}ms) kullanıyorum; erken atış (VAL02) önlenir.",
                            "warning",
                        )
                        server_offset = confirmed
                        accuracy = max(accuracy, medyan_rtt / 2)
                        self._obs_clock_uncertainty = medyan_rtt / 2
                    else:
                        self._log(
                            f"ℹ️ NTP-Date farkı {diff*1000:+.0f}ms teyit edilemedi "
                            f"(tek ölçüm gürültüsü) — NTP korunuyor"
                        )
                else:
                    self._log(f"✅ NTP-Date tutarlı (fark: {abs(diff)*1000:.0f}ms) — OBS NTP-senkron")
        elif date_offset is not None:
            # NTP başarısız → Date header fallback
            server_offset = date_offset
            accuracy = medyan_rtt / 2
            self._log(f"⚠️ NTP başarısız, Date header kullanılıyor (transition, ±{medyan_rtt*500:.0f}ms)", "warning")
            ntp_offset_raw = 0.0
        elif self._cal_samples:
            # NTP+Date başarısız AMA geçmiş havuzda ölçüm var → en iyiyi (en düşük RTT) kullan.
            # Offset=0 varsaymak VAL02'ye yol açar; geçmiş en iyi çok daha güvenli.
            best = min(self._cal_samples, key=lambda s: s[1])
            server_offset = best[0]
            accuracy = best[1] / 2
            ntp_offset_raw = 0.0
            self._log(
                f"⚠️ NTP+Date başarısız → geçmiş en iyi offset kullanılıyor: "
                f"{server_offset*1000:+.0f}ms (havuz RTT {best[1]*1000:.0f}ms)", "warning"
            )
        else:
            # Her ikisi de başarısız ve geçmiş ölçüm yok → son çare offset=0
            server_offset = 0.0
            accuracy = medyan_rtt / 2
            ntp_offset_raw = 0.0
            self._log("❌ Kalibrasyon başarısız ve geçmiş ölçüm yok! Offset=0 varsayılıyor", "error")

        self._calibration = CalibrationData(
            server_offset=server_offset,
            rtt_one_way=medyan_rtt / 2,
            ntp_offset=ntp_offset_raw,
        )
        self._add_sample(server_offset, medyan_rtt, source)

        yon = "İLERİDE" if server_offset > 0 else "GERİDE"
        self._log(
            f"Sonuç: {abs(server_offset*1000):.1f}ms {yon} "
            f"(±{accuracy*1000:.0f}ms) [havuz: {len(self._cal_samples)} ölçüm]"
        )

        self._update_trend_analysis()

        self._emit("calibration", {
            "server_offset_ms": self._calibration.server_offset * 1000,
            "rtt_one_way_ms": self._calibration.rtt_one_way * 1000,
            "rtt_full_ms": self._calibration.rtt_one_way * 2000,
            "ntp_offset_ms": (ntp_offset_raw or 0.0) * 1000,
            # GERÇEK OBS↔NTP farkı: OBS - NTP = -(date_offset + ntp_offset_raw).
            # (Eskiden server_offset - ntp_offset_raw idi = -2×ntp_offset, totoloji; OBS'yi
            # değil yerel makinenin NTP hatasını ölçüyordu.) Date yoksa None.
            "server_ntp_diff_ms": (
                -(date_offset + (ntp_offset_raw or 0.0)) * 1000
                if date_offset is not None
                else None
            ),
            "date_offset_ms": date_offset * 1000 if date_offset is not None else None,
            "accuracy_ms": accuracy * 1000,
            "source": source,
        })
        return self._calibration

    # ── Hafif Kalibrasyon (bekleme sırasında periyodik) ──

    def _quick_calibrate(self, source: str = "auto") -> CalibrationData | None:
        """NTP tabanlı hafif kalibrasyon + RTT ölçümü. ~1-2 saniye sürer."""
        try:
            # 1. NTP ile hassas offset ölçümü
            ntp_result = self._ntp_calibrate()
            if ntp_result is None:
                self._log("⚡ Hızlı kal: NTP başarısız, atlanıyor", "warning")
                return None

            ntp_offset_raw, ntp_delay = ntp_result
            server_offset = -ntp_offset_raw  # işareti çevir: yerel - sunucu

            # 2. RTT ölçümü (OBS'ye POST ile)
            medyan_rtt = self._rtt_olc(3)

            # 3. Havuza ekle (outlier filtresi _add_sample içinde)
            self._add_sample(server_offset, medyan_rtt, source)

            # 4. En iyi ölçümü havuzdan seç
            best = self._best_calibration()
            if best:
                self._calibration = best

            # Trend analizini güncelle
            self._update_trend_analysis()

            self._emit("calibration", {
                "server_offset_ms": self._calibration.server_offset * 1000,
                "rtt_one_way_ms": self._calibration.rtt_one_way * 1000,
                "rtt_full_ms": self._calibration.rtt_one_way * 2000,
                "ntp_offset_ms": ntp_offset_raw * 1000,
                "server_ntp_diff_ms": (self._calibration.server_offset - ntp_offset_raw) * 1000,
                "accuracy_ms": ntp_delay / 2 * 1000,
                "source": source,
            })
            self._log(
                f"⚡ Hızlı kal: NTP={server_offset*1000:+.0f}ms/delay={ntp_delay*1000:.0f}ms "
                f"→ en iyi: {self._calibration.server_offset*1000:+.0f}ms/"
                f"{self._calibration.rtt_one_way*1000:.0f}ms [havuz:{len(self._cal_samples)}]"
            )
            return self._calibration
        except Exception as e:
            self._log(f"Hızlı kalibrasyon hatası: {e}", "warning")
            return None

    # ── Prewarm ──

    def _prewarm(self, head_only: bool = False):
        try:
            # POST isteği ile ısıtma (gerçek kayıt isteği gibi)
            self.session.post(OBS_URL, json={"ECRN": ["00000"], "SCRN": []}, timeout=10)
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
            if self._calibration:
                cal_rtt_ms = self._calibration.rtt_one_way * 2000
                rtt_diff = rtt_ms - cal_rtt_ms
                if rtt_diff > 10:
                    self._log(f"⚠️ RTT spike: test={rtt_ms:.0f}ms vs kalibrasyon={cal_rtt_ms:.0f}ms (+{rtt_diff:.0f}ms)", "warning")
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

            # Date header 1sn granülarite — ms seviyesinde bilgi vermez, loglamaya gerek yok

            # Değerlendirme (sunucu perspektifinden — hedef pencere: 0-50ms)
            if 0 <= sunucu_varis_ms <= 50:
                self._log(f"✅ MÜKEMMEL — Hedef pencere içinde! ({sunucu_varis_ms:+.0f}ms) [0-50ms]")
            elif sunucu_varis_ms < 0:
                self._log(f"⚠️ ERKEN — Sunucuya {abs(sunucu_varis_ms):.0f}ms erken ulaştı (VAL02 riski)", "warning")
            elif sunucu_varis_ms <= 150:
                self._log(f"👍 İYİ — Pencere dışı ama yakın ({sunucu_varis_ms:+.0f}ms) [hedef: 0-50ms]")
            elif sunucu_varis_ms <= 500:
                self._log(f"⚠️ GEÇ — {sunucu_varis_ms:.0f}ms geç (kontenjan riski)", "warning")
            else:
                self._log(f"❌ ÇOK GEÇ — {sunucu_varis_ms:.0f}ms geç (büyük ihtimalle kaçırıldı)", "error")

            self._log("─────────────────────────────────")

            # Kalibrasyon verileriyle karşılaştır
            if self._calibration:
                cal = self._calibration
                self._log(f"📐 Kalibrasyon: offset={cal.server_offset*1000:+.0f}ms, RTT(tek yön)={cal.rtt_one_way*1000:.0f}ms")
                teorik_sunucu_varis = sunucu_gonderim_ms + cal.rtt_one_way * 1000
                self._log(f"📐 Teorik sunucu varış: hedef {teorik_sunucu_varis:+.0f}ms (sunucu saati)")

            # NEGATIF VARIS KORUMASI ANALIZI: Gelecekte bu koruma sayesinde ne olurdu?
            if sunucu_varis_ms < 0:
                # Eğer negatif varış koruması olsaydı, en az 10ms gecikmeli olurdu
                corrected_varis_ms = 10  # En az 10ms gecikmeli (pozitif varış)
                self._log(f"🔄 Simüle edilen koruma: {sunucu_varis_ms:+.0f}ms → {corrected_varis_ms:+.0f}ms (VAL02 riski azaltıldı)")

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
                        if crn in kalan:
                            kalan.remove(crn)
                            basarisiz[crn] = desc
                            crn_degisti = True

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
                self._log("🧪 DRY RUN MODU — Gerçek kayıt yapılmayacak", "warning")
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

            if self._cancelled.is_set():
                return

            # 2b. RTT jitter ölçümü + ölçüm tabanlı buffer hesaplama
            rtt_stats = self._rtt_stats(10)
            self._log(f"📊 RTT: median={rtt_stats['median']*1000:.0f}ms, jitter(σ)={rtt_stats['jitter']*1000:.1f}ms, min={rtt_stats['min']*1000:.0f}ms, max={rtt_stats['max']*1000:.0f}ms ({rtt_stats['count']} örnek)")

            best = self._best_calibration()
            self._measurement_buffer = self._calculate_measurement_based_buffer(best, rtt_stats['jitter'])
            self._log(f"⚡ Ölçüm tabanlı buffer: {self._measurement_buffer*1000:.1f}ms")

            if self._cancelled.is_set():
                return

            # 3. Tetik zamanı (havuzdaki en iyi ölçüme göre)
            hedef = self._saat_to_epoch(self.kayit_saati)
            self._target_time = hedef  # Hedef zamanı sakla
            
            best = self._best_calibration()
            
            # Temel tetik zamanı hesapla
            # OBS ileri → kayıt erken açılır → daha erken tetikle (offset'i çıkar)
            base_trigger = hedef + best.server_offset - best.rtt_one_way - self._obs_clock_offset + self._measurement_buffer
            
            # GELIŞMIŞ KORUMA MEKANIZMALARI UYGULA
            final_trigger = self._apply_advanced_protection(base_trigger, hedef)
            
            self._trigger_time = final_trigger

            kalan_sn = final_trigger - time.time()
            self._log(f"Tetik: {self.kayit_saati} +{self._measurement_buffer*1000:.0f}ms buffer | {kalan_sn:.1f}s kaldı")

            self._emit("countdown", {"trigger_time": final_trigger, "remaining": kalan_sn})

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
            gc.disable()  # GC pause'u engelle (tetik hassasiyeti için)
            self._log("🗑️ GC devre dışı (tetik hassasiyeti)", "info")
            prewarm2 = False
            keepalive_5s = False
            keepalive_3s = False
            final_cal_done = False
            probe_done = False
            last_recal_time = time.time()
            RECAL_INTERVAL = 30  # her X saniyede hafif kalibrasyon
            FINAL_CAL_WINDOW = 20  # son tam kalibrasyon bu saniyede başlar
            FINAL_CAL_MIN = 10  # bundan yakın olursa zaten yapma
            recal_count = 0

            def _recalc_trigger():
                """Havuzdaki en iyi ölçüme göre tetik zamanını yeniden hesapla."""
                best = self._best_calibration()
                if best:
                    # ADVANCED TREND ANALYSIS: Hedef zamanda ofseti tahmin et
                    predicted_offset = self._predict_offset_at_target_time(hedef)
                    
                    # Temel tetik zamanı hesapla
                    # OBS ileri → kayıt erken açılır → daha erken tetikle (offset'i çıkar)
                    base_trigger = hedef + predicted_offset - best.rtt_one_way - self._obs_clock_offset + self._measurement_buffer
                    
                    # GELIŞMIŞ KORUMA MEKANIZMALARI UYGULA
                    new_trigger = self._apply_advanced_protection(base_trigger, hedef)
                    
                    return new_trigger
                return final_trigger

            while not self._cancelled.is_set():
                now = time.time()
                kalan = final_trigger - now

                # Countdown event (her saniye)
                self._emit("countdown", {"trigger_time": final_trigger, "remaining": kalan})

                # ── Periyodik hafif kalibrasyon (>25sn kala, her 30sn) ──
                if kalan > 25 and (now - last_recal_time) >= RECAL_INTERVAL:
                    recal_count += 1
                    self._log(f"🔄 Periyodik kalibrasyon #{recal_count}...")
                    self._quick_calibrate(source="auto")
                    eski_tetik = final_trigger
                    final_trigger = _recalc_trigger()
                    self._trigger_time = final_trigger
                    fark = (final_trigger - eski_tetik) * 1000
                    if abs(fark) > 1:
                        self._log(f"🔄 Tetik güncellendi: {fark:+.0f}ms kayma (en iyi RTT: {self._calibration.rtt_one_way*1000:.0f}ms)")
                    kalan = final_trigger - time.time()
                    last_recal_time = now

                # ── Son TAM kalibrasyon (35-45sn kala) ──
                if not final_cal_done and FINAL_CAL_MIN < kalan <= FINAL_CAL_WINDOW:
                    self._log("🎯 Son tam kalibrasyon başlıyor...")
                    self.calibrate(source="final")
                    eski_tetik = final_trigger
                    final_trigger = _recalc_trigger()
                    self._trigger_time = final_trigger
                    fark = (final_trigger - eski_tetik) * 1000
                    best = self._best_calibration()
                    self._log(f"🎯 Son kalibrasyon tamam → tetik farkı: {fark:+.0f}ms | en iyi: offset={best.server_offset*1000:+.0f}ms RTT={best.rtt_one_way*1000:.0f}ms [havuz:{len(self._cal_samples)}]")
                    kalan = final_trigger - time.time()
                    self._emit("countdown", {"trigger_time": final_trigger, "remaining": kalan})
                    final_cal_done = True
                    # Final sonrası bağlantıyı tekrar ısıt
                    self._prewarm(head_only=True)
                    prewarm2 = True

                # ── Bağlantı canlı tutma (10s, 5s, 3.5s kala — HEAD ile, debounce riski sıfır) ──
                if not prewarm2 and 0 < kalan <= 10:
                    self._prewarm(head_only=True)
                    prewarm2 = True
                elif prewarm2 and not keepalive_5s and 4.5 < kalan <= 5.5:
                    keepalive_5s = True
                    try:
                        # HEAD isteği ile bağlantı canlı tutma (POST debounce tetikler!)
                        self.session.head(OBS_URL, timeout=10)
                    except Exception:
                        pass
                elif keepalive_5s and not keepalive_3s and 3.0 < kalan <= 4.0:
                    keepalive_3s = True
                    try:
                        # HEAD isteği ile bağlantı canlı tutma (POST debounce tetikler!)
                        self.session.head(OBS_URL, timeout=10)
                    except Exception:
                        pass

                # ── Sürekli RTT izleme ve düzeltme (kalan > 5sn ve 30sn aralıklarla) ──
                if kalan > 5 and (now - last_recal_time) >= 30:  # 30sn aralıklarla
                    # RTT trend izleme
                    rtt_trend_data = self._rtt_stats(5)
                    self._log(f"📊 Sürekli RTT izleme: median={rtt_trend_data['median']*1000:.0f}ms, trend={rtt_trend_data['trend']*1000:+.1f}ms", "info")
                    
                    # Anormal artış varsa alarm ver
                    if rtt_trend_data['trend'] > 0.020:  # 20ms artış
                        self._log(f"⚠️ RTT trend artışı tespit edildi: {rtt_trend_data['trend']*1000:+.1f}ms", "warning")
                    
                    # Trend analizini güncelle
                    self._update_trend_analysis()
                    
                    last_recal_time = now

                # ── Son saniye bağlantı kontrolü (2s kala — HEAD ile, debounce riski sıfır) ──
                if not probe_done and 1.5 < kalan <= 2.5:
                    probe_done = True
                    # HEAD ile bağlantı kontrol (POST debounce tetikler, tehlikeli!)
                    try:
                        t0 = time.perf_counter()
                        self.session.head(OBS_URL, timeout=5)
                        head_rtt = (time.perf_counter() - t0) * 1000
                        self._log(f"🎯 Bağlantı kontrol (HEAD): {head_rtt:.0f}ms — POST probe kaldırıldı (debounce riski)")
                    except Exception:
                        self._log("⚠️ Bağlantı kontrol başarısız (HEAD)", "warning")

                # ── Busy-wait (son 50ms — perf_counter ile yüksek çözünürlük) ──
                if kalan <= 0.05:
                    pc_tetik = time.perf_counter() + (final_trigger - time.time())
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
            actual_trigger_fark = (time.time() - self._trigger_time) * 1000
            best = self._best_calibration()
            self._log(f"🚀 BAŞLIYOR! (hedef farkı: {fark_ms:+.0f}ms, tetik farkı: {actual_trigger_fark:+.0f}ms) [buffer={self._measurement_buffer*1000:.0f}ms offset={best.server_offset*1000:+.0f}ms obs_offset={self._obs_clock_offset*1000:+.1f}ms RTT={best.rtt_one_way*1000:.0f}ms havuz:{len(self._cal_samples)}]")
            if self.dry_run:
                self._kayit_yap_dry_run()
            else:
                self._kayit_yap()

        except Exception as e:
            self._log(f"Beklenmeyen hata: {e}", "error")
        finally:
            gc.enable()  # GC'yi tekrar aç
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
