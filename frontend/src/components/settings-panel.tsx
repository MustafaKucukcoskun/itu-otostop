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
} from "lucide-react";

interface SettingsPanelProps {
  kayitSaati: string;
  onKayitSaatiChange: (v: string) => void;
  maxDeneme: number;
  onMaxDenemeChange: (v: number) => void;
  retryAralik: number;
  onRetryAralikChange: (v: number) => void;
  gecikmeBuffer: number;
  onGecikmeBufferChange: (v: number) => void;
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
  disabled,
}: SettingsPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [localRetry, setLocalRetry] = useState(String(retryAralik));

  useEffect(() => {
    setLocalRetry(String(retryAralik));
  }, [retryAralik]);

  return (
    <div className="rounded-2xl glass overflow-hidden">
      {/* Toggle header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-muted/20 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <Settings className="h-4 w-4 text-primary" />
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
                onChange={(e) => onKayitSaatiChange(e.target.value)}
                disabled={disabled}
                className="w-full h-9 rounded-xl bg-background/60 ring-1 ring-border/30 px-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-40 transition-shadow"
              />
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
        </div>
      </motion.div>
    </div>
  );
}
