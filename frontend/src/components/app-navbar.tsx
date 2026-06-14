"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { m } from "motion/react";
import { Calendar, Zap, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { UserButton } from "@clerk/nextjs";
import { useCallback, useSyncExternalStore } from "react";

// ── Navigation items ──

const NAV_ITEMS = [
  { href: "/schedule", label: "Ders Planı", icon: Calendar },
  { href: "/", label: "Kayıt Motoru", icon: Zap },
] as const;

const SUBSCRIBE_NOOP = () => () => {};
const GET_TRUE = () => true;
const GET_FALSE = () => false;

// ── Navbar ──

export function AppNavbar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(SUBSCRIBE_NOOP, GET_TRUE, GET_FALSE);

  const toggleTheme = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  // Determine active tab index
  const activeIndex = NAV_ITEMS.findIndex((item) =>
    item.href === "/" ? pathname === "/" : pathname.startsWith(item.href),
  );

  return (
    <header className="sticky top-0 z-50 w-full">
      <div className="bg-background border-b">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
          {/* Wordmark — turuncu ibre işareti */}
          <Link
            href="/"
            className="flex items-center gap-2 text-lg font-semibold tracking-tight"
          >
            <span className="size-2.5 bg-primary" aria-hidden />
            <span>Otostop</span>
          </Link>

          {/* Tab Navigation */}
          <nav className="flex items-center">
            <div className="relative flex gap-0.5 border bg-muted/40 p-1">
              {/* Animated sliding indicator */}
              {activeIndex >= 0 && (
                <m.div
                  layoutId="nav-indicator"
                  className="absolute inset-y-1 border bg-background"
                  style={{
                    width: `calc(${100 / NAV_ITEMS.length}% - 2px)`,
                    left: `calc(${(activeIndex * 100) / NAV_ITEMS.length}% + 1px)`,
                  }}
                  transition={{
                    type: "spring",
                    stiffness: 400,
                    damping: 35,
                  }}
                />
              )}

              {NAV_ITEMS.map((item) => {
                const isActive =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                const Icon = item.icon;

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`relative z-10 flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors duration-200 ${isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                  >
                    <Icon className="size-3.5" />
                    <span className="hidden sm:inline">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </nav>

          {/* Right section: theme toggle + user */}
          <div className="flex items-center gap-2">
            {mounted && (
              <button
                onClick={toggleTheme}
                className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                aria-label="Tema değiştir"
              >
                {theme === "dark" ? (
                  <Sun className="size-4" />
                ) : (
                  <Moon className="size-4" />
                )}
              </button>
            )}
            <UserButton
              appearance={{
                elements: {
                  avatarBox: "size-7",
                },
              }}
            />
          </div>
        </div>
      </div>
    </header>
  );
}
