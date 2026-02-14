"use client";

import React, { useState } from "react";
import { createPortal } from "react-dom";
import { m, AnimatePresence } from "motion/react";
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
  ZoomIn,
} from "lucide-react";

/* ─── Step definitions ──────────────────────────────────── */

const STEPS = [
  {
    title: "OBS'ye Giriş Yap",
    desc: "Tarayıcından obs.itu.edu.tr adresine gidip İTÜ hesabınla giriş yap.",
    detail:
      "Hangi sayfada olduğunun önemi yok, OBS'e giriş yapmış olman yeterli. Fotoğraftaki kırmızı kutular kullanıcı adı ve şifre alanlarını, yeşil kutu ise giriş butonunu gösteriyor.",
    icon: ExternalLink,
    color: "text-blue-400 bg-blue-500/10",
    image: "/guide/step1-obs-login.png",
  },
  {
    title: "Geliştirici Araçlarını Aç",
    desc: 'F12 tuşuna bas veya sayfada sağ tıklayıp "İncele" seçeneğini seç. Açılan panelde fotoğraftaki kırmızı kutuyla işaretli "Network" sekmesine tıkla.',
    detail:
      'Mac kullanıyorsan Cmd+Option+I kısayolunu kullanabilirsin. Chrome, Firefox ve Edge\'de çalışır. Fotoğrafta "Network" sekmesinin yerini görebilirsin.',
    icon: MonitorSmartphone,
    color: "text-purple-400 bg-purple-500/10",
    image: "/guide/step2-devtools.png",
  },
  {
    title: '"jwt" Filtrele',
    desc: 'Network sekmesinde, fotoğraftaki filtre kutusuna "jwt" yaz. Altta çıkan jwt satırına tıkla.',
    detail:
      'Fotoğrafta kırmızı kutuyla işaretli filtre alanına "jwt" yazdığında, alttaki sonuç satırı görünecek. O satıra tıklaman gerekiyor. Liste boşsa sayfayı F5 ile yenileyi dene.',
    icon: Search,
    color: "text-amber-400 bg-amber-500/10",
    image: "/guide/step3a-jwt-filter.png",
  },
  {
    title: "Token'ı Kopyala",
    desc: 'jwt isteğine tıkladıktan sonra açılan panelde fotoğraftaki "Response" sekmesine geç. Görünen token metninin tamamını seç ve kopyala.',
    detail:
      "Fotoğraftaki kırmızı kutuyla işaretli Response sekmesine tıkla. Açılan token metnini Ctrl+A ile tümünü seç, ardından Ctrl+C ile kopyala.",
    icon: Copy,
    color: "text-orange-400 bg-orange-500/10",
    image: "/guide/step3b-response-copy.png",
  },
  {
    title: "Token'ı Yapıştır",
    desc: 'Kopyaladığın token\'ı fotoğraftaki yeşil kutuyla işaretli "Token" alanına yapıştır (Ctrl+V).',
    detail:
      '"Bearer " ön eki otomatik olarak kaldırılır. Yapıştırdıktan sonra "Token Test Et" butonuyla doğruluğunu kontrol edebilirsin.',
    icon: ClipboardPaste,
    color: "text-cyan-400 bg-cyan-500/10",
    image: "/guide/step4-paste-token.png",
  },
];

/* ─── Component ─────────────────────────────────────────── */

interface TokenGuideModalProps {
  open: boolean;
  onClose: () => void;
}

export function TokenGuideModal({ open, onClose }: TokenGuideModalProps) {
  const [step, setStep] = useState(0);
  const [lightbox, setLightbox] = useState<string | null>(null);

  // Reset to step 0 whenever modal opens
  React.useEffect(() => {
    if (open) {
      setStep(0);
      setLightbox(null);
    }
  }, [open]);

  const prev = () => setStep((s) => Math.max(0, s - 1));
  const next = () => setStep((s) => Math.min(STEPS.length - 1, s + 1));

  const current = STEPS[step];
  const Icon = current.icon;

  // Portal to document.body to escape backdrop-filter containment
  if (typeof window === "undefined") return null;

  return createPortal(
    <>
      {/* ── Main modal ────────────────────────────────── */}
      <AnimatePresence>
        {open && (
          <m.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm"
            onClick={onClose}
          >
            <m.div
              initial={{ scale: 0.92, opacity: 0, y: 12 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.92, opacity: 0, y: 12 }}
              transition={{ type: "spring", damping: 26, stiffness: 300 }}
              onClick={(e) => e.stopPropagation()}
              className="glass rounded-2xl ring-1 ring-border/20 shadow-2xl mx-4 max-w-lg w-full overflow-hidden max-h-[90vh] flex flex-col"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-5 pt-5 pb-2 shrink-0">
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
              <div className="flex gap-1.5 px-5 py-2 shrink-0">
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

              {/* Step content — scrollable */}
              <div className="overflow-y-auto flex-1 min-h-0">
                <AnimatePresence mode="wait">
                  <m.div
                    key={step}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.2 }}
                    className="px-5 py-4 space-y-3"
                  >
                    {/* Title + description */}
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

                    {/* Screenshot */}
                    {current.image && (
                      <button
                        type="button"
                        onClick={() => setLightbox(current.image)}
                        className="group relative w-full rounded-xl overflow-hidden ring-1 ring-border/15 hover:ring-primary/30 transition-all duration-200 cursor-zoom-in"
                      >
                        <img
                          src={current.image}
                          alt={current.title}
                          className="w-full h-auto object-contain"
                          loading="lazy"
                        />
                        {/* Zoom hint overlay */}
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                          <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-black/60 rounded-lg px-2.5 py-1.5 flex items-center gap-1.5">
                            <ZoomIn className="h-3.5 w-3.5 text-white" />
                            <span className="text-xs text-white font-medium">
                              Büyüt
                            </span>
                          </div>
                        </div>
                      </button>
                    )}

                    {/* Tip */}
                    <div className="bg-muted/20 rounded-xl p-3.5 text-xs text-muted-foreground/70 leading-relaxed">
                      💡 {current.detail}
                    </div>
                  </m.div>
                </AnimatePresence>
              </div>

              {/* Navigation */}
              <div className="flex items-center justify-between px-5 pb-5 pt-1 shrink-0">
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
            </m.div>
          </m.div>
        )}
      </AnimatePresence>

      {/* ── Lightbox (full-screen zoom) ───────────────── */}
      <AnimatePresence>
        {lightbox && (
          <m.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[110] flex items-center justify-center bg-black/80 backdrop-blur-md cursor-zoom-out"
            onClick={() => setLightbox(null)}
          >
            <m.img
              src={lightbox}
              alt="Büyütülmüş görsel"
              initial={{ scale: 0.85, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.85, opacity: 0 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="max-w-[92vw] max-h-[90vh] object-contain rounded-xl shadow-2xl"
            />
            {/* Close hint */}
            <div className="absolute top-4 right-4">
              <button
                onClick={() => setLightbox(null)}
                className="h-9 w-9 rounded-xl bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
              >
                <X className="h-5 w-5 text-white" />
              </button>
            </div>
          </m.div>
        )}
      </AnimatePresence>
    </>,
    document.body,
  );
}
