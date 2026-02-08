"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "motion/react";
import { Play, Square, Gauge, Zap } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useWebSocket } from "@/hooks/use-websocket";
import { TokenInput } from "@/components/token-input";
import { CRNManager } from "@/components/crn-manager";
import { CalibrationCard } from "@/components/calibration-card";
import { CountdownTimer } from "@/components/countdown-timer";
import { LiveLogs } from "@/components/live-logs";
import { SettingsPanel } from "@/components/settings-panel";
import { ConnectionStatus } from "@/components/connection-status";
import { ThemeToggle } from "@/components/theme-toggle";

export function Dashboard() {
  // Config state
  const [token, setToken] = useState("");
  const [tokenChanged, setTokenChanged] = useState(false);
  const [crnList, setCrnList] = useState<string[]>([]);
  const [scrnList, setScrnList] = useState<string[]>([]);
  const [kayitSaati, setKayitSaati] = useState("14:00:00");
  const [maxDeneme, setMaxDeneme] = useState(60);
  const [retryAralik, setRetryAralik] = useState(3.0);
  const [gecikmeBuffer, setGecikmeBuffer] = useState(0.005);

  // UI state
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [calibrating, setCalibrating] = useState(false);
  const [starting, setStarting] = useState(false);
  const [calibrationData, setCalibrationData] = useState<Record<
    string,
    number
  > | null>(null);

  // WebSocket real-time data
  const ws = useWebSocket();

  const isRunning =
    ws.phase === "token_check" ||
    ws.phase === "calibrating" ||
    ws.phase === "waiting" ||
    ws.phase === "registering";

  // Load config on mount
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
        if (config.token_set) setTokenValid(true);
      } catch {
        // Backend not running yet
      }
    })();
  }, []);

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
  ]);

  // Auto-save config on changes
  useEffect(() => {
    const timer = setTimeout(() => {
      if (token || crnList.length > 0 || scrnList.length > 0) saveConfig();
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
    saveConfig,
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
    setStarting(true);
    try {
      await saveConfig();
      await api.startRegistration();
      toast.success("Kayıt süreci başlatıldı!");
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
      toast.info("Kayıt iptal edildi");
    } catch (err) {
      toast.error(
        `İptal hatası: ${err instanceof Error ? err.message : "Bilinmeyen hata"}`,
      );
    }
  };

  // Show toast on done
  useEffect(() => {
    if (ws.done) {
      const successCount = Object.values(ws.crnResults).filter(
        (r) => r.status === "success",
      ).length;
      if (successCount > 0) {
        toast.success(`${successCount} ders başarıyla kaydedildi! 🎉`);
      } else {
        toast.warning("Kayıt süreci bitti, başarılı ders yok");
      }
    }
  }, [ws.done, ws.crnResults]);

  return (
    <div className="min-h-screen mesh-bg relative">
      {/* Dot grid overlay */}
      <div className="dot-grid fixed inset-0 pointer-events-none" />

      {/* Header */}
      <header className="sticky top-0 z-50 glass border-b border-border/20">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <motion.div
            className="flex items-center gap-2.5"
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
          >
            <div className="h-8 w-8 rounded-lg bg-primary/15 flex items-center justify-center">
              <Zap className="h-4 w-4 text-primary" />
            </div>
            <h1 className="text-sm font-bold tracking-tight">İTÜ OBS Kayıt</h1>
          </motion.div>
          <div className="flex items-center gap-2">
            <ConnectionStatus connected={ws.connected} />
            <div className="w-px h-5 bg-border/30" />
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-5 relative z-10">
        {/* Countdown */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
        >
          <CountdownTimer
            targetTime={kayitSaati}
            countdown={ws.countdown}
            phase={ws.phase}
          />
        </motion.div>

        {/* Action buttons */}
        <motion.div
          className="flex gap-3"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <button
            onClick={handleCalibrate}
            disabled={calibrating || isRunning || !token}
            className="flex-1 h-10 rounded-xl ring-1 ring-border/30 bg-background/60 hover:bg-muted/60 text-sm font-medium flex items-center justify-center gap-2 transition-colors disabled:opacity-40 disabled:pointer-events-none"
          >
            <Gauge className="h-4 w-4" />
            {calibrating ? "Kalibre ediliyor..." : "Kalibre Et"}
          </button>
          {!isRunning ? (
            <button
              onClick={handleStart}
              disabled={starting || !token || crnList.length === 0}
              className="flex-1 h-10 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium flex items-center justify-center gap-2 transition-colors glow-sm disabled:opacity-40 disabled:pointer-events-none"
            >
              <Play className="h-4 w-4" />
              {starting ? "Başlatılıyor..." : "Kayıt Başlat"}
            </button>
          ) : (
            <button
              onClick={handleCancel}
              className="flex-1 h-10 rounded-xl bg-red-600 hover:bg-red-500 text-white text-sm font-medium flex items-center justify-center gap-2 transition-colors"
            >
              <Square className="h-4 w-4" />
              İptal Et
            </button>
          )}
        </motion.div>

        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Left column */}
          <motion.div
            className="space-y-5"
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.15 }}
          >
            <TokenInput
              token={token}
              onTokenChange={setToken}
              tokenValid={tokenValid}
            />
            <CRNManager
              ecrnList={crnList}
              onEcrnListChange={setCrnList}
              scrnList={scrnList}
              onScrnListChange={setScrnList}
              crnResults={ws.crnResults}
              disabled={isRunning}
            />
            <SettingsPanel
              kayitSaati={kayitSaati}
              onKayitSaatiChange={setKayitSaati}
              maxDeneme={maxDeneme}
              onMaxDenemeChange={setMaxDeneme}
              retryAralik={retryAralik}
              onRetryAralikChange={setRetryAralik}
              gecikmeBuffer={gecikmeBuffer}
              onGecikmeBufferChange={setGecikmeBuffer}
              disabled={isRunning}
            />
          </motion.div>

          {/* Right column */}
          <motion.div
            className="space-y-5"
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
          >
            <CalibrationCard
              calibration={ws.calibration ?? calibrationData}
              loading={calibrating}
            />
            <LiveLogs logs={ws.logs} onClear={ws.clearLogs} />
          </motion.div>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 mt-12 border-t border-border/10">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 text-center text-[11px] text-muted-foreground/40">
          İTÜ OBS Ders Kayıt Otomasyon Aracı — {new Date().getFullYear()}
        </div>
      </footer>
    </div>
  );
}
