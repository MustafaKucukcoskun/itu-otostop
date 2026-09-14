import { supabase } from "@/lib/supabase";
import type { Preset } from "@/hooks/use-presets";

type PresetRow = {
  id: string;
  name: string;
  ecrn_list: string[];
  scrn_list: string[];
  kayit_saati: string;
  max_deneme: number;
  retry_aralik: number;
  created_at: string;
};

export class PresetService {
  /**
   * Kullanıcının tüm şablonlarını buluttan getirir.
   *
   * Hata hâlinde `null` döner — boş dizi DEĞİL. Bu ayrım kritik: eski sürüm
   * hatada `[]` döndürüyordu, çağıran taraf bunu "bulut boş" sanıp yerel
   * şablonları yeniden yüklüyordu ve her geçici ağ hatası şablonları
   * çoğaltıyordu.
   */
  static async getUserPresets(clerkUserId: string): Promise<Preset[] | null> {
    if (!clerkUserId) return null;
    try {
      // Kimlik token'dan (auth.jwt()->>'sub') türetilir — client ID göndermez
      const { data, error } = await supabase.rpc("get_user_presets");
      if (error) {
        console.error("[PresetService] get error:", error.message);
        return null;
      }
      return ((data ?? []) as PresetRow[]).map((row) => ({
        id: row.id,
        name: row.name,
        ecrn_list: row.ecrn_list ?? [],
        scrn_list: row.scrn_list ?? [],
        kayit_saati: row.kayit_saati ?? "",
        max_deneme: row.max_deneme ?? 60,
        retry_aralik: row.retry_aralik ?? 3.0,
        created_at: new Date(row.created_at).getTime(),
      }));
    } catch {
      return null;
    }
  }

  /** Yeni şablon kaydeder; buluttaki gerçek id'yi döndürür. */
  static async savePreset(
    clerkUserId: string,
    preset: Omit<Preset, "id" | "created_at">,
  ): Promise<string | null> {
    if (!clerkUserId) return null;
    try {
      const { data, error } = await supabase.rpc("save_user_preset", {
        p_name: preset.name,
        p_ecrn_list: preset.ecrn_list,
        p_scrn_list: preset.scrn_list,
        p_kayit_saati: preset.kayit_saati,
        p_max_deneme: preset.max_deneme,
        p_retry_aralik: preset.retry_aralik,
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
   * Şablonu id ile siler. SİLİNEN SATIR SAYISINI döndürür; hata hâlinde -1.
   *
   * 0 dönmesi "o id bulutta yok" demektir — yerel id ile bulut id'si ayrışmış
   * olabilir. Çağıran taraf bunu görüp ada göre silmeye geçer, yoksa şablon
   * sayfa yenilenince geri gelir.
   */
  static async deletePreset(
    clerkUserId: string,
    presetId: string,
  ): Promise<number> {
    if (!clerkUserId) return -1;
    try {
      const { data, error } = await supabase.rpc("delete_user_preset", {
        p_preset_id: presetId,
      });
      if (error) {
        console.error("[PresetService] delete error:", error.message);
        return -1;
      }
      return typeof data === "number" ? data : 0;
    } catch {
      return -1;
    }
  }

  /**
   * Onarım yolu: id ile silinemeyen şablonu ada göre siler.
   *
   * Eski sürümdeki göç hatası yüzünden bazı şablonların yerel id'si bulut
   * id'siyle uyuşmuyor; o kayıtlar id ile silinemez ve "ne kadar silersem
   * sileyim gitmiyor" durumu doğar.
   */
  static async deletePresetsByName(
    clerkUserId: string,
    name: string,
  ): Promise<number> {
    if (!clerkUserId) return -1;
    try {
      const { data, error } = await supabase.rpc("delete_user_presets_by_name", {
        p_name: name,
      });
      if (error) {
        console.error("[PresetService] delete-by-name error:", error.message);
        return -1;
      }
      return typeof data === "number" ? data : 0;
    } catch {
      return -1;
    }
  }
}
