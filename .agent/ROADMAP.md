# ROADMAP — İTÜ Otostop

> **Yaşayan doküman.** Her oturumda buradan devam et; biten işi `[x]` işaretle.
> Son güncelleme: 2026-09-12 (Faz 6: GCP taşıma, eşzamanlılık kökü, kimlik, UX yenileme)

## Mevcut Durum (Özet)

- **Kayıt motoru (backend + `/` sayfası):** Production-ready, olgun. Cloud Run + Vercel'de canlı.
- **Schedule Builder (`/schedule`):** ~%90 bitti, **hiçbiri commit edilmemiş** (untracked). Eksik: persist/cloud sync, mobil test.
- **Git:** Son commit 25 Şubat 2026. 1 unpushed commit + 8 modified + ~10 untracked dosya. **3.5 aylık iş kayıp riski altında.**
- **Tasarım:** Fonksiyonel ama "AI slop" kalıplarıyla dolu (aşağıda envanter). Baştan yenilenecek.
- **Test:** Sıfır test.

---

## Faz 0 — Güvence (HEMEN, her şeyden önce)

Amaç: 3.5 aylık commit'lenmemiş işi güvene almak.

- [x] `bun run build` + `bun run lint` — temiz (2026-06-14)
- [x] Anlamlı commit'lere bölündü: schedule (da3b520), redesign (1f86cbc), dev orchestrator (c5436c7), .agent (a098eb3), dev fix (f222b66)
- [x] `git push` — origin/main'e gönderildi; remote yeni konuma güncellendi (MustafaKucukcoskun/itu-otostop)
- [x] `npm run dev` fastapi hatası çözüldü: dev.mjs artık backend/venv Python'ını kullanıyor

> Faz 0 tamamlandı (2026-06-14). main, origin ile senkron.

---

## Faz 1 — Design Renovation (AI slop temizliği) 🎨

Amaç: Efekt istifi yerine karakterli, disiplinli bir görsel dil. Yön kararı kullanıcıyla birlikte verilecek; implementasyon `frontend-design` yaklaşımıyla yapılacak.

### Mevcut AI-slop envanteri (sökülecek/azaltılacak)

`frontend/src/app/page.tsx:8-12` — **5 efekt katmanı üst üste:** `mesh-bg` + `mesh-orb-accent` + `dot-grid` + `grain-overlay` + `cursor-glow`.

| Kalıp | Yer | Anti-pattern ref |
|---|---|---|
| Mesh gradient orbs | `globals.css:437-491` | `design-refs/anti-patterns.csv` #9 (high) |
| Glassmorphism (`.glass`) | `globals.css:188-215` | #10 (medium) |
| Cursor glow (mouse takipli ışık) | `globals.css:291-322` | AI-premium klişesi |
| Dönen conic gradient border | `globals.css:241-285` | AI-premium klişesi |
| Animasyonlu gradient text | `globals.css:496-521` | AI-premium klişesi |
| Glow shadow'lar (`glow-sm/md`) | `globals.css:220-235` | Efekt istifi |
| Grain overlay + dot grid | `globals.css:580-611` | Doku istifi (ikisi birden) |
| Spotlight card | `components/spotlight-card.tsx` | AI-premium klişesi |
| Log/title emoji yoğunluğu | dashboard, engine logları | Emoji overload |

### Korunacak değerler

- oklch renk altyapısı (perceptually uniform — teknik olarak doğru)
- Geist Sans/Mono + `tabular-nums` (Inter değil — iyi)
- 8'li ders renk paleti mantığı (hue slot sistemi)
- Spring-physics etkileşim animasyonları (dekoratif olanlar değil, bilgi taşıyanlar)

### Görevler — TAMAMLANDI (2026-06-14)

Karar: **Precision Instrument** yönü + **Chronometer** paleti (nötr + international orange H38/40).
Karar görseli: `design-refs/palette-preview.png/html`. Sistem: `DESIGN_SYSTEM.md` v3.

- [x] **Yön kararı** (kullanıcı): Precision Instrument / Chronometer paleti seçildi
- [x] DESIGN_SYSTEM v3 yazıldı (renk, tip ölçeği, spacing, motion bütçesi, efekt yasakları)
- [x] `globals.css` yeniden yazıldı (tüm efekt sınıfları söküldü: glass, mesh-bg, cursor-glow, gradient-border, glow, text-gradient, dot-grid, grain, shimmer, pulse-ring; radius 0; panel-label + status pulse + reduced-motion eklendi)
- [x] `page.tsx` + `schedule/page.tsx` arka plan katmanları kaldırıldı
- [x] `Panel`/`PanelHeader` primitive (`components/panel.tsx`); `spotlight-card.tsx` silindi
- [x] Bileşen geçişi: dashboard, navbar, countdown (dev mono + turuncu ms), calibration, logs, CRN manager, token-input, settings, presets, connection-status, weekly-schedule, dashboard-skeleton, privacy-banner, token-guide-modal
- [x] Schedule bileşenleri: grid, sidebar, selector modal
- [x] Auth: auth-layout + clerk-appearance + providers (Clerk primary → orange, radius 0)
- [x] `success-overlay` konfetiden "sonuç stempeli"ne dönüştürüldü
- [x] `prefers-reduced-motion` desteği eklendi (globals.css)
- [x] Emoji temizliği: sayfa title + toast + UI etiketleri (backend log emojileri korundu)
- [x] Light/dark + mobil görsel doğrulama (Playwright) — build + lint temiz
- [x] Badge/UI primitive'leri sharp (radius 0) yapıldı

