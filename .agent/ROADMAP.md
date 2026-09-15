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

---

## Faz 7 — Kayıt Günü Hazırlığı (2026-09-12)

### KRİTİK: tek instance bir doğruluk şartı, maliyet tercihi değil
- [x] `max-instances 1` sabitlendi. Oturum durumu bellekte; Cloud Run session affinity
      **bu mimaride çalışamaz**: affinity çerezi `SameSite=None` taşımıyor, frontend
      (vercel.app) ve backend (run.app) farklı siteler, tarayıcı çerezi göndermiyor.
- [x] 3 instance ile ölçüldü: aynı kullanıcının 8 ardışık okuması ÜÇ farklı sonuç verdi
      (yeni yazılan / başka instance'taki eski / hiç oturumu olmayan boş).
- [x] `credentials: "include"` eklendi — gerekli ama **yeterli değil**, çerez yine gitmiyor.
- [ ] Yatay ölçekleme için ortak oturum deposu veya kullanıcı başına konteyner gerekir (kayıt sonrası iş).

### Kapasite gerçeği (Cloud Run'da gerçek engine ile ölçüldü)
- 15 kullanıcı → yayılım ~5ms | 30 → ~10ms | 50 → ~32ms | 70 → ~78ms
- CPU artırmak İŞE YARAMIYOR (2→8 vCPU, %4 iyileşme) — darboğaz GIL, işlemci değil
- Buffer ~11ms (σ_obs 4.08ms + σ_asimetri 3.1ms baskın); σ_obs'u iyileştirmek
      100.000+ OBS isteği ister, ölçüldü ve **değmez** diye karar verildi
- Sonuç: **~50 kullanıcıya kadar 50ms bütçesi içinde**, 60+ için başlık yok

### Zamanlanmış ısıtma
- [x] `warm-up` / `scale-down` Cloud Run Jobs + 4 Cloud Scheduler tetikleyicisi
- [x] Uçtan uca test edildi (Scheduler → Job → gcloud → servis)
- 15 Eyl 06:00 ısın → 18 Eyl 18:00 küçül (kayıt: 15-18 Eylül)
- 27 Eyl 20:00 ısın → 9 Eki 18:00 küçül (ders bırakıp yazılma: 28 Eyl - 9 Eki)
- **İTÜ tarihleri her yıl kayar — her dönem takvimi kontrol edip cron'ları güncelle.**
  Resmî kaynak `takvim.sis.itu.edu.tr`; toplayıcı siteler yanlış (Ekim'deki çekilmeyi
  "add/drop" sanıyorlar).

---

## Faz 8 — Kayıt Başına İzole Konteyner (2026-09-13)

**Amaç:** GIL çekişmesini bitirmek. Faz 7'de ölçülen tavan (~50 kullanıcı /
50ms bütçe) kullanıcı başına ayrı konteynerle tamamen kalkıyor.

### Ölçümler (europe-west3, gerçek Cloud Run)
- Konteyner provisioning: ilk +10s, **medyan +70s**, 40 eşzamanlı istekte yayılım 62s
- 40 eşzamanlı çalıştırma: **40/40 kabul, 0 hata** (kota engeli yok)
- Tek çalıştırma × 40 paralel görev de aynı: yayılım 62.1s → model farketmiyor
- Konteyner içi: import+init+TLS **0.8s**, `calibrate()` **7.0s**, `_rtt_stats(10)` 0.4s
- **Sonuç: istek → ateşlemeye hazır ~19-20s.** Hedeften 900s önce başlatılıyor (45× pay).

