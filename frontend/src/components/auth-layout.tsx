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
      <div className="min-h-screen mesh-bg flex flex-col items-center justify-center p-4">
        <div className="grain-overlay" />
        <div className="dot-grid fixed inset-0 pointer-events-none z-0" />
        <div className="mesh-orb-accent" />

        {/* Branding */}
        <m.div
          className="relative z-10 text-center mb-6"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        >
          <div className="flex items-center justify-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center ring-1 ring-primary/30 shadow-lg shadow-primary/10">
              <Zap className="h-5 w-5 text-primary" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight">
              <span className="text-gradient-primary">İTÜ</span>{" "}
              <span className="text-foreground/90">Otostop</span>
            </h1>
          </div>
          <p className="text-sm text-muted-foreground/60 font-medium">
            {subtitle}
          </p>
        </m.div>

        {/* Auth card wrapper */}
        <m.div
          className="relative z-10 w-full max-w-[420px]"
          initial={{ opacity: 0, y: 12, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{
            type: "spring",
            stiffness: 260,
            damping: 28,
            delay: 0.1,
          }}
        >
          <div className="glass rounded-2xl shadow-2xl overflow-hidden">
            {children}
          </div>
        </m.div>

        {/* Trust signals */}
        <m.div
          className="relative z-10 mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.5 }}
        >
          {features.map((f) => (
            <div
              key={f.label}
              className="flex items-center gap-1.5 text-[11px] text-muted-foreground/40"
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
