"use client";

import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import { m } from "motion/react";
import { toast } from "sonner";
import { ScheduleSidebar } from "./schedule-sidebar";
import { ScheduleGrid } from "./schedule-grid";
import { api } from "@/lib/api";
import type { CourseInfo } from "@/lib/api";
import { COURSE_HUES } from "@/lib/course-colors";
import {
  scheduleKeyFor,
  scheduleExportKeyFor,
  LEGACY_SCHEDULE_SELECTED,
} from "@/lib/storage-keys";
import { UserDataService, UserDataKeys } from "@/lib/user-data-service";

// ── Constants ──

const DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"] as const;
const DAY_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum"] as const;

// Seçili dersleri sayfa yenilemede korumak için localStorage anahtarı.
// Anahtar kullanıcıya göre ayrılır: aynı tarayıcıda farklı hesapla giriş yapan
// kullanıcı öncekinin planını GÖRMEMELİ (gizlilik) ve ÜZERİNE YAZMAMALI (veri kaybı).
const SELECTED_STORAGE_KEY = LEGACY_SCHEDULE_SELECTED;

// ── Types ──

export interface SelectedCourse {
  course: CourseInfo;
  colorIndex: number;
}

/** Planın hem bulutta hem yerel önbellekte saklanan biçimi. */
interface StoredPlan {
  selected: SelectedCourse[];
  nextColorIdx: number;
}

interface DepartmentItem {
  bransKoduId: number;
  dersBransKodu: string;
}

// ── Helpers ──

function detectConflicts(courses: SelectedCourse[]): string[] {
  const conflicts: string[] = [];
  const allSessions = courses.flatMap((sc) =>
    sc.course.sessions.map((s) => ({
      crn: sc.course.crn,
      code: sc.course.course_code,
      ...s,
    })),
  );

  for (let i = 0; i < allSessions.length; i++) {
    for (let j = i + 1; j < allSessions.length; j++) {
      const a = allSessions[i];
      const b = allSessions[j];
      if (a.day !== b.day) continue;
      // Check time overlap
      const aStart = timeToMinutes(a.start_time);
      const aEnd = timeToMinutes(a.end_time);
      const bStart = timeToMinutes(b.start_time);
      const bEnd = timeToMinutes(b.end_time);
      if (aStart < bEnd && bStart < aEnd) {
        conflicts.push(`${a.code} ↔ ${b.code}`);
      }
    }
  }
  return [...new Set(conflicts)];
}

