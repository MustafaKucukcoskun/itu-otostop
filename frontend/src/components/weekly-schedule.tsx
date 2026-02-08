"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Calendar,
  AlertTriangle,
  ChevronDown,
  Users,
  MapPin,
  GraduationCap,
  Loader2,
} from "lucide-react";
import type { CourseInfo } from "@/lib/api";

// ── Constants ──

const DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum"] as const;
const DAYS_FULL = [
  "Pazartesi",
  "Salı",
  "Çarşamba",
  "Perşembe",
  "Cuma",
] as const;
const SLOT_HEIGHT = 40; // px per 30-min slot
const DEFAULT_MIN_HOUR = 8;
const DEFAULT_MAX_HOUR = 18;

// oklch color palette — works on both light/dark
const COURSE_COLORS = [
  {
    bg: "oklch(0.55 0.18 250 / 0.2)",
    border: "oklch(0.65 0.22 250)",
    text: "oklch(0.82 0.08 250)",
  },
  {
    bg: "oklch(0.55 0.18 165 / 0.2)",
    border: "oklch(0.65 0.22 165)",
    text: "oklch(0.82 0.08 165)",
  },
  {
    bg: "oklch(0.55 0.18 30 / 0.2)",
    border: "oklch(0.65 0.22 30)",
    text: "oklch(0.82 0.08 30)",
  },
  {
    bg: "oklch(0.55 0.18 320 / 0.2)",
    border: "oklch(0.65 0.22 320)",
    text: "oklch(0.82 0.08 320)",
  },
  {
    bg: "oklch(0.55 0.18 140 / 0.2)",
    border: "oklch(0.65 0.22 140)",
    text: "oklch(0.82 0.08 140)",
  },
  {
    bg: "oklch(0.55 0.18 80 / 0.2)",
    border: "oklch(0.65 0.22 80)",
    text: "oklch(0.82 0.08 80)",
  },
  {
    bg: "oklch(0.55 0.18 280 / 0.2)",
    border: "oklch(0.65 0.22 280)",
    text: "oklch(0.82 0.08 280)",
  },
  {
    bg: "oklch(0.55 0.18 200 / 0.2)",
    border: "oklch(0.65 0.22 200)",
    text: "oklch(0.82 0.08 200)",
  },
];

// ── Helpers ──

function timeToMinutes(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return h * 60 + (m || 0);
}

function minutesToTime(min: number): string {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
}

// ── Types ──

interface ScheduleBlock {
  crn: string;
  courseCode: string;
  courseName: string;
  instructor: string;
  room: string;
  building: string;
  day: number;
  startMin: number;
  endMin: number;
  colorIdx: number;
  capacity: number;
  enrolled: number;
}

interface WeeklyScheduleProps {
  courses: Record<string, CourseInfo>;
  crnList: string[];
  loading?: boolean;
}

