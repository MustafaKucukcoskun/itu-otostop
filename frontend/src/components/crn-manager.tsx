"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Plus,
  X,
  BookOpen,
  BookMinus,
  Users,
  MapPin,
  Loader2,
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

const statusStyles: Record<string, { bg: string; text: string; dot: string }> =
  {
    pending: {
      bg: "bg-zinc-500/8",
      text: "text-muted-foreground",
      dot: "bg-zinc-400",
    },
    success: {
      bg: "bg-emerald-500/8",
      text: "text-emerald-400",
      dot: "bg-emerald-400",
    },
    already: { bg: "bg-blue-500/8", text: "text-blue-400", dot: "bg-blue-400" },
    full: { bg: "bg-red-500/8", text: "text-red-400", dot: "bg-red-400" },
    conflict: {
      bg: "bg-orange-500/8",
      text: "text-orange-400",
      dot: "bg-orange-400",
    },
    upgrade: {
      bg: "bg-purple-500/8",
      text: "text-purple-400",
      dot: "bg-purple-400",
    },
    debounce: {
      bg: "bg-yellow-500/8",
      text: "text-yellow-400",
      dot: "bg-yellow-400",
    },
    error: { bg: "bg-red-500/8", text: "text-red-400", dot: "bg-red-400" },
    dropped: {
      bg: "bg-emerald-500/8",
      text: "text-emerald-400",
      dot: "bg-emerald-400",
    },
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

  // Load labels on mount
  useEffect(() => {
    setLabels(loadLabels());
  }, []);

  const activeList = tab === "add" ? ecrnList : scrnList;
  const setActiveList = tab === "add" ? onEcrnListChange : onScrnListChange;

  const addCRN = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed) return;

    // Parse "12345 Ders Adı" format
    const match = trimmed.match(/^(\d{5})\s*(.*)$/);
    if (!match) {
      // Try pure 5-digit
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
  }, [input, activeList, setActiveList]);

  const removeCRN = (crn: string) => {
    setActiveList(activeList.filter((c) => c !== crn));
  };

  return (
    <div className="overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b border-border/20">
        {(["add", "drop"] as Tab[]).map((t) => {
          const isActive = tab === t;
          const count = t === "add" ? ecrnList.length : scrnList.length;
          const Icon = t === "add" ? BookOpen : BookMinus;
          return (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 relative flex items-center justify-center gap-2 py-3.5 text-sm font-medium transition-colors ${
                isActive
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground/70"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{t === "add" ? "Ekle" : "Bırak"}</span>
              {count > 0 && (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${
                    isActive
                      ? "bg-primary/15 text-primary"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {count}
                </span>
              )}
              {isActive && (
                <motion.div
                  layoutId="crn-tab-indicator"
                  className="absolute bottom-0 left-4 right-4 h-0.5 bg-primary rounded-full"
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="p-4 space-y-3">
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
              className="font-mono bg-background/50 border-border/30 rounded-xl text-sm"
            />
            <button
              onClick={addCRN}
              disabled={!input.trim()}
              className="h-9 w-9 shrink-0 rounded-xl bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-30 flex items-center justify-center transition-colors"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* CRN List */}
        <div className="space-y-1.5 min-h-15">
          <AnimatePresence mode="popLayout">
            {activeList.map((crn, i) => {
              const result = crnResults[crn];
              const status = result?.status || "pending";
              const style = statusStyles[status] || statusStyles.pending;
              return (
                <motion.div
                  key={`${tab}-${crn}`}
                  layout
                  initial={{ opacity: 0, y: -8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.94, x: 30 }}
                  transition={{
                    type: "spring",
                    stiffness: 500,
                    damping: 35,
                    delay: i * 0.02,
                  }}
                  className={`flex items-center justify-between py-2.5 px-3.5 rounded-xl ${style.bg} group`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="font-mono font-bold text-[15px] tracking-wider shrink-0">
                      {crn}
                    </span>
                    {/* Course info from API */}
                    {courseInfo[crn] ? (
                      <div className="flex items-center gap-2 min-w-0 truncate">
                        <span className="text-[11px] font-medium text-muted-foreground truncate">
                          {courseInfo[crn].course_code}
                        </span>
                        <span className="text-[10px] text-muted-foreground/60 truncate hidden sm:inline">
                          {courseInfo[crn].course_name}
                        </span>
                        <span className="flex items-center gap-0.5 text-[9px] text-muted-foreground/40 shrink-0">
                          <Users className="h-2.5 w-2.5" />
                          {courseInfo[crn].enrolled}/{courseInfo[crn].capacity}
                        </span>
                      </div>
                    ) : lookingUp.has(crn) ? (
                      <Loader2 className="h-3 w-3 text-muted-foreground/40 animate-spin" />
                    ) : labels[crn] ? (
                      <span className="text-[11px] text-muted-foreground truncate">
                        {labels[crn]}
                      </span>
                    ) : null}
                    {result && (
                      <span
                        className={`flex items-center gap-1.5 text-[11px] font-medium shrink-0 ${style.text}`}
                      >
                        <span
                          className={`h-1.5 w-1.5 rounded-full ${style.dot}`}
                        />
                        {statusLabels[status] || status}
                      </span>
                    )}
                  </div>
                  {!disabled && (
                    <button
                      className="h-7 w-7 rounded-lg flex items-center justify-center text-muted-foreground/50 hover:text-red-400 hover:bg-red-400/10 sm:opacity-0 sm:group-hover:opacity-100 transition-all"
                      onClick={() => removeCRN(crn)}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
          {activeList.length === 0 && (
            <div className="flex items-center justify-center py-8 text-muted-foreground/50 text-sm">
              {tab === "add" ? "Henüz CRN eklenmedi" : "Bırakılacak ders yok"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
