"use client";

import { useEffect, useRef, useCallback } from "react";
import { m, AnimatePresence } from "motion/react";
import { CheckCircle2, PartyPopper } from "lucide-react";
import confetti from "canvas-confetti";

interface SuccessOverlayProps {
  show: boolean;
  results?: Array<{
    crn: string;
    status: string;
    label?: string;
  }>;
  onDismiss?: () => void;
}

export function SuccessOverlay({
  show,
  results = [],
  onDismiss,
}: SuccessOverlayProps) {
  const firedRef = useRef(false);

  const fireConfetti = useCallback(() => {
    // Burst from left and right
    const defaults = {
      startVelocity: 30,
      spread: 360,
      ticks: 60,
      zIndex: 9999,
    };

    confetti({
      ...defaults,
      particleCount: 50,
      origin: { x: 0.2, y: 0.6 },
      colors: ["#10b981", "#06b6d4", "#3b82f6", "#8b5cf6"],
    });

    confetti({
      ...defaults,
      particleCount: 50,
      origin: { x: 0.8, y: 0.6 },
      colors: ["#10b981", "#06b6d4", "#3b82f6", "#8b5cf6"],
    });

    // Delayed center burst
    setTimeout(() => {
      confetti({
        particleCount: 80,
        spread: 100,
        origin: { x: 0.5, y: 0.4 },
        colors: ["#10b981", "#34d399", "#6ee7b7", "#a7f3d0"],
        zIndex: 9999,
      });
    }, 300);
  }, []);

  useEffect(() => {
    if (show && !firedRef.current) {
      firedRef.current = true;
      fireConfetti();
    }
    if (!show) {
      firedRef.current = false;
    }
  }, [show, fireConfetti]);

  const successCount = results.filter(
    (r) => r.status === "success" || r.status === "already",
  ).length;
  const failCount = results.filter(
    (r) =>
      r.status !== "success" &&
      r.status !== "already" &&
      r.status !== "pending",
  ).length;

  return (
    <AnimatePresence>
      {show && (
        <m.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-background/60 backdrop-blur-sm"
          onClick={onDismiss}
        >
          <m.div
            initial={{ opacity: 0, scale: 0.8, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: -10 }}
            transition={{
              type: "spring",
              stiffness: 300,
              damping: 25,
              delay: 0.1,
            }}
            onClick={(e) => e.stopPropagation()}
            className="relative max-w-sm w-full mx-4 rounded-2xl bg-card border border-border/20 shadow-2xl overflow-hidden"
          >
            {/* Success glow */}
            <div
              className="absolute inset-0 opacity-20"
              style={{
                background:
                  "radial-gradient(ellipse at center top, oklch(0.7 0.18 165 / 30%), transparent 70%)",
              }}
            />

            <div className="relative px-6 py-8 text-center">
              {/* Animated checkmark */}
              <m.div
                initial={{ scale: 0, rotate: -180 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{
                  type: "spring",
                  stiffness: 200,
                  damping: 15,
                  delay: 0.2,
                }}
                className="mx-auto mb-4 h-16 w-16 rounded-full bg-emerald-500/10 flex items-center justify-center"
              >
                <CheckCircle2 className="h-8 w-8 text-emerald-500" />
              </m.div>

              <m.h2
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="text-xl font-bold mb-1"
              >
                Kayıt Tamamlandı!
              </m.h2>

              <m.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
                className="text-sm text-muted-foreground mb-5"
              >
                {successCount > 0 && (
                  <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                    {successCount} ders başarılı
                  </span>
                )}
                {successCount > 0 && failCount > 0 && " · "}
                {failCount > 0 && (
                  <span className="text-red-600 dark:text-red-400 font-medium">
                    {failCount} başarısız
                  </span>
                )}
                {successCount === 0 && failCount === 0 && "İşlem tamamlandı"}
              </m.p>

              {/* CRN Results list */}
              {results.length > 0 && (
                <m.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.5 }}
                  className="space-y-1.5 mb-5 max-h-40 overflow-y-auto"
                >
                  {results.map((r, i) => (
                    <div
                      key={`${r.crn}-${i}`}
                      className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-mono ${
                        r.status === "success" || r.status === "already"
                          ? "bg-emerald-500/8 text-emerald-700 dark:text-emerald-400"
                          : r.status === "pending"
                            ? "bg-muted/40 text-muted-foreground"
                            : "bg-red-500/8 text-red-700 dark:text-red-400"
                      }`}
                    >
                      <span>{r.label || r.crn}</span>
                      <span className="text-[10px] font-medium uppercase">
                        {r.status === "success"
                          ? "✓ Başarılı"
                          : r.status === "already"
                            ? "✓ Zaten kayıtlı"
                            : r.status === "full"
                              ? "Kontenjan dolu"
                              : r.status === "conflict"
                                ? "Çakışma"
                                : r.status === "pending"
                                  ? "Bekliyor"
                                  : "Hata"}
                      </span>
                    </div>
                  ))}
                </m.div>
              )}

              {/* Dismiss button */}
              <m.button
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6 }}
                onClick={onDismiss}
                className="w-full h-10 rounded-xl bg-primary/10 hover:bg-primary/20 text-primary text-sm font-medium transition-colors flex items-center justify-center gap-2"
              >
                <PartyPopper className="h-4 w-4" />
                Tamam
              </m.button>
            </div>
          </m.div>
        </m.div>
      )}
    </AnimatePresence>
  );
}
