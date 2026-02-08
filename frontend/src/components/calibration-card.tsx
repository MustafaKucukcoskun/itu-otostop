"use client";

import { useEffect, useState, useMemo } from "react";
import { motion } from "motion/react";
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

// ── Calibration History (localStorage) ──

interface CalibrationEntry {
  timestamp: number;
  server_offset_ms: number;
  rtt_one_way_ms: number;
}

const HISTORY_KEY = "otostop-cal-history";
const MAX_ENTRIES = 10;

function loadHistory(): CalibrationEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveToHistory(cal: CalibrationResult) {
  try {
    const history = loadHistory();
    history.push({
      timestamp: Date.now(),
      server_offset_ms: cal.server_offset_ms,
      rtt_one_way_ms: cal.rtt_one_way_ms,
    });
    // Keep last N entries
    while (history.length > MAX_ENTRIES) history.shift();
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  } catch {
    /* ignore */
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
}

function Metric({
  icon: Icon,
  label,
  value,
  unit,
  color,
  delay = 0,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  unit: string;
  color: string;
  delay?: number;
}) {
  return (
    <motion.div
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
      <div className="flex items-baseline gap-1">
        <span className="font-mono font-semibold text-sm">{value}</span>
        <span className="text-[10px] text-muted-foreground">{unit}</span>
      </div>
    </motion.div>
  );
}

export function CalibrationCard({
  calibration,
  loading,
}: CalibrationCardProps) {
  const [history, setHistory] = useState<CalibrationEntry[]>([]);

  // Save new calibration to history + reload
  useEffect(() => {
    if (calibration) {
      saveToHistory(calibration);
      setHistory(loadHistory());
    }
  }, [calibration]);

  // Load history on mount
  useEffect(() => {
    setHistory(loadHistory());
  }, []);

  // Trend indicator
  const trend = useMemo(() => {
    if (history.length < 2) return null;
    const recent = history[history.length - 1].rtt_one_way_ms;
    const prev = history[history.length - 2].rtt_one_way_ms;
    const diff = recent - prev;
    if (Math.abs(diff) < 1)
      return { icon: Minus, label: "Stabil", color: "text-muted-foreground" };
    return diff > 0
      ? {
          icon: TrendingUp,
          label: `+${diff.toFixed(0)}ms`,
          color: "text-orange-400",
        }
      : {
          icon: TrendingDown,
          label: `${diff.toFixed(0)}ms`,
          color: "text-emerald-400",
        };
  }, [history]);

  return (
    <div className="overflow-hidden">
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-violet-500/10 flex items-center justify-center">
            <Activity className="h-4 w-4 text-violet-400" />
          </div>
          <h3 className="text-sm font-semibold">Kalibrasyon</h3>
          {trend && (
            <span
              className={`flex items-center gap-1 text-[10px] font-medium ${trend.color}`}
            >
              <trend.icon className="h-3 w-3" />
              {trend.label}
            </span>
          )}
        </div>
        {loading && (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
          >
            <Activity className="h-4 w-4 text-muted-foreground" />
          </motion.div>
        )}
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
                delay={0.05}
              />
              <Metric
                icon={Wifi}
                label="RTT (tek yön)"
                value={calibration.rtt_one_way_ms?.toFixed(1) || "—"}
                unit="ms"
                color="text-teal-400"
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
                delay={0.25}
              />
            </div>

            {/* History sparklines */}
            {history.length >= 2 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
                className="mt-3 pt-3 border-t border-border/20"
              >
                <p className="text-[10px] text-muted-foreground/50 uppercase tracking-wider mb-2">
                  Son {history.length} ölçüm
                </p>
                <div className="flex items-center justify-between gap-4">
                  <div className="space-y-0.5">
                    <p className="text-[10px] text-blue-400">Offset</p>
                    <Sparkline
                      data={history.map((h) => h.server_offset_ms)}
                      color="oklch(0.65 0.18 240)"
                    />
                  </div>
                  <div className="space-y-0.5">
                    <p className="text-[10px] text-emerald-400">RTT</p>
                    <Sparkline
                      data={history.map((h) => h.rtt_one_way_ms)}
                      color="oklch(0.7 0.18 165)"
                    />
                  </div>
                </div>
              </motion.div>
            )}
          </>
        ) : (
          <div className="text-center py-8 text-muted-foreground/50 text-sm">
            {loading ? (
              <motion.span
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
              >
                Ölçülüyor...
              </motion.span>
            ) : (
              "Kalibre Et butonuna bas"
            )}
          </div>
        )}
      </div>
    </div>
  );
}
