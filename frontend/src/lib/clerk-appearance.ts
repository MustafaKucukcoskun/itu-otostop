/**
 * Shared Clerk appearance.elements overrides.
 *
 * Clerk UI yüzeylerini (form, OAuth butonları, OTP, hata banner'ı) İTÜ Otostop'un
 * "Chronometer" tasarım diline uyarlar: keskin köşeler, hairline border,
 * solid international orange primary, gradient/glow yok.
 *
 * Dış kart şeffaftır: cam yerine <AuthLayout> hairline panel sağlar.
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
      "!rounded-none !border !border-border !bg-card hover:!bg-accent !transition-colors !shadow-none",
    socialButtonsBlockButtonText: "!font-medium !text-foreground/80",
    socialButtonsProviderIcon: "!w-5 !h-5",

    // ─── Divider ───────────────────────────────────────────
    dividerLine: "!bg-border",
    dividerText: "!text-muted-foreground !text-xs",

    // ─── Form fields ───────────────────────────────────────
    formFieldLabel:
      "!text-muted-foreground !font-medium !text-xs !tracking-wide",
    formFieldInput:
      "!rounded-none !bg-background !border-border focus:!border-primary focus:!ring-0 !transition-colors !text-sm",
    formFieldSuccessText: "!text-[--status-ok] !text-xs",

    // ─── Error states ──────────────────────────────────────
    formFieldErrorText: "!text-[--status-err] !text-xs",
    alert:
      "!rounded-none !bg-card !border-l-2 !border-l-[--status-err] !border !border-border !text-foreground",
    alertText: "!text-sm",

    // ─── Submit button ─────────────────────────────────────
    formButtonPrimary:
      "!rounded-none !bg-primary hover:!bg-primary/90 !text-primary-foreground !font-semibold !shadow-none !transition-colors !h-11",

    // ─── Footer action (Hesabınız yok mu? Kayıt ol) ────────
    footerAction: "!text-muted-foreground !text-sm",
    footerActionLink:
      "!text-primary !font-semibold hover:!text-primary/80 !transition-colors",

    // ─── Verification step (OTP) ───────────────────────────
    otpCodeFieldInput:
      "!rounded-none !border-border !bg-background focus:!border-primary focus:!ring-0 !text-lg !font-mono",
    formResendCodeLink:
      "!text-primary/80 hover:!text-primary !transition-colors !text-sm",

    // ─── Identity preview (back on verification) ───────────
    identityPreviewEditButton:
      "!text-primary/80 hover:!text-primary !transition-colors",
    identityPreviewText: "!text-foreground/80 !text-sm",
  },
} as const;
