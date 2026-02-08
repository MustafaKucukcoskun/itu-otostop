"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { toast } from "sonner";

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
    <div className="rounded-2xl glass overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <ShieldCheck className="h-4 w-4 text-primary" />
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

        <button
          onClick={handleTest}
          disabled={!token || testing}
          className="w-full py-2 px-4 rounded-xl text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
        >
          {testing ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Test ediliyor...
            </>
          ) : (
            "Token Test Et"
          )}
        </button>
      </div>
    </div>
  );
}
