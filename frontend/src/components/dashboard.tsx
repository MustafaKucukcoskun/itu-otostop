"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Play, Square, Gauge, Zap, Volume2, VolumeX } from "lucide-react";
import { toast } from "sonner";
import { UserButton, useUser } from "@clerk/nextjs";
import { api, type CalibrationResult, type CourseInfo } from "@/lib/api";
import { ConfigService } from "@/lib/config-service";
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
import { ThemeToggle } from "@/components/theme-toggle";
import { WeeklySchedule } from "@/components/weekly-schedule";
import { SpotlightCard } from "@/components/spotlight-card";

export function Dashboard() {
  // Auth
  const { user } = useUser();
  const clerkUserId = user?.id ?? null;

  // Config state
  const [token, setToken] = useState("");
  const [tokenChanged, setTokenChanged] = useState(false);
  const [crnList, setCrnList] = useState<string[]>([]);
  const [scrnList, setScrnList] = useState<string[]>([]);
  const [kayitSaati, setKayitSaati] = useState("");
  const [maxDeneme, setMaxDeneme] = useState(60);
  const [retryAralik, setRetryAralik] = useState(3.0);
  const [gecikmeBuffer, setGecikmeBuffer] = useState(0.005);
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

  // Load config on mount (backend) + cloud sync on login
  useEffect(() => {
    (async () => {
      try {
        const config = await api.getConfig();
        if (config.ecrn_list?.length) setCrnList(config.ecrn_list);
        if (config.scrn_list?.length) setScrnList(config.scrn_list);
        if (config.kayit_saati) setKayitSaati(config.kayit_saati);
        if (config.max_deneme) setMaxDeneme(config.max_deneme);
        if (config.retry_aralik)
          setRetryAralik(Math.max(3, config.retry_aralik));
        if (config.gecikme_buffer) setGecikmeBuffer(config.gecikme_buffer);
        if (config.dry_run) setDryRun(config.dry_run);
        if (config.token_set) setTokenValid(true);
      } catch {
        // Backend not running yet — try cloud
        if (clerkUserId) {
          const cloud = await ConfigService.getUserConfig(clerkUserId);
          if (cloud) {
            if (cloud.ecrn_list?.length) setCrnList(cloud.ecrn_list);
            if (cloud.scrn_list?.length) setScrnList(cloud.scrn_list);
            if (cloud.kayit_saati) setKayitSaati(cloud.kayit_saati);
            if (cloud.max_deneme) setMaxDeneme(cloud.max_deneme);
            if (cloud.retry_aralik)
              setRetryAralik(Math.max(3, cloud.retry_aralik));
            if (cloud.gecikme_buffer) setGecikmeBuffer(cloud.gecikme_buffer);
            if (cloud.dry_run) setDryRun(cloud.dry_run);
          }
        }
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clerkUserId]);

  // Sync state from backend when WebSocket connects/reconnects
  const prevConnectedRef = useRef(false);
  useEffect(() => {
    if (ws.connected && !prevConnectedRef.current) {
      // WS just connected — check backend state
      api.getStatus().then((status) => {
        if (status.running && status.phase && status.phase !== "idle" && status.phase !== "done") {
          // Backend is running but frontend might be out of sync
          // WS events will take over from here
        }
      }).catch(() => { /* ignore — backend may be offline */ });
    }
    prevConnectedRef.current = ws.connected;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws.connected]);

  // Save config to backend
  const saveConfig = useCallback(async () => {
    try {
      await api.setConfig({
        ...(tokenChanged && token ? { token } : {}),
        ecrn_list: crnList,
        scrn_list: scrnList,
        kayit_saati: kayitSaati,
        max_deneme: maxDeneme,
        retry_aralik: retryAralik,
        gecikme_buffer: gecikmeBuffer,
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
    gecikmeBuffer,
    dryRun,
  ]);

  // Auto-save config on changes (backend + cloud)
  useEffect(() => {
    const timer = setTimeout(() => {
      saveConfig();
      // Cloud sync (token excluded for security)
      if (clerkUserId) {
        ConfigService.saveUserConfig(clerkUserId, {
          ecrn_list: crnList,
          scrn_list: scrnList,
          kayit_saati: kayitSaati,
          max_deneme: maxDeneme,
          retry_aralik: retryAralik,
          gecikme_buffer: gecikmeBuffer,
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
    gecikmeBuffer,
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
        setTimeout(
          () => setLookupRetry((r) => r + 1),
          Math.min(3000 * Math.pow(2, lookupRetry), 12000),
        );
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
        dryRun ? "🧪 DRY RUN başlatıldı!" : "Kayıt süreci başlatıldı!",
      );
    } catch (err) {
      toast.error(
        `Başlatma hatası: ${err instanceof Error ? err.message : "Bilinmeyen hata"}`,
      );
    } finally {
      setStarting(false);
    }
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

  // Show toast + notification on done
  useEffect(() => {
    if (ws.done) {
      const successCount = Object.values(ws.crnResults).filter(
        (r) => r.status === "success",
      ).length;
      const totalCount = Object.keys(ws.crnResults).length;
      if (successCount > 0) {
        toast.success(`${successCount} ders başarıyla kaydedildi! 🎉`);
      } else {
        toast.warning("Kayıt süreci bitti, başarılı ders yok");
      }
      // Sound + browser notification
      notify.notifyResult(successCount, totalCount, ws.crnResults);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws.done]);

  // Load preset handler
  const handleLoadPreset = useCallback(
    (preset: {
      ecrn_list: string[];
      scrn_list: string[];
      kayit_saati: string;
      max_deneme: number;
      retry_aralik: number;
      gecikme_buffer: number;
    }) => {
      setCrnList(preset.ecrn_list);
      setScrnList(preset.scrn_list);
      setKayitSaati(preset.kayit_saati);
      setMaxDeneme(preset.max_deneme);
      setRetryAralik(Math.max(3, preset.retry_aralik));
      setGecikmeBuffer(preset.gecikme_buffer);
    },
    [],
  );

  // Staggered entrance spring config
  const springIn = { type: "spring" as const, stiffness: 300, damping: 30 };

  return (
    <div className="min-h-screen mesh-bg relative">
      {/* Background layers */}
      <div className="dot-grid fixed inset-0 pointer-events-none z-0" />
      <div className="mesh-orb-accent" />
      <div className="grain-overlay" />

      {/* Header */}
      <header className="sticky top-0 z-50 glass border-b border-border/10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <motion.div
            className="flex items-center gap-3"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={springIn}
          >
            <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center ring-1 ring-primary/20">
              <Zap className="h-4 w-4 text-primary" />
            </div>
            <h1 className="text-sm font-bold tracking-tight text-gradient-primary">
              İTÜ Otostop
            </h1>
            <AnimatePresence>
              {dryRun && (
                <motion.span
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 text-[10px] font-bold tracking-wider ring-1 ring-amber-500/20"
                >
                  DRY RUN
                </motion.span>
              )}
            </AnimatePresence>
          </motion.div>
          <motion.div
            className="flex items-center gap-2"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={springIn}
          >
            <ConnectionStatus connected={ws.connected} latency={ws.latency} />
            <div className="w-px h-5 bg-border/20" />
            <button
              onClick={notify.toggleMute}
              className="h-8 w-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-all duration-200"
              title={notify.muted ? "Sesi aç" : "Sessize al"}
            >
              {notify.muted ? (
                <VolumeX className="h-4 w-4" />
              ) : (
                <Volume2 className="h-4 w-4" />
              )}
            </button>
            <ThemeToggle />
            <UserButton
              appearance={{
                elements: {
                  avatarBox: "h-8 w-8",
                },
              }}
            />
          </motion.div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 relative z-10">
        <div className="space-y-8">
          {/* ═══ SECTION 1: Hero — Countdown + Actions ═══ */}
          <motion.section
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...springIn, delay: 0.05 }}
          >
            <SpotlightCard
              className="glass"
              spotlightColor="oklch(0.7 0.18 195 / 0.08)"
              spotlightSize={500}
              accent="oklch(0.7 0.18 195)"
            >
              <CountdownTimer
                targetTime={kayitSaati}
                countdown={ws.countdown}
                phase={ws.phase}
                dryRun={dryRun}
              />

              {/* Action buttons — inside hero card */}
              <div className="px-6 pb-6 flex gap-3">
                <button
                  onClick={handleCalibrate}
                  disabled={calibrating || isRunning || !token}
                  className="flex-1 h-11 sm:h-10 rounded-xl ring-1 ring-border/20 bg-background/40 hover:bg-muted/40 text-sm font-medium flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-30 disabled:pointer-events-none hover:ring-border/40"
                >
                  <Gauge className="h-4 w-4" />
                  {calibrating ? "Kalibre ediliyor..." : "Kalibre Et"}
                </button>
                {!isRunning ? (
                  <button
                    onClick={handleStart}
                    disabled={starting || !token || crnList.length === 0}
                    className={`flex-1 h-11 sm:h-10 rounded-xl text-white text-sm font-bold flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-30 disabled:pointer-events-none ${
                      dryRun
                        ? "bg-gradient-to-r from-amber-600 to-orange-500 hover:from-amber-500 hover:to-orange-400 shadow-lg shadow-amber-500/20"
                        : "bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 shadow-lg shadow-emerald-500/20"
                    }`}
                  >
                    <Play className="h-4 w-4" />
                    {starting
                      ? "Başlatılıyor..."
                      : dryRun
                        ? "🧪 Dry Run Başlat"
                        : "Kayıt Başlat"}
                  </button>
                ) : (
                  <button
                    onClick={handleCancel}
                    className="flex-1 h-11 sm:h-10 rounded-xl bg-gradient-to-r from-red-600 to-rose-500 hover:from-red-500 hover:to-rose-400 text-white text-sm font-bold flex items-center justify-center gap-2 transition-all duration-200 shadow-lg shadow-red-500/20"
                  >
                    <Square className="h-4 w-4" />
                    İptal Et
                  </button>
                )}
              </div>
            </SpotlightCard>
          </motion.section>

          {/* ═══ SECTION 2: Setup — Token + CRN Manager ═══ */}
          <section>
            <motion.div
              className="flex items-center gap-2 mb-4 px-1"
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ ...springIn, delay: 0.12 }}
            >
              <div className="h-1 w-6 rounded-full bg-gradient-to-r from-blue-400 to-cyan-400" />
              <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                Hazırlık
              </span>
            </motion.div>

            <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
              {/* Token — narrower */}
              <motion.div
                className="lg:col-span-2"
                initial={{ opacity: 0, y: 20, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ ...springIn, delay: 0.15 }}
              >
                <SpotlightCard
                  className="glass h-full"
                  spotlightColor="oklch(0.65 0.18 240 / 0.10)"
                  accent="oklch(0.65 0.2 240)"
                >
                  <TokenInput
                    token={token}
                    onTokenChange={(t) =>
                      setToken(t.replace(/^\s*bearer\s+/i, "").trim())
                    }
                    tokenValid={tokenValid}
                  />
                </SpotlightCard>
              </motion.div>

              {/* CRN Manager — wider */}
              <motion.div
                className="lg:col-span-3"
                initial={{ opacity: 0, y: 20, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ ...springIn, delay: 0.2 }}
              >
                <SpotlightCard
                  className="glass h-full"
                  spotlightColor="oklch(0.7 0.18 165 / 0.10)"
                  accent="oklch(0.7 0.18 165)"
                >
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
                </SpotlightCard>
              </motion.div>
            </div>
          </section>

          {/* ═══ SECTION 3: Monitor — Calibration + Logs ═══ */}
          <section>
            <motion.div
              className="flex items-center gap-2 mb-4 px-1"
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ ...springIn, delay: 0.25 }}
            >
              <div className="h-1 w-6 rounded-full bg-gradient-to-r from-violet-400 to-fuchsia-400" />
              <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                İzleme
              </span>
            </motion.div>

            <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
              {/* Calibration — narrower */}
              <motion.div
                className="lg:col-span-2"
                initial={{ opacity: 0, y: 20, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ ...springIn, delay: 0.28 }}
              >
                <SpotlightCard
                  className="glass h-full"
                  spotlightColor="oklch(0.6 0.15 280 / 0.10)"
                  accent="oklch(0.6 0.18 280)"
                >
                  <CalibrationCard
                    calibration={ws.calibration ?? calibrationData}
                    loading={calibrating}
                    token={token}
                  />
                </SpotlightCard>
              </motion.div>

              {/* Live Logs — wider */}
              <motion.div
                className="lg:col-span-3"
                initial={{ opacity: 0, y: 20, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ ...springIn, delay: 0.32 }}
              >
                <SpotlightCard
                  className="glass h-full"
                  spotlightColor="oklch(0.7 0.18 165 / 0.08)"
                  accent="oklch(0.65 0.2 165)"
                >
                  <LiveLogs logs={ws.logs} onClear={ws.clearLogs} />
                </SpotlightCard>
              </motion.div>
            </div>
          </section>

          {/* ═══ SECTION 4: Schedule — full width ═══ */}
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...springIn, delay: 0.36 }}
          >
            <SpotlightCard
              className="glass"
              spotlightColor="oklch(0.7 0.15 80 / 0.08)"
              spotlightSize={600}
              accent="oklch(0.7 0.15 80)"
            >
              <WeeklySchedule
                courses={courseInfo}
                crnList={[...new Set([...crnList, ...scrnList])]}
                loading={lookingUpCRNs.size > 0}
              />
            </SpotlightCard>
          </motion.section>

          {/* ═══ SECTION 5: Config — Settings + Presets ═══ */}
          <section>
            <motion.div
              className="flex items-center gap-2 mb-4 px-1"
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ ...springIn, delay: 0.4 }}
            >
              <div className="h-1 w-6 rounded-full bg-gradient-to-r from-amber-400 to-orange-400" />
              <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                Yapılandırma
              </span>
            </motion.div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ ...springIn, delay: 0.43 }}
              >
                <SpotlightCard
                  className="glass h-full"
                  spotlightColor="oklch(0.7 0.15 30 / 0.08)"
                  accent="oklch(0.7 0.18 30)"
                >
                  <SettingsPanel
                    kayitSaati={kayitSaati}
                    onKayitSaatiChange={setKayitSaati}
                    maxDeneme={maxDeneme}
                    onMaxDenemeChange={setMaxDeneme}
                    retryAralik={retryAralik}
                    onRetryAralikChange={setRetryAralik}
                    gecikmeBuffer={gecikmeBuffer}
                    onGecikmeBufferChange={setGecikmeBuffer}
                    dryRun={dryRun}
                    onDryRunChange={setDryRun}
                    disabled={isRunning}
                  />
                </SpotlightCard>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ ...springIn, delay: 0.46 }}
              >
                <SpotlightCard
                  className="glass h-full"
                  spotlightColor="oklch(0.65 0.15 30 / 0.08)"
                  accent="oklch(0.65 0.18 50)"
                >
                  <PresetManager
                    currentConfig={{
                      ecrn_list: crnList,
                      scrn_list: scrnList,
                      kayit_saati: kayitSaati,
                      max_deneme: maxDeneme,
                      retry_aralik: retryAralik,
                      gecikme_buffer: gecikmeBuffer,
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
                </SpotlightCard>
              </motion.div>
            </div>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 mt-16 border-t border-border/5">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-2 text-center">
          <p className="text-[11px] text-muted-foreground/30 font-medium">
            İTÜ Otostop — Ders Kayıt Otomasyon Aracı v1.0.0 —{" "}
            {new Date().getFullYear()}
          </p>
          <p className="text-[10px] text-muted-foreground/20">
            Bu araç bağımsız bir projedir, İTÜ ile resmi bir bağlantısı yoktur.
            Kullanım sorumluluğu kullanıcıya aittir.
          </p>
          <div className="flex items-center justify-center gap-3 text-[10px] text-muted-foreground/25">
            <a
              href="mailto:nubealbor@gmail.com?subject=İTÜ Otostop - Sorun Bildirimi"
              className="hover:text-muted-foreground/50 transition-colors underline underline-offset-2"
            >
              Sorun Bildir
            </a>
            <span>·</span>
            <span>Verileriniz yalnızca tarayıcınızda saklanır</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
