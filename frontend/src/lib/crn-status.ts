/**
 * CRN sonuç durumlarının ortak yorumu — sonuç ekranı, toast ve bildirim
 * AYNI tanımı kullanmalı.
 *
 * Eskiden sonuç ekranı "Zaten kayıtlı"yı başarı sayıyordu, toast saymıyordu:
 * aynı kayıt için ekran "KAYIT TAMAM", toast "başarılı ders yok" diyordu.
 * Durum anahtarları backend/models.py CRNStatus ile birebir.
 */

type Sonuclar = Record<string, { status: string }>;

/** Kaydın amacı ders almak: yalnızca alınan ya da zaten kayıtlı ders başarı. */
export function isAlindi(status: string): boolean {
  return status === "success" || status === "already";
}

/**
 * Ne başarı ne hata. Bırakma kaydın amacı değil, bir araç: Bırak:[A] Ekle:[B]
 * takasında B dolu çıkıp A bırakıldıysa öğrenci A'yı kaybetmiş, B'yi
 * alamamıştır. Bırakmayı başarı saymak bu en kötü sonucu yeşil "KAYIT TAMAM"
 * ve başarı sesiyle gösteriyordu. İptal kullanıcının kararı; bekleyen henüz
 * belli değil.
 */
export function isNotr(status: string): boolean {
  return status === "pending" || status === "dropped" || status === "cancelled";
}

/** Geri kalan her şey: dolu, çakışma, bırakılamadı, bilinmeyen kod... */
export function isBasarisiz(status: string): boolean {
  return !isAlindi(status) && !isNotr(status);
}

export function ozetle(results: Sonuclar) {
  const v = Object.values(results);
  return {
    alinan: v.filter((r) => isAlindi(r.status)).length,
    birakilan: v.filter((r) => r.status === "dropped").length,
    basarisiz: v.filter((r) => isBasarisiz(r.status)).length,
    toplam: v.length,
  };
}

/** "2 ders kayıtlı · 1 ders bırakıldı" — hiç ders ALINMADIYSA null. */
export function ozetMetni(results: Sonuclar): string | null {
  const { alinan, birakilan } = ozetle(results);
  if (alinan === 0) return null;
  const parcalar = [`${alinan} ders kayıtlı`];
  if (birakilan > 0) parcalar.push(`${birakilan} ders bırakıldı`);
  return parcalar.join(" · ");
}

/** Ders alınamadığında da bırakılan söylenmeli: " · 1 ders bırakıldı". */
export function birakilanEki(results: Sonuclar): string {
  const { birakilan } = ozetle(results);
  return birakilan > 0 ? ` · ${birakilan} ders bırakıldı` : "";
}
