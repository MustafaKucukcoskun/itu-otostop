/**
 * CRN sonuç durumlarının ortak yorumu — sonuç ekranı, toast ve bildirim
 * AYNI tanımı kullanmalı.
 *
 * Eskiden sonuç ekranı "Zaten kayıtlı"yı başarı sayıyordu, toast saymıyordu:
 * aynı kayıt için ekran "KAYIT TAMAM", toast "başarılı ders yok" diyordu.
 * Durum anahtarları backend/models.py CRNStatus ile birebir.
 */

type Sonuclar = Record<string, { status: string }>;

/** Kaydın amacına ulaştığı durumlar: ders alındı / zaten kayıtlıydı / bırakıldı. */
export function isOk(status: string): boolean {
  return status === "success" || status === "already" || status === "dropped";
}

export function ozetle(results: Sonuclar) {
  const v = Object.values(results);
  return {
    alinan: v.filter((r) => r.status === "success" || r.status === "already")
      .length,
    birakilan: v.filter((r) => r.status === "dropped").length,
    toplam: v.length,
  };
}

/** "2 ders kayıtlı · 1 ders bırakıldı" — olumlu hiçbir şey yoksa null. */
export function ozetMetni(results: Sonuclar): string | null {
  const { alinan, birakilan } = ozetle(results);
  const parcalar: string[] = [];
  if (alinan > 0) parcalar.push(`${alinan} ders kayıtlı`);
  if (birakilan > 0) parcalar.push(`${birakilan} ders bırakıldı`);
  return parcalar.length ? parcalar.join(" · ") : null;
}
