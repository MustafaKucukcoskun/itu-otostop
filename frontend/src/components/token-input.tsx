"use client";

import { useState, useEffect, useMemo } from "react";
import { m, AnimatePresence } from "motion/react";
import {
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  AlertTriangle,
  HelpCircle,
} from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { PanelHeader } from "@/components/panel";
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
  const days = Math.floor(totalSec / 86400);
  const h = Math.floor((totalSec % 86400) / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  if (days > 365) return `${Math.floor(days / 365)} yıl+`;
  if (days > 0) return `${days} gün ${h} saat`;
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

  const rawExpiryStatus = useMemo(() => {
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

  // Server validation overrides client-side JWT decode
  const expiryStatus = useMemo(() => {
    if (tokenValid === false) {
      return {
        level: "expired" as const,
        text: "Token geçersiz veya süresi dolmuş",
        ms: 0,
      };
    }
    return rawExpiryStatus;
  }, [rawExpiryStatus, tokenValid]);

  const handleTest = async () => {
    if (!token) {
      toast.error("Token girilmemiş");
      return;
    }
    setTesting(true);
    try {
      const result = await api.testToken();
      if (result.valid) toast.success("Token geçerli");
      else toast.error(result.message);
    } catch (err) {
      toast.error(
        `Test hatası: ${err instanceof Error ? err.message : "Bilinmeyen hata"}`,
      );
    } finally {
      setTesting(false);
    }
  };

  // Expiry indicator: durum rengine eşle
  const expiryColor =
    expiryStatus?.level === "ok" ? "text-status-ok" : expiryStatus?.level === "warning" ? "text-status-wait" : "text-status-err";

  return (
    <div>
      <PanelHeader
        label="Bearer Token"
        action={
          <AnimatePresence mode="wait">
            {tokenValid === true && (
              <m.span
                key="valid"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-1 border border-status-ok px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-status-ok"
              >
                <CheckCircle2 className="h-3 w-3" /> Geçerli
              </m.span>
            )}
            {tokenValid === false && (
              <m.span
                key="invalid"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-1 border border-status-err px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-status-err"
              >
                <XCircle className="h-3 w-3" /> Geçersiz
              </m.span>
            )}
          </AnimatePresence>
        }
      />

      {/* Token area */}
      <div className="space-y-3 p-4">
        <p className="font-mono text-[11px] text-muted-foreground">
          OBS → F12 → Network → jwt ara → Response
        </p>
        <div className="relative">
          <Textarea
            value={token}
            onChange={(e) => onTokenChange(e.target.value)}
            placeholder="Token'ı buraya yapıştır..."
            aria-label="OBS Bearer token"
            className="min-h-20 resize-none pr-10 font-mono text-xs"
            style={
              !show
                ? ({ WebkitTextSecurity: "disc" } as React.CSSProperties)
                : undefined
            }
          />
          <button
            type="button"
            className="absolute right-2.5 top-2.5 flex h-7 w-7 items-center justify-center border bg-card text-muted-foreground transition-colors hover:text-foreground"
            onClick={() => setShow(!show)}
            aria-label={show ? "Token'ı gizle" : "Token'ı göster"}
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
            <m.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className={`flex items-center gap-2 border-l-2 border-current bg-muted/40 px-3 py-2 text-xs font-medium ${expiryColor}`}
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
                <span className="ml-auto font-mono text-[10px] opacity-70">
                  {jwtInfo.exp.toLocaleTimeString("tr-TR", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              )}
            </m.div>
          )}
          {token && !jwtInfo && token.length > 20 && (
            <m.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="flex items-center gap-2 border-l-2 border-current bg-muted/40 px-3 py-2 text-xs font-medium text-status-wait"
            >
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              <span>JWT formatı tanınmadı — süre bilgisi gösterilemiyor</span>
            </m.div>
          )}
        </AnimatePresence>

        <div className="flex gap-2">
          <button
            onClick={handleTest}
            disabled={!token || testing}
            className="flex flex-1 items-center justify-center gap-2 bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-40"
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
            className="flex h-9 items-center gap-1.5 border px-3 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
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
