import { supabase } from "@/lib/supabase";

export interface CloudConfig {
  ecrn_list: string[];
  scrn_list: string[];
  kayit_saati: string;
  max_deneme: number;
  retry_aralik: number;
  gecikme_buffer: number;
  dry_run: boolean;
  updated_at: string;
}

export class ConfigService {
  /**
   * Kullanıcının bulut ayarlarını getirir.
   * Kayıt yoksa null döner.
   */
  static async getUserConfig(clerkUserId: string): Promise<CloudConfig | null> {
    try {
      const { data, error } = await supabase.rpc("get_user_config", {
        p_clerk_user_id: clerkUserId,
      });
      if (error) {
        console.error("[ConfigService] get error:", error.message);
        return null;
      }
      return data?.[0] ?? null;
    } catch {
      return null;
    }
  }

  /**
   * Kullanıcı ayarlarını buluta kaydeder (upsert).
   */
  static async saveUserConfig(
    clerkUserId: string,
    config: Omit<CloudConfig, "updated_at">,
  ): Promise<boolean> {
    try {
      const { error } = await supabase.rpc("save_user_config", {
        p_clerk_user_id: clerkUserId,
        p_ecrn_list: config.ecrn_list,
        p_scrn_list: config.scrn_list,
        p_kayit_saati: config.kayit_saati,
        p_max_deneme: config.max_deneme,
        p_retry_aralik: config.retry_aralik,
        p_gecikme_buffer: config.gecikme_buffer,
        p_dry_run: config.dry_run,
      });
      if (error) {
        console.error("[ConfigService] save error:", error.message);
        return false;
      }
      return true;
    } catch {
      return false;
    }
  }
}
