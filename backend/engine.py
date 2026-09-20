"""
OBS Ders Kayıt Motoru — API uyumlu versiyon.
claudeai2-optimal.py mantığının sınıf tabanlı, event-driven adaptasyonu.
Zamanlama hassasiyeti korunur (busy-wait, Date header geçişi vb.).
"""

import json
import re
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

# Geri sayım olayları arasındaki asgari süre. Bekleme döngüsü son saniyelerde
# saniyede ~180 tur atıyor; her turda yayın yapmak boşa iştir ve eşzamanlı
# kayıtlarda ana servisi en hassas anda yorar.
COUNTDOWN_INTERVAL = 0.1

# Olay kuyruğunun üst sınırı. Kuyruk sınırsızdı: drenaj (poll_engine_events)
# herhangi bir sebeple ölürse olaylar saatlerce birikir ve 40 oturumda 1 GiB'lık
# konteyner OOM ile ölür — bekleyen BÜTÜN kayıtlar kaybolur. Olaylar geçicidir;
# en eskisini düşürmek servisi çökertmekten iyidir.
EVENT_QUEUE_MAX = 2000
OBS_BASE = "https://obs.itu.edu.tr"

# OBS'in önkoşul ifadesi: {'DersKodu':'MAT 104', 'Min': 'DD'} birimleri,
# aralarında | (veya) ve & (ve), parantezlerle gruplanmış.
_ONSART_BIRIM = re.compile(
    r"\{\s*'DersKodu'\s*:\s*'([^']+)'\s*,\s*'Min'\s*:\s*'([^']+)'\s*\}"
)


def onsart_metni(ham) -> str:
    """OBS'in önkoşul ifadesini okunabilir Türkçeye çevir.

    18 Eylül'de (42vq5) VAL11'in `uyulmayanOnsartlar` alanı görülünce kodun
    ne olduğu kesinleşti: önkoşul sağlanmadı. Ama öğrenci ekranda ham JSON
    görüyordu.

    Çeviri YORUM DEĞİL, birebir: her birim "DERS (en az NOT)" olur, operatörler
    Türkçeleşir, parantezler KORUNUR. Yapıyı kendimiz yorumlayıp düzleştirseydik
    (hepsini "veya" saymak gibi) yanlış bilgi vermiş olurduk; eksik bilgi yanlış
    bilgiden iyidir. Tanımadığımız bir şekil gelirse olduğu gibi döner.
    """
    if not ham:
        return ""
    metin = str(ham).strip()
    # Alan, JSON içinde bir kez daha tırnaklanmış geliyor.
    while len(metin) >= 2 and metin[0] == metin[-1] == '"':
        metin = metin[1:-1].strip()
    if not _ONSART_BIRIM.search(metin):
        return metin
    metin = _ONSART_BIRIM.sub(lambda m: f"{m.group(1)} (en az {m.group(2)})", metin)
    metin = metin.replace("|", " veya ").replace("&", " ve ")
    metin = re.sub(r"\s+", " ", metin).strip()
    # Tümünü saran tek parantez varsa gereksiz; içtekiler korunur.
    if metin.startswith("(") and metin.endswith(")"):
        derinlik = 0
        for i, ch in enumerate(metin):
            derinlik += (ch == "(") - (ch == ")")
            if derinlik == 0 and i < len(metin) - 1:
                break
        else:
            metin = metin[1:-1].strip()
    return metin


# resultData'da açıklamanın hangi anahtarda geldiğini bilmiyoruz; gördüğümüz
# tek örnek VAL22'nin "yukseltmeyeAlinanDers" alanı. Yaygın adları sırayla
# deneyip, hiçbiri tutmazsa alanın tamamını gösteriyoruz.
_ACIKLAMA_ANAHTARLARI = ("message", "mesaj", "aciklama", "açıklama", "description",
                         "hata", "error", "errorMessage", "text", "detail", "detay")
_ACIKLAMA_MAX = 200


