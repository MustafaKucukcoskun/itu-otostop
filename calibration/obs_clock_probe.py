# -*- coding: utf-8 -*-
"""OBS sunucu saatinin NTP'ye göre sapması — Cloud Run'dan hassas ölçüm.

NEDEN BU ARAÇ VAR
─────────────────
`engine._obs_clock_offset = -0.0007` ve `_obs_clock_uncertainty = 0.00408`
sabitleri 15 Şubat 2026'da konmuş. σ_obs, tetik buffer'ındaki toplam
varyansın ~%47'si — yani en büyük tek kalem. Ama iki şey belirsiz:

  1. 4.08ms TEK ÖLÇÜMÜN saçılımı mı, yoksa ORTALAMANIN belirsizliği mi?
     5000 örnekle ortalamanın standart hatası 0.06ms olurdu; aradaki fark
     70 kat ve doğrudan buffer'a giriyor.
  2. Şubat'tan beri OBS'in saati ne kadar kaydı?

YÖNTEM
──────
OBS'in `Date` header'ı 1 saniye çözünürlüklü. Saniyenin DEĞİŞTİĞİ an, OBS'in
saatine göre gerçek bir saniye sınırıdır. O anı NTP-düzeltilmiş saatimizle
karşılaştırınca OBS'in sapması çıkar.

Kritik ayrıntı — EŞZAMANLI ÖRNEKLEME: geçiş, ardışık iki isteğin sunucuya
VARIŞI arasında olur, dolayısıyla ölçüm hassasiyeti isteklerin arasındaki
mesafedir. Sırayla istek atılırsa bu mesafe RTT kadar olur (Frankfurt'tan
~40ms) ve ölçüm kabalaşır. İstekler önceden zamanlanmış threadlerle
ARALIK kadar arayla fırlatılırsa, RTT hepsine aynı şekilde eklendiği için
bracket ARALIK kadar kalır (~3ms).

NEDEN CLOUD RUN
───────────────
Ölçüm, yerel saatin NTP'ye ne kadar iyi bağlı olduğuyla sınırlı. Geliştirici
makinesinden denendi: NTP delay 49-86ms, offset saçılımı σ=7ms → OBS ölçümü
38ms saçıldı, yani araç değil referans kötüydü. Cloud Run'da kendi motor
loglarımız NTP delay'ini 2-6ms gösteriyor.

Tek seferlik bir Cloud Run Job olarak çalıştırılır; istek yolunda değildir.

SONUÇ — 19 EYLÜL 2026: BU YÖNTEM BU SUNUCUDA ÇALIŞMIYOR
───────────────────────────────────────────────────────
Frankfurt'tan temiz bir referansla ölçüldü (NTP delay 2ms, bracket 3ms, yerel
saat kayması <1ms) ve yöntem GEÇERSİZ çıktı. Kanıtlar:

  1. HAM DAĞILIM DÜZ. Gözlenen geçiş anları -20ms ile +140ms arasında
     neredeyse düzgün dağılıyor; çan eğrisi yok. Niceliksel olarak da tutuyor:
     genişliği W olan düzgün dağılımda σ = W/√12 = 194/3.46 = 56ms, ölçülen
     σ = 47ms. Gerçek bir saat sapması + ölçüm gürültüsü Gauss verirdi.
  2. KOŞULAR ANLAŞMIYOR. Beş koşunun ortalamaları +34, +43, +59, +59, +61ms —
     aralarında 27ms fark var, oysa her koşu ±10ms güven aralığı iddia ediyor.
     Örnekler bağımsız değil, dolayısıyla standart hata anlamsız.
  3. CANLI VERİ ÇELİŞİYOR. Bendeki işaret konvansiyonunda pozitif = OBS geride.
     +59ms doğru olsaydı kayıt penceresi gerçek zamanda 59ms sonra açılır ve
     hedef+20ms'de varan isteklerimiz VAL02 alırdı. 15-19 Eylül'de ~30 gerçek
     kayıtta bir tane bile VAL02 yok.

Açıklama: `Date` başlığı önbelleklenmiş bir saatten üretiliyor (nginx bunu
yapar). Gözlenen "geçiş", OBS'in saatinin değil önbellek yenileme aralığının
içine düzgün dağılıyor; ortalama da o aralığın yarısı oluyor. Örnek sayısını
artırmak anlamsız bir niceliğin ortalamasını daraltır, doğruyu vermez.

Dolayısıyla `_obs_clock_offset` ve `_obs_clock_uncertainty` DEĞİŞTİRİLMEDİ.
σ_obs'u küçültme yolu bu yöntemle kapalı; başka bir gözlenebilir bulunmadıkça
4.08ms sabiti yerinde kalmalı. Canlı verinin verdiği dolaylı sınır: hedef+20ms
varışlarda hiç VAL02 görülmemesi, OBS saatinin en azından "geride" yönünde
~20ms'den fazla sapmadığını gösteriyor.

Araç silinmedi çünkü yöntemin NEDEN çalışmadığını tekrar üretebilmek, onu
yeniden denemekten ucuz.
"""

