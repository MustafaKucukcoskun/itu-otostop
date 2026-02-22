"use client";

import { useEffect, useState, useMemo } from "react";
import { m } from "motion/react";
import {
  Activity,
  Server,
  Wifi,
  Clock,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";
import type { CalibrationResult } from "@/lib/api";

// ── Calibration History (localStorage — token bazlı) ──

interface CalibrationEntry {
  timestamp: number;
  server_offset_ms: number;
  rtt_one_way_ms: number;
  source?: string; // manual, initial, auto, final
}

const HISTORY_PREFIX = "otostop-cal-";
const MAX_ENTRIES = 20;

/** Token'ın ilk 16 karakterinden basit bir hash üretir */
function tokenHash(token: string): string {
  if (!token || token.length < 8) return "default";
  let hash = 0;
  const sample = token.slice(0, 32);
  for (let i = 0; i < sample.length; i++) {
    hash = ((hash << 5) - hash + sample.charCodeAt(i)) | 0;
  }
  return Math.abs(hash).toString(36);
}

function historyKey(token: string): string {
  return `${HISTORY_PREFIX}${tokenHash(token)}`;
}

function loadHistory(token: string): CalibrationEntry[] {
  try {
    const raw = localStorage.getItem(historyKey(token));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveToHistory(token: string, cal: CalibrationResult) {
  try {
    const key = historyKey(token);
    const history = loadHistory(token);
    history.push({
      timestamp: Date.now(),
      server_offset_ms: cal.server_offset_ms,
      rtt_one_way_ms: cal.rtt_one_way_ms,
      source: cal.source ?? "manual",
    });
    // Son N kaydı tut
    while (history.length > MAX_ENTRIES) history.shift();
    localStorage.setItem(key, JSON.stringify(history));
  } catch {
    /* ignore */
  }
}

/** Eski global key varsa temizle */
function migrateOldHistory() {
  try {
    localStorage.removeItem("otostop-cal-history");
  } catch {
    /* */
  }
}

// ── Mini SVG Sparkline ──

function Sparkline({
  data,
  color,
  height = 24,
  width = 120,
}: {
  data: number[];
  color: string;
  height?: number;
  width?: number;
}) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.7"
      />
      {/* Last point dot */}
      {data.length > 0 && (
        <circle
          cx={((data.length - 1) / (data.length - 1)) * width}
          cy={
            height - ((data[data.length - 1] - min) / range) * (height - 4) - 2
          }
          r="2.5"
          fill={color}
        />
      )}
    </svg>
  );
}

interface CalibrationCardProps {
  calibration: CalibrationResult | null;
  loading?: boolean;
  token?: string; // History'yi token bazlı tutmak için
}

/** Kaynak etiket çevirisi */
const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  manual: { label: "Manuel", color: "text-blue-400" },
  initial: { label: "Başlangıç", color: "text-violet-400" },
  auto: { label: "Otomatik", color: "text-teal-400" },
  final: { label: "Son Ölçüm", color: "text-amber-400" },
};

/** Standart sapma hesapla */
function stdDev(values: number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const sq = values.map((v) => (v - mean) ** 2);
  return Math.sqrt(sq.reduce((a, b) => a + b, 0) / values.length);
}

/** Kalite seviyesi renkleri */
const QUALITY = {
  excellent: {
    label: "Mükemmel",
    class: "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10",
  },
  good: {
    label: "İyi",
    class: "text-blue-600 dark:text-blue-400 bg-blue-500/10",
  },
  normal: {
    label: "Normal",
    class: "text-amber-600 dark:text-amber-400 bg-amber-500/10",
  },
  poor: {
    label: "Yüksek",
    class: "text-red-600 dark:text-red-400 bg-red-500/10",
  },
} as const;

type QualityLevel = keyof typeof QUALITY;

function rttQuality(ms: number): QualityLevel {
  if (ms < 30) return "excellent";
  if (ms < 80) return "good";
  if (ms < 200) return "normal";
  return "poor";
}

function accuracyQuality(ms: number): QualityLevel {
  if (ms < 5) return "excellent";
  if (ms < 15) return "good";
  if (ms < 40) return "normal";
  return "poor";
}

