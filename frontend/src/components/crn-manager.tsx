"use client";

import { useState, useEffect, useCallback } from "react";
import { m, AnimatePresence } from "motion/react";
import {
  Plus,
  X,
  BookOpen,
  BookMinus,
  Users,
  Loader2,
  Trash2,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import type { CourseInfo } from "@/lib/api";

// ── CRN Labels (localStorage) ──

const LABELS_KEY = "otostop-crn-labels";

function loadLabels(): Record<string, string> {
  try {
    const raw = localStorage.getItem(LABELS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveLabel(crn: string, label: string) {
  try {
    const labels = loadLabels();
    if (label) labels[crn] = label;
    else delete labels[crn];
    localStorage.setItem(LABELS_KEY, JSON.stringify(labels));
  } catch {
    /* ignore */
  }
}

interface CRNManagerProps {
  ecrnList: string[];
  onEcrnListChange: (list: string[]) => void;
  scrnList: string[];
  onScrnListChange: (list: string[]) => void;
  crnResults: Record<string, { status: string; message: string }>;
  courseInfo?: Record<string, CourseInfo>;
  lookingUp?: Set<string>;
  disabled?: boolean;
}

// Her durum → metin/nokta rengi (durum token'ları). Dolgu yok, hairline dil.
const statusColor: Record<string, string> = {
  pending: "text-muted-foreground",
  success: "text-status-ok",
  already: "text-foreground",
  full: "text-status-err",
  conflict: "text-status-wait",
  upgrade: "text-primary",
  debounce: "text-status-wait",
  error: "text-status-err",
  dropped: "text-status-ok",
};

const statusDot: Record<string, string> = {
  pending: "bg-muted-foreground",
  success: "bg-status-ok",
  already: "bg-foreground",
  full: "bg-status-err",
  conflict: "bg-status-wait",
  upgrade: "bg-primary",
  debounce: "bg-status-wait",
  error: "bg-status-err",
  dropped: "bg-status-ok",
};

const statusLabels: Record<string, string> = {
  pending: "Bekliyor",
  success: "Başarılı",
  already: "Kayıtlı",
  full: "Dolu",
  conflict: "Çakışma",
  upgrade: "Yükseltme",
  debounce: "Tekrar",
  error: "Hata",
  dropped: "Bırakıldı",
};

type Tab = "add" | "drop";

export function CRNManager({
  ecrnList,
  onEcrnListChange,
  scrnList,
  onScrnListChange,
  crnResults,
  courseInfo = {},
  lookingUp = new Set(),
  disabled,
}: CRNManagerProps) {
  const [tab, setTab] = useState<Tab>("add");
  const [input, setInput] = useState("");
  const [labels, setLabels] = useState<Record<string, string>>({});

  useEffect(() => {
    setLabels(loadLabels());
  }, []);

  const activeList = tab === "add" ? ecrnList : scrnList;
  const setActiveList = tab === "add" ? onEcrnListChange : onScrnListChange;

  const MAX_ECRN = 12;

  const addCRN = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed) return;

    if (tab === "add" && ecrnList.length >= MAX_ECRN) {
      toast.error(`Maksimum ${MAX_ECRN} ECRN eklenebilir (OBS limiti)`);
      return;
    }

    const match = trimmed.match(/^(\d{5})\s*(.*)$/);
    if (!match) {
      if (!/^\d{5}$/.test(trimmed)) {
        toast.error(
          "CRN 5 haneli sayısal olmalı (ör: 12345 veya 12345 Mat Bilimi)",
        );
        return;
      }
    }

    const crn = match ? match[1] : trimmed;
    const label = match ? match[2].trim() : "";

    if (!activeList.includes(crn)) {
      setActiveList([...activeList, crn]);
    }
    if (label) {
      saveLabel(crn, label);
      setLabels((prev) => ({ ...prev, [crn]: label }));
    }
    setInput("");
  }, [input, activeList, setActiveList, tab, ecrnList.length]);

  const removeCRN = (crn: string) => {
    setActiveList(activeList.filter((c) => c !== crn));
  };

  return (
    <div>
      {/* Tabs */}
      <div className="flex border-b">
        {(["add", "drop"] as Tab[]).map((t) => {
          const isActive = tab === t;
          const count = t === "add" ? ecrnList.length : scrnList.length;
          const Icon = t === "add" ? BookOpen : BookMinus;
          return (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`relative flex flex-1 items-center justify-center gap-2 py-3.5 text-sm font-medium transition-colors ${
                isActive
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{t === "add" ? "Ekle" : "Bırak"}</span>
              {count > 0 && (
                <span
                  className={`border px-1.5 font-mono text-[10px] font-semibold ${
                    isActive
                      ? "border-primary text-primary"
                      : "text-muted-foreground"
                  }`}
                >
                  {count}
                </span>
              )}
              {isActive && (
                <m.div
                  layoutId="crn-tab-indicator"
                  className="absolute inset-x-4 bottom-0 h-0.5 bg-primary"
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="space-y-3 p-4">
        {/* Input */}
        {!disabled && (
          <div className="flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addCRN();
                }
              }}
              placeholder={
                tab === "add"
                  ? "CRN gir (ör: 24066 Mat Bilimi)"
                  : "CRN gir (ör: 20150)"
              }
              aria-label={tab === "add" ? "Eklenecek CRN" : "Bırakılacak CRN"}
              className="font-mono text-sm"
            />
            <button
              onClick={addCRN}
              disabled={!input.trim()}
              className="flex h-9 w-9 shrink-0 items-center justify-center bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-30"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* CRN List */}
        <div className="min-h-15 space-y-1.5">
          <AnimatePresence mode="popLayout">
            {activeList.map((crn, i) => {
              const result = crnResults[crn];
              const status = result?.status || "pending";
              return (
                <m.div
                  key={`${tab}-${crn}`}
                  layout
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: 30 }}
                  transition={{
                    type: "spring",
                    stiffness: 500,
                    damping: 35,
                    delay: i * 0.02,
                  }}
                  className="group flex items-center justify-between border px-3.5 py-2.5"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="shrink-0 font-mono text-[15px] font-bold tracking-wider">
                      {crn}
                    </span>
                    {courseInfo[crn] ? (
                      <div className="flex min-w-0 items-center gap-2 truncate">
                        <span className="truncate font-mono text-[11px] font-medium text-muted-foreground">
                          {courseInfo[crn].course_code}
                        </span>
                        <span className="hidden truncate text-[10px] text-muted-foreground/70 sm:inline">
                          {courseInfo[crn].course_name}
                        </span>
                        <span className="flex shrink-0 items-center gap-0.5 font-mono text-[9px] text-muted-foreground/60">
                          <Users className="h-2.5 w-2.5" />
                          {courseInfo[crn].enrolled}/{courseInfo[crn].capacity}
                        </span>
                      </div>
                    ) : lookingUp.has(crn) ? (
                      <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                    ) : labels[crn] ? (
                      <span className="truncate text-[11px] text-muted-foreground">
                        {labels[crn]}
                      </span>
                    ) : null}
                    {result && (
                      <span
                        className={`flex shrink-0 items-center gap-1.5 text-[11px] font-medium ${statusColor[status]}`}
                      >
                        <span className={`h-1.5 w-1.5 rounded-full ${statusDot[status]}`} />
                        {statusLabels[status] || status}
                      </span>
                    )}
                  </div>
                  {!disabled && (
                    <button
                      className="flex h-7 w-7 items-center justify-center text-muted-foreground transition-colors hover:text-status-err sm:opacity-0 sm:group-hover:opacity-100"
                      onClick={() => removeCRN(crn)}
                      aria-label="CRN kaldır"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </m.div>
              );
            })}
          </AnimatePresence>
          {activeList.length === 0 && (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              {tab === "add" ? "Henüz CRN eklenmedi" : "Bırakılacak ders yok"}
            </div>
          )}
        </div>

        {/* Clear all */}
        {!disabled && activeList.length > 1 && (
          <div className="flex justify-end pb-1">
            <button
              onClick={() => setActiveList([])}
              className="flex items-center gap-1 text-[10px] text-muted-foreground transition-colors hover:text-status-err"
            >
              <Trash2 className="h-2.5 w-2.5" />
              Tümünü temizle
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
