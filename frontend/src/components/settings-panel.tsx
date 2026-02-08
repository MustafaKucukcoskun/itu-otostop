"use client";

import { useState, useEffect } from "react";
import { motion } from "motion/react";
import {
  Settings,
  Clock,
  RefreshCcw,
  Hash,
  Shield,
  ChevronDown,
  FlaskConical,
  Zap,
} from "lucide-react";

// Common ITU registration times
const QUICK_TIMES = [
  { label: "09:30", value: "09:30:00" },
  { label: "10:00", value: "10:00:00" },
  { label: "13:00", value: "13:00:00" },
  { label: "13:30", value: "13:30:00" },
  { label: "14:00", value: "14:00:00" },
];

interface SettingsPanelProps {
  kayitSaati: string;
  onKayitSaatiChange: (v: string) => void;
  maxDeneme: number;
  onMaxDenemeChange: (v: number) => void;
  retryAralik: number;
  onRetryAralikChange: (v: number) => void;
  gecikmeBuffer: number;
  onGecikmeBufferChange: (v: number) => void;
  dryRun: boolean;
  onDryRunChange: (v: boolean) => void;
  disabled?: boolean;
}

function FieldGroup({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ElementType;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
        <Icon className="h-3 w-3" /> {label}
      </label>
      {children}
    </div>
  );
}

export function SettingsPanel({
  kayitSaati,
  onKayitSaatiChange,
  maxDeneme,
  onMaxDenemeChange,
  retryAralik,
  onRetryAralikChange,
  gecikmeBuffer,
  onGecikmeBufferChange,
  dryRun,
  onDryRunChange,
  disabled,
}: SettingsPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [localRetry, setLocalRetry] = useState(String(retryAralik));

  useEffect(() => {
    setLocalRetry(String(retryAralik));
  }, [retryAralik]);

  return (
    <div className="overflow-hidden">
      {/* Toggle header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-muted/20 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
            <Settings className="h-4 w-4 text-amber-400" />
          </div>
          <h3 className="text-sm font-semibold">Ayarlar</h3>
        </div>
        <motion.div
          animate={{ rotate: expanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </motion.div>
      </button>

      {/* Expandable body */}
      <motion.div
        initial={false}
        animate={{ height: expanded ? "auto" : 0, opacity: expanded ? 1 : 0 }}
        transition={{ duration: 0.25, ease: "easeInOut" }}
        className="overflow-hidden"
      >
        <div className="px-5 pb-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <FieldGroup icon={Clock} label="Kayıt Saati">
              <input
                type="time"
                step="1"
                value={kayitSaati}
                onChange={(e) => {
                  const v = e.target.value;
                  // Normalize HH:MM → HH:MM:00 for backend compat
                  onKayitSaatiChange(v && v.length === 5 ? v + ":00" : v);
                }}
                disabled={disabled}
                className={`w-full h-9 rounded-xl bg-background/60 ring-1 px-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-40 transition-shadow ${
                  !kayitSaati
                    ? "ring-amber-500/40 text-muted-foreground"
                    : "ring-border/30"
                }`}
              />
              {/* Quick time buttons */}
              <div className="flex gap-1 flex-wrap">
                {QUICK_TIMES.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => onKayitSaatiChange(t.value)}
                    disabled={disabled}
                    className={`px-2 py-0.5 rounded-lg text-[10px] font-mono font-medium transition-all disabled:opacity-40 ${
                      kayitSaati === t.value
                        ? "bg-primary/15 text-primary ring-1 ring-primary/30"
                        : "bg-background/40 text-muted-foreground hover:bg-muted/50 ring-1 ring-border/20"
                    }`}
                  >
                    <Zap className="h-2.5 w-2.5 inline mr-0.5 -mt-px" />
                    {t.label}
                  </button>
                ))}
              </div>
            </FieldGroup>

            <FieldGroup icon={Hash} label="Maks Deneme">
              <input
                type="number"
                min={1}
                max={300}
                value={maxDeneme}
                onChange={(e) => onMaxDenemeChange(Number(e.target.value))}
                disabled={disabled}
                className="w-full h-9 rounded-xl bg-background/60 ring-1 ring-border/30 px-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-40 transition-shadow"
              />
            </FieldGroup>

            <FieldGroup icon={RefreshCcw} label="Retry Aralığı (sn)">
              <input
                type="number"
                min={3}
                max={10}
                step={0.5}
                value={localRetry}
                onChange={(e) => {
                  const num = Number(e.target.value);
                  const clamped = Math.min(
                    10,
                    Math.max(3, isNaN(num) ? 3 : num),
                  );
                  setLocalRetry(String(clamped));
                  onRetryAralikChange(clamped);
                }}
                onKeyDown={(e) => {
                  const allowed = [
                    "Backspace",
                    "Delete",
                    "Tab",
                    "ArrowUp",
                    "ArrowDown",
                    "ArrowLeft",
                    "ArrowRight",
                    ".",
                    "Home",
                    "End",
                  ];
                  if (
                    !allowed.includes(e.key) &&
                    (e.key < "0" || e.key > "9")
                  ) {
                    e.preventDefault();
                  }
                }}
                disabled={disabled}
                className="w-full h-9 rounded-xl bg-background/60 ring-1 ring-border/30 px-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-40 transition-shadow"
              />
            </FieldGroup>

            <FieldGroup icon={Shield} label="Buffer (ms)">
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                value={gecikmeBuffer * 1000}
                onChange={(e) =>
                  onGecikmeBufferChange(Number(e.target.value) / 1000)
                }
                disabled={disabled}
                className="w-full h-9 rounded-xl bg-background/60 ring-1 ring-border/30 px-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-40 transition-shadow"
              />
            </FieldGroup>
          </div>
          <p className="text-[11px] text-muted-foreground/60 leading-relaxed">
            Retry Aralığı: Sunucu 3sn&apos;den sık istekleri yok sayar (VAL16).
            Buffer: Erken varış cezasını önler (+5ms önerilen).
          </p>

          {/* Dry-Run Toggle */}
          <div className="flex items-center justify-between py-3 px-3 rounded-xl bg-background/40 ring-1 ring-border/20">
            <div className="flex items-center gap-2.5">
              <div className="h-7 w-7 rounded-lg bg-amber-500/10 flex items-center justify-center">
                <FlaskConical className="h-3.5 w-3.5 text-amber-400" />
              </div>
              <div>
                <p className="text-sm font-medium">Test Modu (Dry Run)</p>
                <p className="text-[10px] text-muted-foreground">
                  Gerçek kayıt yapmaz, tüm akışı simüle eder
                </p>
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={dryRun}
              onClick={() => onDryRunChange(!dryRun)}
              disabled={disabled}
              className={`relative h-6 w-11 rounded-full transition-colors disabled:opacity-40 ${
                dryRun ? "bg-amber-500" : "bg-muted"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
                  dryRun ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
