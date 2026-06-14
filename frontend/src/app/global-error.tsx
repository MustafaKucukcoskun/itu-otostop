"use client";

/**
 * Root layout'un kendisi crash ederse devreye girer (error.tsx layout'u
 * yakalayamaz). Kendi <html>/<body>'sini render etmek zorunda.
 */
export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="tr">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          display: "flex",
          minHeight: "100vh",
          alignItems: "center",
          justifyContent: "center",
          margin: 0,
          background: "#141414",
          color: "#ededed",
        }}
      >
        <div style={{ maxWidth: 400, padding: 32, textAlign: "center" }}>
          <h1 style={{ fontSize: 18, fontWeight: 600 }}>
            Uygulama yüklenemedi
          </h1>
          <p style={{ fontSize: 14, opacity: 0.7, marginTop: 8 }}>
            Beklenmeyen bir hata oluştu. Lütfen sayfayı yenileyin.
          </p>
          <button
            onClick={reset}
            style={{
              marginTop: 20,
              height: 40,
              padding: "0 20px",
              background: "#e5562a",
              color: "#fff",
              border: "none",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Tekrar Dene
          </button>
        </div>
      </body>
    </html>
  );
}
