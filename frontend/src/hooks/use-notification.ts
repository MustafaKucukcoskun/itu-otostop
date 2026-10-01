"use client";

import { useCallback, useRef, useState, useEffect } from "react";
import { isOk, ozetMetni } from "@/lib/crn-status";

// ── Web Audio beep generator ──

function createBeep(
  ctx: AudioContext,
  freq: number,
  duration: number,
  startTime: number,
  gain: number = 0.15,
) {
  const osc = ctx.createOscillator();
  const vol = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = freq;
  vol.gain.setValueAtTime(gain, startTime);
  vol.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
  osc.connect(vol);
  vol.connect(ctx.destination);
  osc.start(startTime);
  osc.stop(startTime + duration);
}

type SoundType = "success" | "error" | "warning" | "start";

const SOUND_PATTERNS: Record<SoundType, [number, number][]> = {
  // [frequency, delay_from_start]
  success: [
    [523, 0], // C5
    [659, 0.15], // E5
    [784, 0.3], // G5
  ],
  error: [
    [494, 0], // B4
    [392, 0.2], // G4
  ],
  warning: [
    [440, 0], // A4
    [440, 0.25], // A4 repeat
  ],
  start: [
    [523, 0], // C5
    [659, 0.12], // E5
  ],
};

// ── Hook ──

export function useNotification() {
  const audioCtxRef = useRef<AudioContext | null>(null);
  const [muted, setMuted] = useState(false);

  // Restore mute preference (useEffect required — localStorage unavailable during SSR)
  useEffect(() => {
    try {
      const saved = localStorage.getItem("otostop-muted");
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (saved === "true") setMuted(true);
    } catch {
      /* ignore */
    }
  }, []);

  // Persist mute preference
  const toggleMute = useCallback(() => {
    setMuted((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("otostop-muted", String(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  // Initialize AudioContext lazily (must be after user gesture)
  const getAudioCtx = useCallback(() => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new AudioContext();
    }
    if (audioCtxRef.current.state === "suspended") {
      audioCtxRef.current.resume();
    }
    return audioCtxRef.current;
  }, []);

  // Play a sound pattern
  const playSound = useCallback(
    (type: SoundType) => {
      if (muted) return;
      try {
        const ctx = getAudioCtx();
        const now = ctx.currentTime;
        const pattern = SOUND_PATTERNS[type];
        for (const [freq, delay] of pattern) {
          createBeep(ctx, freq, 0.18, now + delay);
        }
      } catch {
        /* audio not available */
      }
    },
    [muted, getAudioCtx],
  );

  // Request browser notification permission
  const requestPermission = useCallback(async () => {
    if (typeof Notification === "undefined") return false;
    if (Notification.permission === "granted") return true;
    if (Notification.permission === "denied") return false;
    const result = await Notification.requestPermission();
    return result === "granted";
  }, []);

  // Send browser notification
  const sendNotification = useCallback(
    (title: string, body: string, icon?: string) => {
      if (muted) return;
      if (typeof Notification === "undefined") return;
      if (Notification.permission !== "granted") return;

      // Don't notify if tab is focused
      if (document.visibilityState === "visible") return;

      try {
        new Notification(title, {
          body,
          icon: icon || "/favicon.ico",
          tag: "otostop-registration",
          renotify: true,
        } as NotificationOptions);
      } catch {
        /* notification not supported */
      }
    },
    [muted],
  );

  // Convenience: notify registration result
  const notifyResult = useCallback(
    (
      results: Record<string, { status: string; message: string }>,
      dryRun: boolean,
    ) => {
      if (dryRun) {
        playSound("warning");
        sendNotification(
          "Dry run bitti",
          "Gerçek kayıt yapılmadı — zamanlama sonucu uygulamada.",
        );
        return;
      }
      const ozet = ozetMetni(results);
      if (ozet) {
        playSound("success");
        const body = Object.entries(results)
          .filter(([, r]) => isOk(r.status))
          .map(([crn]) => crn)
          .join(", ");
        // Eski başlık "1/3" diyerek eksik kalanı ima ediyordu; o bilgi
        // telefondan bildirime bakan öğrenci için kaybolmamalı.
        const basarisiz = Object.values(results).filter(
          (r) => !isOk(r.status),
        ).length;
        sendNotification(
          `${ozet} 🎉`,
          `CRN: ${body}` + (basarisiz ? ` · ${basarisiz} başarısız` : ""),
        );
      } else {
        playSound("error");
        sendNotification(
          "Kayıt Başarısız",
          "Hiçbir ders kaydedilemedi. Detaylar için uygulamayı kontrol edin.",
        );
      }
    },
    [playSound, sendNotification],
  );

  return {
    muted,
    toggleMute,
    playSound,
    requestPermission,
    sendNotification,
    notifyResult,
  };
}
