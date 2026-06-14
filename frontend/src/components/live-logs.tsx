"use client";

import { useRef, useEffect } from "react";
import { Terminal, Trash2 } from "lucide-react";
import { PanelHeader } from "@/components/panel";
import type { LogEntry } from "@/hooks/use-websocket";

interface LiveLogsProps {
  logs: LogEntry[];
  onClear: () => void;
}

const levelColors: Record<string, string> = {
  info: "text-foreground",
  warning: "text-status-wait",
  error: "text-status-err",
};

const levelDots: Record<string, string> = {
  info: "bg-muted-foreground",
  warning: "bg-status-wait",
  error: "bg-status-err",
};

export function LiveLogs({ logs, onClear }: LiveLogsProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div>
      <PanelHeader
        label={
          <span className="flex items-center gap-2">
            <Terminal className="h-3.5 w-3.5" />
            Canlı Log
          </span>
        }
        action={
          <>
            {logs.length > 0 && (
              <span className="border border-primary px-1.5 font-mono text-[10px] text-primary">
                {logs.length}
              </span>
            )}
            {logs.length > 0 && (
              <button
                onClick={onClear}
                className="flex h-7 w-7 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
                aria-label="Logları temizle"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
          </>
        }
      />

      {/* terminal body */}
      <div className="p-4">
        <div
          ref={scrollRef}
          role="log"
          aria-live="polite"
          aria-label="Canlı kayıt logları"
          className="h-60 space-y-0.5 overflow-y-auto border bg-background p-3 font-mono text-xs sm:h-75"
        >
          {logs.length === 0 ? (
            <div className="flex h-full items-center justify-center text-[13px] text-muted-foreground/60">
              Kayıt başlatılınca loglar burada görünecek
            </div>
          ) : (
            logs.map((log) => (
              <div
                key={log.id}
                className={`log-entry flex items-start gap-2 py-0.5 ${levelColors[log.level]}`}
              >
                <span
                  className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${levelDots[log.level]}`}
                />
                <span className="shrink-0 text-muted-foreground/70">
                  {new Date(log.time * 1000).toLocaleTimeString("tr-TR", {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </span>
                <span className="break-all">{log.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
