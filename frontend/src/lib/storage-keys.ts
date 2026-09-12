/**
 * localStorage anahtarları — kullanıcıya göre ayrılmış.
 *
 * Aynı tarayıcıda farklı hesapla giriş yapan kullanıcı öncekinin verisini
 * ne görmeli (gizlilik) ne de üzerine yazmalı (veri kaybı). Paylaşılan
 * bilgisayarlarda (kampüs laboratuvarı) bu kritik.
 */

const SCHEDULE_SELECTED = "otostop-schedule-selected";
const SCHEDULE_EXPORT = "otostop-schedule-export";

/** Ders planındaki seçili dersler */
export const scheduleKeyFor = (userId: string) => `${SCHEDULE_SELECTED}:${userId}`;

/** Ders planı → kayıt motoru tek seferlik aktarım */
export const scheduleExportKeyFor = (userId: string) => `${SCHEDULE_EXPORT}:${userId}`;

/** Kullanıcıya bağlanmadan önce yazılmış eski küresel anahtarlar (göç/temizlik için) */
export const LEGACY_SCHEDULE_SELECTED = SCHEDULE_SELECTED;
export const LEGACY_SCHEDULE_EXPORT = SCHEDULE_EXPORT;
