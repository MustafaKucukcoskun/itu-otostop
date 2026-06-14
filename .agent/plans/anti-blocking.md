# Plan: Anti-Blocking — OBS bizi nasıl engelleyebilir?

> Kaynak: rakip araç araştırması (itu-helper, AtaTrkgl/itu-ders-secici) + canlı OBS probe (2026-06-14).
> En kritik bulgu: **itu-ders-secici issue #14**'te gerçek öğrencilerin ölçtüğü ban eşiği.

## OBS'nin savunması: WAF DEĞİL, uygulama-seviyesi sayaç

Canlı probe: OBS **Cloudflare/Akamai/CAPTCHA/JS-challenge KULLANMIYOR** (bare ASP.NET/IIS origin).
Botları saf `requests` ile çalışıyor. Yani **tarayıcı-fingerprint / UA rotasyonu / proxy GEREKSİZ** —
OBS sadece **istek frekansı ve hacmini** sayıyor.

| Savunma | Tetik | Belirti | Bizim durumumuz |
|---|---|---|---|
| Min istek aralığı | <3sn (aynı session) | **VAL16** | ✅ retry ≥3sn (zaten yapıyoruz) |
| Saatlik istek kotası | **~6 dakikada ~100 istek** | **VAL21** + ~10–60dk ban | ❌ özel davranış YOK |
| Public uç limiti | yüksek frekans | **HTTP 429** | obs_course_service cache'liyor (kısmi) |
| Dönem kapalı | erken atış | VAL02 | ✅ canlı kalibrasyon |
| CAPTCHA/WAF | — | **YOK** | önemsiz |

**Somut ban eşiği (gerçek ölçüm, Şubat 2026):**
- UlikGames: 14:00:40–14:06:45 arası **100 istek → VAL21 ban**
- ~6 dakikada ~100 istek = ban sınırı; 3sn aralıkla 6dk = ~120 istek (sınırda)
- "1 saat ban" denmiş ama pratikte ~10dk sonra kalkıyor

## Yapılacaklar (öncelik sırası)

### 🔴 P0 — Rate budget guard (EN DEĞERLİ savunma)
Engine'e **kayan pencere sayacı**: son 6 dakikadaki istek sayısı. ~80-90'a yaklaşınca
otomatik yavaşla; VAL21 riskine girme. Bizim tek-atış avantajımız var ama ilk atış VAL06/VAL16
ile düşüp 3sn retry'a girersek biz de aynı pencereye gireriz → bu guard şart.
- Yer: `engine.py` retry döngüsü; her POST'ta timestamp kaydet, pencereyi say.

### 🔴 P0 — VAL21'e özel davranış
VAL21 görünce: **derhal ateşi durdur**, kullanıcıyı uyar ("rate-limit ban, ~10dk bekle"),
cooldown say, körlemesine retry YAPMA (ban süresini uzatır).
- Yer: `engine.py` response parsing + `models.py` CRNStatus'a yeni durum.

### 🟡 P1 — Hata sözlüğünü tamamla
Ek kodlar: `VAL13` (CRN geçici engelli — retry), `VAL14`/`ERRLoad` (sistem yanıt vermiyor — retry),
`NULLParam-CheckOgrenciKayitZamaniKontrolu`. CRNStatus + log mesajlarına ekle.

### 🟡 P1 — Yedek CRN (backup) mantığı
itu-ders-secici modeli: `primary:backup` formatı. **Yalnız VAL06 (kontenjan dolu)** gelince
backup'a geç; timing kodlarında (VAL02/VAL14) aynı CRN'de ısrar et. Kullanıcı UI'da yedek CRN girebilsin.

### 🟢 P2 — Ders/kontenjan verisi için itu-helper/data
`obs_course_service.py` canlı OBS'e proxy yapıyor. Alternatif: `raw.githubusercontent.com/itu-helper/data`
(5dk tazelik, kontenjan dahil, MIT lisans) → OBS'e hiç vurmadan veri, sıfır 429 riski.
Schedule sayfası + CRN-lookup için. (Bağımlılık riski: onların scraper'ı durursa veri eskir → fallback gerekir.)

### 🟢 P2 — Tek çıkış IP riski (gelecek)
Backend Cloud Run'da tek/az instance → tüm kullanıcılar aynı çıkış IP'sinden OBS'e vuruyor.
OBS IP-bazlı sayaç eklerse hepsi birden banlanabilir. İleride: client-side fire (kullanıcının
kendi IP'sinden) veya çıkış IP havuzu. Şimdilik düşük risk (OBS session/token bazlı sayıyor gibi).

## Bizim zaten üstün olduğumuz yerler (araştırma teyidi)
- Milisaniye kalibrasyon (rakiplerde 0.1sn polling — bir lig geride)
- Token güvenliği (JWT elle yapıştır, şifre/diske yazma yok — rakip config.json'a şifre yazıyor)
- Precision buffer + trend analizi + multi-session mimari