def obs_aciklama(rd) -> str:
    """OBS'in `resultData` alanından okunabilir bir açıklama çıkar.

    CANLI OLAY (17 Eylül 14:00): bir kullanıcının 10 dersinin hepsi `VAL21`
    aldı ve 0/10 ile bitti. O kod HATA_KODLARI'nda olmadığı için kullanıcı
    ekranda çıplak "VAL21" gördü ve neden hiç ders alamadığını öğrenemedi —
    oysa OBS aynı cevapta `resultData` gönderiyordu ve biz onu atıyorduk.

    Alanın şekli meçhul, o yüzden hiçbir şekil varsayılmıyor: dict ise
    bilinen anahtarlar denenir, tutmazsa alanın tamamı JSON olarak gösterilir
    (tanımadığımız bir kodun ne olduğunu ancak böyle öğrenebiliriz).
    ensure_ascii kapalı: aksi halde kullanıcı "de\u011fil" görür.
    """
    if rd is None:
        return ""
    if isinstance(rd, str):
        return rd.strip()[:_ACIKLAMA_MAX]
    if isinstance(rd, dict):
        # Önkoşul ifadesi özel: ham hâli okunmaz, çevirisi nettir.
        onsart = rd.get("uyulmayanOnsartlar")
        if onsart:
            cevrilmis = onsart_metni(onsart)
            if cevrilmis:
                return cevrilmis[:_ACIKLAMA_MAX]
        for anahtar in _ACIKLAMA_ANAHTARLARI:
            deger = rd.get(anahtar)
            if isinstance(deger, str) and deger.strip():
                return deger.strip()[:_ACIKLAMA_MAX]
        if not rd:
            return ""
        return json.dumps(rd, ensure_ascii=False)[:_ACIKLAMA_MAX]
    return str(rd)[:_ACIKLAMA_MAX]


