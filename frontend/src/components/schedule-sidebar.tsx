"use client";

import { useState } from "react";
import { m } from "motion/react";
import { Plus, Trash2, AlertTriangle, ArrowRight, Loader2, Hash } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Command,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";
import type { SelectedCourse } from "./schedule-builder";
import { COURSE_HUES, DAY_SHORT } from "./schedule-builder";

// ── Types ──

interface DepartmentItem {
  bransKoduId: number;
  dersBransKodu: string;
}

interface ScheduleSidebarProps {
  departments: DepartmentItem[];
  selectedDept: DepartmentItem | null;
  onDeptChange: (dept: DepartmentItem | null) => void;
  deptLoading: boolean;
  selectedCourses: SelectedCourse[];
  onRemoveCourse: (crn: string) => void;
  onAddCourse: () => void;
  onAddByCrn: (crn: string) => void | Promise<void>;
  conflicts: string[];
  onExport: () => void;
}

// ── Component ──

export function ScheduleSidebar({
  departments,
  selectedDept,
  onDeptChange,
  deptLoading,
  selectedCourses,
  onRemoveCourse,
  onAddCourse,
  onAddByCrn,
  conflicts,
  onExport,
}: ScheduleSidebarProps) {
  const [crnInput, setCrnInput] = useState("");
  const [crnAdding, setCrnAdding] = useState(false);

  const handleCrnAdd = async () => {
    const crn = crnInput.trim();
    if (!crn) return;
    setCrnAdding(true);
    try {
      await onAddByCrn(crn);
      setCrnInput("");
    } finally {
      setCrnAdding(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Department Selector */}
      <div className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-1 text-sm font-semibold tracking-tight text-muted-foreground uppercase">
          Ders Alanı
        </h2>
        <p className="mb-3 text-[11px] text-muted-foreground/70">
          Dersin alan/branş kodu (BLG, MAT, ATA…)
        </p>
        {deptLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Yükleniyor...
          </div>
        ) : (
          <Command className="rounded-lg border border-border">
            <CommandInput placeholder="Ders alanı ara… (BLG, MAT…)" />
            <CommandList>
              <CommandEmpty>Sonuç bulunamadı</CommandEmpty>
              {/* CommandList kendi scroll'una sahip (max-h + overflow-auto);
                  ayrı ScrollArea sarmak native kaydırmayı kırıyordu */}
              <CommandGroup>
                {departments.map((dept) => (
                  <CommandItem
                    key={dept.bransKoduId}
                    value={dept.dersBransKodu}
                    onSelect={() => onDeptChange(dept)}
                    className={`cursor-pointer ${
                      selectedDept?.bransKoduId === dept.bransKoduId
                        ? "bg-primary/10 text-primary"
                        : ""
                    }`}
                  >
                    <span className="mr-2 font-mono text-xs font-semibold">
                      {dept.dersBransKodu}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        )}
        {selectedDept && (
          <m.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-2"
          >
            <Badge variant="secondary" className="font-mono">
              {selectedDept.dersBransKodu}
            </Badge>
          </m.div>
        )}
      </div>

      {/* Selected Courses */}
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-tight text-muted-foreground uppercase">
            Seçili Dersler
          </h2>
          <span className="text-xs text-muted-foreground">
            {selectedCourses.length} ders
          </span>
        </div>

        {selectedCourses.length === 0 ? (
          <p className="text-sm text-muted-foreground/60 py-4 text-center">
            Henüz ders eklenmedi
          </p>
        ) : (
          <div className="space-y-2">
            {selectedCourses.map((sc, i) => {
              const hue = COURSE_HUES[sc.colorIndex];
              return (
                <m.div
                  key={sc.course.crn}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ delay: i * 0.03 }}
                  className="group flex items-start gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-muted/50"
                >
                  {/* Color dot */}
                  <div
                    className="mt-0.5 size-3 shrink-0 rounded-full"
                    style={{ background: `oklch(0.72 0.14 ${hue})` }}
                  />

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold">
                        {sc.course.course_code}
                      </span>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        CRN {sc.course.crn}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground truncate">
                      {sc.course.instructor}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {sc.course.sessions.map((s, si) => (
                        <Badge
                          key={si}
                          variant="outline"
                          className="text-[10px] font-mono px-1.5 py-0"
                        >
                          {DAY_SHORT[s.day]} {s.start_time}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Remove button */}
                  <button
                    onClick={() => onRemoveCourse(sc.course.crn)}
                    className="shrink-0 rounded-md p-1 text-muted-foreground/40 opacity-0 transition-all group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive"
                    aria-label="Dersi kaldır"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </m.div>
              );
            })}
          </div>
        )}

        {/* Add Course Button */}
        <Button
          onClick={onAddCourse}
          disabled={!selectedDept}
          className="mt-3 w-full gap-2"
          variant={selectedCourses.length === 0 ? "default" : "outline"}
        >
          <Plus className="size-4" />
          Ders Ekle
        </Button>

        {!selectedDept && (
          <p className="mt-2 text-center text-[11px] text-muted-foreground/60">
            Önce ders alanı seçin
          </p>
        )}

        {/* CRN'i biliyorsan doğrudan ekle (alan seçmeye gerek yok) */}
        <div className="mt-3 border-t pt-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Hash className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={crnInput}
                onChange={(e) => setCrnInput(e.target.value.replace(/\D/g, ""))}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCrnAdd();
                }}
                placeholder="CRN ile ekle (5 hane)"
                aria-label="CRN ile ders ekle"
                inputMode="numeric"
                maxLength={5}
                className="pl-8 font-mono text-xs"
              />
            </div>
            <button
              onClick={handleCrnAdd}
              disabled={crnInput.length !== 5 || crnAdding}
              className="flex size-9 shrink-0 items-center justify-center border bg-card text-muted-foreground transition-colors hover:border-primary hover:text-primary disabled:opacity-40"
              aria-label="CRN ekle"
            >
              {crnAdding ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Plus className="size-4" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Conflicts Warning */}
      {conflicts.length > 0 && (
        <m.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-destructive/30 bg-destructive/5 p-3"
        >
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="size-4 shrink-0" />
            <span className="text-sm font-medium">Çakışma Var</span>
          </div>
          <ul className="mt-1.5 space-y-0.5">
            {conflicts.map((c) => (
              <li key={c} className="text-xs text-destructive/80 font-mono">
                {c}
              </li>
            ))}
          </ul>
        </m.div>
      )}

      {/* Footer Stats & Export */}
      {selectedCourses.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {selectedCourses.length} ders · {conflicts.length} çakışma
            </span>
          </div>
          <Button onClick={onExport} className="mt-3 w-full gap-2" size="lg">
            <ArrowRight className="size-4" />
            Planı Kayıt Motoruna Aktar
          </Button>
        </div>
      )}
    </div>
  );
}
