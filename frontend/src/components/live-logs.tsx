"use client";

import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Terminal, Trash2 } from "lucide-react";
import type { LogEntry } from "@/hooks/use-websocket";

interface LiveLogsProps {
  logs: LogEntry[];
  onClear: () => void;
}

const levelColors: Record<string, string> = {
  info: "text-foreground",
  warning: "text-yellow-400",
  error: "text-red-400",
};

const levelDots: Record<string, string> = {
  info: "bg-blue-400",
  warning: "bg-yellow-400",
  error: "bg-red-400",
};

export function LiveLogs({ logs, onClear }: LiveLogsProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="overflow-hidden">
      {/* header */}
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <Terminal className="h-4 w-4 text-emerald-400" />
          </div>
          <h3 className="text-sm font-semibold">Canlı Log</h3>
          {logs.length > 0 && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="text-[10px] bg-primary/15 text-primary px-2 py-0.5 rounded-full font-medium"
            >
              {logs.length}
            </motion.span>
          )}
        </div>
        {logs.length > 0 && (
          <button
            onClick={onClear}
            className="h-7 w-7 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* terminal body */}
      <div className="px-5 pb-5">
        <div
          ref={scrollRef}
          className="h-60 sm:h-75 overflow-y-auto rounded-xl bg-background/60 ring-1 ring-border/20 p-3 font-mono text-xs space-y-0.5"
        >
          {logs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground/40 text-[13px]">
              Kayıt başlatılınca loglar burada görünecek
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {logs.map((log) => (
                <motion.div
                  key={log.id}
                  initial={{ opacity: 0, x: -8, height: 0 }}
                  animate={{ opacity: 1, x: 0, height: "auto" }}
                  transition={{ duration: 0.12 }}
                  className={`flex items-start gap-2 py-0.5 ${levelColors[log.level]}`}
                >
                  <span
                    className={`mt-1.5 h-1.5 w-1.5 rounded-full shrink-0 ${levelDots[log.level]}`}
                  />
                  <span className="text-muted-foreground/60 shrink-0">
                    {new Date(log.time * 1000).toLocaleTimeString("tr-TR", {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
                  </span>
                  <span className="break-all">{log.message}</span>
                </motion.div>
              ))}
            </AnimatePresence>
          )}
        </div>
      </div>
    </div>
  );
}
