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

  // Kullanıcı belli olunca (veya değişince) o kullanıcının planını geri yükle
  useEffect(() => {
    if (!userId || !storageKey) return;
    if (restoredForRef.current === storageKey) return;

    // Hesap değiştiyse önceki kullanıcının planını ekranda bırakma
    // eslint-disable-next-line react-hooks/set-state-in-effect -- kullanıcı değişiminde izolasyon
    setSelected([]);
    setNextColorIdx(0);

    try {
      // Tek seferlik göç: kullanıcıya bağlı olmayan eski küresel anahtarı kapat.
      // Sahibi olduğunu bildiğimiz durumda (son giriş yapan kullanıcı aynıysa) taşı,
      // aksi halde sil — başkasının planını devralmaktansa boş başlamak doğru.
      const legacy = localStorage.getItem(SELECTED_STORAGE_KEY);
      if (legacy) {
        const lastUser = localStorage.getItem("otostop-last-user");
        if (lastUser === userId && !localStorage.getItem(storageKey)) {
          localStorage.setItem(storageKey, legacy);
        }
        localStorage.removeItem(SELECTED_STORAGE_KEY);
      }

      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw) as {
          selected: SelectedCourse[];
          nextColorIdx: number;
        };
        if (parsed.selected?.length) {
          setSelected(parsed.selected);
          setNextColorIdx(parsed.nextColorIdx ?? parsed.selected.length);
        }
      }
    } catch {
      /* bozuk veri — yoksay */
    }
    restoredForRef.current = storageKey;
  }, [userId, storageKey]);

  // Persist on change (geri yükleme tamamlanmadan yazma — boş state ezmesin)
  useEffect(() => {
    if (!storageKey) return;
    if (restoredForRef.current !== storageKey) return;
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({ selected, nextColorIdx }),
      );
    } catch {
      /* kota dolu vs. — yoksay */
    }
  }, [selected, nextColorIdx, storageKey]);

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
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <m.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="flex flex-col gap-6 lg:flex-row"
      >
        {/* Sidebar — arama kutusu section detaylarını taşıdığı için biraz genişledi */}
        <div className="w-full shrink-0 lg:w-[400px]">
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

        {/* Grid */}
        <div className="min-w-0 flex-1">
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
