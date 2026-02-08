"use client";

import { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  Loader2,
  ShieldCheck,
  Clock,
  AlertTriangle,
  HelpCircle,
} from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { TokenGuideModal } from "@/components/token-guide-modal";

// ── JWT Decode (client-side, no library needed) ──

interface JwtInfo {
  exp: Date | null;
  iat: Date | null;
  sub: string | null;
}

function decodeJwt(token: string): JwtInfo | null {
  try {
    const parts = token.trim().split(".");
    if (parts.length !== 3) return null;
    // base64url → base64 → JSON
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(b64));
    return {
      exp: payload.exp ? new Date(payload.exp * 1000) : null,
      iat: payload.iat ? new Date(payload.iat * 1000) : null,
      sub: payload.sub || payload.nameid || null,
    };
  } catch {
    return null;
  }
}

function formatRelativeTime(ms: number): string {
  const totalSec = Math.abs(Math.floor(ms / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  if (h > 0) return `${h} saat ${m} dk`;
  if (m > 0) return `${m} dk`;
  return `${totalSec} sn`;
}

interface TokenInputProps {
  token: string;
  onTokenChange: (token: string) => void;
  tokenValid: boolean | null;
}

export function TokenInput({
  token,
  onTokenChange,
  tokenValid,
}: TokenInputProps) {
  const [show, setShow] = useState(false);
  const [testing, setTesting] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [guideOpen, setGuideOpen] = useState(false);

  // Update clock every 30s for expiry countdown
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(interval);
  }, []);

  const jwtInfo = useMemo(() => (token ? decodeJwt(token) : null), [token]);

  const expiryStatus = useMemo(() => {
    if (!jwtInfo?.exp) return null;
    const diff = jwtInfo.exp.getTime() - now;
    if (diff <= 0)
      return {
        level: "expired" as const,
        text: "Token süresi dolmuş!",
        ms: diff,
      };
    if (diff < 15 * 60 * 1000)
      return {
        level: "critical" as const,
        text: `${formatRelativeTime(diff)} sonra sona erecek!`,
        ms: diff,
      };
    if (diff < 60 * 60 * 1000)
      return {
        level: "warning" as const,
        text: `${formatRelativeTime(diff)} sonra sona erecek`,
        ms: diff,
      };
    return {
      level: "ok" as const,
      text: `${formatRelativeTime(diff)} sonra sona erecek`,
      ms: diff,
    };
  }, [jwtInfo, now]);

  const handleTest = async () => {
    if (!token) {
      toast.error("Token girilmemiş");
      return;
    }
    setTesting(true);
    try {
      const result = await api.testToken();
      if (result.valid) toast.success("Token geçerli ✓");
      else toast.error(result.message);
    } catch (err) {
      toast.error(
        `Test hatası: ${err instanceof Error ? err.message : "Bilinmeyen hata"}`,
      );
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <ShieldCheck className="h-4 w-4 text-blue-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold">Bearer Token</h3>
            <p className="text-[11px] text-muted-foreground">
              OBS → F12 → Network → Authorization
            </p>
          </div>
        </div>
        <AnimatePresence mode="wait">
          {tokenValid === true && (
            <motion.div
              key="valid"
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-[11px] font-medium"
            >
              <CheckCircle2 className="h-3 w-3" /> Geçerli
            </motion.div>
          )}
          {tokenValid === false && (
            <motion.div
              key="invalid"
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-red-500/10 text-red-400 text-[11px] font-medium"
            >
              <XCircle className="h-3 w-3" /> Geçersiz
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Token area */}
      <div className="px-5 pb-4 space-y-3">
        <div className="relative group">
          <Textarea
            value={token}
            onChange={(e) => onTokenChange(e.target.value)}
            placeholder="Token'ı buraya yapıştır..."
            className={`font-mono text-xs min-h-20 pr-10 resize-none bg-background/50 border-border/30 rounded-xl focus:ring-1 focus:ring-primary/30 transition-all ${
              !show ? "text-transparent selection:text-transparent" : ""
            }`}
            style={
              !show
                ? ({ WebkitTextSecurity: "disc" } as React.CSSProperties)
                : undefined
            }
          />
          <button
            type="button"
            className="absolute top-2.5 right-2.5 h-7 w-7 rounded-lg bg-muted/50 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            onClick={() => setShow(!show)}
          >
            {show ? (
              <EyeOff className="h-3.5 w-3.5" />
            ) : (
              <Eye className="h-3.5 w-3.5" />
            )}
          </button>
        </div>

        {/* Token Expiry Indicator */}
        <AnimatePresence>
          {token && expiryStatus && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium ${
                expiryStatus.level === "expired"
                  ? "bg-red-500/10 text-red-400"
                  : expiryStatus.level === "critical"
                    ? "bg-red-500/10 text-red-400"
                    : expiryStatus.level === "warning"
                      ? "bg-yellow-500/10 text-yellow-400"
                      : "bg-emerald-500/10 text-emerald-400"
              }`}
            >
              {expiryStatus.level === "expired" ? (
                <XCircle className="h-3.5 w-3.5 shrink-0" />
              ) : expiryStatus.level === "critical" ||
                expiryStatus.level === "warning" ? (
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              ) : (
                <Clock className="h-3.5 w-3.5 shrink-0" />
              )}
              <span>{expiryStatus.text}</span>
              {jwtInfo?.exp && (
                <span className="ml-auto text-[10px] opacity-60 font-mono">
                  {jwtInfo.exp.toLocaleTimeString("tr-TR", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              )}
            </motion.div>
          )}
          {token && !jwtInfo && token.length > 20 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium bg-yellow-500/10 text-yellow-400"
            >
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              <span>JWT formatı tanınmadı — süre bilgisi gösterilemiyor</span>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex gap-2">
          <button
            onClick={handleTest}
            disabled={!token || testing}
            className="flex-1 py-2 px-4 rounded-xl text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
          >
            {testing ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Test
                ediliyor...
              </>
            ) : (
              "Token Test Et"
            )}
          </button>
          <button
            onClick={() => setGuideOpen(true)}
            className="h-9 px-3 rounded-xl ring-1 ring-border/30 bg-background/40 hover:bg-muted/40 text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5 text-xs"
            title="Token nasıl alınır?"
          >
            <HelpCircle className="h-3.5 w-3.5" />
            Nasıl?
          </button>
        </div>
      </div>

      <TokenGuideModal open={guideOpen} onClose={() => setGuideOpen(false)} />
    </div>
  );
}
