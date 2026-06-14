"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { m, AnimatePresence } from "motion/react";
import {
  Play,
  Square,
  Gauge,
  Volume2,
  VolumeX,
  RotateCcw,
} from "lucide-react";
import { toast } from "sonner";
import { useUser } from "@clerk/nextjs";
import { api, type CalibrationResult, type CourseInfo } from "@/lib/api";
import { ConfigService } from "@/lib/config-service";
import { useToken } from "@/lib/token-context";
import { useWebSocket } from "@/hooks/use-websocket";
import { useNotification } from "@/hooks/use-notification";
import { TokenInput } from "@/components/token-input";
import { CRNManager } from "@/components/crn-manager";
import { CalibrationCard } from "@/components/calibration-card";
import { CountdownTimer } from "@/components/countdown-timer";
import { LiveLogs } from "@/components/live-logs";
import { SettingsPanel } from "@/components/settings-panel";
import { PresetManager } from "@/components/preset-manager";
import { ConnectionStatus } from "@/components/connection-status";
import { WeeklySchedule } from "@/components/weekly-schedule";
import { Panel } from "@/components/panel";
import { SuccessOverlay } from "@/components/success-overlay";
import { DashboardSkeleton } from "@/components/dashboard-skeleton";

// ── Wrapper: kullanıcı değiştiğinde key ile tam remount sağlar ──
// Bu, tüm useState/useEffect/useRef'leri sıfırdan başlatır.
// useEffect-based state reset'ten çok daha güvenilir — hiç flash olmaz.
export function Dashboard() {
  const { user, isLoaded } = useUser();

  // Clerk yüklenene kadar bekle — double mount + flash önlenir
  if (!isLoaded) {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="skeleton h-8 w-8" />
      </div>
    );
  }

  return <DashboardContent key={user?.id ?? "anon"} />;
}

