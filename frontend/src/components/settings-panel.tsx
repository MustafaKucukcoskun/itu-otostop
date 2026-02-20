"use client";

import { useState, useEffect } from "react";
import { m } from "motion/react";
import {
  Settings,
  RefreshCcw,
  Hash,
  ChevronDown,
  FlaskConical,
  RotateCcw,
} from "lucide-react";

const DEFAULTS = {
  maxDeneme: 60,
  retryAralik: 3,
  dryRun: false,
} as const;

interface SettingsPanelProps {
  maxDeneme: number;
  onMaxDenemeChange: (v: number) => void;
  retryAralik: number;
  onRetryAralikChange: (v: number) => void;
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
  maxDeneme,
  onMaxDenemeChange,
  retryAralik,
  onRetryAralikChange,
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
            <Settings className="h-4 w-4 text-amber-600 dark:text-amber-400" />
          </div>
          <h3 className="text-sm font-semibold">Ayarlar</h3>
        </div>
        <m.div
          animate={{ rotate: expanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </m.div>
      </button>

      {/* Expandable body */}
      <m.div
        initial={false}
        animate={{ height: expanded ? "auto" : 0, opacity: expanded ? 1 : 0 }}
        transition={{ duration: 0.25, ease: "easeInOut" }}
        className="overflow-hidden"
      >
        <div className="px-5 pb-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
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
          </div>
          <div className="flex items-center justify-between">
            <p className="text-[11px] text-muted-foreground/60 leading-relaxed">
              Retry Aralığı: Sunucu 3sn&apos;den sık istekleri yok sayar
              (VAL16). Buffer: Ölçüm tabanlı olarak otomatik hesaplanır.
            </p>
            {!disabled && (
              <button
                type="button"
                onClick={() => {
                  onMaxDenemeChange(DEFAULTS.maxDeneme);
                  onRetryAralikChange(DEFAULTS.retryAralik);
                  onDryRunChange(DEFAULTS.dryRun);
                }}
                className="shrink-0 ml-3 flex items-center gap-1 text-[10px] text-muted-foreground/40 hover:text-muted-foreground/70 transition-colors"
                title="Varsayılan değerlere sıfırla"
              >
                <RotateCcw className="h-3 w-3" />
                Sıfırla
              </button>
            )}
          </div>

          {/* Dry-Run Toggle */}
          <div className="flex items-center justify-between py-3 px-3 rounded-xl bg-background/40 ring-1 ring-border/20">
            <div className="flex items-center gap-2.5">
              <div className="h-7 w-7 rounded-lg bg-amber-500/10 flex items-center justify-center">
                <FlaskConical className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
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
      </m.div>
    </div>
  );
}