function timeToMinutes(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

// ── Component ──

export function ScheduleBuilder() {
  // Departments
  const [departments, setDepartments] = useState<DepartmentItem[]>([]);

  const [deptLoading, setDeptLoading] = useState(true);

  // Courses for selected dept


  // Selected courses (the user's schedule)
  const [selected, setSelected] = useState<SelectedCourse[]>([]);
  const [nextColorIdx, setNextColorIdx] = useState(0);

  // Modal


  // Router for export navigation
  const router = useRouter();

  // localStorage persist — seçili dersler sayfa yenilemede kaybolmasın.
  // Kullanıcı başına ayrı anahtar; hangi anahtarın geri yüklendiğini takip ederiz.
  const { user } = useUser();
  const userId = user?.id ?? null;
  const storageKey = userId ? scheduleKeyFor(userId) : null;
  const restoredForRef = useRef<string | null>(null);

  // ── Planın kalıcılığı: BULUT ÖNCE ──
  //
  // Plan eskiden yalnızca localStorage'daydı, yani her cihazda ayrı bir plan
  // oluşuyordu: telefondan giren kullanıcı bilgisayardaki planını göremiyordu.
  // Plan kullanıcıya ait bir veridir; cihazda değil kimlikte durmalı.
  //
  // localStorage tamamen kaldırılmadı ama rolü değişti: artık yalnızca bulut
  // okunamadığında gösterilecek çevrimdışı önbellek.
  const cloudOkRef = useRef(false);

  useEffect(() => {
    if (!userId || !storageKey) return;
    if (restoredForRef.current === storageKey) return;

    // Hesap değiştiyse önceki kullanıcının planını ekranda bırakma
    setSelected([]);
    setNextColorIdx(0);

    let iptal = false;

    // Tek seferlik göç: kullanıcıya bağlı olmayan eski küresel anahtarı kapat.
    // Sahibi olduğunu bildiğimiz durumda (son giriş yapan kullanıcı aynıysa)
    // taşı, aksi halde sil — başkasının planını devralmaktansa boş başlamak doğru.
    try {
      const legacy = localStorage.getItem(SELECTED_STORAGE_KEY);
      if (legacy) {
        const lastUser = localStorage.getItem("otostop-last-user");
        if (lastUser === userId && !localStorage.getItem(storageKey)) {
          localStorage.setItem(storageKey, legacy);
        }
        localStorage.removeItem(SELECTED_STORAGE_KEY);
      }
    } catch {
      /* localStorage kapalı — yoksay */
    }

    const yerelOku = (): StoredPlan | null => {
      try {
        const raw = localStorage.getItem(storageKey);
        return raw ? (JSON.parse(raw) as StoredPlan) : null;
      } catch {
        return null;
      }
    };

    const uygula = (plan: StoredPlan | null) => {
      if (!plan?.selected?.length) return;
      setSelected(plan.selected);
      setNextColorIdx(plan.nextColorIdx ?? plan.selected.length);
    };

    (async () => {
      const cloud = await UserDataService.get<StoredPlan>(UserDataKeys.schedule);
      if (iptal) return;

      if (cloud === undefined) {
        // Buluta ULAŞILAMADI (kayıt yok değil). Önbelleği göster ama buluta
        // yazma iznini KAPAT: yazsaydık geçici bir ağ hatasında bu cihazdaki
        // eski plan, buluttaki gerçek planın üzerine yazılırdı.
        uygula(yerelOku());
        cloudOkRef.current = false;
        restoredForRef.current = storageKey;
        return;
      }

      cloudOkRef.current = true;

      if (cloud?.selected?.length) {
        uygula(cloud);
        try {
          localStorage.setItem(storageKey, JSON.stringify(cloud));
        } catch {
          /* kota — yoksay */
        }
      } else {
        // Bulutta plan yok. Bu cihazda varsa bir defaya mahsus yukarı taşı.
        const yerel = yerelOku();
        if (yerel?.selected?.length) {
          uygula(yerel);
          await UserDataService.set(UserDataKeys.schedule, yerel);
        }
      }
      restoredForRef.current = storageKey;
    })();

    return () => {
      iptal = true;
    };
  }, [userId, storageKey]);

  // Değişimde kaydet — önce yerel önbellek, sonra bulut (yazma yoğunluğunu
  // azaltmak için gecikmeli). Geri yükleme tamamlanmadan yazılmaz; yoksa
  // başlangıçtaki boş state gerçek planı ezer.
  useEffect(() => {
    if (!storageKey) return;
    if (restoredForRef.current !== storageKey) return;

    const plan: StoredPlan = { selected, nextColorIdx };
    try {
      localStorage.setItem(storageKey, JSON.stringify(plan));
    } catch {
      /* kota dolu vs. — yoksay */
    }

    if (!cloudOkRef.current) return; // bulut okunamadı → üzerine yazma
    const t = setTimeout(() => {
      void UserDataService.set(UserDataKeys.schedule, plan);
    }, 800);
    return () => clearTimeout(t);
  }, [selected, nextColorIdx, storageKey]);

  // Kontenjan localStorage'da ANLIK GÖRÜNTÜ olarak duruyor; günler önceki sayıyı
  // güncelmiş gibi göstermek kayıt gününde yanıltıcı olur. Sayfa açılışında bir
  // kez tazelenir (backend'in 1 saatlik önbelleği sayesinde ucuz).
  const refreshedForRef = useRef<string | null>(null);
  useEffect(() => {
    if (!storageKey || restoredForRef.current !== storageKey) return;
    if (refreshedForRef.current === storageKey) return;
    if (selected.length === 0) return;
    refreshedForRef.current = storageKey;

    let cancelled = false;
    api
      .lookupCRNs(selected.map((s) => s.course.crn))
      .then((fresh) => {
        if (cancelled) return;
        setSelected((prev) =>
          prev.map((sc) => {
            const f = fresh[sc.course.crn];
            if (!f) return sc;
            return {
              ...sc,
              course: {
                ...sc.course,
                capacity: f.capacity,
                enrolled: f.enrolled,
              },
            };
          }),
        );
      })
      .catch(() => {
        /* tazeleme başarısızsa eldeki veriyle devam — sessiz, kritik değil */
      });
    return () => {
      cancelled = true;
    };
    // `selected` bilerek bağımlılıkta değil: efekt setSelected çağırıyor, eklemek
    // gereksiz yeniden render üretir. refreshedForRef tek seferlik çalışmayı garanti ediyor.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey, selected.length]);

  // Load departments on mount
  useEffect(() => {
    let cancelled = false;
    api
      .getDepartments()
      .then((data) => {
        if (!cancelled) setDepartments(data);
      })
      .catch(() => {
        if (!cancelled) toast.error("Ders alanı listesi yüklenemedi");
      })
      .finally(() => {
        if (!cancelled) setDeptLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Conflicts
  const conflicts = useMemo(() => detectConflicts(selected), [selected]);

  // Add course
  const addCourse = useCallback(
    (course: CourseInfo) => {
      // Check if CRN already selected
      if (selected.some((s) => s.course.crn === course.crn)) {
        toast.warning("Bu ders zaten ekli");
        return;
      }
      const newCourse: SelectedCourse = {
        course,
        colorIndex: nextColorIdx % COURSE_HUES.length,
      };
      setSelected((prev) => [...prev, newCourse]);
      setNextColorIdx((prev) => prev + 1);
      // Modal kapatma çağrısı kaldırıldı: arama sonuçları açık kalıyor,
      // böylece aynı dersin başka section'ı veya sıradaki ders arka arkaya eklenebiliyor.

      // Check for conflicts after adding
      const newConflicts = detectConflicts([...selected, newCourse]);
      if (newConflicts.length > 0) {
        toast.warning(`Çakışma tespit edildi: ${newConflicts.join(", ")}`);
      }
    },
    [selected, nextColorIdx],
  );

  // Remove course
  const removeCourse = useCallback((crn: string) => {
    setSelected((prev) => prev.filter((s) => s.course.crn !== crn));
  }, []);

  // Export schedule to registration engine
  const exportSchedule = useCallback(() => {
    if (selected.length === 0) {
      toast.warning("Aktarılacak ders yok");
      return;
    }
    if (!userId) {
      toast.error("Oturum bilgisi yüklenmedi, tekrar dene");
      return;
    }
    const crns = selected.map((s) => s.course.crn);
    // Aktarım anahtarı da kullanıcıya bağlı: başka hesap devralmasın
    localStorage.setItem(scheduleExportKeyFor(userId), JSON.stringify(crns));
    toast.success(`${crns.length} CRN kayıt motoruna aktarıldı`);
    router.push("/");
  }, [selected, router, userId]);

  return (
    /* Uygulama kabuğu: sayfa aşağı büyümek yerine ekran yüksekliğinde sabit
       kalır. Kenar çubuğu kendi içinde kayar, takvim kalan TÜM alanı doldurur.
       Mobilde bu kilit açılır ve normal belge akışına dönülür. */
    <div className="mx-auto max-w-[1600px] px-4 py-4 sm:px-6 lg:h-[calc(100vh-3.5rem)] lg:overflow-hidden">
      <m.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="flex h-full flex-col gap-4 lg:flex-row lg:gap-6"
      >
        {/* Kenar çubuğu — kendi kaydırmasıyla, sayfayı uzatmaz */}
        <div className="w-full shrink-0 lg:w-[400px] lg:min-h-0 lg:overflow-y-auto lg:pr-1">
          <ScheduleSidebar
            departments={departments}
            deptLoading={deptLoading}
            selectedCourses={selected}
            onRemoveCourse={removeCourse}
            onAddCourse={addCourse}
            conflicts={conflicts}
            onExport={exportSchedule}
          />
        </div>

        {/* Takvim — kalan genişliği VE yüksekliği doldurur */}
        <div className="min-h-0 min-w-0 flex-1 max-lg:h-[32rem]">
          <ScheduleGrid
            selectedCourses={selected}
            onRemoveCourse={removeCourse}
            conflicts={conflicts}
          />
        </div>
      </m.div>
    </div>
  );
}

export { DAYS, DAY_SHORT, COURSE_HUES };