function Metric({
  icon: Icon,
  label,
  value,
  unit,
  color,
  quality,
  delay = 0,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  unit: string;
  color: string;
  quality?: QualityLevel;
  delay?: number;
}) {
  return (
    <m.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
      className="flex items-center justify-between py-2.5"
    >
      <div className="flex items-center gap-2.5">
        <div
          className={`h-6 w-6 rounded-md ${color} bg-current/10 flex items-center justify-center`}
        >
          <Icon className="h-3 w-3" />
        </div>
        <span className="text-[13px] text-muted-foreground">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        {quality && (
          <span
            className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full ${QUALITY[quality].class}`}
          >
            {QUALITY[quality].label}
          </span>
        )}
        <div className="flex items-baseline gap-1">
          <span className="font-mono font-semibold text-sm">{value}</span>
          <span className="text-[10px] text-muted-foreground">{unit}</span>
        </div>
      </div>
    </m.div>
  );
}

export function CalibrationCard({
  calibration,
  loading,
  token = "",
}: CalibrationCardProps) {
  const [history, setHistory] = useState<CalibrationEntry[]>([]);

  // Migrate old global key once
  useEffect(() => {
    migrateOldHistory();
  }, []);

  // Save new calibration to history + reload
  useEffect(() => {
    if (calibration) {
      saveToHistory(token, calibration);
      setHistory(loadHistory(token));
    }
  }, [calibration, token]);

  // Load history on mount / token change
  useEffect(() => {
    setHistory(loadHistory(token));
  }, [token]);

  // Stability indicator — std deviation of last 5 RTT values
  const stability = useMemo(() => {
    const last5 = history.slice(-5);
    if (last5.length < 2) return null;
    const rttValues = last5.map((h) => h.rtt_one_way_ms);
    const sigma = stdDev(rttValues);
    if (sigma < 3)
      return {
        icon: Minus,
        label: "Stabil",
        color: "text-emerald-400",
        desc: `σ=${sigma.toFixed(1)}ms`,
      };
    if (sigma < 10)
      return {
        icon: TrendingUp,
        label: "Dalgalı",
        color: "text-orange-400",
        desc: `σ=${sigma.toFixed(1)}ms`,
      };
    return {
      icon: TrendingDown,
      label: "Kararsız",
      color: "text-red-400",
      desc: `σ=${sigma.toFixed(1)}ms`,
    };
  }, [history]);

  // Source badge
  const sourceBadge = useMemo(() => {
    const src = calibration?.source ?? "manual";
    return SOURCE_LABELS[src] ?? SOURCE_LABELS.manual;
  }, [calibration?.source]);

  return (
    <div className="overflow-hidden">
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-violet-500/10 flex items-center justify-center">
            <Activity className="h-4 w-4 text-violet-400" />
          </div>
          <h3 className="text-sm font-semibold">Kalibrasyon</h3>
          {stability && (
            <span
              className={`flex items-center gap-1 text-[10px] font-medium ${stability.color}`}
              title={stability.desc}
            >
              <stability.icon className="h-3 w-3" />
              {stability.label}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {calibration && (
            <span
              className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-current/5 ${sourceBadge.color}`}
            >
              {sourceBadge.label}
            </span>
          )}
          {loading && (
            <m.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
            >
              <Activity className="h-4 w-4 text-muted-foreground" />
            </m.div>
          )}
        </div>
      </div>
      <div className="px-5 pb-5">
        {calibration ? (
          <>
            <div className="divide-y divide-border/30">
              <Metric
                icon={Server}
                label="Sunucu Offset"
                value={`${calibration.server_offset_ms >= 0 ? "+" : ""}${calibration.server_offset_ms?.toFixed(0)}`}
                unit="ms"
                color="text-blue-400"
                delay={0}
              />
              <Metric
                icon={Wifi}
                label="RTT (tam)"
                value={calibration.rtt_full_ms?.toFixed(0) || "—"}
                unit="ms"
                color="text-emerald-400"
                quality={
                  calibration.rtt_full_ms != null
                    ? rttQuality(calibration.rtt_full_ms)
                    : undefined
                }
                delay={0.05}
              />
              <Metric
                icon={Wifi}
                label="RTT (tek yön)"
                value={calibration.rtt_one_way_ms?.toFixed(1) || "—"}
                unit="ms"
                color="text-teal-400"
                quality={
                  calibration.rtt_one_way_ms != null
                    ? rttQuality(calibration.rtt_one_way_ms)
                    : undefined
                }
                delay={0.1}
              />
              <Metric
                icon={Clock}
                label="NTP Offset"
                value={calibration.ntp_offset_ms?.toFixed(0) || "—"}
                unit="ms"
                color="text-amber-400"
                delay={0.15}
              />
              <Metric
                icon={Server}
                label="Sunucu ↔ NTP"
                value={calibration.server_ntp_diff_ms?.toFixed(0) || "—"}
                unit="ms"
                color="text-orange-400"
                delay={0.2}
              />
              <Metric
                icon={Activity}
                label="Hassasiyet"
                value={`±${calibration.accuracy_ms?.toFixed(1)}`}
                unit="ms"
                color="text-violet-400"
                quality={
                  calibration.accuracy_ms != null
                    ? accuracyQuality(calibration.accuracy_ms)
                    : undefined
                }
                delay={0.25}
              />
            </div>

            {/* History sparklines */}
            {history.length >= 2 && (
              <m.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
                className="mt-3 pt-3 border-t border-border/20"
              >
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[10px] text-muted-foreground/50 uppercase tracking-wider">
                    Son {Math.min(history.length, 10)} ölçüm
                  </p>
                  {history.length > 0 && history[history.length - 1].source && (
                    <p className="text-[9px] text-muted-foreground/40">
                      {new Date(
                        history[history.length - 1].timestamp,
                      ).toLocaleTimeString("tr-TR", {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </p>
                  )}
                </div>
                <div className="flex items-center justify-between gap-4">
                  <div className="space-y-0.5">
                    <p className="text-[10px] text-blue-400">Offset</p>
                    <Sparkline
                      data={history.slice(-10).map((h) => h.server_offset_ms)}
                      color="oklch(0.65 0.18 240)"
                    />
                  </div>
                  <div className="space-y-0.5">
                    <p className="text-[10px] text-emerald-400">RTT</p>
                    <Sparkline
                      data={history.slice(-10).map((h) => h.rtt_one_way_ms)}
                      color="oklch(0.7 0.18 165)"
                    />
                  </div>
                </div>
              </m.div>
            )}
          </>
        ) : (
          <div className="text-center py-8 text-muted-foreground/50 text-sm">
            {loading ? (
              <m.span
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
              >
                Ölçülüyor...
              </m.span>
            ) : (
              "Kalibre Et butonuna bas"
            )}
          </div>
        )}
      </div>
    </div>
  );
}