def robust_jitter(rtts: list[float]) -> float:
    """RTT dağınıklığı — tek bir aykırı ölçümün kandıramayacağı ölçüt.

    CANLI OLAY (17 Eylül 14:00): üç konteynerin 10 RTT ölçümünden biri 76-87ms
    geldi, diğerleri 38-45ms'ydi; `min` hepsinde 38-40ms, yani ağ kusursuz
    çalışıyordu. Popülasyon standart sapması farkların KARESİNİ aldığı için o
    tek örnek σ'yı 0.3ms'den 14-16ms'ye çıkardı. Buffer 11ms yerine 30-33ms
    hesaplandı; buffer tek yön RTT'yi (20ms) aşınca `_apply_advanced_protection`
    alt sınırı devreden çıktı ve tetik 10-15ms GECİKTİ.

    MAD (medyandan sapmaların medyanı) sıralamaya bakar, kare almaz: 10
    örnekten biri uçsa bile kılı kıpırdamaz. 1.4826 çarpanı, normal dağılımda
    MAD'ı standart sapmaya çeviren tutarlılık katsayısıdır — yani sağlıklı
    örneklemde eski ölçütle aynı sayıyı verir, yalnızca aykırı örnekte ayrışır.
    """
    if len(rtts) < 2:
        return 0.0
    s = sorted(rtts)
    medyan = s[len(s) // 2]
    sapmalar = sorted(abs(r - medyan) for r in s)
    mad = sapmalar[len(sapmalar) // 2]
    return mad * 1.4826


# Ateşleme isteğinin zaman sınırları — bağlantı ve okuma AYRI.
#
# CANLI OLAY (19 Eylül 12:00, wsqj2): kayıt İLK istekte tamamlanmıştı ama
# cevap 10sn'de kesildiği için bunu bilemedik. Motor art arda SEKİZ kez zaman
# aşımına düştü, gerçeği 123 saniye sonra öğrendi ve bu arada OBS'e sekiz
# mükerrer kayıt isteği attı. Aynı gün ölçülen cevap süreleri 304ms, 1523ms,
# 2076ms, 7046ms, 9845ms — yani 9845ms eski sınıra kıl payı sığmıştı.
#
# Okuma sınırı ölçülen tavanın belirgin üstünde; bağlantı sınırı kısa, çünkü
# sunucuya hiç bağlanamıyorsak beklemek değil tekrar denemek istiyoruz.
# VAL16 (debounce) görüldüğünde beklenen süre.
#
# CANLI OLAY (17 Eylül 10:00, zmxzl): denemeler 3.04-3.17s aralıklarla gitti
# ve beşi üst üste VAL16 yedi; gerçek cevap ancak 28 saniye sonra geldi.
# Hepsi 3 saniyelik sınırın hemen üstündeydi, hangisinin geçeceği tesadüfe
# kalmıştı. VAL16 "çok erken geldin" demek — aynı hızda tekrar denemek
# denemeyi ziyan eder.
DEBOUNCE_BACKOFF = float(os.getenv("OBS_DEBOUNCE_BACKOFF", "5"))

FIRE_CONNECT_TIMEOUT = float(os.getenv("OBS_CONNECT_TIMEOUT", "5"))
FIRE_READ_TIMEOUT = float(os.getenv("OBS_READ_TIMEOUT", "30"))

HATA_KODLARI = {
    "VAL02": "Kayıt dönemi henüz açılmadı",
    "VAL03": "Bu ders zaten alınmış",
    "VAL06": "Kontenjan dolu",
    "VAL09": "Ders çakışması var",
    # OBS'in kendi alan adı `uyulmayanOnsartlar` ile kesinleşti (18 Eylül).
    "VAL11": "Önkoşul sağlanmadı",
    "VAL16": "Debounce (sunucu <3sn'de tekrarı yok saydı)",
    "VAL22": "Yükseltmeye alınan ders çakışması",
}


@dataclass
class CalibrationData:
    server_offset: float = 0.0
    rtt_one_way: float = 0.003
    ntp_offset: float = 0.0
    # Bu ÖLÇÜMÜN kendi NTP gecikmesi. Belirsizlik (σ_ntp), offseti aldığımız
    # örnekten gelmeli; başka bir örneğin gecikmesini kullanmak tutarsız.
    ntp_delay: float = 0.0
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

        self._events: queue.Queue = queue.Queue(maxsize=EVENT_QUEUE_MAX)
        self._cancelled = threading.Event()
        # İzole konteyner kaydı üstlendiğinde bu motor sessizce çekilir.
        # İptalden AYRI tutulur: kullanıcı iptal etmedi, sadece devredildi.
        self._stood_down = threading.Event()
        # Konteyner sahiplenince bu motor beklemeye DEVAM eder ama susar:
        # aksi halde kullanıcı iki motorun loglarını iç içe görür ve faz
        # göstergesi titrer. Susmak çekilmek değildir — söz geri alınırsa
        # unmute() ile yeniden görünür olur ve ateşler.
        self._muted = threading.Event()
        # Geri sayım yayın kısıtlayıcısı (bkz. _countdown_due)
        self._last_countdown = 0.0
        self._running = False
        self._phase = "idle"
        self._current_attempt = 0
        self._calibration: Optional[CalibrationData] = None
        self._cal_samples: list[tuple[float, float, float, str, float]] = []  # (offset, rtt, timestamp, source, ntp_delay)
        # Son ölçülen RTT jitter'ı. Buffer tazelenirken yeniden ağ ölçümü
        # YAPILMAZ: tetik yolunda ağ beklemek hassasiyeti bozar.
        self._rtt_jitter: float = 0.0003
        self._crn_results: dict[str, dict] = {}
        self._trigger_time: Optional[float] = None
        # Tetik öncesi hazırlanan istek (eşzamanlılık: tetikten sonra iş kalmasın)
        self._prepped: Optional[requests.PreparedRequest] = None
        self._prepped_for: Optional[list[str]] = None

        # Ölçüm tabanlı zamanlama
        self._last_ntp_delay: Optional[float] = None  # Son NTP delay (sn)
        # Cloud Run kalibrasyon sonuçları (2026-06-14, 5000 ölçüm, europe-west1)
        # OBS saati NTP'ye göre -0.7ms geride, σ=4.08ms (95% CI: ±8.0ms) — pratikte senkron.
        # (Önceki ölçüm 2026-02-15: +1.5ms; 4 ayda 2.2ms değişim = ±8ms içinde, stabil.)
        self._obs_clock_offset: float = -0.0007  # OBS-NTP saat farkı (sn) [+ileri / -geride]
        self._obs_clock_uncertainty: float = 0.00408  # OBS saat belirsizliği σ (sn)

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

    @property
    def muted(self) -> bool:
        return self._muted.is_set()

    def mute(self):
        """Olay yayınını durdur (bekleme ve ateşleme yeteneği korunur)."""
        self._muted.set()

    def unmute(self):
        self._muted.clear()

    def _countdown_due(self, now: float) -> bool:
        """Geri sayım olayı yayınlansın mı? En fazla COUNTDOWN_INTERVAL'de bir.

        Bekleme döngüsü son 5 saniyede saniyede ~180 tur atıyor ve her turda
        yayın yapıyordu: tek motorda 902 olay, 32 konteynerde ana servise
        saniyede ~5800 olay. Bu hem boşa iş, hem de DEVİR KARARININ verilmesi
        gereken anda event loop'a yük bindiriyordu. Yerel motorda daha kötüsü:
        yayın, tetiği vurması gereken thread'in içinde oluyor.

        Arayüz saniyede 10 güncellemeden fazlasını zaten kullanamaz.
        """
        if (now - self._last_countdown) >= COUNTDOWN_INTERVAL:
            self._last_countdown = now
            return True
        return False

    def _emit(self, event_type: str, data: dict | None = None):
        if self._muted.is_set():
            return
        olay = {
            "type": event_type,
            "data": data or {},
            "timestamp": time.time(),
        }
        try:
            self._events.put_nowait(olay)
        except queue.Full:
            # Kuyruk dolu: EN ESKİ olayı düşür, yenisini koy. Kullanıcı için
            # güncel durum eskisinden değerli. Bu yol tetik anında da
            # çalışabildiği için ASLA exception sızdırmamalı.
            try:
                self._events.get_nowait()
            except queue.Empty:
                pass
            try:
                self._events.put_nowait(olay)
            except queue.Full:
                pass

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

    @property
    def stood_down(self) -> bool:
        return self._stood_down.is_set()

    def stand_down(self):
        """İzole konteyner devraldı — ateşlemeden çekil.

        Busy-wait'e girilmeden çağrılırsa bu motor CPU'yu boşuna meşgul etmez;
        eşzamanlı kullanıcılarda GIL çekişmesini azaltan asıl kazanç budur.
        """
        self._stood_down.set()

    def _should_announce_done(self) -> bool:
        """Bitiş olayı yayınlansın mı?

        Çekilme bir bitiş değildir: kayıt izole konteynerde sürüyor. done
        yayınlansaydı arayüz 'KAYIT TAMAMLANDI' modalını açar, kullanıcı dersi
        alınmadan alınmış sanırdı. İptalde ise done gitmeli — arayüz iptal
        ekranını ondan öğreniyor.
        """
        return not self._stood_down.is_set()

    def _wait_should_continue(self) -> bool:
        """Bekleme döngüsü sürsün mü? İptal veya devir varsa hayır."""
        return not self._cancelled.is_set() and not self._stood_down.is_set()

    def _best_calibration(self) -> Optional[CalibrationData]:
        """Havuzdan en iyi ölçümü seç — ama İKİ AYRI ölçütle.

        `server_offset`'in doğruluğunu NTP gecikmesi belirler; `rtt_one_way`'in
        doğruluğunu HTTP RTT belirler. Bunlar farklı büyüklükler ve tek örnekten
        tek ölçütle seçmek, birinde kazanıp ötekinde kaybetmek demek.

        CANLI OLAY (20 Eylül 06:05, gerçek kullanıcı): ateşlemeden 14 saniye
        önce buffer 10.2ms'den 14.5ms'ye ÇIKTI. Son tam kalibrasyonun NTP
        gecikmesi 11ms'ydi (öncekiler 3-7ms) ama HTTP RTT'si en düşüktü;
        yalnızca RTT'ye bakıldığı için o örnek seçildi ve kötü NTP gecikmesini
        de beraberinde getirdi. Alt sınır yine bağladı, ama pay 7.7ms yerine
        3.5ms kaldı — 18 Eylül'de 0.9ms'ye inen hatanın bir kat derinindeki
        hali.

        NTP'si olmayan örnekler (gecikme 0 kaydedilir) offset seçiminde yarışa
        girmez: aksi hâlde "en düşük gecikme" diye kazanırlardı.
        """
        if not self._cal_samples:
            return self._calibration
        en_dusuk_rtt = min(self._cal_samples, key=lambda s: s[1])
        ntp_li = [s for s in self._cal_samples if len(s) > 4 and s[4] > 0]
        offset_ornegi = min(ntp_li, key=lambda s: s[4]) if ntp_li else en_dusuk_rtt
        return CalibrationData(
            server_offset=offset_ornegi[0],
            rtt_one_way=en_dusuk_rtt[1] / 2,
            ntp_offset=self._calibration.ntp_offset if self._calibration else 0.0,
            # Eski örnekler bu alanı taşımıyor olabilir; 0 → geri düşülür.
            ntp_delay=offset_ornegi[4] if len(offset_ornegi) > 4 else 0.0,
        )

    def _refresh_buffer(self) -> float:
        """Buffer'ı havuzdaki EN İYİ ölçümden yeniden hesapla ve sakla.

        Buffer motor başlarken bir kez hesaplanıp donuyordu. Tetik bekleme
        boyunca defalarca yeniden hesaplanıyor (periyodik kalibrasyon, son tam
        kalibrasyon) ama hep o donmuş buffer'la. 18 Eylül'de 42vq5'in kötü
        başlangıç ölçümü (NTP gecikmesi 16.2ms → buffer 19.1ms) hedefe kadar
        taşındı ve alt sınırın 0.9ms yakınına kadar geldi; oysa havuz o sırada
        2ms gecikmeli ölçümlerle dolmuştu.

        Ağ ölçümü yapılmaz: jitter en son ölçülen değerden okunur.
        """
        cal = self._best_calibration()
        if cal is None:
            cal = self._calibration or CalibrationData()
        self._measurement_buffer = self._calculate_measurement_based_buffer(
            cal, self._rtt_jitter
        )
        return self._measurement_buffer

    def _apply_advanced_protection(
        self,
        calculated_trigger: float,
        target_time: float,
        server_offset: Optional[float] = None,
    ) -> float:
        """Tetik zamanını güvenli pencereye sıkıştır.

        GERÇEK DAVRANIŞ (ölçüldü): formül hedeften ~8ms ÖNCE ateşlemek ister
        ama alt sınır tetiği hedef+1ms'ye çeker; istek OBS'e ~hedef+20ms'de
        varır. Bu bilinçli: erken varış VAL02 + 3sn ceza demek. Beklenen değer
        hesabı bunu doğruluyor — hedef+10ms'yi hedefleseydik 10ms kazanıp
        %2.3 ihtimalle 3 saniye kaybederdik (beklenen kayıp 68ms).
        Dolayısıyla hesaplanan buffer pratikte tetiği etkilemez; sınır bağlar.

        SINIRLAR YEREL SAATTE DEĞİL, GERÇEK ZAMANDA ANLAMLIDIR. `server_offset`
        (= yerel saat − gerçek zaman) ile kaydırılırlar:
          - saatimiz ileri giderse sınır ileri kayar → erken varış önlenir
          - saatimiz geri kalırsa sınır geri kayar → gereksiz gecikme önlenir
        Saat doğruyken (offset≈0) davranış bugünküyle birebir aynıdır.
        """
        if server_offset is None:
            best = self._best_calibration()
            server_offset = best.server_offset if best else 0.0

        protected_trigger = calculated_trigger

        # ALT SINIR: paketin gerçek zamanda hedef+1ms'den önce yola çıkmaması.
        # RTT tek yön (~20ms) zaten doğal güvenlik tamponu sağlar.
        min_safe_time = target_time + 0.001 + server_offset
        if protected_trigger < min_safe_time:
            delay_ms = (min_safe_time - protected_trigger) * 1000
            if abs(delay_ms - self._last_val02_delay) > 1:  # Sadece değişince logla
                self._log(f"🔒 VAL02 koruma: tetik {delay_ms:+.0f}ms geciktirildi (hard floor: hedef+1ms)", "info")
                self._last_val02_delay = delay_ms
            protected_trigger = min_safe_time

        # ÜST SINIR: 200ms sonra kontenjan dolmuş olabilir.
        latest_allowed = target_time + 0.200 + server_offset
        if protected_trigger > latest_allowed:
            self._log(f"⚠️ Geç varış koruması: {(protected_trigger - latest_allowed)*1000:.0f}ms öne çekildi", "warning")
            protected_trigger = latest_allowed

        return protected_trigger

    def _add_sample(self, offset: float, rtt: float, source: str,
                    ntp_delay: float = 0.0):
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

        sample = (offset, rtt, time.time(), source, ntp_delay)
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
                # HEAD — POST DEĞİL. Ölçtüğümüz şey ağ transiti; POST buna
                # OBS'in kimlik+kayıt mantığı maliyetini de katıyordu ve
                # kayıt başına ~37 sahte kayıt isteği ediyordu (bkz.
                # _rtt_stats yorumu).
                self.session.head(OBS_URL, timeout=10)
            except Exception:
                continue
            rtts.append(time.perf_counter() - t0)
        if not rtts:
            return 0.010
        rtts.sort()
        return rtts[len(rtts) // 2]

    # ── RTT İstatistikleri ──

    def _rtt_stats(self, n: int = 10) -> dict:
        """RTT istatistikleri: median, jitter (robust), min, max.

        HEAD kullanılır, POST değil. Eskiden gerçek kayıt ucuna
        `ECRN:["00000"]` ile POST atılıyordu; `_rtt_olc` ile birlikte kayıt
        başına ~37 sahte kayıt isteği ediyordu (40 kullanıcılık dalgada
        ~1500). Üniversitenin kayıt ucuna bu hacimde sahte istek, aracın
        engellenmesine yol açabilecek bir risk.

        ÖLÇÜLDÜ (19 Eylül, Frankfurt, n=120, dönüşümlü):
            HEAD kayıt ucu : min 36.1  medyan 36.5  p90 36.8 ms  (HTTP 405)
            POST kayıt ucu : min 36.1  medyan 36.6  p90 37.0 ms  (HTTP 401)
            fark (min)     : 0.0 ms

        Birebir aynı — HEAD, kayıt ucunda 405 ile yönlendirme katmanında
        kesilip uygulamaya hiç girmediği hâlde. Yani ölçtüğümüz saf ağ
        transiti. Üretimdeki gerçek token'lı POST'un min'i 38.0ms; aradaki
        1.9ms OBS'in kimlik+kayıt mantığı maliyeti, formülün istemediği bir
        pay. Dolayısıyla HEAD hem daha nazik hem daha DOĞRU.
        """
        rtts = []
        for _ in range(n):
            if self._cancelled.is_set():
                break
            t0 = time.perf_counter()
            try:
                self.session.head(OBS_URL, timeout=10)
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
        # Popülasyon std sapması DEĞİL: tek bir takılan ölçüm tetiği
        # kaydırıyordu (bkz. robust_jitter).
        jitter = robust_jitter(rtts)

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

        # σ_ntp: offseti ALDIĞIMIZ ölçümün hassasiyeti (delay/2).
        #
        # CANLI OLAY (18 Eylül, 42vq5): buffer motor başlarken bir kez
        # hesaplanıp donuyordu. Başlangıç turunun NTP gecikmesi 16.2ms'ydi →
        # σ_ntp 8.1ms → buffer 19.1ms, tek yön RTT'nin (20.0ms) yalnızca
        # 0.9ms altı. σ_ntp 9ms olsaydı buffer sınırı devre dışı bırakır,
        # tetik gecikirdi. Oysa havuz sonradan çok daha iyi ölçümlerle
        # doluyor ve offset oradan seçiliyordu — belirsizliği başka bir
        # örnekten almak tutarsızdı.
        ntp_delay = getattr(cal, "ntp_delay", 0.0) or self._last_ntp_delay or 0.008
        sigma_ntp = ntp_delay / 2

        # σ_rtt: Ağ RTT değişkenliği (ölçülen jitter)
        sigma_rtt = rtt_jitter  # tipik: ~1-3ms

        # σ_obs: OBS sunucu saat farkı belirsizliği
        sigma_obs = self._obs_clock_uncertainty  # kalibrasyon yoksa 25ms

        # σ_asimetri: RTT gidiş-dönüş asimetrisi.
        #
        # Bu bir VARSAYIM, ölçüm değil — ve öyle kalmak zorunda. Doğrudan
        # ölçmek OBS tarafında senkron bir saat ister; tek aday `Date`
        # başlığıydı ve 19 Eylül'de ÖNBELLEKLİ olduğu kanıtlandı (bkz.
        # calibration/obs_clock_probe.py). TCP timestamp'leri requests
        # seviyesinden okunamıyor.
        #
        # Canlı verinin verdiği dolaylı sınır zayıf: 15-19 Eylül'de ~30 gerçek
        # kayıtta hiç VAL02 yok, bu da |asimetri| < ~20ms diyor.
        #
        # Ama değeri pratikte ÖNEMSİZ: %10, %15, %20 varsayımlarının üçünde de
        # buffer tek yön RTT'nin altında kalıyor (9.2 / 10.2 / 11.3ms vs 19ms),
        # yani alt sınır bağlıyor ve tetik değişmiyor. Bu terim ancak gecikmeler
        # bugünkünden çok düşerse anlam kazanır.
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
                    self._log(f"Date geçişi: RTT={rtt*1000:.0f}ms, offset={offset*1000:+.0f}ms (±500ms hassasiyet)")
                    return offset
                time.sleep(poll_aralik)

            return None
        except Exception:
            return None

    def calibrate(self, source: str = "manual") -> CalibrationData:
        """NTP birincil offset kaynağı, Date header cross-validation."""
        self._set_phase("calibrating")
        self._log("Sunucu saati ölçülüyor...")

        # 1. Bağlantıyı ısıt — HEAD ile, kayıt ucuna sahte POST atmadan.
        try:
            self.session.head(OBS_URL, timeout=10)
        except Exception as e:
            self._log(f"Bağlantı ısıtma hatası: {e}, ana sayfa deneniyor...", "warning")
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

            # Date header ile karşılaştır (sanity check)
            if date_offset is not None:
                diff = abs(server_offset - date_offset)
                if diff > 0.500:
                    self._log(f"ℹ️ NTP-Date farkı: {diff*1000:.0f}ms (beklenen — Date header 1sn granülarite)")
                else:
                    self._log(f"✅ NTP-Date tutarlı (fark: {diff*1000:.0f}ms)")
        elif date_offset is not None:
            # NTP başarısız → Date header fallback
            server_offset = date_offset
            accuracy = medyan_rtt / 2
            self._log(f"⚠️ NTP başarısız, Date header kullanılıyor (±500ms hassasiyet)", "warning")
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
        # Gecikmeyi ÖRNEĞE yaz: belirsizlik, offseti aldığımız ölçümden
        # gelmeli. NTP başarısızsa None kalır → 0.0, eski davranışa düşülür.
        self._add_sample(server_offset, medyan_rtt, source,
                         ntp_delay=ntp_delay or 0.0)

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
            "server_ntp_diff_ms": (self._calibration.server_offset - (ntp_offset_raw or 0.0)) * 1000,
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
            self._add_sample(server_offset, medyan_rtt, source,
                             ntp_delay=ntp_delay or 0.0)

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
        """TCP+TLS bağlantısını ısıt. HEAD ile — POST ile DEĞİL.

        Eskiden POST atıyordu ve `head_only=True` yalnızca İKİNCİ POST'u
        atlıyordu; buna rağmen "Bağlantı hazır (HEAD only)" diye logluyor,
        çağrıldığı yerdeki yorum da "HEAD ile, debounce riski sıfır" diyordu.
        Üçü de yanlıştı.

        Şu ana dek zararsız kalmıştı çünkü son tam kalibrasyon T-20s civarında
        bitiyor ve ısıtma T-13s'ye düşüyordu. Ama latent bir ders kaybı riski:
        `calibrate()` bir kez 9004ms sürdü ve OBS yavaşlayabiliyor; kalibrasyon
        17 saniye sürseydi ısıtma POST'u T-3s'ye, yani debounce penceresinin
        içine düşer ve GERÇEK kayıt isteği VAL16 alırdı.

        HEAD aynı bağlantıyı aynı şekilde ısıtır: ÖLÇÜLDÜ (19 Eylül, Frankfurt,
        n=120) HEAD ve POST'un RTT'si birebir aynı (min 36.1ms / 36.1ms).

        `head_only` artık yalnızca istek SAYISINI belirler.
        """
        try:
            self.session.head(OBS_URL, timeout=10)
            if not head_only:
                self.session.head(OBS_URL, timeout=10)
            self._log("Bağlantı hazır" + (" (tek istek)" if head_only else ""))
        except Exception as e:
            self._log(f"Prewarm hatası: {e}", "warning")

    # ── PreparedRequest ──

    def _build_request(self, ecrn_list: list[str]) -> requests.PreparedRequest:
        req = requests.Request(
            method="POST", url=OBS_URL,
            json={"ECRN": ecrn_list, "SCRN": self.scrn_list},
        )
        return self.session.prepare_request(req)

    def _prepare_fire(self):
        """Tetikten ÖNCE yapılabilecek her şeyi yap.

        Ölçüm (2026-09-12): tetikten sonra istek inşa etmek, eşzamanlı kullanıcı
        başına ~1.4ms gecikme ekliyor — 15 kullanıcıda medyan 26ms, 100'de 173ms.
        Bu hazırlık tetikten önce çalıştığında tetik anında geriye yalnızca
        session.send() kalır ve gecikme kullanıcı sayısından bağımsızlaşır.
        """
        if self._prepped is not None and self._prepped_for == self.ecrn_list:
            return
        kalan = list(self.ecrn_list)
        for crn in kalan:
            self._crn_results.setdefault(crn, {"status": "pending", "message": "Bekliyor"})
        self._prepped = self._build_request(kalan)
        self._prepped_for = kalan

    def _done_payload(self) -> dict:
        """Bitiş olayının içeriği.

        İptal ile gerçek tamamlanmayı AYIRIR. run() finally bloğu her durumda
        done yayınladığı için, iptal eden kullanıcıya da "KAYIT TAMAMLANDI"
        modalı gösteriliyordu — hiçbir şey tamamlanmamışken.
        """
        return {
            "results": dict(self._crn_results),
            "cancelled": self._cancelled.is_set(),
            "stood_down": self._stood_down.is_set(),
        }

    def _request_for(self, ecrn_list: list[str]) -> requests.PreparedRequest:
        """Hazır istek bu CRN listesiyle eşleşiyorsa onu kullan; değilse yeniden inşa et.

        Kayıt döngüsünde başarılı CRN'ler listeden düştükçe istek yenilenmeli;
        ama ilk (en kritik) istekte hazır olan doğrudan kullanılır.
        """
        if self._prepped is not None and self._prepped_for == ecrn_list:
            return self._prepped
        self._prepped = self._build_request(ecrn_list)
        self._prepped_for = list(ecrn_list)
        return self._prepped

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

        # CRN sonuçları + istek tetikten ÖNCE hazırlanmış olmalı.
        # _prepare_fire idempotent: hazırsa hiçbir şey yapmaz, değilse burada hazırlar.
        self._prepare_fire()
        prepped = self._request_for(kalan)
        ilk = True
        crn_degisti = False

        for deneme in range(1, self.max_deneme + 1):
            if not kalan or self._cancelled.is_set():
                break

            self._current_attempt = deneme
            t0 = time.perf_counter()

            if not ilk:
                if crn_degisti:
                    prepped = self._request_for(kalan)
                    crn_degisti = False

            try:
                resp = self.session.send(
                    prepped,
                    timeout=(FIRE_CONNECT_TIMEOUT, FIRE_READ_TIMEOUT),
                )
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
            debounce_var = False

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
                        debounce_var = True
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
                        # Etiket bizden, AYRINTI OBS'ten. Kodu tanıyor olmak
                        # OBS'in açıklamasını yutmamalı: VAL11'i "Önkoşul
                        # sağlanmadı" diye bilmek yetmez, öğrencinin HANGİ
                        # dersi hangi notla alması gerektiğini görmesi lazım
                        # (18 Eylül, 42vq5).
                        desc = HATA_KODLARI.get(rc, rc)
                        ek = obs_aciklama(rd)
                        if ek:
                            desc = f"{desc}: {ek}"
                        elif rc not in HATA_KODLARI:
                            desc = f"{rc} (OBS açıklama göndermedi)"
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
                if debounce_var:
                    # "Çok erken geldin" — aynı hızda ısrar etmek denemeyi
                    # ziyan eder (bkz. DEBOUNCE_BACKOFF).
                    time.sleep(max(self.retry_aralik, DEBOUNCE_BACKOFF))
                elif tum_val02:
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
            self._finalize_pending(kalan)

    def _finalize_all(self):
        """Kaydın bittiği HER yolda çağrılır: kalan tüm CRN'leri karara bağlar.

        _kayit_yap yalnızca kendi döngüsü tükenince finalize ediyordu; bekleme
        sırasında iptal edilen bir kayıtta dersler "Bekliyor" olarak kalıyordu.
        """
        if self._crn_results:
            self._finalize_pending(list(self._crn_results.keys()))

    def _finalize_pending(self, kalan: list[str]):
        """Karara bağlanmamış CRN'lere NİHAİ bir durum yaz.

        Denemeler tükendiğinde yalnızca log yazılıyordu; _crn_results'taki
        "Bekliyor" olduğu gibi kalıyordu. Kayıt bitmiş görünürken ders ekranda
        hâlâ "Bekliyor" yazıyordu ve öğrenci dersi alıp almadığını anlayamıyordu.
        Biten bir kaydın her CRN'i ne olduğunu söylemeli.

        Karara bağlanmış sonuçlara DOKUNULMAZ: alınmış bir ders başarısız
        yazılamaz.
        """
        iptal = self._cancelled.is_set()
        degisti = False
        for crn in kalan:
            mevcut = self._crn_results.get(crn, {})
            if mevcut.get("status") not in (None, "pending", "debounce"):
                continue  # zaten karara bağlanmış
            if iptal:
                self._crn_results[crn] = {
                    "status": "dropped", "message": "İptal edildi"
                }
            else:
                self._crn_results[crn] = {
                    "status": "error",
                    "message": "Denemeler tükendi — kayıt alınamadı",
                }
            degisti = True
        if degisti:
            self._emit("crn_update", {"results": dict(self._crn_results)})

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
            self._rtt_jitter = rtt_stats['jitter']
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

            # 3b. TETİK ÖNCESİ HAZIRLIK — eşzamanlılık için kritik.
            # İstek inşası ve CRN sözlüğü burada, beklemeye girmeden önce yapılır;
            # tetik anında geriye yalnızca session.send() kalır.
            self._prepare_fire()
            self._log("📦 İstek tetik öncesi hazırlandı (gönderim anında ek iş yok)")

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
                    # Buffer'ı da tazele: havuz iyileştiyse belirsizlik de
                    # küçülmüş demektir (bkz. _refresh_buffer).
                    self._refresh_buffer()
                    # ADVANCED TREND ANALYSIS: Hedef zamanda ofseti tahmin et
                    predicted_offset = self._predict_offset_at_target_time(hedef)
                    
                    # Temel tetik zamanı hesapla
                    # OBS ileri → kayıt erken açılır → daha erken tetikle (offset'i çıkar)
                    base_trigger = hedef + predicted_offset - best.rtt_one_way - self._obs_clock_offset + self._measurement_buffer
                    
                    # GELIŞMIŞ KORUMA MEKANIZMALARI UYGULA
                    new_trigger = self._apply_advanced_protection(base_trigger, hedef)
                    
                    return new_trigger
                return final_trigger

            while self._wait_should_continue():
                now = time.time()
                kalan = final_trigger - now

                # Countdown event — 10 Hz ile sınırlı (bkz. _countdown_due)
                if self._countdown_due(now):
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

                # ── Bağlantı canlı tutma (10s, 5s, 3.5s kala — hepsi HEAD) ──
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

            if self._stood_down.is_set():
                self._log("İzole konteyner kaydı üstlendi — bu motor çekildi", "info")
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
            if self._should_announce_done():
                # Hangi yoldan bittiysek bitelim, hiçbir ders "Bekliyor" kalmasın
                self._finalize_all()
                self._set_phase("done")
                self._emit("done", self._done_payload())
            else:
                # Çekildik: sessizce sus. Arayüzü konteynerin olayları sürdürür.
                self._log("Kayıt izole konteynerde sürüyor", "info")
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