> Not: Faz 1 bitti. Sıradaki: Faz 0 (commit/push güvencesi) veya Faz 2 (Schedule Builder bitirme).
> Faz 0 hâlâ bekliyor — bu redesign da commit edilmeli.

---

## Faz 2 — Schedule Builder'ı Bitirme 🏗️

Plan: `plans/schedule-builder.md` (10 maddeden 9'u bitti)

- [x] Seçili derslerin **localStorage persist**'i (Playwright ile teyit: ders kalıyor)
- [ ] `schedule-service.ts` — Supabase cloud sync *(opsiyonel, ERTELENDİ — localStorage yeterli; cihazlar-arası senkron isteğe bağlı)*
- [x] `weekly-schedule` vs `schedule-grid` tutarlılığı → `lib/course-colors.ts` tek kaynak; metin tema-duyarlı (light okunabilirlik bug'ı da düzeldi)
- [x] `AppNavbar` → `ConditionalNavbar` ile `layout.tsx`'e taşındı (DRY)
- [x] CRN import toast feedback ("N ders aktarıldı")
- [x] CRN ile doğrudan ekleme + breadcrumb + "Ders Alanı" rename (bonus)
- [x] Uçtan uca akış: bölüm seç → ders ekle (modal + CRN ile) → grid → aktar — Playwright ile teyit
- [x] Mobil: redesign'da 390px test edildi; navbar yapısı değişmedi

> Faz 2 TAMAM (2026-06-14). Tek açık: schedule cloud sync (opsiyonel, ertelendi).

---

## Faz 3 — Backend Sağlamlaştırma 🔧

Analizde tespit edilen sorunlar (satır numaraları 2026-06-13 itibarıyla):

- [x] **Race condition (TOCTOU):** `SessionState.lock` ile engine start atomik (commit + prod deploy)
- [x] **`token_preview`:** ilk4…son4 maskeli (prod'da test edildi: `eyJh…9999`)
- [x] **Kalibrasyon failover:** NTP+Date başarısızsa offset=0 yerine geçmiş en iyi (en düşük RTT) offset
- [x] **CORS:** Cloud Run `CORS_ORIGINS=https://itu-otostop.vercel.app` doğrulandı (preflight test edildi)
- [~] **`/api/config` rate limit:** ATLANDI (gerekçe) — kampüs paylaşımlı IP'de per-IP limit meşru kullanıcıyı engeller; config token döndürmüyor (sızma yok)
- [~] **Sessiz exception'lar:** main.py'dekiler uygun (WS disconnect/enum fallback); engine.py tight-loop logları ertelendi (gürültü riski)
- [~] **SCRN sonuç takibi / `CRNStatus.DROPPED`:** ERTELENDİ — kayıt loop'unu riske atar, orta değer
- [~] *(İsteğe bağlı)* `engine.run()` refactor — atlandı (çalışıyor, dokunma riski)

> Faz 3 TAMAM (2026-06-14). Backend revision 00002 prod'da. Riskli/düşük-değerli maddeler gerekçeyle ertelendi.

---

## Faz 4 — Kalite & Dayanıklılık 🧪

- [x] Global **Error Boundary** (`app/error.tsx` + `global-error.tsx`; crash → "Tekrar Dene")
- [x] Offline/WS banner (dashboard: bağlantı kopunca görünür uyarı)
- [x] **pytest başlangıcı:** `backend/test_engine.py` 10 test (TrendAnalyzer regresyon, ChangeDetector eşik, token_preview maske) — hepsi geçiyor
- [x] A11y: form input aria-label'ları (token, CRN, ayarlar) + reduced-motion (Faz 1) + focus outline'lar
- [~] Frontend smoke test (Playwright harness): ERTELENDİ — akışlar Playwright ile defalarca manuel doğrulandı; formal test harness ayrı altyapı işi
- [~] Lighthouse audit: ERTELENDİ — opsiyonel; lighthouse CLI + dev server gerektirir, ayrı adım

> Faz 4 ana maddeler TAMAM (2026-06-14). Smoke harness + Lighthouse opsiyonel/ertelendi.

---

## Faz 5 — Yayın & Kapanış 🚀

- [ ] Production build + deploy (Cloud Run backend güncellemesi gerekiyorsa)
- [ ] Vercel'de yeni tasarımın canlı doğrulaması
- [ ] README güncelle (ekran görüntüleri yeni tasarımla)
- [x] CLAUDE.md son mimariye göre güncellendi (2026-09-07): NTP-birincil kalibrasyon, ölçüm-tabanlı buffer, _obs_clock_offset, proxy.ts, --workers 1 kısıtı, pytest + root `npm run dev` komutları

---

## Faz 6 — Taşıma, Eşzamanlılık ve UX (2026-09-12)

### Altyapı
- [x] Yeni GCP projesine taşındı: `itu-otostop-2026`, **europe-west3** (Frankfurt)
- [x] Eski servis 404 veriyordu; sitedeki tüm backend bağımlı özellikler bu yüzden ölüydü
- [x] Supabase duraklatılmıştı (silinmemişti); Cloud Scheduler ile günlük uyanık tutuluyor
- [x] Hiç çalışmamış Azure workflow'u kaldırıldı

### Kök neden: ders kapılması
- [x] **Bulundu ve ölçüldü**: istek tetikten SONRA inşa ediliyordu; eşzamanlı kullanıcı başına ~1.4ms gecikme
- [x] `_prepare_fire()` / `_request_for()` ile tetik öncesine alındı
- [x] Gerçek motor sınıfıyla doğrulandı: 15 kullanıcı 30.4ms → **1.8ms**, 100 kullanıcı 188ms → 47ms
- [x] **Ölçülerek elenen alternatifler**: process izolasyonu (thread'lerden kötü), CPU artırımı (2→16 vCPU kazanç yok).
      Gönderim yolu I/O ağırlıklı olduğu için thread'ler zaten paralel — kullanıcı başına instance'a GEREK YOK
- [x] OBS aynı-IP testi: **90 eşzamanlıya kadar kısıtlama yok**, gecikme düz (37→38ms)

### Kimlik ve kota
- [x] Backend Clerk token'ını doğruluyor (`auth.py`, RS256/JWKS)
- [x] Oturumlar tarayıcıya değil **kimliğe** bağlı → bir kişi tek slot; `MAX_SESSIONS` 100 → 200
- [x] `REQUIRE_AUTH=true`; kimliksiz istek 401
- [x] WS token'ı URL yerine `Sec-WebSocket-Protocol` başlığında (URL'ler loglanıyor)
- [x] Giriş artık uygulamanın kendi Türkçe sayfasında (`signInUrl`) — alan adı gerekmeden

### Düzeltilen hatalar
- [x] Ders planı kullanıcılar arasında sızıyordu (sabit localStorage anahtarı)
- [x] `saveConfig` hataları sessizce yutuluyordu → yanlış CRN ile kayıt riski
- [x] `manifest.json` 404 (middleware `.json`'u muaf tutmuyordu) + eksik PWA ikonları
- [x] Devre dışı düğmeler aktif görünüyordu (global `grayscale` kuralı)
- [x] Dry-run gerçek kayıtla aynı "KAYIT TAMAM" ekranını gösteriyordu
- [x] İptal "TAMAMLANDI" gösteriyordu; ayrıca araya "HAZIR" parlaması giriyordu
- [x] Gizlilik metni yanlıştı ve kendiyle çelişiyordu
- [x] Preset bulut hataları sessizdi (Supabase duraklamasını aylarca gizledi)

### UX yenileme
- [x] 5 kademeli sihirbaz → tek akıllı arama kutusu (modal silindi, 511 satır)
- [x] Gözatma ızgarası (177 alan) — kod bilmeyen için
- [x] Ders **adına** göre arama (Türkçe karaktersiz yazım dahil)
- [x] Takvim yüksekliğe duyarlı; sayfa uygulama kabuğuna dönüştü
- [x] Çakışan dersler yan yana (eskiden biri diğerini tamamen gizliyordu)
- [x] Geri sayım paneli duruma göre ölçekleniyor

### Açık kalanlar
- [ ] **Clerk production** — alan adı gerektiriyor, kullanıcı şu an alamıyor
- [ ] Gerçek eşzamanlı yük Cloud Run'da test edilmedi (ölçümler yerelde gerçek motor sınıfıyla)
- [ ] İptal, bloke eden ağ çağrısının ortasında duramıyor (arayüzde "DURDURULUYOR" ile maskelendi)
- [ ] Olmayan CRN sorgusu 14 saniye sürüyor
- [ ] Dashboard sol sütun boşluğu; komut paleti (Cmd+K) fikri
- [ ] Frontend testi yok
- [ ] `.github/copilot-instructions.md` hâlâ tek dosyalı scripti anlatıyor (yanıltıcı)
