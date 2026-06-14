"use client";

import { useState, useMemo } from "react";
import { m, AnimatePresence } from "motion/react";
import {
  ArrowLeft,
  Search,
  Clock,
  MapPin,
  Users,
  Loader2,
  X,
  Plus,
  Check,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { CourseInfo } from "@/lib/api";
import { DAY_SHORT } from "./schedule-builder";

// ── Types ──

interface CourseSelectorModalProps {
  open: boolean;
  onClose: () => void;
  deptCourses: CourseInfo[];
  groupedCourses: Map<string, CourseInfo[]>;
  uniqueCourses: Map<string, CourseInfo>;
  coursesLoading: boolean;
  selectedDept: { bransKoduId: number; dersBransKodu: string } | null;
  onSelectCourse: (course: CourseInfo) => void;
  selectedCRNs: Set<string>;
}

type Step = "code" | "course" | "section";

// ── Helpers ──

const CAPACITY_THRESHOLD_MED = 0.7;
const CAPACITY_THRESHOLD_HIGH = 0.9;

function capacityColor(enrolled: number, capacity: number): string {
  if (capacity === 0) return "text-muted-foreground";
  const ratio = enrolled / capacity;
  if (ratio >= CAPACITY_THRESHOLD_HIGH) return "text-status-err";
  if (ratio >= CAPACITY_THRESHOLD_MED) return "text-status-wait";
  return "text-status-ok";
}

function capacityPercent(enrolled: number, capacity: number): number {
  if (capacity === 0) return 0;
  return Math.min(100, Math.round((enrolled / capacity) * 100));
}

// ── Component ──

export function CourseSelectorModal({
  open,
  onClose,
  deptCourses,
  groupedCourses,
  uniqueCourses,
  coursesLoading,
  selectedDept,
  onSelectCourse,
  selectedCRNs,
}: CourseSelectorModalProps) {
  const [step, setStep] = useState<Step>("code");
  const [selectedCodePrefix, setSelectedCodePrefix] = useState("");
  const [selectedCourseCode, setSelectedCourseCode] = useState("");
  const [search, setSearch] = useState("");

  // Reset on close
  const handleClose = () => {
    setStep("code");
    setSelectedCodePrefix("");
    setSelectedCourseCode("");
    setSearch("");
    onClose();
  };

  // Step 1: Course code prefixes (e.g., BLG, MAT, FIZ)
  const codePrefixes = useMemo(() => {
    return [...groupedCourses.keys()].sort();
  }, [groupedCourses]);

  const filteredPrefixes = useMemo(() => {
    if (!search) return codePrefixes;
    const q = search.toLowerCase();
    return codePrefixes.filter((p) => p.toLowerCase().includes(q));
  }, [codePrefixes, search]);

  // Step 2: Courses under selected prefix
  const coursesForPrefix = useMemo(() => {
    if (!selectedCodePrefix) return [];
    // Group by course_code to get unique courses
    const map = new Map<string, CourseInfo>();
    const courses = groupedCourses.get(selectedCodePrefix) ?? [];
    for (const c of courses) {
      if (!map.has(c.course_code)) {
        map.set(c.course_code, c);
      }
    }
    return [...map.values()];
  }, [selectedCodePrefix, groupedCourses]);

  const filteredCourses = useMemo(() => {
    if (!search) return coursesForPrefix;
    const q = search.toLowerCase();
    return coursesForPrefix.filter(
      (c) =>
        c.course_code.toLowerCase().includes(q) ||
        c.course_name.toLowerCase().includes(q),
    );
  }, [coursesForPrefix, search]);

  // Step 3: Sections (all CRNs) for selected course code
  const sectionsForCourse = useMemo(() => {
    return deptCourses.filter((c) => c.course_code === selectedCourseCode);
  }, [selectedCourseCode, deptCourses]);

  // Navigate
  const goToStep = (s: Step) => {
    setSearch("");
    setStep(s);
  };

  const selectPrefix = (prefix: string) => {
    setSelectedCodePrefix(prefix);
    goToStep("course");
  };

  const selectCourse = (courseCode: string) => {
    setSelectedCourseCode(courseCode);
    goToStep("section");
  };

  const goBack = () => {
    if (step === "section") goToStep("course");
    else if (step === "course") goToStep("code");
  };

  // Title
  const title =
    step === "code"
      ? "Ders Kodu Seç"
      : step === "course"
        ? selectedCodePrefix
        : selectedCourseCode;

  const subtitle =
    step === "code"
      ? (selectedDept?.dersBransKodu ?? "")
      : step === "course"
        ? "Ders Seç"
        : (uniqueCourses.get(selectedCourseCode)?.course_name ?? "Section Seç");

  return (
    <Sheet open={open} onOpenChange={handleClose}>
      <SheetContent
        side="right"
        showCloseButton={false}
        className="flex w-full flex-col gap-0 border-l border-border p-0 sm:max-w-lg"
      >
        <SheetHeader className="border-b border-border px-5 py-4">
          <div className="flex items-center gap-3">
            {step !== "code" && (
              <button
                onClick={goBack}
                className="rounded-lg p-1.5 text-muted-foreground transition-colors
                           hover:bg-muted hover:text-foreground"
              >
                <ArrowLeft className="size-4" />
              </button>
            )}
            <div className="min-w-0 flex-1">
              <SheetTitle className="text-base font-semibold">
                {title}
              </SheetTitle>
              {subtitle && (
                <p className="mt-0.5 text-xs text-muted-foreground truncate">
                  {subtitle}
                </p>
              )}
            </div>
            <button
              onClick={handleClose}
              className="rounded-lg p-1.5 text-muted-foreground transition-colors
                         hover:bg-muted hover:text-foreground"
              aria-label="Kapat"
            >
              <X className="size-4" />
            </button>
          </div>

          {/* Breadcrumb: ders alanı › ders › section (3 katman ayrı) */}
          <div className="mt-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            <span className={step === "code" ? "text-primary" : ""}>
              {selectedDept?.dersBransKodu ?? "Alan"}
            </span>
            {(step === "course" || step === "section") && selectedCodePrefix && (
              <>
                <span className="text-muted-foreground/40">›</span>
                <span className={step === "course" ? "text-primary" : ""}>
                  {selectedCodePrefix}
                </span>
              </>
            )}
            {step === "section" && (
              <>
                <span className="text-muted-foreground/40">›</span>
                <span className="text-primary">{selectedCourseCode}</span>
              </>
            )}
          </div>
        </SheetHeader>

        {/* Search */}
        {step !== "section" && (
          <div className="border-b border-border px-5 py-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder={
                  step === "code" ? "Ders kodu ara..." : "Ders ara..."
                }
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
        )}

        {/* Content */}
        <ScrollArea className="min-h-0 flex-1">
          <div className="px-5 py-4">
            {coursesLoading ? (
              <div className="flex flex-col items-center justify-center py-12 gap-3">
                <Loader2 className="size-6 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">
                  Dersler yükleniyor...
                </p>
              </div>
            ) : (
              <AnimatePresence mode="wait">
                {step === "code" && (
                  <StepCodePrefixes
                    key="code"
                    prefixes={filteredPrefixes}
                    groupedCourses={groupedCourses}
                    onSelect={selectPrefix}
                  />
                )}
                {step === "course" && (
                  <StepCourses
                    key="course"
                    courses={filteredCourses}
                    onSelect={selectCourse}
                  />
                )}
                {step === "section" && (
                  <StepSections
                    key="section"
                    sections={sectionsForCourse}
                    onSelect={onSelectCourse}
                    selectedCRNs={selectedCRNs}
                  />
                )}
              </AnimatePresence>
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

// ── Step 1: Code Prefix Grid ──

function StepCodePrefixes({
  prefixes,
  groupedCourses,
  onSelect,
}: {
  prefixes: string[];
  groupedCourses: Map<string, CourseInfo[]>;
  onSelect: (prefix: string) => void;
}) {
  if (prefixes.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Sonuç bulunamadı
      </p>
    );
  }
  return (
    <m.div
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -8 }}
      transition={{ duration: 0.2 }}
      className="grid grid-cols-3 gap-2"
    >
      {prefixes.map((prefix, i) => {
        const count = new Set(
          (groupedCourses.get(prefix) ?? []).map((c) => c.course_code),
        ).size;
        return (
          <m.button
            key={prefix}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.02 }}
            onClick={() => onSelect(prefix)}
            className="flex flex-col items-center gap-1 border border-border
                       bg-card p-3 transition-colors
                       hover:border-primary hover:bg-accent"
          >
            <span className="font-mono text-sm font-bold">{prefix}</span>
            <span className="text-[10px] text-muted-foreground">
              {count} ders
            </span>
          </m.button>
        );
      })}
    </m.div>
  );
}

