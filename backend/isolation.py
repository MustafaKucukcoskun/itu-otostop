"""Kayıt ateşlemesinin sahipliğini ve izole konteyner devrini yönetir.

NEDEN VAR: Tek konteynerde N kullanıcı aynı anda ateşlediğinde Python GIL
busy-wait thread'lerini sıraya sokuyor (ölçüm: 15 kullanıcı 1.8ms, 100
kullanıcı 47ms en kötü sapma). Her kayda ayrı Cloud Run konteyneri vermek
bu sıralamayı ortadan kaldırır.

İzole konteyner *ek* bir yol; mevcut yerel motor yedek olarak durur. İki yol
olunca iki tehlike doğar ve bu modül ikisini de kesmek zorundadır:

  1. ÇİFT ATEŞLEME — aynı token'la art arda giden iki POST'u OBS VAL16 ile
     düşürür (3sn debounce). İki motor 3sn aralıkla yeniden denerse birbirinin
     penceresine düşer ve ders hiç alınamaz. Sahiplik tam olarak bir kez verilir.

  2. HİÇ ATEŞLEMEME — bundan kötüsü yok. Konteyner sahiplenip ölürse kimse
     ateşlemez. Bu yüzden sahiplik "ateşleme hakkı" değil "ateşleme SÖZÜ"dür:
     konteyner nabız atarak sözünü tutabildiğini sürekli gösterir. Nabız
     kesilirse söz geri alınır (revoke) ve yerel motor devralır.

Bu yüzden yerel motor sahiplenme anında DEĞİL, hedefe ~8 saniye kala çekilir:
o ana kadar konteynerin gerçekten hayatta olduğu doğrulanmış olur. Busy-wait
son 50ms'de başladığı için bu geç çekilme GIL kazancının tamamını korur.
"""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

# Hedeften ne kadar önce izole konteyner açılsın.
# Ölçüm (europe-west3, 40 eşzamanlı): provisioning ~70s'ye yayılıyor, üstüne
# kalibrasyon 7s + ısınma 1s. 900s bunun 10 katından fazla pay bırakır.
DEFAULT_LEAD = 900.0

# (Eskiden ayrı bir "hazır olma" eşiği vardı: 120 saniye. Uyarı sahiplenme
# HÂLÂ MÜMKÜNKEN çıkıyordu — canlı testte kullanıcı T-61s'de başlattı, uyarıyı
# 1 saniye sonra gördü ve 19 saniye sonra konteyner zaten sahiplendi. Artık
# eşik min_claim_margin: uyarı ancak sahiplenme imkânsızlaştığında çıkar.)

# Hedefe bundan az kalmışsa sahiplenme reddedilir. Geç kalkan bir konteyner,
# yerel motor ateşleme hazırlığına girmişken devralmamalı.
DEFAULT_MIN_CLAIM_MARGIN = 20.0

# Yerel motorun çekildiği an (hedefe kalan saniye).
DEFAULT_HANDOVER_WINDOW = 8.0

# Nabız bu kadar eskiyse konteyner ölü sayılır.
DEFAULT_HEARTBEAT_MAX_AGE = 10.0

# Konteyner açma isteği en fazla bu kadar denenir. 429 (hız sınırı) geçici
# olduğu için cömert tutuldu; denemeler denetleyicinin 2 saniyelik turlarına
# yayılır, yani ~12 saniyelik bir pencere.
MAX_LAUNCH_ATTEMPTS = 6

# Hatırlanan kasıtlı silme sayısı. Sınır, uzun süre ayakta kalan bir serviste
# belleğin sınırsız büyümesini engeller; en eski mezar taşı düşer.
MAX_MEZAR = 5000


@dataclass
class _Entry:
    session_id: str
    target_epoch: float
    ticket: str
    launched: bool = False
    launched_at: float = 0.0
    owner: Optional[str] = None  # None | "remote" | "local"
    launch_error: str = ""
    launch_attempts: int = 0
    last_heartbeat: float = 0.0
    revoked: bool = False
    cancelled: bool = False
    # "Devir kararı verildi" demek — yerel motorun çekildiği anlamına GELMEZ.
    # Nabız ölüyse karar, sözü geri alıp yereli göreve döndürmek olur.
    handover_decided: bool = False


