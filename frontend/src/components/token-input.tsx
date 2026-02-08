"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  KeyRound,
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
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
      if (result.valid) {
        toast.success("Token geçerli ✓");
      } else {
        toast.error(result.message);
      }
    } catch (err) {
      toast.error(
        `Test hatası: ${err instanceof Error ? err.message : "Bilinmeyen hata"}`,
      );
    } finally {
      setTesting(false);
    }
  };

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <KeyRound className="h-5 w-5 text-primary" />
          JWT Token
          <AnimatePresence mode="wait">
            {tokenValid === true && (
              <motion.div
                key="valid"
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0, opacity: 0 }}
              >
                <Badge
                  variant="default"
                  className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                >
                  <CheckCircle2 className="h-3 w-3 mr-1" /> Geçerli
                </Badge>
              </motion.div>
            )}
            {tokenValid === false && (
              <motion.div
                key="invalid"
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0, opacity: 0 }}
              >
                <Badge
                  variant="destructive"
                  className="bg-red-500/20 text-red-400 border-red-500/30"
                >
                  <XCircle className="h-3 w-3 mr-1" /> Geçersiz
                </Badge>
              </motion.div>
            )}
          </AnimatePresence>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="relative">
          <Textarea
            value={token}
            onChange={(e) => onTokenChange(e.target.value)}
            placeholder="OBS'den kopyaladığın Bearer token'ı yapıştır..."
            className={`font-mono text-xs min-h-20 pr-10 resize-none ${
              !show ? "text-transparent selection:text-transparent" : ""
            }`}
            style={
              !show
                ? ({ WebkitTextSecurity: "disc" } as React.CSSProperties)
                : undefined
            }
          />
          <Button
            variant="ghost"
            size="icon"
            className="absolute top-2 right-2 h-7 w-7"
            onClick={() => setShow(!show)}
          >
            {show ? (
              <EyeOff className="h-4 w-4" />
            ) : (
              <Eye className="h-4 w-4" />
            )}
          </Button>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleTest}
          disabled={!token || testing}
          className="w-full"
        >
          {testing ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Test ediliyor...
            </>
          ) : (
            "Token Test Et"
          )}
        </Button>
        <p className="text-xs text-muted-foreground">
          OBS web → F12 → Network → ders-kayit isteği → Authorization header
        </p>
      </CardContent>
    </Card>
  );
}
