"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";

interface CountdownTimerProps {
  targetTime: string;
  countdown: number | null;
  phase: string;
  dryRun?: boolean;
}

export function CountdownTimer({
  targetTime,
  countdown,
  phase,
  dryRun,
}: CountdownTimerProps) {
  const [displayTime, setDisplayTime] = useState("--:--:--");
  const [currentTime, setCurrentTime] = useState("");
  const [localCountdown, setLocalCountdown] = useState<number | null>(null);

  const hasTarget = !!targetTime && /^\d{2}:\d{2}/.test(targetTime);

  // Live clock — updates every 100ms
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      const h = String(now.getHours()).padStart(2, "0");
      const m = String(now.getMinutes()).padStart(2, "0");
      const s = String(now.getSeconds()).padStart(2, "0");
      const ms = Math.floor(now.getMilliseconds() / 100);
      setCurrentTime(`${h}:${m}:${s}.${ms}`);
    };
    updateClock();
    const interval = setInterval(updateClock, 100);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (countdown !== null) setLocalCountdown(countdown);
  }, [countdown]);

  useEffect(() => {
    if (localCountdown === null || phase === "done" || phase === "idle") return;
    const interval = setInterval(() => {
      setLocalCountdown((prev) => {
        if (prev === null || prev <= 0) return 0;
        return prev - 0.1;
      });
    }, 100);
    return () => clearInterval(interval);
  }, [localCountdown, phase]);

  useEffect(() => {
    if (localCountdown === null || localCountdown <= 0) {
      if (phase === "registering") setDisplayTime("KAYIT YAPILIYOR");
      else if (phase === "done") setDisplayTime("TAMAMLANDI");
      else if (phase === "idle")
        setDisplayTime(""); // idle = live clock shown separately
      else setDisplayTime(targetTime || "--:--:--");
      return;
    }
    const total = Math.max(0, localCountdown);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = Math.floor(total % 60);
    const ms = Math.floor((total % 1) * 10);
    setDisplayTime(
      h > 0
        ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
        : `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${ms}`,
    );
  }, [localCountdown, phase, targetTime]);

  const isIdle = phase === "idle";
  const isActive =
    phase === "waiting" || phase === "calibrating" || phase === "token_check";
  const isRegistering = phase === "registering";
  const isDone = phase === "done";

  const phaseLabel = isActive
    ? "Kayıt saatine kalan"
    : isRegistering
      ? "Kayıt devam ediyor"
      : isDone
        ? "Tamamlandı"
        : hasTarget
          ? "Hazır"
          : "Canlı Saat";

  return (
    <div className="relative overflow-hidden">
      {/* Active state animated gradient */}
      {isActive && (
        <motion.div
          className="absolute inset-0 opacity-20"
          style={{
            background:
              "conic-gradient(from 0deg, oklch(0.70 0.18 195 / 20%), oklch(0.60 0.15 280 / 15%), oklch(0.65 0.18 165 / 20%), oklch(0.70 0.18 195 / 20%))",
            backgroundSize: "200% 200%",
          }}
          animate={{ rotate: [0, 360] }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        />
      )}

      {/* Registering pulse */}
      {isRegistering && (
        <motion.div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at center, oklch(0.70 0.20 30 / 12%), transparent 70%)",
          }}
          animate={{ opacity: [0.2, 0.5, 0.2], scale: [1, 1.05, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
      )}

      {/* Done glow */}
      {isDone && (
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at center, oklch(0.70 0.18 165 / 10%), transparent 70%)",
          }}
        />
      )}

      <div className="relative px-6 py-12 sm:py-14 text-center">
        {/* Dry-run badge */}
        {dryRun && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-4 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-500/10 text-amber-400 text-[11px] font-bold tracking-wider uppercase ring-1 ring-amber-500/20"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
            🧪 DRY RUN
          </motion.div>
        )}

        {/* Phase label */}
        <motion.p
          className="text-xs font-semibold text-muted-foreground/60 mb-4 tracking-[0.2em] uppercase"
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          key={phaseLabel}
        >
          {phaseLabel}
        </motion.p>

        {/* Main timer display — idle shows live clock, active shows countdown */}
        <motion.div
          key={`${phase}-${isIdle ? "live" : displayTime.length > 12 ? "text" : "num"}`}
          initial={{ opacity: 0, scale: 0.9, filter: "blur(8px)" }}
          animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
          transition={{ type: "spring", stiffness: 200, damping: 20 }}
          className={`font-mono font-black tracking-[0.06em] leading-none ${
            isRegistering
              ? "text-4xl sm:text-5xl bg-gradient-to-r from-orange-400 to-amber-300 bg-clip-text text-transparent"
              : isDone
                ? "text-4xl sm:text-5xl bg-gradient-to-r from-emerald-400 to-teal-300 bg-clip-text text-transparent"
                : isActive
                  ? "text-6xl sm:text-7xl text-gradient-primary"
                  : isIdle && !hasTarget
                    ? "text-5xl sm:text-6xl text-foreground/70"
                    : isIdle && hasTarget
                      ? "text-5xl sm:text-6xl text-gradient-primary"
                      : "text-5xl sm:text-6xl text-muted-foreground/40"
          }`}
        >
          {isIdle
            ? hasTarget
              ? targetTime
              : currentTime || "— : — : —"
            : displayTime}
        </motion.div>

        {/* Bottom info bar — context depends on state */}
        <div className="mt-5 flex items-center justify-center gap-6 text-xs font-mono text-muted-foreground/50">
          {isIdle && !hasTarget ? (
            <span className="text-muted-foreground/30 text-[10px]">
              Aşağıdan kayıt saatini belirle
            </span>
          ) : isIdle && hasTarget ? (
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary/50 animate-pulse" />
              <span className="text-muted-foreground/40 text-[10px]">
                Şu an
              </span>
              <span className="text-foreground/60">{currentTime}</span>
            </span>
          ) : (
            <>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary/50 animate-pulse" />
                <span className="text-muted-foreground/40 text-[10px]">
                  Şu an
                </span>
                <span className="text-foreground/60">{currentTime}</span>
              </span>
              {hasTarget && (
                <>
                  <span className="w-px h-3.5 bg-border/20" />
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500/50" />
                    <span className="text-muted-foreground/40 text-[10px]">
                      Hedef
                    </span>
                    <span className="text-foreground/60">{targetTime}</span>
                  </span>
                </>
              )}
            </>
          )}
        </div>

        {/* Progress bar */}
        {isActive && localCountdown !== null && localCountdown > 0 && (
          <div className="mt-7 mx-auto max-w-md">
            <div className="h-1 rounded-full bg-primary/8 overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-primary/40 via-primary to-primary/40"
                initial={{ width: "100%" }}
                animate={{ width: "0%" }}
                transition={{ duration: localCountdown, ease: "linear" }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
