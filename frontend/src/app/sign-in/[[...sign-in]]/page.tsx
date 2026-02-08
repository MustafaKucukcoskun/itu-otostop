import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="min-h-screen mesh-bg flex flex-col items-center justify-center p-4 gap-6">
      <div className="grain-overlay" />

      {/* Kendi Türkçe başlığımız */}
      <div className="relative z-10 text-center">
        <div className="flex items-center justify-center gap-2.5 mb-2">
          <span className="text-2xl">⚡</span>
          <h1 className="text-2xl font-bold tracking-tight">
            <span className="text-gradient-primary">İTÜ OBS</span>{" "}
            <span className="text-foreground/80">Kayıt</span>
          </h1>
        </div>
        <p className="text-sm text-muted-foreground/60">
          Otomatik ders kayıt aracına giriş yap
        </p>
      </div>

      <SignIn
        appearance={{
          elements: {
            rootBox: "relative z-10 w-full max-w-[400px]",
            card: "glass !rounded-2xl ring-1 ring-border/20 shadow-2xl !bg-transparent",
            headerTitle: "!hidden",
            headerSubtitle: "!hidden",
            socialButtonsBlockButton:
              "!rounded-xl ring-1 ring-border/20 !bg-background/30 hover:!bg-muted/40",
            formFieldInput:
              "!rounded-xl !bg-background/50 ring-1 ring-border/30",
            formButtonPrimary:
              "!rounded-xl !bg-primary hover:!bg-primary/90 !text-primary-foreground",
            footerAction__signIn: "!text-muted-foreground",
            footerActionLink: "!text-primary hover:!underline",
          },
        }}
      />
    </div>
  );
}