export function WeeklySchedule({
  courses,
  crnList,
  loading,
}: WeeklyScheduleProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [hoveredBlock, setHoveredBlock] = useState<string | null>(null);

  // Build schedule data
  const { blocks, timeRange, conflicts, colorMap } = useMemo(() => {
    const colorMap: Record<string, number> = {};
    let colorIdx = 0;
    const blocks: ScheduleBlock[] = [];

    for (const crn of crnList) {
      const course = courses[crn];
      if (!course?.sessions?.length) continue;

      const codeKey = course.course_code;
      if (!(codeKey in colorMap)) {
        colorMap[codeKey] = colorIdx % COURSE_COLORS.length;
        colorIdx++;
      }

      for (const session of course.sessions) {
        blocks.push({
          crn,
          courseCode: course.course_code,
          courseName: course.course_name,
          instructor: course.instructor,
          room: session.room,
          building: session.building,
          day: session.day,
          startMin: timeToMinutes(session.start_time),
          endMin: timeToMinutes(session.end_time),
          colorIdx: colorMap[codeKey],
          capacity: course.capacity,
          enrolled: course.enrolled,
        });
      }
    }

    // Compute time range
    let minMin = DEFAULT_MIN_HOUR * 60;
    let maxMin = DEFAULT_MAX_HOUR * 60;
    if (blocks.length > 0) {
      minMin = Math.min(...blocks.map((b) => b.startMin));
      maxMin = Math.max(...blocks.map((b) => b.endMin));
      minMin = Math.floor(minMin / 60) * 60;
      maxMin = Math.ceil(maxMin / 60) * 60;
      if (maxMin - minMin < 4 * 60) maxMin = minMin + 4 * 60;
    }

    // Detect conflicts (overlapping blocks on same day)
    const conflicts = new Set<number>();
    for (let i = 0; i < blocks.length; i++) {
      for (let j = i + 1; j < blocks.length; j++) {
        if (
          blocks[i].day === blocks[j].day &&
          blocks[i].startMin < blocks[j].endMin &&
          blocks[j].startMin < blocks[i].endMin
        ) {
          conflicts.add(i);
          conflicts.add(j);
        }
      }
    }

    return {
      blocks,
      timeRange: { min: minMin, max: maxMin },
      conflicts,
      colorMap,
    };
  }, [courses, crnList]);

  // Time slots
  const timeSlots = useMemo(() => {
    const slots: number[] = [];
    for (let m = timeRange.min; m < timeRange.max; m += 30) {
      slots.push(m);
    }
    return slots;
  }, [timeRange]);

  const totalHeight = timeSlots.length * SLOT_HEIGHT;
  const activeCRNs = crnList.filter((crn) => courses[crn]?.sessions?.length);

  // Empty state
  if (activeCRNs.length === 0 && !loading) {
    return (
      <div className="overflow-hidden">
        <div className="px-5 py-4 flex items-center gap-2 text-muted-foreground">
          <Calendar className="h-4 w-4" />
          <span className="text-xs font-medium">Haftalık Program</span>
        </div>
        <div className="px-5 pb-6 text-center text-sm text-muted-foreground/50 py-8">
          <GraduationCap className="h-8 w-8 mx-auto mb-2 opacity-30" />
          CRN eklendikçe haftalık ders programınız burada görünecek
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full px-5 py-3 flex items-center justify-between hover:bg-muted/20 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-primary" />
          <span className="text-xs font-semibold">Haftalık Program</span>
          {activeCRNs.length > 0 && (
            <span className="text-[10px] text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded-full">
              {activeCRNs.length} ders
            </span>
          )}
          {loading && (
            <Loader2 className="h-3 w-3 text-muted-foreground animate-spin" />
          )}
          {conflicts.size > 0 && (
            <span className="flex items-center gap-1 text-[10px] text-red-400 font-medium">
              <AlertTriangle className="h-3 w-3" />
              çakışma
            </span>
          )}
        </div>
        <ChevronDown
          className={`h-4 w-4 text-muted-foreground transition-transform ${collapsed ? "-rotate-90" : ""}`}
        />
      </button>

      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            {/* Schedule Grid */}
            <div className="px-2 sm:px-3 pb-2 overflow-x-auto">
              <div
                className="grid min-w-[560px]"
                style={{
                  gridTemplateColumns: "44px repeat(5, minmax(0, 1fr))",
                }}
              >
                {/* Header row */}
                <div className="h-7" />
                {DAYS.map((day, i) => (
                  <div
                    key={day}
                    className="h-7 flex items-center justify-center text-[10px] font-bold text-muted-foreground/60 uppercase tracking-wider"
                    title={DAYS_FULL[i]}
                  >
                    {day}
                  </div>
                ))}

                {/* Time column */}
                <div className="relative" style={{ height: totalHeight }}>
                  {timeSlots.map((min, i) => (
                    <div
                      key={min}
                      className="absolute w-full text-right pr-1.5 text-[8px] text-muted-foreground/30 font-mono leading-none"
                      style={{ top: i * SLOT_HEIGHT - 3 }}
                    >
                      {min % 60 === 0 ? minutesToTime(min) : ""}
                    </div>
                  ))}
                </div>

                {/* Day columns */}
                {[0, 1, 2, 3, 4].map((dayIdx) => (
                  <div
                    key={dayIdx}
                    className="relative border-l border-border/10"
                    style={{ height: totalHeight }}
                  >
                    {/* Grid lines */}
                    {timeSlots.map((min, i) => (
                      <div
                        key={min}
                        className={`absolute w-full ${
                          min % 60 === 0
                            ? "border-t border-border/15"
                            : "border-t border-border/5"
                        }`}
                        style={{ top: i * SLOT_HEIGHT }}
                      />
                    ))}

                    {/* Course blocks */}
                    {blocks
                      .map((block, globalIdx) => ({ block, globalIdx }))
                      .filter(({ block }) => block.day === dayIdx)
                      .map(({ block, globalIdx }) => {
                        const top =
                          ((block.startMin - timeRange.min) / 30) * SLOT_HEIGHT;
                        const height =
                          ((block.endMin - block.startMin) / 30) * SLOT_HEIGHT;
                        const color = COURSE_COLORS[block.colorIdx];
                        const isConflict = conflicts.has(globalIdx);
                        const isCompact = height < 60;
                        const isTiny = height < 40;
                        const isHovered = hoveredBlock === block.courseCode;

                        return (
                          <motion.div
                            key={`${block.crn}-${dayIdx}-${block.startMin}`}
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{
                              opacity: 1,
                              scale: isHovered ? 1.02 : 1,
                              zIndex: isHovered ? 10 : 1,
                            }}
                            className={`absolute left-0.5 right-0.5 rounded-lg overflow-hidden cursor-default transition-shadow ${
                              isConflict
                                ? "ring-1 ring-red-400/60 shadow-[0_0_8px_-2px_rgba(248,113,113,0.3)]"
                                : ""
                            } ${isHovered ? "shadow-lg" : ""}`}
                            style={{
                              top: top + 1,
                              height: Math.max(height - 2, 16),
                              backgroundColor: color.bg,
                              borderLeft: `3px solid ${color.border}`,
                              backdropFilter: "blur(8px)",
                            }}
                            onMouseEnter={() =>
                              setHoveredBlock(block.courseCode)
                            }
                            onMouseLeave={() => setHoveredBlock(null)}
                            title={[
                              `${block.courseCode} — ${block.courseName}`,
                              block.instructor,
                              block.room !== "--" ? `Salon: ${block.room}` : "",
                              `${minutesToTime(block.startMin)}–${minutesToTime(block.endMin)}`,
                              `${block.enrolled}/${block.capacity} kişi`,
                            ]
                              .filter(Boolean)
                              .join("\n")}
                          >
                            <div className="p-1 h-full flex flex-col justify-center overflow-hidden">
                              <p
                                className="text-[9px] sm:text-[10px] font-bold leading-tight truncate"
                                style={{ color: color.text }}
                              >
                                {block.courseCode}
                              </p>
                              {!isTiny && (
                                <p className="text-[7px] sm:text-[8px] text-muted-foreground truncate leading-tight mt-px">
                                  {block.instructor}
                                </p>
                              )}
                              {!isCompact && block.room !== "--" && (
                                <p className="text-[7px] text-muted-foreground/50 truncate leading-tight flex items-center gap-0.5">
                                  <MapPin
                                    className="h-2 w-2 inline shrink-0"
                                    style={{ color: color.border }}
                                  />
                                  {block.room}
                                </p>
                              )}
                            </div>
                            {isConflict && (
                              <div className="absolute top-0.5 right-0.5">
                                <AlertTriangle className="h-2.5 w-2.5 text-red-400" />
                              </div>
                            )}
                          </motion.div>
                        );
                      })}
                  </div>
                ))}
              </div>
            </div>

            {/* Course legend */}
            {Object.keys(colorMap).length > 0 && (
              <div className="px-3 pb-3 flex flex-wrap gap-1.5">
                {Object.entries(colorMap).map(([code, idx]) => {
                  const color = COURSE_COLORS[idx];
                  const course = Object.values(courses).find(
                    (c) => c.course_code === code,
                  );
                  return (
                    <div
                      key={code}
                      className="flex items-center gap-1.5 text-[9px] rounded-md px-2 py-1 transition-colors cursor-default"
                      style={{ backgroundColor: color.bg }}
                      onMouseEnter={() => setHoveredBlock(code)}
                      onMouseLeave={() => setHoveredBlock(null)}
                    >
                      <div
                        className="h-2 w-2 rounded-sm shrink-0"
                        style={{ backgroundColor: color.border }}
                      />
                      <span className="font-bold" style={{ color: color.text }}>
                        {code}
                      </span>
                      {course && (
                        <span className="text-muted-foreground hidden sm:inline max-w-24 truncate">
                          {course.course_name}
                        </span>
                      )}
                      {course && (
                        <span className="flex items-center gap-0.5 text-muted-foreground/50">
                          <Users className="h-2.5 w-2.5" />
                          {course.enrolled}/{course.capacity}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
