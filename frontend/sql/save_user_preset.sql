-- ═══════════════════════════════════════════════════
-- save_user_preset: Yeni şablon kaydeder
-- ═══════════════════════════════════════════════════
DROP FUNCTION IF EXISTS save_user_preset;

CREATE FUNCTION save_user_preset(
  p_clerk_user_id TEXT,
  p_name TEXT,
  p_ecrn_list TEXT[],
  p_scrn_list TEXT[],
  p_kayit_saati TEXT,
  p_max_deneme INTEGER,
  p_retry_aralik DOUBLE PRECISION,
  p_gecikme_buffer DOUBLE PRECISION
)
RETURNS UUID
LANGUAGE sql
SECURITY DEFINER
AS $$
  INSERT INTO user_presets (clerk_user_id, name, ecrn_list, scrn_list, kayit_saati, max_deneme, retry_aralik, gecikme_buffer)
  VALUES (p_clerk_user_id, p_name, p_ecrn_list, p_scrn_list, p_kayit_saati, p_max_deneme, p_retry_aralik, p_gecikme_buffer)
  RETURNING id;
$$;