### Tasarım — izolasyon yalnızca EKLER
- [x] Yerel motor **sökülmedi**. Her kayıt bugünkü gibi kalibre olup bekliyor.
- [x] İzole konteyner yanında açılıyor; **hazır olduğunu kanıtlayana kadar
      kaydı üstlenmiyor** (önce kalibre olur, sonra T-180s'de sahiplenir).
- [x] Sahiplik geçince yerel motor `stand_down()` ile çekiliyor (busy-wait'e hiç girmiyor).
- [x] Konteyner kalkmazsa / kalibre olamazsa / geç kalırsa sahiplik geçmiyor →
      yerel motor bugünkü gibi ateşliyor. **Tek ateşleyici garantisi** `IsolationBroker`'da.
- [x] OBS token'ı görev env'ine KONULMUYOR (Cloud Run çalıştırma kaydında günlerce durur);
      konteyner tek kullanımlık biletle `/internal/config`'ten HTTPS ile çekiyor.

### Dosyalar
- `isolation.py` — sahiplik/zamanlama çekirdeği (23 test)
- `job_launcher.py` — Run Admin API v2 istemcisi (6 test)
- `isolated_runner.py` — konteyner giriş noktası
- `engine.py` — `stand_down()` / `_wait_should_continue()` eklendi (6 test)
- `main.py` — `_isolation_supervisor()` + `/internal/{config,claim,events}` (10 test)

### Canlı doğrulama
- [x] Servis hesabı görevi başlatabiliyor (IAM ampirik doğrulandı)
- [x] Konteyner açıldı, yapılandırmayı çekti, kalibre oldu, sahiplendi
- [ ] Gerçek OBS token'lı tam ateşleme testi — kayıt gününde izlenecek

### Maliyet
40 kullanıcı × 900s × 1 vCPU = 36.000 vCPU-s. Aylık ücretsiz kota 240.000 vCPU-s
ve 450.000 GiB-s. Bellek: 40 × 900s × 0.5GiB = 18.000 GiB-s. **Ücretsiz kotanın
içinde (~6× pay).** Ders seçimi ayda birkaç gün olduğu için ek maliyet yok.

### Operasyon
- `ISOLATION=true` ile açılır/kapanır. Kapatmak bugünkü davranışa anında döner.
- Görev imajı servis imajıyla **aynı** olmalı: servisi yeniden dağıtınca
  `itu-otostop-kayit` görevini de yeni imaja güncelle.

---

## Faz 8b — Devir Güvenliği (2026-09-13)

Faz 8'in ardından baştan sona edge case analizi yapıldı. Dört gerçek hata çıktı.

### Bulunan hatalar
1. **İptal çalışmıyordu.** Konteyner devralınca yerel motor duruyordu,
   `/api/register/cancel` 404 dönüyordu. Kullanıcı iptal edemiyor, konteyner
   yine de kaydediyordu. → İptal broker'a yazılıyor, nabızla konteynere gidiyor.
2. **Kimse ateşlemeyebilirdi.** Yerel motor T-180s'de çekiliyordu; konteyner
   sonra ölürse ateşleyen kalmıyordu. → Çekilme T-8s'ye alındı ve nabız şartına
   bağlandı. Sahiplik artık "hak" değil "söz".
3. **Çift ateşleme (ağ kopması).** Konteyner ulaşamazken sözünü tuttuğunu
   sanıyor, ana servis onu ölü sayıp yerel motora devrediyordu. → Simetri
   kuralı: konteyner de 10sn rapor veremediyse çekiliyor.
4. **Geç sahiplenme.** → Hedefe 20sn'den az kalmışsa reddediliyor.

### Ayrıca düzeltilenler
- Yerel motor sahiplenmede susturuluyor (iki motorun logları iç içe geçiyordu)
- Konteyner durumu oturuma aynalanıyor (sayfa yenileyince sonuç görünüyor)
- Konteyner motorun anlık görüntüsünü alıyor (aynı CRN listesi garantisi)
- Başlatma hatasında 3 deneme; devir denetimi başlatmaların önüne alındı
- Biten kayıtlar periyodik temizleniyor
- `/internal/diag` — anahtarla korumalı canlı durum dökümü

### Canlı doğrulama (gerçek OBS token'ı, dry-run)
- [x] **A — geç kayıt:** hedefe 20sn'den az kalınca konteyner sahiplenmedi,
      yerel motor ateşledi ve BAŞARDI. Tek ateşleyici. *(geçerli token)*
- [x] **B — tam akış:** sahiplenme T-179.9s, nabız 2sn'de bir, devir T-5.6s,
      konteyner ateşledi ve BAŞARDI. Sayfa yenilense konteynerin sonucu
      görünüyor (durum aynası çalışıyor). *(geçerli token)*
- [x] **E — konteyner söz verip ÖLÜYOR (en kritik):** nabız donuk kaldı
      (132→172sn yaşlandı), ana servis **T-7.1s'de sözü geri aldı**, sahiplik
      yerel motora döndü. Felaket senaryosu kapalı.
- [x] **D — iki kullanıcı aynı anda:** ayrı konteynerler, bağımsız sahiplenme,
      devirler kendi T-8s'lerinde (aralarında 40sn) — biri diğerini etkilemedi.
- [x] **Simetri kuralı sahada:** bileti geçersizleşen konteyner nabzı 403
      alınca kendini geri çekti.
- [x] **C — devir sonrası iptal (taze token'la tekrarlandı):** iptal HTTP **200**
      döndü (eski kod 404 veriyordu), broker'da `cancelled=True`, konteyner bunu
      nabızdan öğrenip motorunu durdurdu, CRN `pending` kaldı — **hiç ateşleme olmadı.**

### Üretim imajıyla son doğrulama (2026-09-14, geçerli token)
- [x] **Tam akış:** sahiplenme T-180s, nabız 0.1–2.0s, devir T-4.2s, konteyner
      ateşledi → `success`. Nabız T-2s'de durdu (busy-wait'i bozmasın).
- [x] **NİHAİ TEST — konteyner öldürüldü:** sahiplendikten sonra Cloud Run'dan
      `executions cancel` ile öldürüldü. Nabız dondu (114→160sn), ana servis
      **T-4.8s'de sözü geri aldı**, sahiplik yerele geçti ve **YEREL MOTOR
      DERSİ ALDI** (`success`). Söz verip ölen konteyner ders kaybettirmiyor.

### Sayılar tek yerde tutulmalı
`isolation.py` ve `isolated_runner.py` aynı eşikleri kullanıyor:
`HEARTBEAT_MAX_AGE=10`, `HANDOVER_WINDOW/GUARD=8`. Birini değiştirirken
diğerini de değiştir — simetri bozulursa çift ateşleme veya hiç ateşleme olur.

---

## Faz 8c — Kapasite Tavanı Ölçüldü (2026-09-14)

**Soru:** Kaç konteyner açacağız, kullanıcı sayısını bilmeden nasıl planlarız?

**Cevap: planlamıyoruz.** Konteyner önceden ayrılmıyor; her aktif kayıt için
hedeften 15 dk önce bir tane açılıyor, ateşleme bitince kapanıyor. Bilinmesi
gereken tek şey sistemin ne hızda konteyner açabildiği.

### Ölçüm (europe-west3, gerçek Run Admin API)
| Deneme | Sonuç |
|---|---|
| 100 istek aynı anda | 63/100 kabul, **37 × HTTP 429** |
| 100 istek, saniyede 5 | 61/100 kabul, 39 × 429 |
| 40 istek, saniyede 2 | **40/40** |
| 40 istek, saniyede 1 | **40/40** |
| Toplam 229 çalıştırma | **0 hata** (CPU kotası sorun değil) |

Yani Run Admin API bir **token-bucket** uyguluyor: kova ~60, dolum ~2/sn.
Kova boşaldıktan sonra sürekli doluyor (70sn sonra 10/10, 30sn sonra 10/10).

### Buna göre yapılan değişiklik
- `ISOLATION_LAUNCH_PER_TICK=4` — denetleyici 2 saniyede bir döndüğü için
  saniyede 2 konteyner. 90 kullanıcı 45 saniyede açılır; pencere 900 saniye.
- `MAX_LAUNCH_ATTEMPTS` 3 → 6. 429 geçici olduğu için cömert tutuldu;
  denemeler turlara yayılıyor (~12 saniyelik pencere).
- Başlatma sınırı kayıt DÜŞÜRMEZ, yalnızca yayar.

### Gerçek tavan
Konteyner sayısı değil, **oturum sayısı** sınırlıyor: `MAX_SESSIONS=200`.
Bir konteyner hiç açılamazsa yerel motor ateşliyor — kimse dışarıda kalmıyor.

### Maliyet
Konteyner yalnızca çalışırken ücretlendiriliyor: 40 kullanıcı × 900s × 1 vCPU
= 36.000 vCPU-s ≈ **$0.65**, bellek $0.04. Ders seçimi başına ~$0.70.

---

## Faz 9 — Kullanıcı Verisi Buluta Taşındı (2026-09-14)

İki kullanıcı şikâyetinin ortak kökü: plan, şablon ve CRN etiketleri
localStorage'daydı.

1. **Telefonda farklı plan.** Ders planı cihaz başına saklanıyordu.
2. **Şablon silinmiyordu.** İlk göçte yerel şablonlar buluta yükleniyor ama
   dönen bulut id'si yerele yazılmıyordu; silme eski id ile gidip hiçbir satır
   silmiyor, sayfa yenilenince şablon geri geliyordu. `getUserPresets` hata
   hâlinde `[]` döndürdüğü için her geçici ağ hatası da şablonları çoğaltıyordu.

### Kurallar
- Giriş yapmış kullanıcıda **bulut tek doğruluk kaynağı**; localStorage
  yalnızca çevrimdışı önbellek.
- Başarısız okuma boş değer değil `null`/`undefined` döner ve **yazmayı kapatır**
  — eski bir cihaz buluttaki gerçeği ezemez.
- Satır oluşturan her yazma sunucunun döndürdüğü id'yi saklar.
- Silme bulut yeniden okunarak **doğrulanır**; id'si ayrışmış kayıtlar için
  ada göre silmeye düşer. "Silindi" mesajı doğrulamadan sonra çıkar.

### YAPILACAK (kullanıcı)
- [ ] `frontend/sql/002_user_data.sql` → Supabase SQL Editor → RUN.
      Çalıştırılana kadar kod güvenle localStorage'a düşer ve silme
      başarısızlığını açıkça bildirir.

---

## Faz 10 — Baştan Sona Denetim (2026-09-15)

Kullanıcı "dersi kaçırmanın kaç yolu var, hepsi kapalı mı" diye sordu. Her yolu
çıkardım ve **dört gerçek hata** buldum.

### 1. Plan buluta yazılmadan sayfa değişiyordu
Plan değişikliği 800ms gecikmeyle buluta yazılıyor, ama "Kayıt Motoruna Aktar"
sayfa değiştirdiği için `clearTimeout` bekleyen yazmayı iptal ediyordu. Ders
eklenip hemen aktarılırsa buluta hiç gitmiyor, telefonda eksik görünüyordu.
→ Bekleyen yazma `pagehide`, `visibilitychange` ve sökülmede boşaltılıyor.

### 2. Token kayıt saatinden önce dolabiliyordu — EN SESSİZ KAYIP
Motor token'ı yalnızca BAŞLARKEN kontrol ediyor. Akşam kurulan bir kayıt
ertesi gün ateşlerken token gece ölmüş oluyor, OBS 401 dönüyor, ders gidiyor.
Arayüz "6 saat sonra sona erecek" diyerek sakin görünüyordu çünkü bu değer
kayıt saatiyle hiç karşılaştırılmıyordu.
→ `token_expiry.py` + `/api/register/start` 400 ile reddediyor; arayüz de
   ayrı ve kırmızı bir uyarı gösteriyor. Okunamayan `exp` engellemez.

### 3. Belirsizlikte çekilme (yön yanlıştı)
Konteyner ana servise ulaşamadığında "geri alınmış olmalıyım" deyip
çekiliyordu. Ama servis ÇÖKTÜYSE yerel motor da ölüdür → kesin kayıp.
→ Kural çevrildi: **belirsizlikte ateşle.** Üç yerde: nabız kopması,
   sahiplenme isteğinin cevapsız kalması, yapılandırma çekmenin ilk denemede
   tutmaması. Yalnızca NET cevaplar durdurur (iptal / geri alma / 403).

### 4. Hız limiti IP başınaydı — KAYIT GÜNÜ DERS KAYBETTİRİRDİ
`/api/register/start` dakikada 6 istek, IP başına. Kampüs WiFi'si, yurt ağı ve
mobil CGNAT yüzünden onlarca öğrenci aynı IP'den çıkar; 7. öğrenci 429 alır ve
kaydı HİÇ başlamaz. 40 oturumluk test bunu birebir üretti: 40'ın sadece 6'sı
başlayabildi.
→ Limit Clerk kimliğine bağlandı. Yeniden test: **40/40 başladı, 0 hata.**

### 40 kullanıcı ölçek testi (ilk kez gerçek ölçekte)
- 40 kayıt başlatıldı: **40/40, 0 hata** (limit düzeltmesinden sonra)
- 40 konteyner açıldı: **40/40, 0 açılma hatası**, ~25 saniyede
- 32 konteyner sahiplendi, 8'i geç kaldığı için reddedildi → **yerel motor
  ateşledi, ders kaybı yok** (tasarlandığı davranış)
- Kalibrasyon 40 konteynerde: 6.8–7.8 saniye

### ÖLÇÜM: konteyner soğuk başlangıcı 40 eşzamanlıda 7 DAKİKAYA çıkıyor
*(Bu sonuç YANLIŞ çıktı — Faz 12'ye bakın. Gerçek sebep CPU kotasıymış.)*
→ `ISOLATION_LEAD` 900 → **1800 saniye**. Maliyet $0.65 → $1.30, önemsiz.

### Güvenlik denetimi (GitHub)
- Geçmişte hiç `.env.local`, anahtar dosyası, sertifika veya şifre yok
- `frontend/.env` izleniyor ama yalnızca public backend URL'i içeriyor
- `CLAUDE.md` gitignore'da (teşhis anahtarını içeriyor)
- Tek "sır" eşleşmesi: arayüzdeki `Bearer eyJ...` örnek metni
- Klasör yapısı temiz: `.agent/ backend/ calibration/ frontend/ scripts/`

### KAYIT GÜNÜ KURALI
**Kayıt penceresinde DAĞITIM YAPMA.** Durum bellekte; yeni sürüm konteyneri
değiştirir ve bekleyen bütün motorları öldürür.

---

## Faz 11 — Çökme Sebepleri ve Motor Algoritması Denetimi (2026-09-15)

Soru: ana servisi ne çökertebilir, motor algoritması doğru mu, istek erken
veya gereksiz geç varıyor mu?

### ÇÖKME SEBEPLERİ — üç tanesi bulundu ve kapatıldı

**1. Event loop'u bloke eden senkron çağrı (EN CİDDİ).**
`/api/search-courses` `search_courses()`'ı doğrudan çağırıyordu. Onbellek
boşken bu 41 sıralı OBS isteği demek (~8sn, OBS yavaşsa çok daha fazla) ve tek
uvicorn worker'ı olduğu için o sürede servis HİÇBİR şeye cevap veremez:
WebSocket susar, `/internal/heartbeat` cevapsız kalır, izolasyon denetleyicisi
çalışamaz (T-8s devir penceresi kaçar), Cloud Run sağlık yoklaması zaman
aşımına uğrarsa instance yeniden başlar ve bekleyen tüm kayıtlar ölür.
→ `asyncio.to_thread` + `SEARCH_CONCURRENCY` semaforu (thread havuzunu
  tüketip konteyner başlatmayı geciktirmesin).
→ `test_event_loop.py`: loop durmasını BEKÇİ GÖREVLE ölçüyor. İsteğin süresini
  ölçmek yanıltıcıydı — ölçümden önceki `await` blokajı soğuruyordu. Bekçinin
  kör olmadığını kanıtlayan ayrı bir test var.

**2. Geri sayım olayları saniyede 180 üretiliyordu.**
Bekleme döngüsü son 5 saniyede ~180 Hz dönüyor ve her turda yayın yapıyordu:
tek motorda 902 olay. 32 konteyner bunu aktarınca ana servise saniyede ~5800
olay — tam devir kararının verildiği anda. Yerel motorda daha kötü: yayın,
tetiği vurması gereken thread'in içinde.
→ 10 Hz'e kısıtlandı (`COUNTDOWN_INTERVAL`). 902 → ~50 olay.

**3. Olay kuyruğu sınırsızdı (OOM).**
Drenaj ölürse olaylar saatlerce birikir; 40 oturumda yüzlerce MB ve 1 GiB'lık
konteyner OOM ile ölür.
→ `EVENT_QUEUE_MAX=2000`, taşmada en eski düşer. `_emit` tetik yolunda
  çağrıldığı için taşma dalı asla exception sızdırmaz.

### MOTOR ALGORİTMASI — doğrulandı

**Formülün işareti doğru.** `tetik = hedef + server_offset − rtt − obs_offset
+ buffer`. NTP `sunucu − yerel` verir ama kalibrasyonda `server_offset =
-ntp_offset_raw` ile çevriliyor, yani `yerel − gerçek`. Türetme formülle
birebir örtüşüyor. (Varsayımla değil, türeterek doğrulandı.)

**Gerçek davranış: hedef+1ms'de gönder, OBS'e ~hedef+20ms'de var.**
Formül hedeften 8.3ms ÖNCE ateşlemek istiyor ama koruma alt sınırı sıkıştırıyor.
İki sonuç:
- Hesaplanan buffer tetiği HİÇ etkilemiyor (sınır, buffer < ~20ms olduğu
  sürece bağlayıcı; buffer 10.3ms).
- 20ms gecikme DOĞRU tercih. Beklenen değer hesabı:

  | varış | erken varma | beklenen kayıp | kazanç |
  |---|---|---|---|
  | hedef+20.3ms | %0.004 | 0.12 ms | — (şimdiki) |
  | hedef+15ms | %0.179 | 5.4 ms | 5.3 ms |
  | hedef+10.3ms | %2.275 | 68.3 ms | 10 ms |

  VAL02 = 3 saniye debounce cezası. Daha erken ateşlemek beklenen değerde
  zarar. **Alt sınırı bu hesabı yeniden yapmadan aşağı çekme.**

**Tetik ile gönderim arasındaki iş ihmal edilebilir:** 2000 ölçümde medyan
7 µs, en kötü 41 µs.

**Koruma sınırları saat farkına duyarlı hale getirildi.** Sınırlar yerel
saatteydi; saatimiz 20ms'den fazla ileri giderse erken varırdık ve bunu
önleyecek offset telafisi tam da sıkıştırmayla atılıyordu. Artık ölçülen
`server_offset` ile kaydırılıyorlar. Saat doğruyken davranış birebir aynı.

196 test geçiyor.

---

## Faz 12 — Asıl Darboğaz Bulundu: CPU Kotası (2026-09-15)

Kullanıcı kritik bir düzeltme yaptı: **kullanıcılar başlata T-5/T-10 dakikada
basıyor**, saatler önce değil. Bu, "konteyneri erken açalım" tasarımının
dayandığı varsayımı çürüttü ve kökten yeniden ölçüm gerektirdi.

### Önce: motor 5-10 dakikalık lead ile çalışıyor mu?
**Evet.** Hazır olma süresi 8 saniye (token kontrolü 0.3 + kalibrasyon 7.2 +
ısınma 0.1 + RTT 0.4). Kalibrasyon takvimi 5 dakikaya rahat sığıyor:
T-300s ilk kalibrasyon, 30sn'de bir periyodik, T-20s son tam kalibrasyon.

### Yanlış hipotez: imaj boyutu
Göreve minimal imaj yapıldı (`engine.py` `models.py`'ı hiç kullanmıyor, yani
pydantic bile gerekmiyor — sadece requests + ntplib + tzdata). Aynı koşullarda:

| | Minimal imaj | Üretim imajı |
|---|---|---|
| Son konteyner | +28s | **+37s** |

Fark 9 saniye. **Faz 11'de raporladığım "7 dakika" yanlıştı** — o rakam 40
kullanıcı testinin log zamanlarından ÇIKARILMIŞTI, doğrudan ölçülmemişti.

### Asıl sebep: bölgesel CPU kotası
40 uzun yaşayan (180sn) konteyner açıldığında çalışan sayısı **tam 18'de**
iki dakikadan uzun süre sabit kaldı, sonrakiler yer açıldıkça başladı.

```
Total CPU allocation per project per region
  europe-west3 = 20000 milli vCPU = 20 vCPU
```

Ana servis 2 vCPU tutuyor → geriye **tam 18** kalıyor. Plato tesadüf değil,
kotanın kendisiydi. Konteynerler yavaş kalkmıyordu, **sıra bekliyordu**.
40 kullanıcı testindeki "32 sahiplendi, 8 yetişemedi" de bununla açıklanıyor
(hedefler 5'er saniye kaymıştı, erken bitenler yer açtı).

### Çözüm: kota artırımı — anında onaylandı
Cloud Quotas API ile `CpuAllocPerProjectRegion` 20 → **64 vCPU** istendi ve
**anında onaylandı**. Yeniden ölçüm: **40/40 konteyner aynı anda çalıştı.**

Geriye 62 yuva kalıyor, 40 kullanıcıya birebir konteyner düşüyor.

### Değerlendirilen ama gerekmeyen: kullanıcıları gruplama
Kullanıcının önerisi (bir konteynere birkaç kullanıcı) teknik olarak
doğruydu — GIL çekişmesi süreç başınadır, 3 kullanıcı bir konteynerde 1ms'nin
altında kalır. Eski kotayla 18×3 = 54 kullanıcıyı karşılardı. Kota artışından
sonra gereksiz kaldı; en kritik kod yoluna karmaşıklık eklemekten kaçınıldı.

### GERÇEK SENARYO TESTİ — 40 kullanıcı, T-5 dakikada başlat
Kullanıcının tarif ettiği davranışın birebir testi: 40 kullanıcı, hepsi aynı
hedefe, hepsi hedeften 5 dakika önce başlat'a basıyor.

```
açılan konteyner : 40/40    0 hata
SAHİPLENEN       : 40/40    ilk sahiplenme hedefe 178.2s kala
devir kararı     : 40/40    T-6s'de, hepsi birden
```

Kota artışından önce bu 18'de tıkanıyordu. Artık T-5dk'da başlayan 40
kullanıcının hepsi kendi izole konteynerini alıyor.

Aynı test, token koruması için de canlı doğrulama oldu: süresi 1.4 dakika
kalmış token'la 5 dakika sonrasına kayıt denendiğinde sistem
`400 "Token kayıt saatinden önce sona eriyor (4 dakika erken)"` döndü.

### Kayıt günü kontrol listesi
1. `CpuAllocPerProjectRegion` = 64000 olduğunu doğrula. Konteynerler yavaş
   kalkıyor gibi görünürse **önce kotaya bak**, başka bir şey arama.
2. Kayıt penceresinde **dağıtım yapma** — durum bellekte, yeni sürüm bekleyen
   bütün motorları öldürür.
3. `/internal/diag` ile canlı durumu izle (anahtar: `X-Diag-Key`).

---

## Faz 13 — Satır Satır Kod Denetimi (2026-09-15)

Beş katmanda denetim: kayıt yaşam döngüsü → izolasyon devri → kullanıcı edge
case'leri → veri katmanı → gerçek veriyle kanıt. **Altı hata bulundu.**

### 1. `/api/register/reset` event loop'u bloke ediyordu
`engine_thread.join(timeout=3)` bir async handler içindeydi. İptal bayrağı
kalibrasyon sırasında (7sn ağ çağrısı) kontrol edilmediği için tam 3 saniye
bloke edebiliyordu — ve bu uç frontend tarafından OTOMATİK çağrılıyordu.
→ `asyncio.to_thread`. Bekçi görevli test eklendi.

### 2. Geçersiz kayıt saati modelden geçiyordu
`\d{2}:\d{2}:\d{2}` düzenli ifadesi `25:00:00` ve `12:70:00`'ı kabul ediyor;
motor `datetime.replace(hour=25)` ile patlıyor, hata dış except'e düşüyor ve
kullanıcı "Kayıt başlatıldı" mesajını aldıktan sonra sessizce hiçbir şey
olmuyordu. Kayıt gününde yanlış yazılan saat = sessiz ders kaybı.
→ Aralık doğrulaması (00:00:00 - 23:59:59), uçtan uca 422.

### 3. Geçmiş kayıt saatiyle başlatma
Uygulamada tarih kavramı yok; "10:00" her zaman BUGÜNÜN 10:00'u. Gece kurulum
yapan kullanıcının hedefi saatlerce geçmiş olur; motor "hedef geçti, hemen
başla" diye ateşler, VAL02 alır, 60 kez boşuna dener.
→ 120 saniyeden fazla geçmişse net mesajla 400. Birkaç saniye geç kalan
   kullanıcı yine deneyebiliyor.

### 4. Biten kayıtta dersler "Bekliyor" kalıyordu
60 denemenin hepsi VAL02 alırsa kod sadece logluyordu; `_crn_results`
güncellenmiyordu. Öğrenci kayıt gününde dersi alıp almadığını anlayamıyordu.
→ `_finalize_all()` her çıkış yolunda çağrılıyor. İptal "dropped", tükenme
   "error" olarak işaretleniyor; karara bağlanmış sonuçlara dokunulmuyor.

### 5. ⚠️ EN ÖNEMLİSİ — ders önbelleği 50 bölüm, ITÜ'de 177 bölüm var
`max_cache_depts=50`. Bulunamayan bir CRN tüm bölümleri taratır; tarama
sırasında ilk 50 bölüm sonrakiler tarafından ATILIR ve bir sonraki sorgu her
şeyi baştan indirir.

**Ölçüldü (üretim):** her sorgu ~12 saniye ve OBS'e ~127 istek — aynı CRN
tekrar sorulsa bile. Ders planı sayfası açılışta toplu sorgu yapıyor;
40 kullanıcı = 5000+ istek, tam OBS'in sağlıklı olması gereken anda.

→ Önbellek 200 bölüme çıkarıldı + bulunamayan CRN'ler için negatif önbellek
  (15 dk). Uç hız sınırına ve arama semaforuna bağlandı, toplu sorgu 50 CRN
  ile sınırlandı.

**Kanıt (üretim, gerçek ölçüm):**

| | Önce | Sonra |
|---|---|---|
| Olmayan CRN, ilk | ~12s | 17.5s (bir kez ısınma) |
| Olmayan CRN, tekrar | ~12s | **0.1s** |
| Başka olmayan CRN | ~12s | **0.2s** |
| 500 CRN'lik liste | kabul | **400** |

OBS'e giden istek: 5080 → ~177 (28 kat azalma).

### 6. İkinci sekme çalışan kaydı sessizce öldürüyordu
Frontend 409 alınca otomatik sıfırlayıp yeniden başlatıyordu. Ama sunucu
409'u YALNIZCA motor thread'i gerçekten yaşıyorsa döndürüyor (ölü thread'in
bayrağını kendi temizliyor). Yani otomatik sıfırlama, ikinci bir sekmeden
gelen tıklamanın çalışan kaydı ve izole konteynerini öldürmesi demekti.
→ Otomatik sıfırlama kaldırıldı; kullanıcıya açık mesaj veriliyor.

### Ayrıca: denetleyici hataları görünür hale getirildi
`_isolation_supervisor` tüm döngüyü `except Exception: pass` ile sarıyordu —
devir mantığı bozulsa asla öğrenemezdik. Kısıtlı loglama eklendi (yeni hata
hemen, tekrarlayan hata dakikada bir).

### Denetlenen ve TEMİZ çıkan yerler
- Zamanlama formülünün işareti (türetilerek doğrulandı)
- `/api/test-token` ve `/api/calibrate` (ikisi de `asyncio.to_thread`)
- `/api/config` çalışan kaydı etkilemiyor (motor kendi kopyasını tutuyor)
- WebSocket try/except/finally ve istemci temizliği
- Kalibrasyon örnek havuzları (ikisi de 20 ile sınırlı)
- Konteyner koşucusunun tüm çıkış yolları
- `_kayit_yap` yeniden deneme mantığı ve OBS hata kodu işleme

236 test geçiyor.

---

## Faz 14 — Canlı Dry-Run Analizi (2026-09-15)

Kullanıcı gerçek token'la, gerçek arayüzden dry-run yaptı. Log iki hata
gösterdi; ikisi de yalnızca canlı koşuda görülebilirdi.

### Ateşleme sonucu — hedef tam tutturuldu
```
🚀 BAŞLIYOR! (hedef farkı: -0ms, tetik farkı: +0ms)
🎯 Sunucu perspektifi: gönderim +1ms, varış +27ms
✅ MÜKEMMEL — Hedef pencere içinde! (+27ms) [0-50ms]
```
Kalibrasyon: jitter 0.1ms, buffer 12.1ms, havuz 3 ölçüm.
Koruma beklendiği gibi çalıştı: formül hedeften 9ms önce ateşlemek istedi,
alt sınır hedef+1ms'ye çekti (analizle birebir aynı).
NTP/Date çapraz doğrulaması doğru: Date 791ms saptı (1sn granülarite),
motor NTP'yi kullandı ve farkı "beklenen" diye işaretledi.

### HATA 1 — "İzole konteyner yetişmedi" uyarısı erken çıkıyordu
```
05:42:59  başlat
05:43:00  ⚠️ İzole konteyner yetişmedi     <-- 1 saniye sonra!
05:43:19  ✅ İzole konteyner kaydı üstlendi  <-- zaten yetişti
```
`fallback_due` eşiği 120 saniyeydi; kullanıcı T-61s'de başlatınca hemen
tetiklendi. Ama sahiplenme T-20s'ye (min_claim_margin) kadar mümkün.
Uyarı, hâlâ ümit varken kullanıcıyı korkutuyordu.
→ Eşik `min_claim_margin`'e bağlandı; uyarı ancak sahiplenme gerçekten
  imkânsızken çıkıyor. `ISOLATION_READY_DEADLINE` kaldırıldı.

### HATA 2 — Konteynerin hazırlık logları sırasız akıyordu
Konteyner açılışta kalibre olurken motorun kuyruğuna onlarca olay yazıyor,
ama olay akışı ancak sahiplenmeden SONRA başlıyor. Canlı logda
"kaydı üstlendi" satırından sonra 8 saniye öncesine ait satırlar geliyordu.
→ Sahiplenmeden önce kuyruk atılıyor. Kullanıcı zaten tek satırlık özeti
  alıyor; detay konteynerin kendi Cloud Run logunda duruyor.

241 test geçiyor.
