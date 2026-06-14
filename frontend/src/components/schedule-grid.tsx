"use client";

import { useMemo } from "react";
import { m } from "motion/react";
import { Calendar } from "lucide-react";
import type { SelectedCourse } from "./schedule-builder";
import { COURSE_HUES, DAY_SHORT } from "./schedule-builder";

// ── Constants ──

const MIN_HOUR = 8;
const MAX_HOUR = 19;
const SLOT_HEIGHT = 48; // px per hour
const TOTAL_HOURS = MAX_HOUR - MIN_HOUR;

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
  hue: number;
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
        hue: COURSE_HUES[sc.colorIndex],
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

  const gridHeight = TOTAL_HOURS * SLOT_HEIGHT;

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
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
      <div className="relative grid grid-cols-[60px_repeat(5,1fr)]">
        {/* Time labels column */}
        <div className="border-r border-border" style={{ height: gridHeight }}>
          {timeLabels.map((label) => (
            <div
              key={label}
              className="flex items-start justify-end pr-2 text-[10px] font-mono text-muted-foreground/60"
              style={{
                height: SLOT_HEIGHT,
                paddingTop: 2,
              }}
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
            style={{ height: gridHeight }}
          >
            {/* Hour grid lines */}
            {timeLabels.map((_, i) => (
              <div
                key={i}
                className="absolute left-0 right-0 border-t border-border/30"
                style={{ top: i * SLOT_HEIGHT }}
              />
            ))}

            {/* Course blocks for this day */}
            {blocks
              .filter((b) => b.day === dayIdx)
              .map((block) => {
                const topPx =
                  ((block.startMin - MIN_HOUR * 60) / 60) * SLOT_HEIGHT;
                const heightPx =
                  ((block.endMin - block.startMin) / 60) * SLOT_HEIGHT;

                return (
                  <m.div
                    key={`${block.crn}-${block.day}-${block.startMin}`}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                    className="absolute inset-x-1 z-10 cursor-pointer overflow-hidden border transition-colors hover:brightness-110"
                    style={{
                      top: topPx,
                      height: Math.max(heightPx, 28),
                      background: `oklch(0.72 0.14 ${block.hue} / 0.15)`,
                      borderColor: `oklch(0.72 0.16 ${block.hue} / 0.4)`,
                      borderLeftWidth: 3,
                      borderLeftColor: `oklch(0.72 0.18 ${block.hue})`,
                    }}
                    onClick={() => onRemoveCourse(block.crn)}
                    title={`${block.courseCode} — ${block.instructor}\nTıkla: kaldır`}
                  >
                    <div className="flex h-full flex-col justify-center px-2 py-1">
                      <span
                        className="text-[11px] font-bold leading-tight truncate"
                        style={{ color: `oklch(0.85 0.08 ${block.hue})` }}
                      >
                        {block.courseCode}
                      </span>
                      {heightPx > 40 && (
                        <span className="mt-0.5 text-[9px] text-muted-foreground truncate">
                          {block.instructor.split(" ").slice(0, 2).join(" ")}
                        </span>
                      )}
                      {heightPx > 56 && (
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
