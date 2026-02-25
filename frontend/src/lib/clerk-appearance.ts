/**
 * Shared Clerk appearance.elements overrides.
 *
 * These class strings deeply restyle every Clerk UI surface —
 * initial form, OAuth buttons, verification step (OTP), and error banners —
 * to match İTÜ Otostop's glassmorphism design system.
 *
 * The outer card is made transparent: the glass wrapper is provided by
 * <AuthLayout> instead of Clerk's own card styling.
 */
export const clerkAppearance = {
  elements: {
    // ─── Card ──────────────────────────────────────────────
    rootBox: "w-full",
    cardBox: "!shadow-none !rounded-none !ring-0",
    card: "!bg-transparent !shadow-none !border-none !rounded-none !ring-0",
    card__main: "!gap-5",

    // ─── Hide Clerk's branding ─────────────────────────────
    headerTitle: "!hidden",
    headerSubtitle: "!hidden",
    footer: "!hidden",

    // ─── Social login buttons ──────────────────────────────
    socialButtonsBlockButton:
      "!rounded-xl !border !border-border/30 !bg-card/50 hover:!bg-muted/60 !transition-all !duration-200 !shadow-sm hover:!shadow-md",
    socialButtonsBlockButtonText: "!font-medium !text-foreground/80",
    socialButtonsProviderIcon: "!w-5 !h-5",

    // ─── Divider ───────────────────────────────────────────
    dividerLine: "!bg-border/30",
    dividerText: "!text-muted-foreground/50 !text-xs",

    // ─── Form fields ───────────────────────────────────────
    formFieldLabel:
      "!text-muted-foreground/70 !font-medium !text-xs !tracking-wide",
    formFieldInput:
      "!rounded-xl !bg-background/60 !border-border/40 focus:!border-primary/50 focus:!ring-2 focus:!ring-primary/20 !transition-all !duration-200 !text-sm",
    formFieldSuccessText: "!text-emerald-600 dark:!text-emerald-400 !text-xs",

    // ─── Error states ──────────────────────────────────────
    formFieldErrorText: "!text-red-500 dark:!text-red-400 !text-xs",
    alert:
      "!rounded-xl !bg-red-500/8 !border-red-500/20 !border !text-red-700 dark:!text-red-300",
    alertText: "!text-sm",

    // ─── Submit button ─────────────────────────────────────
    formButtonPrimary:
      "!rounded-xl !bg-gradient-to-r !from-primary !to-emerald-600 hover:!from-primary/90 hover:!to-emerald-500 !text-white !font-semibold !shadow-lg !shadow-primary/20 hover:!shadow-primary/30 !transition-all !duration-200 !h-11",

    // ─── Footer action (Hesabınız yok mu? Kayıt ol) ────────
    footerAction: "!text-muted-foreground/50 !text-sm",
    footerActionLink:
      "!text-primary !font-semibold hover:!text-primary/80 !transition-colors",

    // ─── Verification step (OTP) ───────────────────────────
    otpCodeFieldInput:
      "!rounded-lg !border-border/40 !bg-background/60 focus:!border-primary/50 focus:!ring-2 focus:!ring-primary/20 !text-lg !font-mono",
    formResendCodeLink:
      "!text-primary/70 hover:!text-primary !transition-colors !text-sm",

    // ─── Identity preview (back on verification) ───────────
    identityPreviewEditButton:
      "!text-primary/70 hover:!text-primary !transition-colors",
    identityPreviewText: "!text-foreground/80 !text-sm",
  },
} as const;
