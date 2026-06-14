"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useUser, useClerk } from "@clerk/nextjs";
import { m, AnimatePresence } from "motion/react";
import { Settings, LogOut, ChevronDown } from "lucide-react";
import Image from "next/image";

export function UserMenu() {
  const { user } = useUser();
  const { signOut, openUserProfile } = useClerk();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  const handleManageAccount = useCallback(() => {
    setOpen(false);
    openUserProfile();
  }, [openUserProfile]);

  const handleSignOut = useCallback(() => {
    setOpen(false);
    signOut();
  }, [signOut]);

  if (!user) return null;

  const initials =
    ((user.firstName?.[0] ?? "") + (user.lastName?.[0] ?? "")).toUpperCase() ||
    user.emailAddresses?.[0]?.emailAddress?.[0]?.toUpperCase() ||
    "?";

  const displayName =
    user.fullName ||
    user.emailAddresses?.[0]?.emailAddress?.split("@")[0] ||
    "Kullanıcı";

  const email = user.primaryEmailAddress?.emailAddress || "";

  return (
    <div className="relative" ref={menuRef}>
      {/* Trigger */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 p-1 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        aria-expanded={open}
        aria-haspopup="true"
      >
        {user.imageUrl ? (
          <Image
            src={user.imageUrl}
            alt={displayName}
            width={32}
            height={32}
            className="h-8 w-8 border object-cover"
          />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center border border-primary bg-primary/10 text-xs font-bold text-primary">
            {initials}
          </div>
        )}
        <ChevronDown
          className={`h-3 w-3 text-muted-foreground transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {/* Dropdown */}
      <AnimatePresence>
        {open && (
          <m.div
            initial={{ opacity: 0, scale: 0.95, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -4 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute right-0 top-full z-[200] mt-2 w-64 origin-top-right border bg-popover"
          >
            {/* User Info Section */}
            <div className="border-b p-3">
              <div className="flex items-center gap-3">
                {user.imageUrl ? (
                  <Image
                    src={user.imageUrl}
                    alt={displayName}
                    width={40}
                    height={40}
                    className="h-10 w-10 border object-cover"
                  />
                ) : (
                  <div className="flex h-10 w-10 items-center justify-center border border-primary bg-primary/10 text-sm font-bold text-primary">
                    {initials}
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-foreground truncate">
                    {displayName}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {email}
                  </p>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="p-1.5">
              <button
                onClick={handleManageAccount}
                className="flex w-full items-center gap-2.5 px-2.5 py-2 text-sm text-foreground/80 transition-colors hover:bg-accent hover:text-foreground"
              >
                <Settings className="h-4 w-4 text-muted-foreground" />
                Hesabı Yönet
              </button>

              <div className="my-1 h-px bg-border" />

              <button
                onClick={handleSignOut}
                className="flex w-full items-center gap-2.5 px-2.5 py-2 text-sm text-status-err transition-colors hover:bg-status-err/10"
              >
                <LogOut className="h-4 w-4" />
                Çıkış Yap
              </button>
            </div>
          </m.div>
        )}
      </AnimatePresence>
    </div>
  );
}
