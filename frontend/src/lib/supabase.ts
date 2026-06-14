import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

// Clerk session token'ını Supabase'e ilet (Third-Party Auth).
// Kimlik sunucuda RPC içinde auth.jwt()->>'sub' ile doğrulanır — client
// hiçbir kullanıcı ID'si göndermez. window.Clerk, client'ta yüklendikten
// sonra hazırdır; supabase-js her istekte accessToken'ı yeniden çağırır.
declare global {
  interface Window {
    Clerk?: { session?: { getToken: () => Promise<string | null> } };
  }
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  accessToken: async () => {
    if (typeof window === "undefined") return null;
    return (await window.Clerk?.session?.getToken()) ?? null;
  },
});
