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
    <div>
      {/* Toggle header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex h-11 w-full items-center justify-between border-b px-4 text-left transition-colors hover:bg-accent/40"
      >
        <span className="panel-label flex items-center gap-2">
          <Settings className="h-3.5 w-3.5" />
          Ayarlar
        </span>
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
        <div className="space-y-4 p-4">
          <div className="grid grid-cols-2 gap-4">
            <FieldGroup icon={Hash} label="Maks Deneme">
              <input
                type="number"
                min={1}
                max={300}
                value={maxDeneme}
                onChange={(e) => onMaxDenemeChange(Number(e.target.value))}
                disabled={disabled}
                className="h-9 w-full border bg-background px-3 font-mono text-sm transition-colors focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-40"
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
                className="h-9 w-full border bg-background px-3 font-mono text-sm transition-colors focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-40"
              />
            </FieldGroup>
          </div>
          <div className="flex items-center justify-between">
            <p className="text-[11px] leading-relaxed text-muted-foreground">
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
                className="ml-3 flex shrink-0 items-center gap-1 text-[10px] text-muted-foreground transition-colors hover:text-foreground"
                title="Varsayılan değerlere sıfırla"
              >
                <RotateCcw className="h-3 w-3" />
                Sıfırla
              </button>
            )}
          </div>

          {/* Dry-Run Toggle */}
          <div className="flex items-center justify-between border px-3 py-3">
            <div className="flex items-center gap-2.5">
              <FlaskConical className="h-4 w-4 text-[--status-wait]" />
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
              className={`relative h-6 w-11 shrink-0 border transition-colors disabled:opacity-40 ${
                dryRun
                  ? "border-[--status-wait] bg-[--status-wait]"
                  : "border-border bg-input"
              }`}
            >
              <span
                className={`absolute top-0.5 size-4 transition-all ${
                  dryRun ? "left-[22px] bg-white" : "left-0.5 bg-foreground"
                }`}
              />
            </button>
          </div>
        </div>
      </m.div>
    </div>
  );
}