// ── Step 2: Course List ──

function StepCourses({
  courses,
  onSelect,
}: {
  courses: CourseInfo[];
  onSelect: (courseCode: string) => void;
}) {
  if (courses.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Sonuç bulunamadı
      </p>
    );
  }
  return (
    <m.div
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -8 }}
      transition={{ duration: 0.2 }}
      className="space-y-2"
    >
      {courses.map((course, i) => (
        <m.button
          key={course.course_code}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.03 }}
          onClick={() => onSelect(course.course_code)}
          className="w-full border border-border bg-card p-4
                     text-left transition-colors
                     hover:border-primary hover:bg-accent"
        >
          <div className="flex items-center justify-between">
            <span className="font-mono text-sm font-bold">
              {course.course_code}
            </span>
            <Badge variant="outline" className="text-[10px]">
              {course.teaching_method === "Physical (Face to face)"
                ? "Yüz Yüze"
                : course.teaching_method}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {course.course_name}
          </p>
        </m.button>
      ))}
    </m.div>
  );
}

// ── Step 3: Section Cards (Rich) ──

function StepSections({
  sections,
  onSelect,
  selectedCRNs,
}: {
  sections: CourseInfo[];
  onSelect: (course: CourseInfo) => void;
  selectedCRNs: Set<string>;
}) {
  if (sections.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Bu ders için section bulunamadı
      </p>
    );
  }
  return (
    <m.div
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -8 }}
      transition={{ duration: 0.2 }}
      className="space-y-3"
    >
      {sections.map((section, i) => {
        const isSelected = selectedCRNs.has(section.crn);
        const pct = capacityPercent(section.enrolled, section.capacity);
        const colorCls = capacityColor(section.enrolled, section.capacity);

        return (
          <m.div
            key={section.crn}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
          >
            <button
              onClick={() => !isSelected && onSelect(section)}
              disabled={isSelected}
              className={`group w-full border p-4 text-left transition-colors ${
                isSelected
                  ? "cursor-not-allowed border-primary bg-accent opacity-70"
                  : "border-border bg-card hover:border-primary hover:bg-accent"
              }`}
            >
              {/* Header: CRN + ekle/eklendi durumu */}
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-semibold text-muted-foreground">
                  CRN {section.crn}
                </span>
                {isSelected ? (
                  <span className="flex items-center gap-1 border border-primary px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-primary">
                    <Check className="size-3" /> Eklendi
                  </span>
                ) : (
                  <span className="flex items-center gap-1 border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground transition-colors group-hover:border-primary group-hover:text-primary">
                    <Plus className="size-3" /> Ekle
                  </span>
                )}
              </div>

              <p className="mt-2 text-sm font-medium">{section.instructor}</p>

              {/* Sessions */}
              <div className="mt-2.5 space-y-1.5">
                {section.sessions.map((s, si) => (
                  <div
                    key={si}
                    className="flex items-center gap-3 text-xs text-muted-foreground"
                  >
                    <div className="flex items-center gap-1.5">
                      <Clock className="size-3" />
                      <span className="font-mono">
                        {DAY_SHORT[s.day]} {s.start_time}→{s.end_time}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <MapPin className="size-3" />
                      <span className="font-mono">
                        {s.building} {s.room}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Capacity bar */}
              <div className="mt-3 flex items-center gap-2">
                <Users className={`size-3 ${colorCls}`} />
                <div className="flex-1">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${pct}%`,
                        background:
                          pct >= 90
                            ? "oklch(0.65 0.18 25)"
                            : pct >= 70
                              ? "oklch(0.75 0.16 85)"
                              : "oklch(0.70 0.16 145)",
                      }}
                    />
                  </div>
                </div>
                <span
                  className={`font-mono text-[11px] font-semibold ${colorCls}`}
                >
                  {section.enrolled}/{section.capacity}
                </span>
              </div>
            </button>
          </m.div>
        );
      })}
    </m.div>
  );
}
