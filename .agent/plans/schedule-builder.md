# Schedule Builder — Implementation Plan

> **Durum (2026-06-13):** 10 maddeden 9'u kodlandı (commit edilmedi). Kalan: `schedule-service.ts` (madde 9)
> ve doğrulama planındaki manuel testler. Güncel görev listesi: `../ROADMAP.md` → Faz 2.

## Genel Bakış

Ders planı oluşturma sayfası: kullanıcı bölüm seçer, ders ekler (kod → ders → section),
haftalık grid'de görselleştirir, hazır planı kayıt motoruna aktarır.

---

## Proposed Changes

### Navigation (Site Geneli)

#### [NEW] `frontend/src/components/app-navbar.tsx`

Paylaşılan navbar: logo + tab navigation (Ders Planı / Kayıt Motoru) + theme toggle + user menu.
Mevcut dashboard header'ı bununla değiştirilecek (site-wide update'de).

#### [MODIFY] `frontend/src/app/layout.tsx`

- Inter fontu → Geist Sans + Geist Mono
- Navbar'ı layout'a taşı (tüm sayfalarda görünsün)

---

### Schedule Page

#### [NEW] `frontend/src/app/schedule/page.tsx`

Ana sayfa route — schedule builder'ı render eder.

#### [NEW] `frontend/src/components/schedule-builder.tsx`

Ana container: sidebar + weekly grid layout. State yönetimi:

- `selectedDepartment` — bölüm ID
- `selectedCourses` — Map<CRN, CourseInfo> (seçili dersler)
- `courseColors` — Map<courseCode, colorIndex>

#### [NEW] `frontend/src/components/schedule-sidebar.tsx`

Sol panel:

- Bölüm seçimi (combobox)
- Seçili dersler listesi (chip + silme)
- "+ Ders Ekle" butonu → modal açar
- "Planı Kayıt Motoruna Aktar" CTA

#### [NEW] `frontend/src/components/course-selector-modal.tsx`

3 adımlı modal (sheet):

1. Ders kodu seçimi — Command palette (searchable grid)
2. Ders seçimi — filtered list (ad + kredi + dil)
3. Section seçimi — rich radio cards (hoca + gün + saat + yer + kontenjan)

#### [MODIFY] `frontend/src/components/weekly-schedule.tsx`

Mevcut bileşen güncelleme:

- Edit mode: tıklayarak ders silme
- Renk sistemi: DESIGN_SYSTEM'deki 8 oklch tone
- Empty state: "Henüz ders eklenmedi" placeholder
- Responsive: horizontal scroll on mobile

---

### API Layer

#### [MODIFY] `frontend/src/lib/api.ts`

Yeni tipler ve fonksiyonlar:

```ts
// Bölüme ait tüm dersler (mevcut endpoint, yeni tip)
type DepartmentCourse = CourseInfo & { sessions: CourseSession[] };
api.getCourses(bransKoduId: number) → DepartmentCourse[]
```

#### Backend — DEĞİŞİKLİK GEREKMİYOR

Tüm endpoint'ler zaten mevcut:

- `GET /api/departments`
- `GET /api/courses/{id}`
- `GET /api/crn-lookup/{crn}`

---

### Data Persistence

#### [NEW] `frontend/src/lib/schedule-service.ts`

Seçilen ders planını Supabase'e kaydet (cloud sync):

- `saveSchedule(userId, selectedCRNs)`
- `getSchedule(userId)`

Alternatif: localStorage (daha basit) + "Kayıt Motoruna Aktar" butonu CRN'leri push eder.

---

## File Checklist

| #   | Dosya                       | Tip    | Öncelik              |
| --- | --------------------------- | ------ | -------------------- |
| 1   | `layout.tsx`                | MODIFY | High (font)          |
| 2   | `app-navbar.tsx`            | NEW    | High                 |
| 3   | `schedule/page.tsx`         | NEW    | High                 |
| 4   | `schedule-builder.tsx`      | NEW    | High                 |
| 5   | `schedule-sidebar.tsx`      | NEW    | High                 |
| 6   | `course-selector-modal.tsx` | NEW    | High                 |
| 7   | `weekly-schedule.tsx`       | MODIFY | Medium               |
| 8   | `api.ts`                    | MODIFY | Medium               |
| 9   | `schedule-service.ts`       | NEW    | Low                  |
| 10  | `globals.css`               | MODIFY | High (colors, fonts) |

---

## Verification Plan

### Automated

- `npx next build` — sıfır hata

### Manual

1. `/schedule` sayfası açılır, bölüm seçilir
2. Ders ekle → 3 adımlı modal çalışır
3. Section seçilir → grid'e doğru gün/saate yerleşir
4. Çakışma senaryosu → uyarı gösterilir
5. "Planı Aktar" → dashboard'da CRN'ler görünür
6. Mobile responsive test (Chrome DevTools)
7. Light/dark tema kontrolü
