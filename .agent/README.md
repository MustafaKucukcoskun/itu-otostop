# .agent — Geliştirme Süreci Dokümanları

Bu klasör, projenin Claude Code ile yürütülen geliştirme sürecinin **yaşayan dokümanlarını** tutar.
Kod talimatları için tek kaynak `CLAUDE.md`'dir; bu klasör plan, durum ve tasarım kararlarını taşır.

## Yapı

| Dosya / Klasör | Amaç |
|---|---|
| `ROADMAP.md` | Ana yaşayan doküman: fazlar, görevler, durum. Her oturumda buradan devam edilir, biten işler işaretlenir. |
| `DESIGN_SYSTEM.md` | Aktif tasarım sistemi referansı. Redesign tamamlandığında güncellenir. |
| `plans/` | Özellik bazlı implementasyon planları (ör. `schedule-builder.md`). |
| `design-refs/` | Tasarım karar destek verileri: `anti-patterns.csv` (33 AI-slop kalıbı), `personas.csv` (59 tasarım personası), `reference-sites.csv` (109 ödüllü site). |

## Çalışma Kuralları

1. **Oturum başı:** `ROADMAP.md` oku → aktif fazı ve sıradaki görevi belirle.
2. **İş bitince:** İlgili görevi `[x]` işaretle, gerekiyorsa kısa not düş (tarih + ne değişti).
3. **Yeni iş çıkarsa:** Doğru faza ekle; faz yapısını bozma.
4. **Tasarım işi yaparken:** `design-refs/anti-patterns.csv`'ye karşı kontrol et — listedeki kalıplardan biri çıktıya giriyorsa durup alternatifini kullan.
5. **Plan büyürse:** Özellik planını `plans/<slug>.md` olarak ayır, ROADMAP'ten link ver.

> Not: Bu klasör eskiden "refine-kit" adlı Gemini Antigravity framework'ünü içeriyordu (165+ jenerik dosya).
> 2026-06-13'te Claude Code akışına uygun bu sade yapıya dönüştürüldü; proje-spesifik içerik korundu.
