"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ShieldCheck, X } from "lucide-react";

const STORAGE_KEY = "otostop-privacy-ack";

export function PrivacyBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Show banner only on first visit
    if (!localStorage.getItem(STORAGE_KEY)) {
      setVisible(true);
    }
  }, []);

  const dismiss = () => {
    localStorage.setItem(STORAGE_KEY, "1");
    setVisible(false);
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ y: 80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 80, opacity: 0 }}
          transition={{ type: "spring", damping: 24, stiffness: 260 }}
          className="fixed bottom-4 left-4 right-4 z-[90] flex justify-center pointer-events-none"
        >
          <div className="pointer-events-auto glass rounded-2xl ring-1 ring-border/20 shadow-2xl px-5 py-4 max-w-lg w-full flex items-start gap-3.5">
            <div className="h-9 w-9 rounded-lg bg-emerald-500/10 flex items-center justify-center shrink-0 mt-0.5">
              <ShieldCheck className="h-4.5 w-4.5 text-emerald-400" />
            </div>
            <div className="flex-1 min-w-0 space-y-2">
              <p className="text-sm font-semibold">Gizlilik Bildirimi</p>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Bu uygulama İTÜ şifrenizi saklamaz. CRN listeniz ve ayarlarınız
                tarayıcınızda tutulur. Kayıt başlatıldığında yalnızca token
                güvenli şekilde sunucuya iletilir. Hiçbir veri üçüncü taraflarla
                paylaşılmaz.
              </p>
              <button
                onClick={dismiss}
                className="h-8 px-4 rounded-xl bg-emerald-500/15 text-emerald-400 text-xs font-semibold hover:bg-emerald-500/25 transition-colors"
              >
                Anladım
              </button>
            </div>
            <button
              onClick={dismiss}
              className="h-6 w-6 rounded-lg flex items-center justify-center text-muted-foreground/40 hover:text-foreground transition-colors shrink-0"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
