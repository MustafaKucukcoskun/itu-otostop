import { supabase } from "@/lib/supabase";
import type { Preset } from "@/hooks/use-presets";

export class PresetService {
  /**
   * Kullanıcının tüm şablonlarını buluttan getirir.
   */
  static async getUserPresets(clerkUserId: string): Promise<Preset[]> {
    try {
      const { data, error } = await supabase.rpc("get_user_presets", {
        p_clerk_user_id: clerkUserId,
      });
      if (error) {
        console.error("[PresetService] get error:", error.message);
        return [];
      }
      return (data ?? []).map(
        (row: {
          id: string;
          name: string;
          ecrn_list: string[];
          scrn_list: string[];
          kayit_saati: string;
          max_deneme: number;
          retry_aralik: number;
          gecikme_buffer: number;
          created_at: string;
        }) => ({
          id: row.id,
          name: row.name,
          ecrn_list: row.ecrn_list ?? [],
          scrn_list: row.scrn_list ?? [],
          kayit_saati: row.kayit_saati ?? "",
          max_deneme: row.max_deneme ?? 60,
          retry_aralik: row.retry_aralik ?? 3.0,
          gecikme_buffer: row.gecikme_buffer ?? 0.025,
          created_at: new Date(row.created_at).getTime(),
        }),
      );
    } catch {
      return [];
    }
  }

  /**
   * Yeni şablon kaydeder.
   */
  static async savePreset(
    clerkUserId: string,
    preset: Omit<Preset, "id" | "created_at">,
  ): Promise<string | null> {
    try {
      const { data, error } = await supabase.rpc("save_user_preset", {
        p_clerk_user_id: clerkUserId,
        p_name: preset.name,
        p_ecrn_list: preset.ecrn_list,
        p_scrn_list: preset.scrn_list,
        p_kayit_saati: preset.kayit_saati,
        p_max_deneme: preset.max_deneme,
        p_retry_aralik: preset.retry_aralik,
        p_gecikme_buffer: preset.gecikme_buffer,
      });
      if (error) {
        console.error("[PresetService] save error:", error.message);
        return null;
      }
      return data;
    } catch {
      return null;
    }
  }

  /**
   * Şablon siler.
   */
  static async deletePreset(
    clerkUserId: string,
    presetId: string,
  ): Promise<boolean> {
    try {
      const { error } = await supabase.rpc("delete_user_preset", {
        p_clerk_user_id: clerkUserId,
        p_preset_id: presetId,
      });
      if (error) {
        console.error("[PresetService] delete error:", error.message);
        return false;
      }
      return true;
    } catch {
      return false;
    }
  }
}
