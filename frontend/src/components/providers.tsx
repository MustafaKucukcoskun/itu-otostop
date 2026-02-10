"use client";

import { ClerkProvider } from "@clerk/nextjs";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import { dark } from "@clerk/themes";
import { trTR } from "@clerk/localizations";
import { useTheme } from "next-themes";
import { LazyMotion, domMax } from "motion/react";

function ClerkThemeWrapper({ children }: { children: React.ReactNode }) {
  const { resolvedTheme } = useTheme();
  return (
    <ClerkProvider
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
      afterSignOutUrl="/sign-in"
      localization={{
        ...trTR,
        signIn: {
          ...((trTR as Record<string, unknown>).signIn as Record<
            string,
            unknown
          >),
          start: {
            ...((
              (trTR as Record<string, unknown>).signIn as Record<
                string,
                unknown
              >
            )?.start as Record<string, unknown>),
            title: "İTÜ Otostop",
            subtitle: "Otomatik ders kayıt aracına giriş yap",
          },
        } as never,
        signUp: {
          ...((trTR as Record<string, unknown>).signUp as Record<
            string,
            unknown
          >),
          start: {
            ...((
              (trTR as Record<string, unknown>).signUp as Record<
                string,
                unknown
              >
            )?.start as Record<string, unknown>),
            title: "İTÜ Otostop",
            subtitle: "Hesap oluştur ve hemen başla",
          },
        } as never,
        userButton: {
          action__signOut: "Çıkış Yap",
          action__manageAccount: "Hesabı Yönet",
        },
      }}
      appearance={{
        baseTheme: resolvedTheme === "dark" ? dark : undefined,
        variables: {
          colorPrimary: "oklch(0.70 0.18 195)",
        },
      }}
    >
      {children}
    </ClerkProvider>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      <LazyMotion features={domMax} strict>
        <ClerkThemeWrapper>{children}</ClerkThemeWrapper>
      </LazyMotion>
    </NextThemesProvider>
  );
}
