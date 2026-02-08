"use client";

import { motion } from "motion/react";
import { Activity, Server, Wifi, Clock } from "lucide-react";

interface CalibrationCardProps {
  calibration: Record<string, number> | null;
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
  return (
    <div className="rounded-2xl glass overflow-hidden">
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <Activity className="h-4 w-4 text-primary" />
          </div>
          <h3 className="text-sm font-semibold">Kalibrasyon</h3>
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
