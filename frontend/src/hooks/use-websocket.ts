"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  createWebSocket,
  api,
  type WSEvent,
  type CalibrationResult,
} from "@/lib/api";

export interface LogEntry {
  id: number;
  time: number;
  message: string;
  level: "info" | "warning" | "error";
}

// Exponential backoff: 0.5s → 1s → 2s → 4s → max 5s
// Eski değerler (3s tabanlı, 30s tavan) kayıt anında felaketti: bağlantı T-20sn'de
// koparsa kullanıcı geri sayımı ve logları en kritik pencerede 30 saniye kaybediyordu.
// Motor sunucuda çalışmaya devam eder ama kullanıcı kör kalır.
const RECONNECT_BASE = 500;
const RECONNECT_MAX = 5000;

function getReconnectDelay(attempt: number): number {
  return Math.min(RECONNECT_BASE * Math.pow(2, attempt), RECONNECT_MAX);
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const reconnectAttemptRef = useRef(0);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pingSentRef = useRef<number>(0);
  const [connected, setConnected] = useState(false);
  const [latency, setLatency] = useState<number | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [phase, setPhase] = useState<string>("idle");
  const [countdown, setCountdown] = useState<number | null>(null);
  const [crnResults, setCrnResults] = useState<
    Record<string, { status: string; message: string }>
  >({});
  const [calibration, setCalibration] = useState<CalibrationResult | null>(
    null,
  );
  const [done, setDone] = useState(false);
  // İptal edilerek biten süreç, tamamlanan süreçten AYRI izlenir:
  // ikisi de aynı 'done' olayını üretiyor ama kullanıcıya aynı şey söylenemez.
  const [cancelled, setCancelled] = useState(false);
  // Yalnızca CANLI "done" event'inde artar (siz izlerken kayıt bitince).
  // reconnect/remount'ta getStatus "done" dönse bile artmaz → overlay/toast
  // sadece gerçek tamamlanmada tetiklenir, her sayfa açılışında değil.
  const [completionTick, setCompletionTick] = useState(0);
  const logIdRef = useRef(0);

  // Clerk token'ı asenkron alındığı için connect de asenkron.
  const connect = useCallback(async () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    // CONNECTING durumda kalmış eski bağlantıyı kapat
    if (wsRef.current?.readyState === WebSocket.CONNECTING) {
      wsRef.current.close();
      wsRef.current = null;
    }

    try {
      const ws = await createWebSocket();

      ws.onopen = () => {
        setConnected(true);
        reconnectAttemptRef.current = 0; // Başarılı bağlantıda sayacı sıfırla

        // Reconnect sonrası backend state'i senkronize et
        api
          .getStatus()
          .then((status) => {
            if (status.phase && status.phase !== "idle") {
              setPhase(status.phase);
              if (status.countdown_seconds != null) {
                setCountdown(status.countdown_seconds);
              }
              if (status.crn_results?.length) {
                const map: Record<string, { status: string; message: string }> =
                  {};
                for (const r of status.crn_results) {
                  map[r.crn] = { status: r.status, message: r.message };
                }
                setCrnResults(map);
              }
              if (status.calibration) {
                setCalibration(status.calibration);
              }
              if (status.phase === "done") {
                setDone(true);
              }
            }
          })
          .catch(() => {
            /* backend offline — WS events will sync later */
          });

        // Start ping interval for latency measurement
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            pingSentRef.current = performance.now();
            ws.send("ping");
          }
        }, 10_000);
        // First ping immediately
        pingSentRef.current = performance.now();
        ws.send("ping");
      };

      ws.onclose = () => {
        setConnected(false);
        setLatency(null);
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }
        // Exponential backoff ile reconnect
        const delay = getReconnectDelay(reconnectAttemptRef.current);
        reconnectAttemptRef.current++;
        reconnectTimeoutRef.current = setTimeout(connect, delay); // eslint-disable-line react-hooks/immutability -- self-referencing closure, valid at call time
      };

      ws.onerror = () => ws.close();

      ws.onmessage = (evt) => {
        try {
          const event: WSEvent = JSON.parse(evt.data);

          switch (event.type) {
            case "log":
              setLogs((prev) => [
                ...prev.slice(-200), // Son 200 log
                {
                  id: ++logIdRef.current,
                  time: event.timestamp,
                  message: String(event.data.message || ""),
                  level: (event.data.level as LogEntry["level"]) || "info",
                },
              ]);
              break;

            case "state":
              setPhase(String(event.data.phase || "idle"));
              break;

            case "countdown":
              setCountdown(event.data.remaining as number);
              break;

            case "crn_update":
              if (event.data.results) {
                setCrnResults(
                  event.data.results as Record<
                    string,
                    { status: string; message: string }
                  >,
                );
              }
              break;

            case "calibration":
              setCalibration(event.data as unknown as CalibrationResult);
              break;

            case "done": {
              const wasCancelled = event.data.cancelled === true;
              setDone(true);
              setCancelled(wasCancelled);
              // İptalde tamamlanma sayacı artmaz → "KAYIT TAMAM" modalı açılmaz.
              if (!wasCancelled) setCompletionTick((t) => t + 1);
              if (event.data.results) {
                setCrnResults(
                  event.data.results as Record<
                    string,
                    { status: string; message: string }
                  >,
                );
              }
              break;
            }

            case "pong":
              if (pingSentRef.current > 0) {
                setLatency(Math.round(performance.now() - pingSentRef.current));
                pingSentRef.current = 0;
              }
              break;
          }
        } catch {
          // ignore parse errors
        }
      };

      wsRef.current = ws;
    } catch {
      const delay = getReconnectDelay(reconnectAttemptRef.current);
      reconnectAttemptRef.current++;
      reconnectTimeoutRef.current = setTimeout(connect, delay);
    }
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  const clearLogs = useCallback(() => {
    setLogs([]);
    logIdRef.current = 0;
  }, []);

  const reset = useCallback(() => {
    clearLogs();
    setPhase("idle");
    setCountdown(null);
    setCrnResults({});
    setCalibration(null);
    setDone(false);
    setCancelled(false);
  }, [clearLogs]);

  // Cancel sonrası: logları koruyarak state sıfırla
  const softReset = useCallback(() => {
    setPhase("idle");
    setCountdown(null);
    setCrnResults({});
    setDone(false);
    setCancelled(false);
  }, []);

  useEffect(() => {
    connect();
    return disconnect;
  }, [connect, disconnect]);

  return {
    connected,
    latency,
    logs,
    phase,
    countdown,
    crnResults,
    calibration,
    done,
    cancelled,
    completionTick,
    clearLogs,
    reset,
    softReset,
  };
}
