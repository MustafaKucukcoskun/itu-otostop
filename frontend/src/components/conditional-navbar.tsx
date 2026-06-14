"use client";

import { usePathname } from "next/navigation";
import { AppNavbar } from "@/components/app-navbar";

// Navbar'ı tüm sayfalarda layout'tan tek sefer render et; auth sayfalarında gizle.
const HIDDEN_PREFIXES = ["/sign-in", "/sign-up"];

export function ConditionalNavbar() {
  const pathname = usePathname();
  if (HIDDEN_PREFIXES.some((p) => pathname.startsWith(p))) return null;
  return <AppNavbar />;
}
