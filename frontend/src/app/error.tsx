"use client";

import { useEffect } from "react";
import { RotateCcw, AlertTriangle } from "lucide-react";

/**
 * Route segment Error Boundary — sayfa/bileşen crash'inde beyaz ekran yerine
 * kurtarma ekranı gösterir. reset() segment'i yeniden render etmeyi dener.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Konsola logla (prod'da gözlemlenebilir)
    console.error("[ErrorBoundary]", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <div className="w-full max-w-md border bg-card p-8 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center border border-status-err text-status-err">
          <AlertTriangle className="h-6 w-6" />
        </div>
        <h1 className="text-lg font-semibold">Bir şeyler ters gitti</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Beklenmeyen bir hata oluştu. Verileriniz güvende — tekrar deneyebilir
          veya sayfayı yenileyebilirsiniz.
        </p>
        {error.digest && (
          <p className="mt-2 font-mono text-[10px] text-muted-foreground/60">
            Hata kodu: {error.digest}
          </p>
        )}
        <button
          onClick={reset}
          className="mt-5 inline-flex h-10 items-center justify-center gap-2 bg-primary px-5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <RotateCcw className="h-4 w-4" />
          Tekrar Dene
        </button>
      </div>
    </div>
  );
}
