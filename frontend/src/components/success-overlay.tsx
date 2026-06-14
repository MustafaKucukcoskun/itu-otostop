"use client";

import { m, AnimatePresence } from "motion/react";
import { Check, X } from "lucide-react";

interface SuccessOverlayProps {
  show: boolean;
  results?: Array<{
    crn: string;
    status: string;
    label?: string;
  }>;
  onDismiss?: () => void;
}

const STATUS_TEXT: Record<string, string> = {
  success: "Başarılı",
  already: "Zaten kayıtlı",
  full: "Kontenjan dolu",
  conflict: "Çakışma",
  pending: "Bekliyor",
  error: "Hata",
};

function isOk(status: string) {
  return status === "success" || status === "already";
}

/**
 * Sonuç stempeli — kayıt bittiğinde tam ekran sonuç paneli.
 * Konfeti yok: durum, dev mono başlık + kalın durum şeridi + CRN listesiyle anlatılır.
 */
export function SuccessOverlay({
  show,
  results = [],
  onDismiss,
}: SuccessOverlayProps) {
  const successCount = results.filter((r) => isOk(r.status)).length;
  const failCount = results.filter(
    (r) => !isOk(r.status) && r.status !== "pending",
  ).length;
  const allFailed = successCount === 0 && failCount > 0;

  const accent = allFailed ? "var(--status-err)" : "var(--status-ok)";
  const headline = allFailed ? "KAYIT BAŞARISIZ" : "KAYIT TAMAM";

  return (
    <AnimatePresence>
      {show && (
        <m.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/55 p-4"
          onClick={onDismiss}
        >
          <m.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-sm border bg-card"
          >
            {/* Status bar */}
            <div
              className="h-1.5 w-full"
              style={{ backgroundColor: accent }}
              aria-hidden
            />

            <div className="p-6 text-center">
              <div
                className="mx-auto mb-4 flex h-14 w-14 items-center justify-center border-2"
                style={{ borderColor: accent, color: accent }}
              >
                {allFailed ? (
                  <X className="h-7 w-7" strokeWidth={2.5} />
                ) : (
                  <Check className="h-7 w-7" strokeWidth={2.5} />
                )}
              </div>

              <h2 className="font-mono text-2xl font-semibold tracking-tight">
                {headline}
              </h2>

              <p className="mt-2 font-mono text-sm text-muted-foreground tabular-nums">
                {successCount > 0 && (
                  <span className="text-[--status-ok]">
                    {successCount} başarılı
                  </span>
                )}
                {successCount > 0 && failCount > 0 && " · "}
                {failCount > 0 && (
                  <span className="text-[--status-err]">
                    {failCount} başarısız
                  </span>
                )}
                {successCount === 0 && failCount === 0 && "İşlem tamamlandı"}
              </p>

              {/* CRN Results list */}
              {results.length > 0 && (
                <div className="mt-5 max-h-40 space-y-px overflow-y-auto border">
                  {results.map((r, i) => (
                    <div
                      key={`${r.crn}-${i}`}
                      className="flex items-center justify-between gap-2 px-3 py-2 font-mono text-xs"
                    >
                      <span className="truncate text-left">
                        {r.label || r.crn}
                      </span>
                      <span
                        className={`shrink-0 uppercase tracking-wider ${
                          isOk(r.status)
                            ? "text-[--status-ok]"
                            : r.status === "pending"
                              ? "text-muted-foreground"
                              : "text-[--status-err]"
                        }`}
                      >
                        {STATUS_TEXT[r.status] ?? r.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <button
                onClick={onDismiss}
                className="mt-5 h-10 w-full bg-primary text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Tamam
              </button>
            </div>
          </m.div>
        </m.div>
      )}
    </AnimatePresence>
  );
}