function DashboardContent() {
  // Auth
  const { user } = useUser();
  const clerkUserId = user?.id ?? null;

  // Config state — token sayfa-üstü context'te (navigasyonda korunur, diske yazılmaz)
  const { token, setToken } = useToken();
  const [tokenChanged, setTokenChanged] = useState(false);
  const [crnList, setCrnList] = useState<string[]>([]);
  const [scrnList, setScrnList] = useState<string[]>([]);
  const [kayitSaati, setKayitSaati] = useState<string | null>(null);
  const [maxDeneme, setMaxDeneme] = useState(60);
  const [retryAralik, setRetryAralik] = useState(3.0);
  const [dryRun, setDryRun] = useState(false);

  // UI state
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [calibrating, setCalibrating] = useState(false);
  const [starting, setStarting] = useState(false);
  const [calibrationData, setCalibrationData] =
    useState<CalibrationResult | null>(null);

  // WebSocket real-time data
  const ws = useWebSocket();

  // Notifications
  const notify = useNotification();

  // Course info from OBS API
  const [courseInfo, setCourseInfo] = useState<Record<string, CourseInfo>>({});
  const [lookingUpCRNs, setLookingUpCRNs] = useState<Set<string>>(new Set());

  const isRunning =
    ws.phase === "token_check" ||
    ws.phase === "calibrating" ||
    ws.phase === "waiting" ||
    ws.phase === "registering";

  const isDone = ws.phase === "done";

  // Success overlay: yalnızca CANLI tamamlanmada açılır (completionTick).
  // Ders Planı'ndan dönünce / reconnect'te backend hâlâ "done" olsa bile
  // overlay tekrar patlamaz — sonuç CRN listesinde + "Tamamlandı" etiketinde
  // zaten inline görünür.
  const [showSuccess, setShowSuccess] = useState(false);
  useEffect(() => {
    if (ws.completionTick > 0) setShowSuccess(true);
  }, [ws.completionTick]);

  // Guard: auto-save'in config load bitmeden cloud'u ezmesini engelle
  const initialLoadDone = useRef(false);
  const configReadyRef = useRef(false);
  const [configReady, setConfigReady] = useState(false);

  // Delayed skeleton: only show after 300ms, then keep for min 1 shimmer cycle
  const [showSkeleton, setShowSkeleton] = useState(false);
  const [minSkeletonDone, setMinSkeletonDone] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (!configReadyRef.current) setShowSkeleton(true);
    }, 300);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!showSkeleton) return;
    const timer = setTimeout(() => setMinSkeletonDone(true), 1800);
    return () => clearTimeout(timer);
  }, [showSkeleton]);

  // Kullanıcı değişiminde localStorage temizliği (defense-in-depth)
  // NOT: State sıfırlama artık gerekli değil — key prop ile tam remount oluyor
  useEffect(() => {
    if (!clerkUserId) return;
    const lastUser = localStorage.getItem("otostop-last-user");
    if (lastUser && lastUser !== clerkUserId) {
      localStorage.removeItem("otostop-presets");
      localStorage.removeItem("otostop-presets-owner");
      localStorage.removeItem("otostop-crn-labels");
      const calKeys: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key?.startsWith("otostop-cal-")) calKeys.push(key);
      }
      calKeys.forEach((k) => localStorage.removeItem(k));
      localStorage.removeItem("otostop_session_id");
    }
    localStorage.setItem("otostop-last-user", clerkUserId);
  }, [clerkUserId]);

  // Load config on mount (backend) + cloud sync on login
  useEffect(() => {
    initialLoadDone.current = false; // Auto-save'i kilitle
    (async () => {
      let loaded = false;
      try {
        const config = await api.getConfig();
        if (config.ecrn_list?.length) {
          setCrnList(config.ecrn_list);
          loaded = true;
        }
        if (config.scrn_list?.length) {
          setScrnList(config.scrn_list);
          loaded = true;
        }
        if (config.kayit_saati) {
          setKayitSaati(config.kayit_saati);
          loaded = true;
        }
        if (config.max_deneme) setMaxDeneme(config.max_deneme);
        setRetryAralik(Math.max(3, config.retry_aralik));
        if (config.dry_run) setDryRun(config.dry_run);
        if (config.token_set) setTokenValid(true);
      } catch {
        // Backend error
      }

      // Backend boşsa veya hata verdiyse cloud'dan da kontrol et
      if (!loaded && clerkUserId) {
        try {
          const cloud = await ConfigService.getUserConfig(clerkUserId);
          if (cloud) {
            if (cloud.ecrn_list?.length) setCrnList(cloud.ecrn_list);
            if (cloud.scrn_list?.length) setScrnList(cloud.scrn_list);
            if (cloud.kayit_saati) setKayitSaati(cloud.kayit_saati);
            if (cloud.max_deneme) setMaxDeneme(cloud.max_deneme);
            setRetryAralik(Math.max(3, cloud.retry_aralik));
            if (cloud.dry_run) setDryRun(cloud.dry_run);
          }
        } catch {
          // Cloud da erişilemez
        }
      }

      initialLoadDone.current = true; // Auto-save kilidini aç
      configReadyRef.current = true;
      setConfigReady(true);

      // Import CRNs from schedule builder if available
      const scheduleExport = localStorage.getItem("otostop-schedule-export");
      if (scheduleExport) {
        try {
          const importedCRNs = JSON.parse(scheduleExport) as string[];
          if (importedCRNs.length > 0) {
            setCrnList((prev) => {
              const existing = new Set(prev);
              const newCRNs = importedCRNs.filter((c) => !existing.has(c));
              if (newCRNs.length === 0) return prev;
              // Tek seferlik import bildirimi (mount'ta; key hemen siliniyor)
              toast.success(
                newCRNs.length === 1
                  ? "1 ders kayıt motoruna aktarıldı"
                  : `${newCRNs.length} ders kayıt motoruna aktarıldı`,
              );
              return [...prev, ...newCRNs];
            });
          }
        } catch {
          // Invalid JSON, ignore
        }
        localStorage.removeItem("otostop-schedule-export");
      }

      // null → "" : config loaded but no time was saved by user
      setKayitSaati((prev) => prev ?? "");
    })();
  }, [clerkUserId]);

  // Sync state from backend when WebSocket connects/reconnects
  const prevConnectedRef = useRef(false);
  useEffect(() => {
    if (ws.connected && !prevConnectedRef.current) {
      // WS just connected — check backend state
      api
        .getStatus()
        .then((status) => {
          if (
            status.running &&
            status.phase &&
            status.phase !== "idle" &&
            status.phase !== "done"
          ) {
            // Backend is running but frontend might be out of sync
            // WS events will take over from here
          }
        })
        .catch(() => {
          /* ignore — backend may be offline */
        });
    }
    prevConnectedRef.current = ws.connected;
  }, [ws.connected]);

  // Save config to backend
  const saveConfig = useCallback(async () => {
    try {
      await api.setConfig({
        ...(tokenChanged && token ? { token } : {}),
        ecrn_list: crnList,
        scrn_list: scrnList,
        kayit_saati: kayitSaati ?? "",
        max_deneme: maxDeneme,
        retry_aralik: retryAralik,
        dry_run: dryRun,
      });
    } catch {
      // silent fail for auto-save
    }
  }, [
    token,
    tokenChanged,
    crnList,
    scrnList,
    kayitSaati,
    maxDeneme,
    retryAralik,
    dryRun,
  ]);

  // Auto-save config on changes (backend + cloud)
  // Guard: config load tamamlanmadan kaydetme — yoksa boş state cloud'u ezer
  useEffect(() => {
    if (!initialLoadDone.current) return;
    const timer = setTimeout(() => {
      saveConfig();
      // Cloud sync (token excluded for security)
      if (clerkUserId) {
        ConfigService.saveUserConfig(clerkUserId, {
          ecrn_list: crnList,
          scrn_list: scrnList,
          kayit_saati: kayitSaati ?? "",
          max_deneme: maxDeneme,
          retry_aralik: retryAralik,
          dry_run: dryRun,
        });
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [
    token,
    crnList,
    scrnList,
    kayitSaati,
    maxDeneme,
    retryAralik,
    dryRun,
    saveConfig,
    clerkUserId,
  ]);

  // WebSocket'ten gelen kalibrasyon verisini de senkronize et
  useEffect(() => {
    if (ws.calibration) setCalibrationData(ws.calibration);
  }, [ws.calibration]);

  // Watch token changes
  useEffect(() => {
    setTokenValid(null);
    setTokenChanged(true);
  }, [token]);

  // Auto-lookup CRN course info from OBS
  const [lookupRetry, setLookupRetry] = useState(0);

  useEffect(() => {
    const allCRNs = [...new Set([...crnList, ...scrnList])];
    // Lookup CRNs we don't have OR that previously failed (no sessions + placeholder name)
    const missing = allCRNs.filter((crn) => {
      if (lookingUpCRNs.has(crn)) return false;
      const info = courseInfo[crn];
      if (!info) return true;
      // Retry CRNs that failed before (placeholder entries)
      if (
        info.sessions.length === 0 &&
        (info.course_name === "Yüklenemedi" ||
          info.course_name === "Bulunamadı")
      )
        return true;
      return false;
    });
    if (missing.length === 0) return;

    // Track in-flight to prevent duplicate requests
    setLookingUpCRNs((prev) => new Set([...prev, ...missing]));

    api
      .lookupCRNs(missing)
      .then((results) => {
        setCourseInfo((prev) => {
          const next = { ...prev };
          for (const crn of missing) {
            const info = results?.[crn];
            if (info && info.sessions?.length > 0) {
              next[crn] = info;
            } else if (info) {
              next[crn] = info;
            } else {
              next[crn] = {
                crn,
                course_code: crn,
                course_name: "Bulunamadı",
                instructor: "",
                teaching_method: "",
                capacity: 0,
                enrolled: 0,
                programmes: "",
                sessions: [],
              } as CourseInfo;
            }
          }
          return next;
        });
      })
      .catch(() => {
        // Mark failed CRNs with placeholder — will be retried
        setCourseInfo((prev) => {
          const next = { ...prev };
          for (const crn of missing) {
            if (!next[crn] || next[crn].course_name === "Yüklenemedi")
              next[crn] = {
                crn,
                course_code: crn,
                course_name: "Yüklenemedi",
                instructor: "",
                teaching_method: "",
                capacity: 0,
                enrolled: 0,
                programmes: "",
                sessions: [],
              } as CourseInfo;
          }
          return next;
        });
        // Schedule automatic retry (3s, 6s, 12s — max 3 retries)
        const MAX_RETRIES = 3;
        if (lookupRetry < MAX_RETRIES) {
          setTimeout(
            () => setLookupRetry((r) => r + 1),
            Math.min(3000 * Math.pow(2, lookupRetry), 12000),
          );
        }
      })
      .finally(() => {
        setLookingUpCRNs((prev) => {
          const next = new Set(prev);
          missing.forEach((crn) => next.delete(crn));
          return next;
        });
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [crnList, scrnList, lookupRetry]);

  // Calibrate
  const handleCalibrate = async () => {
    if (!token) {
      toast.error("Önce token gir");
      return;
    }
    setCalibrating(true);
    try {
      await saveConfig();
      const result = await api.calibrate();
      setCalibrationData(result);
      toast.success(
        `Kalibrasyon tamam: offset ${result.server_offset_ms >= 0 ? "+" : ""}${result.server_offset_ms?.toFixed(0)}ms, RTT ${result.rtt_one_way_ms?.toFixed(1)}ms`,
      );
    } catch (err) {
      toast.error(
        `Kalibrasyon hatası: ${err instanceof Error ? err.message : "Bilinmeyen hata"}`,
      );
    } finally {
      setCalibrating(false);
    }
  };

  // Start registration
  const handleStart = async () => {
    if (!token) {
      toast.error("Önce token gir");
      return;
    }
    if (crnList.length === 0) {
      toast.error("En az bir CRN ekle");
      return;
    }
    if (!kayitSaati || !/^\d{2}:\d{2}/.test(kayitSaati)) {
      toast.error(
        "Kayıt saati ayarlanmamış — Yapılandırma bölümünden saati gir",
      );
      return;
    }

    // Done/stuck state'den yeniden başlatıyorsak önce temizle
    if (ws.phase === "done" || ws.done) {
      try {
        await api.resetRegistration();
      } catch {
        /* temiz olabilir */
      }
      ws.softReset();
    }

    setStarting(true);
    // Request notification permission on first start
    notify.requestPermission();
    notify.playSound("start");
    try {
      await saveConfig();
      try {
        await api.startRegistration();
      } catch (err) {
        // 409 = stuck engine — auto-reset and retry once
        if (err instanceof Error && err.message.includes("zaten çalışıyor")) {
          toast.info("Önceki oturum temizleniyor...");
          await api.resetRegistration();
          await api.startRegistration();
        } else {
          throw err;
        }
      }
      toast.success(
        dryRun ? "DRY RUN başlatıldı" : "Kayıt süreci başlatıldı",
      );
    } catch (err) {
      toast.error(
        `Başlatma hatası: ${err instanceof Error ? err.message : "Bilinmeyen hata"}`,
      );
    } finally {
      setStarting(false);
    }
  };

  // Reset — done state'den idle'a dön (logları koru)
  const handleReset = async () => {
    try {
      await api.resetRegistration();
    } catch {
      /* temiz olabilir */
    }
    ws.softReset();
  };

  // Cancel
  const handleCancel = async () => {
    try {
      await api.cancelRegistration();
      // Backend emits done via WS, but add fallback in case WS event is missed
      setTimeout(() => {
        if (ws.phase !== "idle" && ws.phase !== "done") {
          ws.softReset();
        }
      }, 2000);
      toast.info("Kayıt iptal edildi");
    } catch (err) {
      toast.error(
        `İptal hatası: ${err instanceof Error ? err.message : "Bilinmeyen hata"}`,
      );
    }
  };

  // Toast + bildirim — yalnızca CANLI tamamlanmada (her remount'ta değil)
  useEffect(() => {
    if (ws.completionTick > 0) {
      const successCount = Object.values(ws.crnResults).filter(
        (r) => r.status === "success",
      ).length;
      const totalCount = Object.keys(ws.crnResults).length;
      if (successCount > 0) {
        toast.success(`${successCount} ders başarıyla kaydedildi`);
      } else {
        toast.warning("Kayıt süreci bitti, başarılı ders yok");
      }
      // Sound + browser notification
      notify.notifyResult(successCount, totalCount, ws.crnResults);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws.completionTick]);

  // Load preset handler
  const handleLoadPreset = useCallback(
    (preset: {
      ecrn_list: string[];
      scrn_list: string[];
      kayit_saati: string;
      max_deneme: number;
      retry_aralik: number;
    }) => {
      setCrnList(preset.ecrn_list);
      setScrnList(preset.scrn_list);
      setKayitSaati(preset.kayit_saati);
      setMaxDeneme(preset.max_deneme);
      setRetryAralik(Math.max(3, preset.retry_aralik));
      setDryRun(false); // Preset yüklendiğinde dry_run kapalı
    },
    [],
  );

  // Keyboard shortcuts: Ctrl+Enter = start, Escape = cancel
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ctrl+Enter → start registration
      if (
        e.ctrlKey &&
        e.key === "Enter" &&
        !isRunning &&
        token &&
        crnList.length > 0
      ) {
        e.preventDefault();
        handleStart();
      }
      // Escape → cancel registration
      if (e.key === "Escape" && isRunning) {
        e.preventDefault();
        handleCancel();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isRunning, token, crnList.length]); // eslint-disable-line react-hooks/exhaustive-deps -- handlers use latest state via closure

  // Dynamic page title based on engine phase
  useEffect(() => {
    const base = "İTÜ Otostop";
    switch (ws.phase) {
      case "token_check":
        document.title = `Token kontrol — ${base}`;
        break;
      case "calibrating":
        document.title = `Kalibrasyon — ${base}`;
        break;
      case "waiting": {
        if (ws.countdown !== null && ws.countdown > 0) {
          const total = Math.max(0, ws.countdown);
          const h = Math.floor(total / 3600);
          const m = Math.floor((total % 3600) / 60);
          const s = Math.floor(total % 60);
          const timeStr =
            h > 0
              ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
              : `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
          document.title = `${timeStr} — ${base}`;
        } else {
          document.title = `Bekleniyor — ${base}`;
        }
        break;
      }
      case "registering":
        document.title = `KAYIT YAPILIYOR — ${base}`;
        break;
      case "done":
        document.title = `TAMAMLANDI — ${base}`;
        break;
      default:
        document.title = base;
    }
    return () => {
      document.title = "İTÜ Otostop";
    };
  }, [ws.phase, ws.countdown]);

  // Staggered entrance spring config
  const springIn = { type: "spring" as const, stiffness: 300, damping: 30 };

  // Skeleton display logic:
  // - Config loads fast (<300ms): no skeleton, dashboard appears directly
  // - Config loads slow (>300ms): skeleton appears, stays for min 1 shimmer cycle
  const shouldShowContent = configReady && (!showSkeleton || minSkeletonDone);

  if (!shouldShowContent) {
    if (showSkeleton) return <DashboardSkeleton />;
    // Before 300ms: page.tsx provides background, just render nothing
    return null;
  }

  return (
    <>
      {/* Dashboard status bar */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-3">
        <m.div
          className="flex items-center justify-end gap-2"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={springIn}
        >
          <AnimatePresence>
            {dryRun && (
              <m.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="border border-status-wait px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-status-wait"
              >
                Dry Run
              </m.span>
            )}
          </AnimatePresence>
          <ConnectionStatus connected={ws.connected} latency={ws.latency} />
          <div className="h-4 w-px bg-border" />
          <button
            onClick={notify.toggleMute}
            className="flex h-7 w-7 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
            title={notify.muted ? "Sesi aç" : "Sessize al"}
          >
            {notify.muted ? (
              <VolumeX className="h-3.5 w-3.5" />
            ) : (
              <Volume2 className="h-3.5 w-3.5" />
            )}
          </button>
        </m.div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* ═══ HERO: Countdown + Actions (always full width) ═══ */}
        <m.section
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...springIn, delay: 0.05 }}
        >
          <Panel>
            <CountdownTimer
              targetTime={kayitSaati}
              onTargetTimeChange={(t) => setKayitSaati(t)}
              countdown={ws.countdown}
              phase={ws.phase}
              dryRun={dryRun}
              disabled={isRunning}
            />

            {/* Action buttons — inside hero card */}
            <div className="flex gap-3 border-t p-4 sm:px-6">
              {isDone ? (
                <>
                  <button
                    onClick={handleReset}
                    className="flex h-11 flex-1 items-center justify-center gap-2 border text-sm font-medium transition-colors hover:bg-accent sm:h-10"
                  >
                    <RotateCcw className="h-4 w-4" />
                    Yeni Kayıt
                  </button>
                  <button
                    onClick={handleStart}
                    disabled={starting || !token || crnList.length === 0}
                    className="flex h-11 flex-1 items-center justify-center gap-2 bg-primary text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:pointer-events-none disabled:opacity-30 sm:h-10"
                  >
                    <Play className="h-4 w-4" />
                    {starting ? "Başlatılıyor..." : "Tekrar Başlat"}
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={handleCalibrate}
                    disabled={calibrating || isRunning || !token}
                    className="flex h-11 flex-1 items-center justify-center gap-2 border text-sm font-medium transition-colors hover:bg-accent disabled:pointer-events-none disabled:opacity-30 sm:h-10"
                  >
                    <Gauge className="h-4 w-4" />
                    {calibrating ? "Kalibre ediliyor..." : "Kalibre Et"}
                  </button>
                  {!isRunning ? (
                    <button
                      onClick={handleStart}
                      disabled={starting || !token || crnList.length === 0}
                      className={`flex h-11 flex-1 items-center justify-center gap-2 text-sm font-semibold transition-colors disabled:pointer-events-none disabled:opacity-30 sm:h-10 ${
                        dryRun
                          ? "border border-status-wait text-status-wait hover:bg-status-wait/10"
                          : "bg-primary text-primary-foreground hover:bg-primary/90"
                      }`}
                    >
                      <Play className="h-4 w-4" />
                      {starting
                        ? "Başlatılıyor..."
                        : dryRun
                          ? "Dry Run Başlat"
                          : "Kayıt Başlat"}
                    </button>
                  ) : (
                    <button
                      onClick={handleCancel}
                      className="flex h-11 flex-1 items-center justify-center gap-2 border border-destructive text-sm font-semibold text-destructive transition-colors hover:bg-destructive/10 sm:h-10"
                    >
                      <Square className="h-4 w-4" />
                      İptal Et
                    </button>
                  )}
                </>
              )}
            </div>
          </Panel>
        </m.section>

        {/* ═══ 2-COLUMN LAYOUT: Config (left) + Monitor (right) ═══ */}
        <div className="flex flex-col lg:grid lg:grid-cols-12 gap-5 lg:gap-6">
          {/* ── Left Column: Yapılandırma ── */}
          <div className="lg:col-span-6 space-y-5">
            <m.div
              className="flex items-center gap-2.5 px-1"
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ ...springIn, delay: 0.1 }}
            >
              <div className="h-3 w-0.5 bg-primary" />
              <span className="panel-label">Yapılandırma</span>
            </m.div>

            {/* Token */}
            <m.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...springIn, delay: 0.13 }}
            >
              <Panel className="h-full">
                <TokenInput
                  token={token}
                  onTokenChange={(t) =>
                    setToken(t.replace(/^\s*bearer\s+/i, "").trim())
                  }
                  tokenValid={tokenValid}
                />
              </Panel>
            </m.div>

            {/* CRN Manager */}
            <m.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...springIn, delay: 0.16 }}
            >
              <Panel className="h-full">
                <CRNManager
                  ecrnList={crnList}
                  onEcrnListChange={setCrnList}
                  scrnList={scrnList}
                  onScrnListChange={setScrnList}
                  crnResults={ws.crnResults}
                  courseInfo={courseInfo}
                  lookingUp={lookingUpCRNs}
                  disabled={isRunning}
                />
              </Panel>
            </m.div>

            {/* Settings */}
            <m.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...springIn, delay: 0.19 }}
            >
              <Panel className="h-full">
                <SettingsPanel
                  maxDeneme={maxDeneme}
                  onMaxDenemeChange={setMaxDeneme}
                  retryAralik={retryAralik}
                  onRetryAralikChange={setRetryAralik}
                  dryRun={dryRun}
                  onDryRunChange={setDryRun}
                  disabled={isRunning}
                />
              </Panel>
            </m.div>
          </div>

          {/* ── Right Column: İzleme ── */}
          <div className="lg:col-span-6 space-y-5">
            <m.div
              className="flex items-center gap-2.5 px-1"
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ ...springIn, delay: 0.1 }}
            >
              <div className="h-3 w-0.5 bg-primary" />
              <span className="panel-label">İzleme</span>
            </m.div>

            {/* Calibration */}
            <m.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...springIn, delay: 0.13 }}
            >
              <Panel className="h-full">
                <CalibrationCard
                  calibration={ws.calibration ?? calibrationData}
                  loading={calibrating}
                  token={token}
                />
              </Panel>
            </m.div>

            {/* Live Logs */}
            <m.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...springIn, delay: 0.16 }}
            >
              <Panel className="h-full">
                <LiveLogs logs={ws.logs} onClear={ws.clearLogs} />
              </Panel>
            </m.div>

            {/* Presets */}
            <m.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...springIn, delay: 0.19 }}
            >
              <Panel className="h-full">
                <PresetManager
                  currentConfig={{
                    ecrn_list: crnList,
                    scrn_list: scrnList,
                    kayit_saati: kayitSaati ?? "",
                    max_deneme: maxDeneme,
                    retry_aralik: retryAralik,
                  }}
                  onLoadPreset={handleLoadPreset}
                  courseLabels={Object.fromEntries(
                    Object.entries(courseInfo).map(([crn, info]) => [
                      crn,
                      info.course_code,
                    ]),
                  )}
                  disabled={isRunning}
                />
              </Panel>
            </m.div>
          </div>
        </div>

        {/* ═══ FULL WIDTH: Schedule ═══ */}
        <m.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...springIn, delay: 0.28 }}
        >
          <Panel>
            <WeeklySchedule
              courses={courseInfo}
              crnList={[...new Set([...crnList, ...scrnList])]}
              loading={lookingUpCRNs.size > 0}
            />
          </Panel>
        </m.section>
      </div>

      {/* Footer */}
      <footer className="mt-16 border-t">
        <div className="mx-auto max-w-7xl space-y-2 px-4 py-6 text-center sm:px-6">
          <p className="text-[11px] font-medium text-muted-foreground/50">
            İTÜ Otostop — Ders Kayıt Otomasyon Aracı v1.0.0 —{" "}
            {new Date().getFullYear()}
          </p>
          <p className="text-[10px] text-muted-foreground/40">
            Bu araç bağımsız bir projedir, İTÜ ile resmi bir bağlantısı yoktur.
            Kullanım sorumluluğu kullanıcıya aittir.
          </p>
          <div className="flex items-center justify-center gap-3 text-[10px] text-muted-foreground/40">
            <a
              href="mailto:nubealbor@gmail.com?subject=İTÜ Otostop - Sorun Bildirimi"
              className="underline underline-offset-2 transition-colors hover:text-foreground"
            >
              Sorun Bildir
            </a>
            <span>·</span>
            <span>Verileriniz yalnızca tarayıcınızda saklanır</span>
          </div>
        </div>
      </footer>

      {/* Success overlay — sadece canlı tamamlanmada */}
      <SuccessOverlay
        show={showSuccess}
        results={Object.entries(ws.crnResults).map(([crn, r]) => ({
          crn,
          status: r.status,
          label: courseInfo[crn]?.course_name
            ? `${crn} — ${courseInfo[crn].course_name}`
            : crn,
        }))}
        onDismiss={() => setShowSuccess(false)}
      />
    </>
  );
}
