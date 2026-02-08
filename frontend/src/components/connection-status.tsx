"use client";

import { motion } from "motion/react";
import { Wifi, WifiOff } from "lucide-react";

interface ConnectionStatusProps {
  connected: boolean;
  latency?: number | null;
}

function latencyColor(ms: number): string {
  if (ms < 200) return "text-emerald-400";
  if (ms < 500) return "text-yellow-400";
  return "text-red-400";
}

export function ConnectionStatus({
  connected,
  latency,
}: ConnectionStatusProps) {
  return (
    <motion.div
      className="flex items-center gap-2 px-3 py-1.5 rounded-full glass"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <div className="relative">
        <motion.div
          className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "bg-red-400"}`}
        />
        {connected && (
          <motion.div
            className="absolute inset-0 h-2 w-2 rounded-full bg-emerald-400"
            animate={{ scale: [1, 2.5], opacity: [0.6, 0] }}
            transition={{ repeat: Infinity, duration: 2, ease: "easeOut" }}
          />
        )}
      </div>
      {connected ? (
        <Wifi className="h-3.5 w-3.5 text-emerald-400" />
      ) : (
        <WifiOff className="h-3.5 w-3.5 text-red-400" />
      )}
      <span className="text-[11px] font-medium text-muted-foreground">
        {connected ? "Canlı" : "Bağlantı yok"}
      </span>
      {connected && latency != null && (
        <span
          className={`text-[10px] font-mono font-medium ${latencyColor(latency)}`}
        >
          {latency}ms
        </span>
      )}
    </motion.div>
  );
}
