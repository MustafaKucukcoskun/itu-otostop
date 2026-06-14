"use client";

import { useState, useEffect } from "react";
import { m, AnimatePresence } from "motion/react";
import { X } from "lucide-react";

const STORAGE_KEY = "otostop-privacy-ack";

export function PrivacyBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Show banner only on first visit (useEffect required — localStorage unavailable during SSR)
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!localStorage.getItem(STORAGE_KEY)) setVisible(true);
  }, []);

  const dismiss = () => {
    localStorage.setItem(STORAGE_KEY, "1");
    setVisible(false);
  };

  return (
    <AnimatePresence>
      {visible && (
        <m.div
          initial={{ y: 80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 80, opacity: 0 }}
          transition={{ type: "spring", damping: 24, stiffness: 260 }}
          className="pointer-events-none fixed bottom-4 left-4 right-4 z-[90] flex justify-center"
        >
          <div className="pointer-events-auto flex w-full max-w-lg items-start gap-3.5 border-l-2 border-l-primary border bg-popover px-5 py-4">
            <div className="min-w-0 flex-1 space-y-2">
              <p className="panel-label">Gizlilik Bildirimi</p>
              <p className="text-xs leading-relaxed text-muted-foreground">
                Bu uygulama İTÜ şifrenizi saklamaz. CRN listeniz ve ayarlarınız
                tarayıcınızda tutulur. Kayıt başlatıldığında yalnızca token
                güvenli şekilde sunucuya iletilir. Hiçbir veri üçüncü taraflarla
                paylaşılmaz.
              </p>
              <button
                onClick={dismiss}
                className="h-8 bg-primary px-4 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Anladım
              </button>
            </div>
            <button
              onClick={dismiss}
              className="flex h-6 w-6 shrink-0 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
              aria-label="Kapat"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </m.div>
      )}
    </AnimatePresence>
  );
}
