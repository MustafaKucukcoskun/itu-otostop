"use client";

import { useMemo } from "react";
import { m } from "motion/react";
import { Calendar } from "lucide-react";
import type { SelectedCourse } from "./schedule-builder";
import { DAY_SHORT } from "./schedule-builder";
import { courseBlockStyle } from "@/lib/course-colors";

// ── Constants ──

const MIN_HOUR = 8;
const MAX_HOUR = 19;
const TOTAL_HOURS = MAX_HOUR - MIN_HOUR;
const TOTAL_MIN = TOTAL_HOURS * 60;

// Izgara sabit 48px/saat ile ciziliyordu (toplam 528px) ve genis ekranda
// kucucuk kaliyordu. Artik yuzde ile konumlaniyor: kapsayici ne kadar
// yuksekse takvim o kadar buyuyor.
const pct = (minFromStart: number) => (minFromStart / TOTAL_MIN) * 100;

// ── Types ──

interface ScheduleGridProps {
  selectedCourses: SelectedCourse[];
  onRemoveCourse: (crn: string) => void;
  conflicts: string[];
}

interface GridBlock {
  crn: string;
  courseCode: string;
  instructor: string;
  day: number;
  startMin: number;
  endMin: number;
  room: string;
  building: string;
  colorIndex: number;
}

// ── Helpers ──

function timeToMinutes(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

// ── Component ──

export function ScheduleGrid({
  selectedCourses,
  onRemoveCourse,
}: ScheduleGridProps) {
  // Build grid blocks from selected courses
  const blocks = useMemo<GridBlock[]>(() => {
    return selectedCourses.flatMap((sc) =>
      sc.course.sessions.map((s) => ({
        crn: sc.course.crn,
        courseCode: sc.course.course_code,
        instructor: sc.course.instructor,
        day: s.day,
        startMin: timeToMinutes(s.start_time),
        endMin: timeToMinutes(s.end_time),
        room: s.room,
        building: s.building,
        colorIndex: sc.colorIndex,
      })),
    );
  }, [selectedCourses]);

  // Time labels
  const timeLabels = useMemo(() => {
    const labels: string[] = [];
    for (let h = MIN_HOUR; h < MAX_HOUR; h++) {
      labels.push(`${String(h).padStart(2, "0")}:00`);
    }
    return labels;
  }, []);

  return (
    <div className="flex h-full min-h-0 flex-col border border-border bg-card">
      {/* Header row: days */}
      <div className="grid grid-cols-[60px_repeat(5,1fr)] border-b border-border">
        <div className="border-r border-border p-2" />
        {DAY_SHORT.map((day) => (
          <div
            key={day}
            className="border-r border-border/50 p-2 text-center text-xs font-semibold text-muted-foreground last:border-r-0"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Grid body */}
      <div className="relative grid min-h-0 flex-1 grid-cols-[60px_repeat(5,1fr)]">
        {/* Time labels column */}
        <div className="flex flex-col border-r border-border">
          {timeLabels.map((label) => (
            <div
              key={label}
              className="flex flex-1 items-start justify-end pr-2 pt-0.5 font-mono text-[10px] text-muted-foreground/60"
            >
              {label}
            </div>
          ))}
        </div>

        {/* Day columns */}
        {Array.from({ length: 5 }, (_, dayIdx) => (
          <div
            key={dayIdx}
            className="relative border-r border-border/50 last:border-r-0"
          >
            {/* Hour grid lines */}
            {timeLabels.map((_, i) => (
              <div
                key={i}
                className="absolute left-0 right-0 border-t border-border/30"
                style={{ top: `${pct(i * 60)}%` }}
              />
            ))}

            {/* Course blocks for this day */}
            {blocks
              .filter((b) => b.day === dayIdx)
              .map((block) => {
                const durationMin = block.endMin - block.startMin;
                const topPct = pct(block.startMin - MIN_HOUR * 60);
                const heightPct = pct(durationMin);
                const color = courseBlockStyle(block.colorIndex);

                return (
                  <m.div
                    key={`${block.crn}-${block.day}-${block.startMin}`}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                    className="absolute inset-x-1 z-10 cursor-pointer overflow-hidden border transition-[filter] hover:brightness-110"
                    style={{
                      top: `${topPct}%`,
                      height: `${heightPct}%`,
                      minHeight: 28,
                      background: color.background,
                      borderColor: color.borderColor,
                      borderLeftWidth: 3,
                      borderLeftColor: color.accent,
                    }}
                    onClick={() => onRemoveCourse(block.crn)}
                    title={`${block.courseCode} — ${block.instructor}\nTıkla: kaldır`}
                  >
                    <div className="flex h-full flex-col justify-center px-2 py-1">
                      <span className="truncate text-[11px] font-bold leading-tight text-foreground">
                        {block.courseCode}
                      </span>
                      {durationMin >= 50 && (
                        <span className="mt-0.5 text-[9px] text-muted-foreground truncate">
                          {block.instructor.split(" ").slice(0, 2).join(" ")}
                        </span>
                      )}
                      {durationMin >= 80 && (
                        <span className="mt-0.5 text-[9px] font-mono text-muted-foreground/60 truncate">
                          {block.building} {block.room}
                        </span>
                      )}
                    </div>
                  </m.div>
                );
              })}
          </div>
        ))}

        {/* Empty state overlay */}
        {selectedCourses.length === 0 && (
          <div
            className="absolute inset-0 flex flex-col items-center justify-center"
            style={{ gridColumn: "2 / -1" }}
          >
            <Calendar className="size-10 text-muted-foreground/20 mb-3" />
            <p className="text-sm font-medium text-muted-foreground/40">
              Henüz ders eklenmedi
            </p>
            <p className="mt-1 text-xs text-muted-foreground/30">
              Soldaki panelden ders ekleyerek başla
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
