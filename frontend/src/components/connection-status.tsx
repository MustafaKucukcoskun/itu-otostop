"use client";

import { Wifi, WifiOff } from "lucide-react";

interface ConnectionStatusProps {
  connected: boolean;
  latency?: number | null;
}

function latencyColor(ms: number): string {
  if (ms < 200) return "text-status-ok";
  if (ms < 500) return "text-status-wait";
  return "text-status-err";
}

export function ConnectionStatus({
  connected,
  latency,
}: ConnectionStatusProps) {
  return (
    <div
      role="status"
      aria-label={
        connected
          ? `Bağlı${latency != null ? `, gecikme ${latency}ms` : ""}`
          : "Bağlantı yok"
      }
      className="flex items-center gap-2 border px-3 py-1.5"
    >
      <span
        className={`h-2 w-2 rounded-full ${connected ? "bg-status-ok status-pulse" : "bg-status-err"}`}
        style={
          connected
            ? ({ "--pulse-color": "var(--status-ok)" } as React.CSSProperties)
            : undefined
        }
      />
      {connected ? (
        <Wifi className="h-3.5 w-3.5 text-status-ok" />
      ) : (
        <WifiOff className="h-3.5 w-3.5 text-status-err" />
      )}
      <span className="text-[11px] font-medium text-muted-foreground">
        {connected ? "Canlı" : "Bağlantı yok"}
      </span>
      {connected && latency != null && (
        <span className={`font-mono text-[10px] font-medium ${latencyColor(latency)}`}>
          {latency}ms
        </span>
      )}
    </div>
  );
}
