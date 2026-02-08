-- ═══════════════════════════════════════════════════
-- save_user_config: Kullanıcı ayarlarını upsert eder
-- ═══════════════════════════════════════════════════
DROP FUNCTION IF EXISTS save_user_config;

CREATE FUNCTION save_user_config(
  p_clerk_user_id TEXT,
  p_ecrn_list TEXT[],
  p_scrn_list TEXT[],
  p_kayit_saati TEXT,
  p_max_deneme INTEGER,
  p_retry_aralik DOUBLE PRECISION,
  p_gecikme_buffer DOUBLE PRECISION,
  p_dry_run BOOLEAN
)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
AS $$
  INSERT INTO user_configs (clerk_user_id, ecrn_list, scrn_list, kayit_saati, max_deneme, retry_aralik, gecikme_buffer, dry_run, updated_at)
  VALUES (p_clerk_user_id, p_ecrn_list, p_scrn_list, p_kayit_saati, p_max_deneme, p_retry_aralik, p_gecikme_buffer, p_dry_run, now())
  ON CONFLICT (clerk_user_id)
  DO UPDATE SET
    ecrn_list = EXCLUDED.ecrn_list,
    scrn_list = EXCLUDED.scrn_list,
    kayit_saati = EXCLUDED.kayit_saati,
    max_deneme = EXCLUDED.max_deneme,
    retry_aralik = EXCLUDED.retry_aralik,
    gecikme_buffer = EXCLUDED.gecikme_buffer,
    dry_run = EXCLUDED.dry_run,
    updated_at = now();
$$;
