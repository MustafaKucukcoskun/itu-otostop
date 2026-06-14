"use client";

import { useEffect, useState, useMemo } from "react";
import { m } from "motion/react";
import { Loader2 } from "lucide-react";
import { PanelHeader } from "@/components/panel";
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
  height = 24,
  width = 120,
}: {
  data: number[];
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
        stroke="var(--primary)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.8"
      />
      <circle
        cx={width}
        cy={height - ((data[data.length - 1] - min) / range) * (height - 4) - 2}
        r="2.5"
        fill="var(--primary)"
      />
    </svg>
  );
}

interface CalibrationCardProps {
  calibration: CalibrationResult | null;
  loading?: boolean;
  token?: string; // History'yi token bazlı tutmak için
}

/** Kaynak etiket çevirisi */
const SOURCE_LABELS: Record<string, string> = {
  manual: "Manuel",
  initial: "Başlangıç",
  auto: "Otomatik",
  final: "Son Ölçüm",
};

/** Standart sapma hesapla */
function stdDev(values: number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const sq = values.map((v) => (v - mean) ** 2);
  return Math.sqrt(sq.reduce((a, b) => a + b, 0) / values.length);
}

/** Kalite seviyesi — durum rengine eşlenir */
const QUALITY = {
  excellent: { label: "Mükemmel", color: "text-status-ok" },
  good: { label: "İyi", color: "text-status-ok" },
  normal: { label: "Normal", color: "text-status-wait" },
  poor: { label: "Yüksek", color: "text-status-err" },
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
  label,
  value,
  unit,
  quality,
  delay = 0,
}: {
  label: string;
  value: string;
  unit: string;
  quality?: QualityLevel;
  delay?: number;
}) {
  return (
    <m.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.25 }}
      className="flex items-center justify-between py-2"
    >
      <span className="text-[13px] text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2.5">
        {quality && (
          <span
            className={`font-mono text-[10px] uppercase tracking-wider ${QUALITY[quality].color}`}
          >
            {QUALITY[quality].label}
          </span>
        )}
        <div className="flex items-baseline gap-1">
          <span className="font-mono text-sm font-semibold tabular-nums">
            {value}
          </span>
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

  useEffect(() => {
    migrateOldHistory();
  }, []);

  useEffect(() => {
    if (calibration) {
      saveToHistory(token, calibration);
      setHistory(loadHistory(token));
    }
  }, [calibration, token]);

  useEffect(() => {
    setHistory(loadHistory(token));
  }, [token]);

  // Stability indicator — std deviation of last 5 RTT values
  const stability = useMemo(() => {
    const last5 = history.slice(-5);
    if (last5.length < 2) return null;
    const sigma = stdDev(last5.map((h) => h.rtt_one_way_ms));
    if (sigma < 3)
      return { label: "Stabil", color: "text-status-ok", desc: `σ=${sigma.toFixed(1)}ms` };
    if (sigma < 10)
      return { label: "Dalgalı", color: "text-status-wait", desc: `σ=${sigma.toFixed(1)}ms` };
    return { label: "Kararsız", color: "text-status-err", desc: `σ=${sigma.toFixed(1)}ms` };
  }, [history]);

  const sourceLabel = useMemo(() => {
    const src = calibration?.source ?? "manual";
    return SOURCE_LABELS[src] ?? SOURCE_LABELS.manual;
  }, [calibration?.source]);

  return (
    <div>
      <PanelHeader
        label="Kalibrasyon"
        action={
          <>
            {stability && (
              <span
                className={`font-mono text-[10px] uppercase tracking-wider ${stability.color}`}
                title={stability.desc}
              >
                {stability.label}
              </span>
            )}
            {calibration && (
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                {sourceLabel}
              </span>
            )}
            {loading && (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
            )}
          </>
        }
      />
      <div className="p-4">
        {calibration ? (
          <>
            <div className="divide-y">
              <Metric
                label="Sunucu Offset"
                value={`${calibration.server_offset_ms >= 0 ? "+" : ""}${calibration.server_offset_ms?.toFixed(0)}`}
                unit="ms"
              />
              <Metric
                label="RTT (tam)"
                value={calibration.rtt_full_ms?.toFixed(0) || "—"}
                unit="ms"
                quality={
                  calibration.rtt_full_ms != null
                    ? rttQuality(calibration.rtt_full_ms)
                    : undefined
                }
                delay={0.04}
              />
              <Metric
                label="RTT (tek yön)"
                value={calibration.rtt_one_way_ms?.toFixed(1) || "—"}
                unit="ms"
                quality={
                  calibration.rtt_one_way_ms != null
                    ? rttQuality(calibration.rtt_one_way_ms)
                    : undefined
                }
                delay={0.08}
              />
              <Metric
                label="NTP Offset"
                value={calibration.ntp_offset_ms?.toFixed(0) || "—"}
                unit="ms"
                delay={0.12}
              />
              <Metric
                label="Sunucu ↔ NTP"
                value={calibration.server_ntp_diff_ms?.toFixed(0) || "—"}
                unit="ms"
                delay={0.16}
              />
              <Metric
                label="Hassasiyet"
                value={`±${calibration.accuracy_ms?.toFixed(1)}`}
                unit="ms"
                quality={
                  calibration.accuracy_ms != null
                    ? accuracyQuality(calibration.accuracy_ms)
                    : undefined
                }
                delay={0.2}
              />
            </div>

            {/* History sparklines */}
            {history.length >= 2 && (
              <m.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.24 }}
                className="mt-3 border-t pt-3"
              >
                <div className="mb-2 flex items-center justify-between">
                  <p className="panel-label">
                    Son {Math.min(history.length, 10)} ölçüm
                  </p>
                  {history[history.length - 1]?.source && (
                    <p className="font-mono text-[10px] text-muted-foreground">
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
                  <div className="space-y-1">
                    <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      Offset
                    </p>
                    <Sparkline
                      data={history.slice(-10).map((h) => h.server_offset_ms)}
                    />
                  </div>
                  <div className="space-y-1">
                    <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      RTT
                    </p>
                    <Sparkline
                      data={history.slice(-10).map((h) => h.rtt_one_way_ms)}
                    />
                  </div>
                </div>
              </m.div>
            )}
          </>
        ) : (
          <div className="py-8 text-center text-sm text-muted-foreground">
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
