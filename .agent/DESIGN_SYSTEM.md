# İTÜ Otostop — Design System v3 "Chronometer"

> **Aktif sistem** (2026-06-13'te v2 "Premium Edition"ın yerini aldı).
> Yön: **Precision Instrument** · Palet: **Chronometer** (nötr + international orange).
> Karar süreci: kullanıcı seçimi, görsel kanıt `design-refs/palette-preview.png`.

---

## 1. Kimlik

Ürün bir **hassasiyet enstrümanı**: milisaniye doğruluğunda çalışan bir kronometre.
Arayüz bir cihaz paneli gibi davranır — net, ölçülü, sessiz; konuşan şey **veridir**.

- Tek metafor: **turuncu ibre.** Kronometrenin saniye ibresi gibi, international orange
  yalnız "canlı/kritik an"ı işaret eder: milisaniye haneleri, primary aksiyon, aktif durum.
- Dekorasyon yoktur. Her görsel öğe ya bilgi taşır ya yoktur.
- Duygu, efektle değil **tipografik ölçek ve boşlukla** kurulur.

## 2. Renk — "Chronometer"

Nötr skala tamamen renksizdir (chroma 0). Renk = anlam; dekorasyonda renk kullanılmaz.

### Light mode
```css
--background: oklch(0.985 0 0);   /* kâğıt beyazı */
--foreground: oklch(0.2 0 0);
--card:       oklch(1 0 0);
--muted-fg:   oklch(0.5 0 0);
--border:     oklch(0.88 0 0);    /* hairline — görünür */
--primary:    oklch(0.6 0.19 38); /* international orange */
```

### Dark mode
```css
--background: oklch(0.15 0 0);    /* near-black, mavi/mor izi yok */
--foreground: oklch(0.93 0 0);
--card:       oklch(0.18 0 0);
--muted-fg:   oklch(0.6 0 0);
--border:     oklch(0.27 0 0);
--primary:    oklch(0.67 0.19 40);
```

### Durum renkleri (yalnız durum bildiriminde)
```css
--status-ok:   yeşil  light oklch(0.55 0.15 150) / dark oklch(0.7 0.16 150)
--status-wait: amber  light oklch(0.62 0.13 80)  / dark oklch(0.75 0.13 80)
--status-err:  kırmızı light oklch(0.55 0.2 25)  / dark oklch(0.65 0.19 25)
```

**Kurallar**
1. Orange: primary buton, milisaniye/kritik rakam vurgusu, focus göstergesi, aktif tab. Başka yerde yasak.
2. Yeşil/amber/kırmızı: yalnız sonuç-durum iletişimi (CRN sonucu, bağlantı, motor fazı).
3. Ders renkleri (schedule grid): mevcut 8'li hue sistemi korunur — bilgi taşır.
4. Gradient hiçbir yerde kullanılmaz. İki rengin geçişine ihtiyaç yoksa zaten tek renk yeter.

## 3. Tipografi — Geist, mono-öncelikli

| Rol | Font | Boyut/Ağırlık | Not |
|---|---|---|---|
| Countdown (hero) | Geist Mono | 56–96px / 600 | `tabular-nums`, ms haneleri orange |
| Sayısal veri (offset, RTT, CRN, saat) | Geist Mono | 12.5–14px / 500 | her zaman mono |
| Panel etiketi | Geist Mono | 10–11px / 600 | UPPERCASE, `tracking 0.1em`, muted |
| H1 sayfa başlığı | Geist Sans | 22–24px / 650 | `tracking -0.02em` |
| Kart başlığı | Geist Mono | 11px / 600 | UPPERCASE tracked (cihaz paneli dili) |
| Gövde | Geist Sans | 14px / 400 | |
| Küçük metin | Geist Sans | 12.5px / 450 | |

Hiyerarşi ağırlıkla değil **ölçek kontrastıyla** kurulur: dev rakamlar ↔ minik etiketler.

## 4. Yüzey & Derinlik

- **Radius: 0** — tüm köşeler keskin (`--radius: 0rem`). İstisna: durum noktası ve avatar (tam yuvarlak).
- **Gölge yok.** Derinlik 3 kademe zemin + hairline border ile: `background → card → popover`.
- Kart anatomisi: 1px border; başlık şeridi (`head`) alt-border'lı, mono-uppercase etiket + sağda meta.
- Bölücü: tam genişlik 1px hairline (`border-t`), gradient çizgi yok.
- Modal scrim: solid karartma `oklch(0 0 0 / 55%)` — **blur yok**.

## 5. Motion Bütçesi

İlke: **animasyon bilgi taşır, dekore etmez.**

| İzinli | Süre/Eğri | Taşıdığı bilgi |
|---|---|---|
| Log satırı girişi | 120ms ease-out | yeni kayıt geldi |
| Durum dot pulse | 2s, yalnız motor `running` iken | sistem canlı |
| Countdown son 5 sn ölçek vurgusu | spring | kritik an yaklaşıyor |
| Tab indicator kayması | spring(400,35) | konum değişti |
| Dialog/sheet açılış | 150–200ms ease-out | bağlam değişti |
| Buton press | scale(0.98), 80ms | giriş alındı |
| Stagger reveal (sayfa girişi, tek sefer) | 300ms, 25ms/öğe | sayfa hazır |

**Yasak:** sonsuz dekoratif döngüler (float, rotate-gradient, shimmer-dekor), hover glow,
parallax, cursor takibi, konfeti. Başarı anı: tam ekran **sonuç stempeli** (solid yeşil
çerçeve + dev mono "KAYIT TAMAM" + CRN listesi) — konfetiden daha karakterli, anında okunur.

**Zorunlu:** `prefers-reduced-motion: reduce` → tüm animasyon ve geçişler kapanır.

## 6. Yasak Kalıplar (anti-pattern sözleşmesi)

v2'den sökülenler — geri getirilmesi yasak (`design-refs/anti-patterns.csv` ile uyumlu):

`mesh-bg` `mesh-orb-accent` `glass / backdrop-blur` `glow-sm/md` `gradient-border`
`text-gradient-primary` `cursor-glow` `spotlight-card` `grain-overlay` `dot-grid`
`shimmer (dekoratif)` `confetti` `view-transition tema dalgası` `UI chrome'da emoji`

Not: Backend log mesajlarındaki emoji CLAUDE.md gereği backend'de kalır; log panelinde
olduğu gibi gösterilir (terminal çıktısı sayılır). UI etiket/başlık/butonlarında emoji yok.

## 7. Bileşen Dili

- **Buton:** primary = solid orange, beyaz metin; secondary = hairline outline; ghost = düz metin.
  Hepsi radius 0, mono-uppercase küçük etiket veya sans 13px.
- **Input:** hairline border; focus = `outline: 2px solid primary; outline-offset: 2px` (glow ring yok).
- **Badge/tag:** hairline border, mono 10px uppercase, dolgu yok (durum badge'inde durum rengi metin+border).
- **Status dot:** 7px daire, durum rengi; `running` iken pulse.
- **Tablo/metrik satırı:** `key (muted, sans) ........ value (mono, sağa hizalı)`.
- **Skeleton:** sade nötr blok + yumuşak opaklık nabzı (shimmer sweep yok).

## 8. Layout

- Navbar: sticky, **solid** zemin + alt hairline (blur yok); sol logo (sans 650), orta tab grubu
  (kayar indicator), sağ tema + kullanıcı.
- Sayfa: `max-w-7xl`, yatay padding 16/24/32, kartlar arası boşluk 16px, section arası 24–32px.
- Dashboard iki sütun yapısı korunur; görsel dil değişir, yerleşim mimarisi değişmez.
- Boşluk disiplini: kart içi 16–20px; ilişkili öğeler sıkı (8px), bölümler arası cömert.

## 9. Dosya Eşlemesi

| Sistem öğesi | Uygulama yeri |
|---|---|
| Tema değişkenleri | `frontend/src/app/globals.css` (`:root`, `.dark`) |
| Durum renkleri | `--status-ok/wait/err` değişkenleri + Tailwind arbitrary değerler |
| Panel etiketi | `.panel-label` utility |
| Hairline | standart `border` (renk token'ı zaten hairline) |
| Ders renkleri | `--course-h-0..7` (korundu) |