import os
import socket
import statistics
import struct
import threading
import time
from email.utils import parsedate_to_datetime

import requests

OBS = os.getenv("OBS_BASE", "https://obs.itu.edu.tr")
HEDEF_ORNEK = int(os.getenv("ORNEK", "60"))
ARALIK = float(os.getenv("ARALIK", "0.003"))        # istekler arası mesafe = bracket
PENCERE = float(os.getenv("PENCERE", "0.060"))      # sınırın ±bu kadarını tara
NTP_SUNUCULARI = ["time.google.com", "metadata.google.internal", "time.cloudflare.com"]
# Şubat 2026'da konan sabit — kayma bununla kıyaslanır.
ESKI_SABIT_MS = -0.70


def ntp_olc(sunucu, timeout=2.0):
    """(offset, delay). offset = sunucu_saati − yerel_saat."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        t1 = time.time()
        s.sendto(b"\x1b" + 47 * b"\0", (sunucu, 123))
        veri, _ = s.recvfrom(1024)
        t4 = time.time()
    finally:
        s.close()
    t2 = struct.unpack("!I", veri[32:36])[0] + struct.unpack("!I", veri[36:40])[0] / 2**32 - 2208988800
    t3 = struct.unpack("!I", veri[40:44])[0] + struct.unpack("!I", veri[44:48])[0] / 2**32 - 2208988800
    return ((t2 - t1) + (t3 - t4)) / 2, (t4 - t1) - (t3 - t2)


def en_iyi_ntp(tur=3):
    """En DÜŞÜK gecikmeli ölçüm en güvenilir olandır; onu seç."""
    en_iyi = None
    for _ in range(tur):
        for sunucu in NTP_SUNUCULARI:
            try:
                off, delay = ntp_olc(sunucu)
            except Exception:
                continue
            if delay <= 0:
                continue
            if en_iyi is None or delay < en_iyi[1]:
                en_iyi = (off, delay, sunucu)
    return en_iyi


def _atis(oturum, gonder_at, sonuc, idx):
    """Planlanmış anda tek HEAD at; (gonderim, Date saniyesi) kaydet."""
    bekle = gonder_at - time.time()
    if bekle > 0:
        time.sleep(bekle)
    t0 = time.perf_counter()
    gercek_gonderim = time.time()
    try:
        r = oturum.head(OBS, timeout=5)
        d = r.headers.get("Date")
    except Exception:
        return
    if not d:
        return
    sonuc[idx] = (gercek_gonderim, parsedate_to_datetime(d).timestamp(),
                  time.perf_counter() - t0)


def gecis_yakala(oturum, ntp_off, merkez=0.0):
    """Bir saniye sınırını eşzamanlı örneklemeyle yakala.

    `merkez`: OBS'in sapması hakkında şimdiye kadar öğrendiğimiz tahmin.
    Pencere onun etrafına kurulur — ilk örneklerden sonra sınırın nerede
    olduğunu bildiğimiz için hem yakalama oranı yükselir hem OBS'e gereksiz
    istek atılmaz.

    Döner: (sapma_sn, bracket_sn, rtt_sn) veya None.
    """
    simdi_gercek = time.time() + ntp_off
    sinir_gercek = float(int(simdi_gercek) + 1) + merkez
    ilk_gonderim_gercek = sinir_gercek - PENCERE
    ilk_gonderim_yerel = ilk_gonderim_gercek - ntp_off

    n = int(2 * PENCERE / ARALIK)
    sonuc = [None] * n
    threadler = [
        threading.Thread(target=_atis,
                         args=(oturum, ilk_gonderim_yerel + i * ARALIK, sonuc, i),
                         daemon=True)
        for i in range(n)
    ]
    for t in threadler:
        t.start()
    for t in threadler:
        t.join(timeout=8)

    ham = [x for x in sonuc if x]
    if len(ham) < 2:
        return None
    # Her isteğin VARIŞI kendi RTT'siyle tahmin edilir; gönderim sırası
    # varış sırasına eşit değildir (bağlantı başına gecikme farklı olabilir).
    varisli = sorted(((g + rtt / 2, sn, rtt) for g, sn, rtt in ham),
                     key=lambda x: x[0])

    # TANI: varışa göre sıralanmış Date dizisi GERİ giderse, isteklerimiz
    # saatleri farklı BİRDEN FAZLA sunucuya dağılıyor demektir ve bu
    # yöntemin tamamını geçersiz kılar.
    geri_adim = sum(1 for a, b in zip(varisli, varisli[1:]) if b[1] < a[1])

    for onceki, simdiki in zip(varisli, varisli[1:]):
        if simdiki[1] > onceki[1]:
            bracket = simdiki[0] - onceki[0]
            gecis_yerel = (onceki[0] + simdiki[0]) / 2
            gecis_gercek = gecis_yerel + ntp_off
            kesir = gecis_gercek % 1.0
            sapma = kesir - 1.0 if kesir > 0.5 else kesir
            return sapma, bracket, (onceki[2] + simdiki[2]) / 2, geri_adim, len(ham)
    return None


def main():
    oturum = requests.Session()
    oturum.headers.update({"User-Agent": "itu-otostop-clock-probe/1.0"})
    oturum.mount("https://", requests.adapters.HTTPAdapter(
        pool_connections=64, pool_maxsize=64))

    ntp = en_iyi_ntp()
    if ntp is None:
        print("NTP olculemedi — olcum yapilamaz"); return 1
    ntp_off, ntp_delay, sunucu = ntp
    print(f"NTP referansi : offset {ntp_off*1000:+.2f}ms  delay {ntp_delay*1000:.2f}ms  ({sunucu})")
    if ntp_delay > 0.020:
        print(f"UYARI: NTP delay {ntp_delay*1000:.0f}ms — referans zayif, sonuc guvenilmez")

    r = oturum.head(OBS, timeout=5)
    print(f"OBS           : HTTP {r.status_code}  Date: {r.headers.get('Date')}")

    # Havuzu ÖNCEDEN ısıt. Zamanlanmış atışta bazı istekler yeni bağlantı
    # açarsa TLS el sıkışması (~40ms) varış anını kaydırır ve saçılım,
    # bracket'ten bağımsız olarak büyür. Isıtma bunu ortadan kaldırır.
    n_baglanti = int(2 * PENCERE / ARALIK)
    isit = [threading.Thread(target=lambda: oturum.head(OBS, timeout=5), daemon=True)
            for _ in range(n_baglanti)]
    for t in isit:
        t.start()
    for t in isit:
        t.join(timeout=10)
    print(f"Havuz         : {n_baglanti} baglanti isitildi")
    print(f"Plan          : {HEDEF_ORNEK} ornek, {ARALIK*1000:.0f}ms aralik, "
          f"+/-{PENCERE*1000:.0f}ms pencere\n")

    sapmalar, bracketler, rttler, ntp_gecmis = [], [], [], [(0.0, ntp_off, ntp_delay)]
    geri_adimlar, istek_sayilari = [], []
    t_basla = time.time()
    for i in range(HEDEF_ORNEK):
        if i and i % 15 == 0:
            yeni = en_iyi_ntp(tur=1)
            if yeni and yeni[1] < 0.020:
                ntp_off, ntp_delay = yeni[0], yeni[1]
                ntp_gecmis.append((time.time() - t_basla, ntp_off, ntp_delay))
        # İlk birkaç örnekten sonra pencereyi öğrenilen sapmaya merkezle.
        merkez = statistics.median(sapmalar) if len(sapmalar) >= 5 else 0.0
        s = gecis_yakala(oturum, ntp_off, merkez)
        if s is None:
            continue
        sapma, bracket, rtt, geri, n_istek = s
        sapmalar.append(sapma); bracketler.append(bracket); rttler.append(rtt)
        geri_adimlar.append(geri); istek_sayilari.append(n_istek)
        if len(sapmalar) % 15 == 0:
            print(f"  [{i+1:3d}] n={len(sapmalar):3d}  "
                  f"ort={statistics.mean(sapmalar)*1000:+6.2f}ms  "
                  f"σ={statistics.stdev(sapmalar)*1000:5.2f}ms  "
                  f"bracket={statistics.median(bracketler)*1000:4.1f}ms")

    print("\n" + "=" * 66)
    if len(sapmalar) < 10:
        print(f"Yetersiz ornek ({len(sapmalar)}) — sonuc uretilmedi"); return 1

    ort = statistics.mean(sapmalar); med = statistics.median(sapmalar)
    sd = statistics.stdev(sapmalar); sh = sd / len(sapmalar) ** 0.5
    print(f"  sure / ornek        : {time.time()-t_basla:.0f}sn / {len(sapmalar)}")
    print(f"  medyan bracket      : {statistics.median(bracketler)*1000:.2f} ms  (olcum hassasiyeti)")
    print(f"  medyan RTT          : {statistics.median(rttler)*1000:.1f} ms")
    print(f"  RTT sacilimi        : {statistics.stdev(rttler)*1000:.1f} ms")
    toplam_geri = sum(geri_adimlar)
    toplam_istek = sum(istek_sayilari)
    print(f"  Date GERI gitti     : {toplam_geri} / {toplam_istek} istek "
          f"({toplam_geri/max(toplam_istek,1)*100:.1f}%)   <-- >0 ise COK SUNUCU")
    print(f"  NTP delay (son)     : {ntp_delay*1000:.2f} ms")
    ntp_kayma = (ntp_gecmis[-1][1] - ntp_gecmis[0][1]) * 1000 if len(ntp_gecmis) > 1 else 0.0
    print(f"  yerel saat kaymasi  : {ntp_kayma:+.2f} ms (olcum boyunca)")
    print()
    print(f"  OBS sapmasi ORTALAMA: {ort*1000:+.3f} ms")
    print(f"  OBS sapmasi MEDYAN  : {med*1000:+.3f} ms")
    print(f"  tek olcum sacilimi σ: {sd*1000:.3f} ms")
    print(f"  ORTALAMANIN std hat.: {sh*1000:.3f} ms   <-- sabitin gercek belirsizligi")
    print(f"  %95 guven araligi   : {ort*1000:+.3f} +/- {1.96*sh*1000:.3f} ms")
    print()
    # HAM DAGILIM — sonucu yorumlamadan once sekline bakmak sart.
    # Duzgun (Gauss) ise gercek saat + olcum gurultusu; DUZ/KUTU seklinde ise
    # Date basliginin onbelleklendigine isaret eder ve yontem bu sunucuda
    # gecersizdir.
    ms = sorted(x * 1000 for x in sapmalar)
    print("")
    print("  ham dagilim (10ms kovalar):")
    alt, ust = int(min(ms) // 10 * 10), int(max(ms) // 10 * 10 + 10)
    for k in range(alt, ust, 10):
        n = sum(1 for v in ms if k <= v < k + 10)
        print(f"    {k:+4d}..{k+10:+4d} ms  {'#' * n}{'' if n else ''} {n}")
    print(f"  min={ms[0]:+.1f}  p25={ms[len(ms)//4]:+.1f}  "
          f"p50={ms[len(ms)//2]:+.1f}  p75={ms[3*len(ms)//4]:+.1f}  max={ms[-1]:+.1f} ms")
    print(f"  genislik (max-min)  : {ms[-1]-ms[0]:.1f} ms")
    print()
    print(f"  Subat 2026 sabiti   : {ESKI_SABIT_MS:+.2f} ms")
    print(f"  kayma               : {ort*1000 - ESKI_SABIT_MS:+.3f} ms")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
