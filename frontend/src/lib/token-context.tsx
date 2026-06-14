"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import { useUser } from "@clerk/nextjs";

/**
 * OBS Bearer token'ı için bellek-içi context.
 *
 * Token sayfa-üstü tutulduğu için Ders Planı ↔ Kayıt Motoru gibi SPA
 * navigasyonlarında KAYBOLMAZ. Diske/buluta YAZILMAZ (güvenlik modeli aynı):
 * sekme kapanışında / hard refresh'te silinir. Clerk kullanıcısı değişince
 * de temizlenir (başka kullanıcı önceki token'ı görmesin).
 */
interface TokenContextValue {
  token: string;
  setToken: (t: string) => void;
}

const TokenContext = createContext<TokenContextValue | null>(null);

export function TokenProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState("");
  const { user } = useUser();
  const lastUserRef = useRef<string | null | undefined>(undefined);

  useEffect(() => {
    const uid = user?.id ?? null;
    // İlk render'da temizleme yapma; sadece gerçek kullanıcı DEĞİŞİMİNDE
    if (lastUserRef.current !== undefined && lastUserRef.current !== uid) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- kullanıcı değişiminde token güvenlik temizliği
      setToken("");
    }
    lastUserRef.current = uid;
  }, [user?.id]);

  return (
    <TokenContext.Provider value={{ token, setToken }}>
      {children}
    </TokenContext.Provider>
  );
}

export function useToken(): TokenContextValue {
  const ctx = useContext(TokenContext);
  if (!ctx) {
    throw new Error("useToken, <TokenProvider> içinde kullanılmalı");
  }
  return ctx;
}
