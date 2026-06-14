# Plan: Program-bazlı Ders Filtresi ("Bölümüm" akışı)

> **Durum:** ERTELENDİ — kullanıcı isteği: "bütün geliştirmeler bittikten sonra düşünelim."
> Mevcut akış (Ders Alanı → Ders → Section) korunur; bu, üstüne eklenecek opsiyonel katman.

## Fikir (kullanıcı önerisi)

Kullanıcı önce **kendi program/bölüm kodunu** girsin (ör. `BLG_LS` = Bilgisayar Müh. Lisans).
Sonra ders eklerken yalnızca **o programın alabileceği** dersleri / ders alanlarını görsün.
Akış: Bölümüm → (uygun ders alanları) → ders → section.

OBS'deki **"Dersi Alabilen Programlar"** sütununa dayanır (her dersin alınabileceği program kodları).

## Fizibilite: ✅ Veri zaten var

Backend `CourseInfo.programmes` alanını döndürüyor — bu tam olarak "Dersi Alabilen Programlar":
```
"programmes": "ARC_LS, BIO_LS, BIOE_LS, BLG_LS, BLGE_LS, CEN_LS, ..."
```
Yani bir ders programa uygun mu? → `programmes.includes(userProgram)`. Ek veri gerekmiyor.

## Zorluk: "tüm uygun dersleri" göstermek pahalı

Bir programın alabileceği TÜM dersleri göstermek = 175 ders alanındaki tüm dersleri tarayıp
`programmes` filtresi uygulamak. Her seferinde 175 OBS isteği makul değil.

### Seçenekler
1. **Backend index (önerilen):** `GET /api/program-courses/{program}` — tüm kataloğu (dönem
   boyunca statik) bir kez çekip program→dersler indeksi kurar, TTL cache'ler. İlk istek yavaş,
   sonrası anında. `obs_course_service.py`'ye eklenebilir (zaten LRU+TTL cache var).
2. **Lazy/hibrit (düşük efor):** Mevcut "Ders Alanı → Ders → Section" akışını koru; "Bölümüm"
   girilince section kartlarında **uygunluk rozeti** göster ("Programın alabilir ✓" / "uygun değil").
   Ders alanı listesinde programa uygun alanları üste al / işaretle.
3. **Tam yeniden tasarım:** Bölümüm → kategorize edilmiş uygun dersler (fotoğraftaki gibi tablo).
   En çok iş; kendi kategori sorgularımız gerekebilir.

## Önerilen yol

Faz olarak: önce **Seçenek 2** (hibrit, hızlı değer) — "Bölümüm" opsiyonel alanı + section'larda
uygunluk rozeti. Talep olursa **Seçenek 1** (backend index) ile "bana uygun tüm dersler" görünümü.

## Dokunulacak yerler
- `backend/obs_course_service.py` + `main.py` (Seçenek 1 için program-courses endpoint)
- `frontend/src/lib/api.ts` (CourseInfo.programmes zaten var; yeni endpoint tipi)
- `schedule-sidebar.tsx` ("Bölümüm" alanı), `course-selector-modal.tsx` (uygunluk rozeti)
- Bölüm kodu kullanıcı başına saklanabilir (Supabase user_configs'e `program` kolonu)
