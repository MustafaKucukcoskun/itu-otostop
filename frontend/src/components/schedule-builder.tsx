"use client";

import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { m, AnimatePresence } from "motion/react";
import { toast } from "sonner";
import { ScheduleSidebar } from "./schedule-sidebar";
import { CourseSelectorModal } from "./course-selector-modal";
import { ScheduleGrid } from "./schedule-grid";
import { api } from "@/lib/api";
import type { CourseInfo } from "@/lib/api";

// ── Constants ──

const DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"] as const;
const DAY_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum"] as const;

const COURSE_HUES = [250, 185, 35, 350, 145, 65, 290, 210] as const;

// Seçili dersleri sayfa yenilemede korumak için localStorage anahtarı
const SELECTED_STORAGE_KEY = "otostop-schedule-selected";

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
  const [selectedDept, setSelectedDept] = useState<DepartmentItem | null>(null);
  const [deptLoading, setDeptLoading] = useState(true);

  // Courses for selected dept
  const [deptCourses, setDeptCourses] = useState<CourseInfo[]>([]);
  const [coursesLoading, setCoursesLoading] = useState(false);

  // Selected courses (the user's schedule)
  const [selected, setSelected] = useState<SelectedCourse[]>([]);
  const [nextColorIdx, setNextColorIdx] = useState(0);

  // Modal
  const [modalOpen, setModalOpen] = useState(false);

  // Router for export navigation
  const router = useRouter();

  // localStorage persist — seçili dersler sayfa yenilemede kaybolmasın
  const restoredRef = useRef(false);

  // Restore on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(SELECTED_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as {
          selected: SelectedCourse[];
          nextColorIdx: number;
        };
        if (parsed.selected?.length) {
          // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time localStorage hidratasyonu
          setSelected(parsed.selected);
          setNextColorIdx(parsed.nextColorIdx ?? parsed.selected.length);
        }
      }
    } catch {
      /* bozuk veri — yoksay */
    }
    restoredRef.current = true;
  }, []);

  // Persist on change (restore tamamlanmadan yazma — boş state ezmesin)
  useEffect(() => {
    if (!restoredRef.current) return;
    try {
      localStorage.setItem(
        SELECTED_STORAGE_KEY,
        JSON.stringify({ selected, nextColorIdx }),
      );
    } catch {
      /* kota dolu vs. — yoksay */
    }
  }, [selected, nextColorIdx]);

  // Department change handler — resets courses before setting dept
  const handleDeptChange = useCallback((dept: DepartmentItem | null) => {
    setDeptCourses([]);
    setCoursesLoading(!!dept);
    setSelectedDept(dept);
  }, []);

  // Load departments on mount
  useEffect(() => {
    let cancelled = false;
    api
      .getDepartments()
      .then((data) => {
        if (!cancelled) setDepartments(data);
      })
      .catch(() => {
        if (!cancelled) toast.error("Bölüm listesi yüklenemedi");
      })
      .finally(() => {
        if (!cancelled) setDeptLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Load courses when department changes
  useEffect(() => {
    if (!selectedDept) return;
    let cancelled = false;
    api
      .getCourses(selectedDept.bransKoduId)
      .then((data) => {
        if (!cancelled) setDeptCourses(data);
      })
      .catch(() => {
        if (!cancelled) toast.error("Dersler yüklenemedi");
      })
      .finally(() => {
        if (!cancelled) setCoursesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedDept]);

  // Grouped courses: course_code prefix → unique course names
  const groupedCourses = useMemo(() => {
    const map = new Map<string, CourseInfo[]>();
    for (const c of deptCourses) {
      const prefix = c.course_code.replace(/\s*\d.*$/, "").trim();
      const arr = map.get(prefix) ?? [];
      arr.push(c);
      map.set(prefix, arr);
    }
    return map;
  }, [deptCourses]);

  // Unique course codes (e.g., "BLG 212E") with first matching CourseInfo
  const uniqueCourses = useMemo(() => {
    const seen = new Map<string, CourseInfo>();
    for (const c of deptCourses) {
      if (!seen.has(c.course_code)) {
        seen.set(c.course_code, c);
      }
    }
    return seen;
  }, [deptCourses]);

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
      setModalOpen(false);

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
    const crns = selected.map((s) => s.course.crn);
    localStorage.setItem("otostop-schedule-export", JSON.stringify(crns));
    toast.success(`${crns.length} CRN kayıt motoruna aktarıldı`);
    router.push("/");
  }, [selected, router]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <m.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="flex flex-col gap-6 lg:flex-row"
      >
        {/* Sidebar */}
        <div className="w-full shrink-0 lg:w-[340px]">
          <ScheduleSidebar
            departments={departments}
            selectedDept={selectedDept}
            onDeptChange={handleDeptChange}
            deptLoading={deptLoading}
            selectedCourses={selected}
            onRemoveCourse={removeCourse}
            onAddCourse={() => setModalOpen(true)}
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

      {/* Course Selector Modal */}
      <AnimatePresence>
        {modalOpen && (
          <CourseSelectorModal
            open={modalOpen}
            onClose={() => setModalOpen(false)}
            deptCourses={deptCourses}
            groupedCourses={groupedCourses}
            uniqueCourses={uniqueCourses}
            coursesLoading={coursesLoading}
            selectedDept={selectedDept}
            onSelectCourse={addCourse}
            selectedCRNs={new Set(selected.map((s) => s.course.crn))}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

export { DAYS, DAY_SHORT, COURSE_HUES };
