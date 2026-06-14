"use client";

import { m, LazyMotion, domMax } from "motion/react";
import { Zap, Timer, Shield } from "lucide-react";

const features = [
  { icon: Timer, label: "Milisaniye hassasiyetiyle kayıt" },
  { icon: Zap, label: "Otomatik çoklu ders ekleme" },
  { icon: Shield, label: "Verileriniz yalnızca tarayıcınızda" },
];

interface AuthLayoutProps {
  children: React.ReactNode;
  subtitle?: string;
}

export default function AuthLayout({
  children,
  subtitle = "Otomatik ders kayıt aracı",
}: AuthLayoutProps) {
  return (
    <LazyMotion features={domMax} strict>
      <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4">
        {/* Branding */}
        <m.div
          className="mb-6 text-center"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        >
          <div className="mb-2 flex items-center justify-center gap-2.5">
            <span className="h-3 w-3 bg-primary" aria-hidden />
            <h1 className="text-3xl font-semibold tracking-tight">
              İTÜ Otostop
            </h1>
          </div>
          <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
            {subtitle}
          </p>
        </m.div>

        {/* Auth card wrapper */}
        <m.div
          className="w-full max-w-[420px]"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 260, damping: 28, delay: 0.1 }}
        >
          <div className="border bg-card p-6">{children}</div>
        </m.div>

        {/* Trust signals */}
        <m.div
          className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.5 }}
        >
          {features.map((f) => (
            <div
              key={f.label}
              className="flex items-center gap-1.5 text-[11px] text-muted-foreground"
            >
              <f.icon className="h-3 w-3" />
              <span>{f.label}</span>
            </div>
          ))}
        </m.div>
      </div>
    </LazyMotion>
  );
}
