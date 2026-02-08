-- ═══════════════════════════════════════════════════
-- get_user_config: Kullanıcı ayarlarını getirir
-- ═══════════════════════════════════════════════════
DROP FUNCTION IF EXISTS get_user_config;

CREATE FUNCTION get_user_config(p_clerk_user_id TEXT)
RETURNS TABLE (
  ecrn_list TEXT[],
  scrn_list TEXT[],
  kayit_saati TEXT,
  max_deneme INTEGER,
  retry_aralik DOUBLE PRECISION,
  gecikme_buffer DOUBLE PRECISION,
  dry_run BOOLEAN,
  updated_at TIMESTAMPTZ
)
LANGUAGE sql
SECURITY DEFINER
AS $$
  SELECT ecrn_list, scrn_list, kayit_saati, max_deneme, retry_aralik, gecikme_buffer, dry_run, updated_at
  FROM user_configs
  WHERE clerk_user_id = p_clerk_user_id
  LIMIT 1;
$$;
