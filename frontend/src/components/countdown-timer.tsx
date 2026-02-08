"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";

interface CountdownTimerProps {
  targetTime: string;
  countdown: number | null;
  phase: string;
}

export function CountdownTimer({
  targetTime,
  countdown,
  phase,
}: CountdownTimerProps) {
  const [displayTime, setDisplayTime] = useState("--:--:--");
  const [localCountdown, setLocalCountdown] = useState<number | null>(null);

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
      else setDisplayTime(targetTime);
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
        : `Hedef → ${targetTime}`;

  return (
    <div className="relative overflow-hidden rounded-2xl">
      {/* Background layers */}
      <div className="absolute inset-0 glass" />

      {/* Active state animated gradient */}
      {isActive && (
        <motion.div
          className="absolute inset-0 opacity-30"
          style={{
            background:
              "linear-gradient(135deg, oklch(0.70 0.18 195 / 30%), oklch(0.60 0.15 280 / 20%), oklch(0.70 0.18 195 / 30%))",
            backgroundSize: "200% 200%",
          }}
          animate={{ backgroundPosition: ["0% 0%", "100% 100%", "0% 0%"] }}
          transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
        />
      )}

      {/* Registering pulse */}
      {isRegistering && (
        <motion.div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(135deg, oklch(0.70 0.20 30 / 15%), oklch(0.65 0.22 45 / 10%))",
          }}
          animate={{ opacity: [0.3, 0.7, 0.3] }}
          transition={{ duration: 1.2, repeat: Infinity }}
        />
      )}

      {/* Done glow */}
      {isDone && (
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(135deg, oklch(0.70 0.18 165 / 10%), oklch(0.65 0.15 195 / 8%))",
          }}
        />
      )}

      <div className="relative px-6 py-10 text-center">
        {/* Phase label */}
        <motion.p
          className="text-sm font-medium text-muted-foreground mb-3 tracking-wide uppercase"
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          key={phaseLabel}
        >
          {phaseLabel}
        </motion.p>

        {/* Main timer display */}
        <motion.div
          key={`${phase}-${displayTime.length > 12 ? "text" : "num"}`}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", stiffness: 300, damping: 25 }}
          className={`font-mono font-bold tracking-[0.08em] leading-none ${
            isRegistering
              ? "text-3xl sm:text-4xl text-orange-400"
              : isDone
                ? "text-3xl sm:text-4xl text-emerald-400"
                : isActive
                  ? "text-5xl sm:text-6xl text-primary"
                  : "text-4xl sm:text-5xl text-muted-foreground/60"
          }`}
        >
          {displayTime}
        </motion.div>

        {/* Progress bar */}
        {isActive && localCountdown !== null && localCountdown > 0 && (
          <div className="mt-6 mx-auto max-w-sm">
            <div className="h-0.75 rounded-full bg-primary/10 overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-linear-to-r from-primary/60 to-primary"
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
