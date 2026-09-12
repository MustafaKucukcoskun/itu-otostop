"use client";

import { m } from "motion/react";
import { Trash2, AlertTriangle, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CourseSearch } from "./course-search";
import type { SelectedCourse } from "./schedule-builder";
import { COURSE_HUES, DAY_SHORT } from "./schedule-builder";
import type { CourseInfo } from "@/lib/api";

// ── Types ──

interface DepartmentItem {
  bransKoduId: number;
  dersBransKodu: string;
}

interface ScheduleSidebarProps {
  departments: DepartmentItem[];
  deptLoading: boolean;
  selectedCourses: SelectedCourse[];
  onRemoveCourse: (crn: string) => void;
  onAddCourse: (course: CourseInfo) => void;
  conflicts: string[];
  onExport: () => void;
}

// ── Component ──

export function ScheduleSidebar({
  departments,
  deptLoading,
  selectedCourses,
  onRemoveCourse,
  onAddCourse,
  conflicts,
  onExport,
}: ScheduleSidebarProps) {
  const selectedCRNs = new Set(selectedCourses.map((s) => s.course.crn));

  return (
    <div className="flex flex-col gap-4">
      {/* Tek arama kutusu — eski beş kademeli sihirbazın yerine */}
      <CourseSearch
        departments={departments}
        departmentsLoading={deptLoading}
        selectedCRNs={selectedCRNs}
        onAdd={onAddCourse}
      />

      {/* Seçili Dersler */}
      <div className="border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="panel-label">Seçili Dersler</p>
          <span className="font-mono text-[10px] text-muted-foreground">
            {selectedCourses.length} ders
          </span>
        </div>

        {selectedCourses.length === 0 ? (
          <p className="px-4 py-6 text-center text-xs text-muted-foreground/60">
            Yukarıdan ders ara ve ekle
          </p>
        ) : (
          <div>
            {selectedCourses.map((sc, i) => {
              const hue = COURSE_HUES[sc.colorIndex];
              return (
                <m.div
                  key={sc.course.crn}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                  className="flex items-start gap-3 border-t border-border px-4 py-3"
                >
                  <div
                    className="mt-1 size-2.5 shrink-0"
                    style={{ background: `oklch(0.72 0.14 ${hue})` }}
                  />

                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-xs font-semibold">
                        {sc.course.course_code}
                      </span>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        CRN {sc.course.crn}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {sc.course.instructor}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {sc.course.sessions.map((s, si) => (
                        <Badge
                          key={si}
                          variant="outline"
                          className="px-1.5 py-0 font-mono text-[10px]"
                        >
                          {DAY_SHORT[s.day]} {s.start_time}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Kaldır — her zaman görünür (hover'da belirmesi dokunmatikte bulunamıyordu) */}
                  <button
                    onClick={() => onRemoveCourse(sc.course.crn)}
                    className="shrink-0 p-1 text-muted-foreground/50 transition-colors hover:text-destructive"
                    aria-label={`${sc.course.course_code} dersini kaldır`}
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </m.div>
              );
            })}
          </div>
        )}
      </div>

      {/* Çakışma uyarısı */}
      {conflicts.length > 0 && (
        <m.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="border border-destructive/40 bg-destructive/5 p-3"
        >
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="size-4 shrink-0" />
            <span className="text-sm font-medium">Çakışma var</span>
          </div>
          <ul className="mt-1.5 space-y-0.5">
            {conflicts.map((c) => (
              <li key={c} className="font-mono text-xs text-destructive/80">
                {c}
              </li>
            ))}
          </ul>
        </m.div>
      )}

      {/* Aktarım */}
      {selectedCourses.length > 0 && (
        <div className="border border-border bg-card p-4">
          <p className="font-mono text-[11px] text-muted-foreground">
            {selectedCourses.length} ders · {conflicts.length} çakışma
          </p>
          <Button onClick={onExport} className="mt-3 w-full gap-2" size="lg">
            <ArrowRight className="size-4" />
            Planı Kayıt Motoruna Aktar
          </Button>
        </div>
      )}
    </div>
  );
}
