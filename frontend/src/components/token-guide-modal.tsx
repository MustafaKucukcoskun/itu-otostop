"use client";

import React, { useState } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "motion/react";
import {
  X,
  ExternalLink,
  MonitorSmartphone,
  Search,
  Copy,
  ClipboardPaste,
  ChevronRight,
  ChevronLeft,
  HelpCircle,
} from "lucide-react";

const STEPS = [
  {
    title: "OBS'ye Giriş Yap",
    desc: "Tarayıcından obs.itu.edu.tr adresine gidip İTÜ hesabınla giriş yap.",
    detail:
      "Ders kayıt veya dersprogram sayfasına git — hangi sayfa olduğu farketmez, önemli olan giriş yapmış olman.",
    icon: ExternalLink,
    color: "text-blue-400 bg-blue-500/10",
  },
  {
    title: "DevTools'u Aç (F12)",
    desc: 'Tarayıcıda F12 tuşuna bas veya sağ tık → "İncele" (Inspect) menüsünü aç.',
    detail:
      'Açılan panelde üstteki sekmelerden "Network" (Ağ) sekmesine geç. Eğer boşsa sayfayı yenile (F5).',
    icon: MonitorSmartphone,
    color: "text-purple-400 bg-purple-500/10",
  },
  {
    title: "Bir API İsteği Bul",
    desc: "Network sekmesindeki listeden herhangi bir isteğe tıkla.",
    detail:
      'Filtre kutusuna "api" veya "ders" yaz — obs.itu.edu.tr/api/ ile başlayan istekleri göreceksin. Herhangi birine tıkla.',
    icon: Search,
    color: "text-amber-400 bg-amber-500/10",
  },
  {
    title: "Token'ı Kopyala",
    desc: 'Açılan panelde "Headers" sekmesinde Authorization satırını bul.',
    detail:
      '"Authorization: Bearer eyJ..." şeklinde uzun bir metin göreceksin. "Bearer " kısmı dahil tamamını kopyala. (Sağ tık → Kopyala veya Ctrl+C)',
    icon: Copy,
    color: "text-emerald-400 bg-emerald-500/10",
  },
  {
    title: "Buraya Yapıştır",
    desc: "Kopyaladığın token'ı soldaki Token alanına yapıştır.",
    detail:
      '"Bearer " prefix\'i otomatik kaldırılır, ikisi de çalışır. Ardından "Token Test Et" butonuyla doğrulayabilirsin.',
    icon: ClipboardPaste,
    color: "text-cyan-400 bg-cyan-500/10",
  },
];

interface TokenGuideModalProps {
  open: boolean;
  onClose: () => void;
}

export function TokenGuideModal({ open, onClose }: TokenGuideModalProps) {
  const [step, setStep] = useState(0);

  // Reset to step 0 whenever modal opens
  React.useEffect(() => {
    if (open) setStep(0);
  }, [open]);

  const prev = () => setStep((s) => Math.max(0, s - 1));
  const next = () => setStep((s) => Math.min(STEPS.length - 1, s + 1));

  const current = STEPS[step];
  const Icon = current.icon;

  // Portal to document.body to escape backdrop-filter containment
  if (typeof window === "undefined") return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.92, opacity: 0, y: 12 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.92, opacity: 0, y: 12 }}
            transition={{ type: "spring", damping: 26, stiffness: 300 }}
            onClick={(e) => e.stopPropagation()}
            className="glass rounded-2xl ring-1 ring-border/20 shadow-2xl mx-4 max-w-md w-full overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 pt-5 pb-2">
              <div className="flex items-center gap-2">
                <HelpCircle className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-bold">Token Nasıl Alınır?</h2>
              </div>
              <button
                onClick={onClose}
                className="h-7 w-7 rounded-lg flex items-center justify-center text-muted-foreground/50 hover:text-foreground hover:bg-muted/40 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Step indicator */}
            <div className="flex gap-1.5 px-5 py-2">
              {STEPS.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setStep(i)}
                  className={`h-1.5 rounded-full flex-1 transition-all duration-300 ${
                    i === step
                      ? "bg-primary"
                      : i < step
                        ? "bg-primary/30"
                        : "bg-border/20"
                  }`}
                />
              ))}
            </div>

            {/* Step content */}
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="px-5 py-4 space-y-3"
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${current.color}`}
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-semibold">
                      <span className="text-primary mr-1.5">
                        {step + 1}/{STEPS.length}
                      </span>
                      {current.title}
                    </p>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {current.desc}
                    </p>
                  </div>
                </div>

                <div className="bg-muted/20 rounded-xl p-3.5 text-xs text-muted-foreground/70 leading-relaxed">
                  💡 {current.detail}
                </div>
              </motion.div>
            </AnimatePresence>

            {/* Navigation */}
            <div className="flex items-center justify-between px-5 pb-5 pt-1">
              <button
                onClick={prev}
                disabled={step === 0}
                className="flex items-center gap-1 h-9 px-3 rounded-xl text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/40 disabled:opacity-30 disabled:pointer-events-none transition-colors"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Önceki
              </button>
              {step < STEPS.length - 1 ? (
                <button
                  onClick={next}
                  className="flex items-center gap-1 h-9 px-4 rounded-xl bg-primary/15 text-primary text-xs font-semibold hover:bg-primary/25 transition-colors"
                >
                  Sonraki
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              ) : (
                <button
                  onClick={onClose}
                  className="h-9 px-4 rounded-xl bg-emerald-500/15 text-emerald-400 text-xs font-semibold hover:bg-emerald-500/25 transition-colors"
                >
                  Anladım, Kapat
                </button>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
