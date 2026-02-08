import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="min-h-screen mesh-bg flex flex-col items-center justify-center pt-6 p-4">
      <div className="grain-overlay" />

      {/* Animated orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full bg-primary/5 blur-3xl animate-pulse" />
        <div
          className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full bg-emerald-500/5 blur-3xl animate-pulse"
          style={{ animationDelay: "1s" }}
        />
      </div>

      {/* Branding */}
      <div className="relative z-10 text-center mb-8">
        <div className="flex items-center justify-center gap-3 mb-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center ring-1 ring-primary/30">
            <span className="text-lg">⚡</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">
            <span className="text-gradient-primary">İTÜ</span>{" "}
            <span className="text-foreground/90">Otostop</span>
          </h1>
        </div>
        <p className="text-sm text-muted-foreground/50 font-medium">
          Hesap oluştur ve hemen başla
        </p>
      </div>

      <SignUp
        appearance={{
          elements: {
            rootBox: "relative z-10 w-full max-w-[420px]",
            card: "glass !rounded-2xl ring-1 ring-border/20 shadow-2xl !bg-card/80 backdrop-blur-xl",
            headerTitle: "!hidden",
            headerSubtitle: "!hidden",
            socialButtonsBlockButton:
              "!rounded-xl ring-1 ring-border/20 !bg-background/40 hover:!bg-muted/50 !transition-all !duration-200",
            socialButtonsBlockButtonText: "!font-medium",
            dividerLine: "!bg-border/20",
            dividerText: "!text-muted-foreground/40",
            formFieldLabel: "!text-muted-foreground/70 !font-medium !text-sm",
            formFieldInput:
              "!rounded-xl !bg-background/50 !border-border/30 focus:!ring-primary/40 !transition-all",
            formButtonPrimary:
              "!rounded-xl !bg-gradient-to-r !from-primary !to-primary/80 hover:!opacity-90 !text-primary-foreground !font-semibold !shadow-lg !shadow-primary/20 !transition-all !duration-200",
            footerAction: "!text-muted-foreground/50",
            footerActionLink:
              "!text-primary hover:!text-primary/80 !font-medium",
            card__main: "!gap-6",
          },
        }}
      />
    </div>
  );
}
