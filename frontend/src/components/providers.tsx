"use client";

import { ClerkProvider } from "@clerk/nextjs";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import { dark } from "@clerk/themes";
import { trTR } from "@clerk/localizations";
import { useTheme } from "next-themes";

function ClerkThemeWrapper({ children }: { children: React.ReactNode }) {
  const { resolvedTheme } = useTheme();
  return (
    <ClerkProvider
      localization={{
        ...trTR,
        signIn: {
          start: {
            title: "İTÜ Otostop'a Giriş",
            subtitle: "Devam etmek için giriş yap",
            actionText: "Hesabın yok mu?",
            actionLink: "Kayıt ol",
          },
        },
        signUp: {
          start: {
            title: "İTÜ Otostop'a Kayıt",
            subtitle: "Hesap oluşturmak için devam et",
            actionText: "Zaten hesabın var mı?",
            actionLink: "Giriş yap",
          },
        },
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
      <ClerkThemeWrapper>{children}</ClerkThemeWrapper>
    </NextThemesProvider>
  );
}
