"use client";

import { useEffect, useState, useMemo } from "react";
import { m, AnimatePresence } from "motion/react";
import { Clock, Pencil } from "lucide-react";

// Common ITU registration times
const QUICK_TIMES = [
  { label: "10:00", value: "10:00:00" },
  { label: "14:00", value: "14:00:00" },
];

interface CountdownTimerProps {
  targetTime: string | null;
  onTargetTimeChange: (v: string) => void;
  countdown: number | null;
  phase: string;
  dryRun?: boolean;
  disabled?: boolean;
}

export function CountdownTimer({
  targetTime,
  onTargetTimeChange,
  countdown,
  phase,
  dryRun,
  disabled,
}: CountdownTimerProps) {
  const [currentTime, setCurrentTime] = useState("");
  const [localCountdown, setLocalCountdown] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Prevent time editor flash during initial hydration
  useEffect(() => {
    setMounted(true); // eslint-disable-line react-hooks/set-state-in-effect -- one-time mount flag
  }, []);

  // null = config not loaded yet, "" = no time set, "HH:MM:SS" = time set
  const configLoaded = targetTime !== null;
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
    // eslint-disable-next-line react-hooks/set-state-in-effect -- prop-to-state sync for local interpolation
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
  }, [localCountdown !== null, phase]); // eslint-disable-line react-hooks/exhaustive-deps -- only re-run when countdown starts or phase changes

  // Split countdown into main part + fractional (ms) part — ms shown in primary
  const display = useMemo(() => {
    if (localCountdown === null || localCountdown <= 0) {
      if (phase === "registering") return { main: "KAYIT YAPILIYOR", ms: "" };
      if (phase === "done") return { main: "TAMAMLANDI", ms: "" };
      if (phase === "idle") return { main: "", ms: "" };
      return { main: targetTime ?? "--:--:--", ms: "" };
    }
    const total = Math.max(0, localCountdown);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = Math.floor(total % 60);
    const ms = Math.floor((total % 1) * 10);
    if (h > 0) {
      return {
        main: `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`,
        ms: "",
      };
    }
    return {
      main: `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`,
      ms: `.${ms}`,
    };
  }, [localCountdown, phase, targetTime]);

  const isIdle = phase === "idle";
  const isActive =
    phase === "waiting" || phase === "calibrating" || phase === "token_check";
  const isRegistering = phase === "registering";
  const isDone = phase === "done";

  // Last 5 seconds of waiting phase — urgency via scale (not glow)
  const isLastFive =
    isActive &&
    localCountdown !== null &&
    localCountdown > 0 &&
    localCountdown <= 5;
  const urgencyScale = isLastFive ? 1 + (1 - localCountdown / 5) * 0.12 : 1;

  const showTimeEditor =
    configLoaded && mounted && isIdle && (!hasTarget || editing) && !disabled;

  const phaseLabel = isActive
    ? "Hedefe kalan"
    : isRegistering
      ? "Kayıt devam ediyor"
      : isDone
        ? "Tamamlandı"
        : !configLoaded
          ? "Yükleniyor"
          : hasTarget
            ? "Hazır"
            : "Kayıt saatini ayarla";

  const handleTimeChange = (v: string) => {
    onTargetTimeChange(v && v.length === 5 ? v + ":00" : v);
  };

  const handleQuickTime = (value: string) => {
    onTargetTimeChange(value);
    setEditing(false);
  };

  // Big number color: registering = primary, done = status-ok, otherwise foreground
  const mainColor = isRegistering
    ? "text-primary"
    : isDone
      ? "text-[--status-ok]"
      : isIdle && !hasTarget
        ? "text-muted-foreground"
        : "text-foreground";

  return (
    <div
      className="relative px-6 py-12 text-center sm:py-14"
      role="timer"
      aria-live="assertive"
      aria-label="Geri sayım sayacı"
    >
      {/* Dry-run marker */}
      {dryRun && (
        <div className="mb-4 inline-flex items-center gap-2 border border-[--status-wait] px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-[--status-wait]">
          <span className="h-1.5 w-1.5 bg-[--status-wait]" />
          Dry Run
        </div>
      )}

      {/* Phase label */}
      <m.p
        className="panel-label mb-5"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        key={phaseLabel}
      >
        {phaseLabel}
      </m.p>

      {/* Main timer display */}
      <m.div
        key={`${phase}-${isIdle ? "live" : display.main.length > 12 ? "text" : "num"}`}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0, scale: urgencyScale }}
        transition={
          isLastFive
            ? { type: "tween", duration: 0.15 }
            : { type: "spring", stiffness: 220, damping: 24 }
        }
        className={`font-mono font-semibold leading-none tracking-tight ${
          display.main.length > 12
            ? "text-2xl sm:text-4xl"
            : "text-[2.6rem] sm:text-7xl"
        } ${isLastFive ? "text-primary" : mainColor}`}
      >
        {isIdle ? (
          hasTarget ? (
            targetTime
          ) : (
            currentTime || "--:--:--"
          )
        ) : (
          <>
            {display.main}
            {display.ms && <span className="text-primary">{display.ms}</span>}
          </>
        )}
      </m.div>

      {/* Idle + has target → edit button */}
      {isIdle && hasTarget && !editing && !disabled && (
        <m.button
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          onClick={() => setEditing(true)}
          className="mt-4 inline-flex items-center gap-1.5 border px-3 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <Pencil className="h-3 w-3" />
          Değiştir
        </m.button>
      )}

      {/* ═══ INLINE TIME PICKER ═══ */}
      <AnimatePresence>
        {showTimeEditor && (
          <m.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ type: "tween", duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            className="mt-6 overflow-hidden"
          >
            <div className="mx-auto max-w-xs space-y-3">
              {/* Time input */}
              <div className="relative">
                <Clock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="time"
                  step="1"
                  value={targetTime}
                  onChange={(e) => handleTimeChange(e.target.value)}
                  aria-label="Kayıt saati"
                  className={`h-11 w-full border bg-background pl-10 pr-4 text-center font-mono text-base transition-colors focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
                    !targetTime ? "border-primary text-muted-foreground" : ""
                  }`}
                  autoFocus={editing}
                />
              </div>

              {/* Quick time buttons */}
              <div className="flex flex-wrap items-center justify-center gap-1.5">
                {QUICK_TIMES.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => handleQuickTime(t.value)}
                    className={`border px-3 py-1 font-mono text-[11px] font-medium transition-colors ${
                      targetTime === t.value
                        ? "border-primary text-primary"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {editing && hasTarget && (
                <button
                  onClick={() => setEditing(false)}
                  className="text-[10px] text-muted-foreground transition-colors hover:text-foreground"
                >
                  Kapat
                </button>
              )}
            </div>
          </m.div>
        )}
      </AnimatePresence>

      {/* Bottom info bar */}
      <div
        className={`${showTimeEditor ? "mt-4" : "mt-6"} flex items-center justify-center gap-6 font-mono text-xs text-muted-foreground`}
      >
        {isIdle && !hasTarget && !showTimeEditor ? (
          <span className="text-[10px] text-muted-foreground/70">
            Yukarıdan kayıt saatini belirle
          </span>
        ) : isIdle && hasTarget ? (
          <span className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground/70">
              Şu an
            </span>
            <span className="text-foreground">{currentTime}</span>
          </span>
        ) : !isIdle ? (
          <>
            <span className="flex items-center gap-1.5">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground/70">
                Şu an
              </span>
              <span className="text-foreground">{currentTime}</span>
            </span>
            {hasTarget && (
              <>
                <span className="h-3.5 w-px bg-border" />
                <span className="flex items-center gap-1.5">
                  <span className="text-[10px] uppercase tracking-wider text-muted-foreground/70">
                    Hedef
                  </span>
                  <span className="text-foreground">{targetTime}</span>
                </span>
              </>
            )}
          </>
        ) : null}
      </div>

      {/* Progress bar */}
      {isActive && localCountdown !== null && localCountdown > 0 && (
        <div className="mx-auto mt-7 max-w-md">
          <div className="h-0.5 w-full overflow-hidden bg-muted">
            <m.div
              className="h-full bg-primary"
              initial={{ width: "100%" }}
              animate={{ width: "0%" }}
              transition={{ duration: localCountdown, ease: "linear" }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
