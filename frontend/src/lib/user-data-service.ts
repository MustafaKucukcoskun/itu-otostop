import { supabase } from "@/lib/supabase";

/**
 * Kullanıcı verisinin buluttaki tek adresi (anahtar → JSONB).
 *
 * NEDEN VAR: ders planı yalnızca localStorage'daydı, yani her cihazda ayrı bir
 * plan oluşuyordu — kullanıcı telefondan girdiğinde bilgisayardaki planını
 * göremiyordu. Kullanıcıya ait veri cihazda değil, kimliğinde durmalı.
 *
 * Kimlik client'tan GELMEZ: RPC'ler kullanıcıyı auth.jwt()->>'sub' ile
 * token'dan türetir (bkz. sql/002_user_data.sql).
 */

/** Bulut anahtarları — tek yerde tutulur ki yazım hatası sessizce veri bölmesin. */
export const UserDataKeys = {
  schedule: "schedule",
  crnLabels: "crn_labels",
} as const;

export type UserDataKey = (typeof UserDataKeys)[keyof typeof UserDataKeys];

export class UserDataService {
  /**
   * Veriyi getirir.
   *
   * `null` iki farklı şeyi anlatır ve ayırmak ÖNEMLİDİR:
   *   - kayıt yok (kullanıcı hiç plan yapmamış)
   *   - buluta ulaşılamadı
   * Çağıran taraf ikisini ayırt edemezse, geçici bir ağ hatasında boş planı
   * "kullanıcının planı boş" sanıp üzerine yazabilir. Bu yüzden hata durumunda
   * `undefined`, kayıt yoksa `null` döner.
   */
  static async get<T>(key: UserDataKey): Promise<T | null | undefined> {
    try {
      const { data, error } = await supabase.rpc("get_user_data", {
        p_key: key,
      });
      if (error) {
        console.error(`[UserData] get(${key}) error:`, error.message);
        return undefined; // ulaşılamadı
      }
      return (data ?? null) as T | null;
    } catch {
      return undefined;
    }
  }

  /** Veriyi yazar (upsert). Başarılıysa true. */
  static async set(key: UserDataKey, value: unknown): Promise<boolean> {
    try {
      const { error } = await supabase.rpc("save_user_data", {
        p_key: key,
        p_value: value,
      });
      if (error) {
        console.error(`[UserData] set(${key}) error:`, error.message);
        return false;
      }
      return true;
    } catch {
      return false;
    }
  }

  /** Veriyi siler. */
  static async remove(key: UserDataKey): Promise<boolean> {
    try {
      const { error } = await supabase.rpc("delete_user_data", { p_key: key });
      if (error) {
        console.error(`[UserData] remove(${key}) error:`, error.message);
        return false;
      }
      return true;
    } catch {
      return false;
    }
  }
}