@dataclass
class IsolationBroker:
    lead: float = DEFAULT_LEAD
    min_claim_margin: float = DEFAULT_MIN_CLAIM_MARGIN
    handover_window: float = DEFAULT_HANDOVER_WINDOW
    heartbeat_max_age: float = DEFAULT_HEARTBEAT_MAX_AGE
    clock: Callable[[], float] = time.time
    _entries: dict[str, _Entry] = field(default_factory=dict)
    # Kasıtlı silmelerin hafızası — bkz. release().
    _mezar: dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # ── Kayıt ──

    def register(self, session_id: str, target_epoch: float) -> str:
        """Kaydı sıraya al, konteynerin kimliğini kanıtlayacağı bileti üret.

        Bilet aynı zamanda kullanıcının OBS token'ını çekme yetkisidir; bu
        yüzden kriptografik rastgelelikle üretilir ve asla loglanmaz.
        """
        ticket = secrets.token_urlsafe(32)
        with self._lock:
            self._entries[session_id] = _Entry(
                session_id=session_id, target_epoch=target_epoch, ticket=ticket
            )
            # Aynı kullanıcı yeniden başlattı: eski mezar taşı yeni kaydı gömmesin.
            self._mezar.pop(session_id, None)
        return ticket

    def restore(self, session_id: str, target_epoch: float, ticket: str) -> None:
        """Yeniden başlatma sonrası kaydı ORİJİNAL biletiyle geri koy.

        `register()` kullanılamaz çünkü yeni bilet üretir. Yeniden başlatmadan
        önce açılmış bir konteyner o başlatmadan SAĞ ÇIKAR (soğuk başlangıç
        toleransı sayesinde sözünü tutar) ve elinde eski bilet vardır; yeni
        bilet üretmek, kurtarmaya çalışırken hayatta olanı öldürmek olur.

        Kayıt `launched=False` döner: orijinal konteyner ölmüşse ikinci bir
        şans doğar, sağsa ikinci konteyner "söz verilemedi" deyip çekilir.
        """
        with self._lock:
            self._entries[session_id] = _Entry(
                session_id=session_id, target_epoch=target_epoch, ticket=ticket
            )
            self._mezar.pop(session_id, None)

    def release(self, session_id: str) -> None:
        """Kaydı tamamen sil (sıfırlama). Biletler geçersizleşir.

        Silmeyi HATIRLARIZ. Yeniden başlamış bir ana servis hiçbir kaydı
        tanımaz, dolayısıyla bilmediği bir bileti "silinmiş" sayamaz (bkz.
        main.py soğuk başlangıç toleransı). Mezar taşı "unuttum" ile
        "sildim" arasındaki farkı korur; böylece sıfırlama, tolerans
        penceresinde bile kesin cevabını sürdürür ve kullanıcının
        istemediği kayıt yapılmaz.
        """
        with self._lock:
            self._entries.pop(session_id, None)
            self._mezar[session_id] = time.time()
            if len(self._mezar) > MAX_MEZAR:
                eski = sorted(self._mezar.items(), key=lambda kv: kv[1])
                for sid, _ in eski[: len(self._mezar) - MAX_MEZAR]:
                    self._mezar.pop(sid, None)

    def deliberately_released(self, session_id: str) -> bool:
        """Bu kaydı biz mi sildik? (Yeniden başlamış servis hiçbirini bilmez.)"""
        return session_id in self._mezar

    def target_of(self, session_id: str) -> Optional[float]:
        e = self._entries.get(session_id)
        return e.target_epoch if e else None

    def owner_of(self, session_id: str) -> Optional[str]:
        e = self._entries.get(session_id)
        return e.owner if e else None

    def is_cancelled(self, session_id: str) -> bool:
        e = self._entries.get(session_id)
        return bool(e and e.cancelled)

    # ── Bilet ──

    def verify_ticket(self, session_id: str, ticket: str) -> bool:
        """Bileti doğrular ama SAHİPLİK VERMEZ.

        Konteyner yapılandırmayı (OBS token dahil) çekerken ve olay akışını
        gönderirken bunu kullanır; sahiplenme ayrı ve tek seferlik bir adımdır.
        """
        with self._lock:
            e = self._entries.get(session_id)
            if e is None:
                return False
            # Sabit zamanlı karşılaştırma: bilet tahminine zaman sızdırmasın
            return hmac.compare_digest(e.ticket, ticket or "")

    # ── Sahiplenme (tek ateşleyici garantisi) ──

    def claim_remote(self, session_id: str, ticket: str) -> bool:
        """İzole konteyner ateşleme sözü verir. Yalnızca ilk çağrı True döner.

        Reddedilme sebepleri: kayıt yok / bilet yanlış / zaten sahipli /
        iptal edilmiş / sözü geri alınmış / hedefe çok az kalmış.
        """
        now = self.clock()
        with self._lock:
            e = self._entries.get(session_id)
            if e is None or e.owner is not None or e.cancelled or e.revoked:
                return False
            if not hmac.compare_digest(e.ticket, ticket or ""):
                return False
            if (e.target_epoch - now) < self.min_claim_margin:
                # Geç kaldı: yerel motor ateşleme hazırlığında, bölme.
                return False
            e.owner = "remote"
            e.last_heartbeat = now
            return True

    def claim_local(self, session_id: str) -> bool:
        """Ana servis üstlenir. Konteyner sözünü tutuyorsa False."""
        with self._lock:
            e = self._entries.get(session_id)
            if e is None or e.owner is not None:
                return False
            e.owner = "local"
            return True

    # ── Nabız ──

    def heartbeat(self, session_id: str, ticket: str) -> Optional[dict]:
        """Konteynerin hayatta olduğunu bildirir; karşılığında durumu alır.

        None → bilet geçersiz. Aksi halde konteyner `cancelled` / `revoked`
        bayraklarını görüp kendini durdurur.
        """
        now = self.clock()
        with self._lock:
            e = self._entries.get(session_id)
            if e is None or not hmac.compare_digest(e.ticket, ticket or ""):
                return None
            e.last_heartbeat = now
            return {"cancelled": e.cancelled, "revoked": e.revoked}

    def remote_alive(self, session_id: str, max_age: Optional[float] = None) -> bool:
        """Konteynerden son `max_age` saniyede nabız geldi mi?

        Hiç nabız gelmediyse ölü sayılır — söz verip susan konteyner, hiç söz
        vermemiş konteynerden daha tehlikelidir.
        """
        limit = self.heartbeat_max_age if max_age is None else max_age
        now = self.clock()
        with self._lock:
            e = self._entries.get(session_id)
            if e is None or e.last_heartbeat <= 0:
                return False
            return (now - e.last_heartbeat) <= limit

    # ── Devir ──

    def handover_due(self) -> list[str]:
        """Yerel motorun çekilip çekilmeyeceğine şimdi karar verilmeli.

        Sahiplenme anında değil BURADA karar verilir: o ana kadar konteynerin
        nabzı izlenmiş olur, yani söz verip ölen konteyner yakalanır.
        """
        now = self.clock()
        with self._lock:
            return [
                e.session_id
                for e in self._entries.values()
                if e.owner == "remote"
                and not e.handover_decided
                and (e.target_epoch - now) <= self.handover_window
            ]

    def mark_handover_decided(self, session_id: str) -> None:
        """Devir kararı bir kez verilir (çekilme ya da geri alma)."""
        with self._lock:
            e = self._entries.get(session_id)
            if e is not None:
                e.handover_decided = True

    def revoke(self, session_id: str) -> None:
        """Konteynerin ateşleme sözünü geri al — yerel motor devralabilsin.

        Konteyner bunu nabızdan öğrenir ve kendini iptal eder. Nabzı gelmiyorsa
        (ölü olduğu için) öğrenemez, ama zaten ateşlemeyecektir.
        """
        with self._lock:
            e = self._entries.get(session_id)
            if e is not None:
                e.owner = None
                e.revoked = True

    def request_cancel(self, session_id: str) -> bool:
        """Kullanıcı iptal etti.

        Kayıt SİLİNMEZ: silinseydi bilet geçersizleşir, konteyner nabız atamaz
        ve iptali hiç öğrenemezdi — kullanıcı iptal ettiği kaydı yine alırdı.
        """
        with self._lock:
            e = self._entries.get(session_id)
            if e is None:
                return False
            e.cancelled = True
            return True

    # ── Zamanlama ──

    def due_for_launch(self, limit: Optional[int] = None) -> list[tuple[str, str]]:
        """Konteyneri şimdi açılması gereken (session_id, bilet) çiftleri.

        `limit` verilirse en fazla o kadarı döner. ÖLÇÜM (europe-west3):
        Run Admin API token-bucket uyguluyor (kova ~60, dolum ~2/sn). 100 isteği
        birden ya da saniyede 5 atınca %39'u 429 aldı; saniyede 2'de 40/40 geçti.
        Kayıt düşmez, sadece yayılır — 900 saniyelik pencerede bolca yer var.
        """
        now = self.clock()
        with self._lock:
            hazir = [
                (e.session_id, e.ticket)
                for e in self._entries.values()
                if not e.launched
                and e.owner is None
                and not e.cancelled
                and (e.target_epoch - now) <= self.lead
            ]
        return hazir if limit is None else hazir[:limit]

    def mark_launched(self, session_id: str, error: str = "") -> None:
        with self._lock:
            e = self._entries.get(session_id)
            if e is not None:
                e.launched = True
                e.launched_at = self.clock()
                e.launch_error = error

    def launch_failed(self, session_id: str, error: str) -> bool:
        """Başlatma isteği hata verdi. True → tekrar denenecek.

        Geçici bir Run API hatası izolasyonu kalıcı kaybettirmemeli; ama
        kalıcı hata da 900 saniye boyunca API'yi dövmemeli.
        """
        with self._lock:
            e = self._entries.get(session_id)
            if e is None:
                return False
            e.launch_attempts += 1
            e.launch_error = error
            if e.launch_attempts >= MAX_LAUNCH_ATTEMPTS:
                return False
            e.launched = False  # bir sonraki turda yeniden denensin
            return True

    def fallback_due(self) -> list[str]:
        """Konteyner artık YETİŞEMEZ — kullanıcıyı bilgilendirmek için.

        Eşik `min_claim_margin`: sahiplenmenin reddedilmeye başladığı an.
        Daha erken uyarmak yanlıştı; konteyner hâlâ yetişebilecekken
        "yetişmedi" demek kullanıcıyı boş yere korkutuyordu.

        `launched` bayrağına BAKILMAZ: başlatma isteği hiç gitmemiş olsa da
        (Run API hatası, geç kayıt) sahibi yoksa yerel motor ateşleyecektir.
        Kullanıcının hiç ateşlenmemesi, geç ateşlenmesinden kötüdür.
        """
        now = self.clock()
        with self._lock:
            return [
                e.session_id
                for e in self._entries.values()
                if e.owner is None
                and not e.cancelled
                and (e.target_epoch - now) <= self.min_claim_margin
            ]

    def purge_finished(self, older_than: float = 3600.0) -> list[str]:
        """Hedefi çoktan geçmiş kayıtları sil.

        Servis aylarca ayakta kalıyor; her kayıt bir giriş bırakırsa bellek
        sessizce şişer. Yeni bitenler durur — kullanıcı hâlâ sonucu izliyor
        olabilir ve konteyner son olaylarını gönderiyor olabilir.
        """
        now = self.clock()
        with self._lock:
            eski = [
                e.session_id
                for e in self._entries.values()
                if (now - e.target_epoch) > older_than
            ]
            for sid in eski:
                del self._entries[sid]
            return eski

    def snapshot(self) -> list[dict]:
        """Teşhis için durum dökümü — bilet asla dışarı verilmez."""
        now = self.clock()
        with self._lock:
            return [
                {
                    "session_id": e.session_id,
                    "kalan_sn": round(e.target_epoch - now, 1),
                    "launched": e.launched,
                    "owner": e.owner,
                    "revoked": e.revoked,
                    "cancelled": e.cancelled,
                    "devir_karari": e.handover_decided,
                    "nabiz_yasi_sn": (
                        round(now - e.last_heartbeat, 1) if e.last_heartbeat else None
                    ),
                    "launch_error": e.launch_error,
                }
                for e in self._entries.values()
            ]
