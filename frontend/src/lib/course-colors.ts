/**
 * Ders renkleri — schedule-grid (ders planı) ve weekly-schedule (dashboard)
 * arasında TEK kaynak. Aynı ders her iki sayfada aynı rengi alır.
 *
 * Tasarım: ders kimliği hue'lu **bg tint + sol kenar şeridi** ile verilir;
 * METİN her zaman tema-duyarlı (text-foreground) — böylece light/dark her
 * temada okunur. (Önceki oklch(0.85 ...) açık metin light temada kayboluyordu.)
 *
 * Hue slotları globals.css `--course-h-0..7` ve DESIGN_SYSTEM ile aynı.
 */
export const COURSE_HUES = [250, 185, 35, 350, 145, 65, 290, 210] as const;

export interface CourseBlockStyle {
  background: string;
  borderColor: string;
  /** Sol kenar şeridi + renk noktası (solid hue) */
  accent: string;
}

export function courseBlockStyle(colorIndex: number): CourseBlockStyle {
  const h = COURSE_HUES[colorIndex % COURSE_HUES.length];
  return {
    background: `oklch(0.62 0.13 ${h} / 0.16)`,
    borderColor: `oklch(0.62 0.14 ${h} / 0.35)`,
    accent: `oklch(0.66 0.17 ${h})`,
  };
}
