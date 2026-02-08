-- ═══════════════════════════════════════════════════
-- get_user_presets: Kullanıcının tüm şablonlarını getirir
-- ═══════════════════════════════════════════════════
DROP FUNCTION IF EXISTS get_user_presets;

CREATE FUNCTION get_user_presets(p_clerk_user_id TEXT)
RETURNS TABLE (
  id UUID,
  name TEXT,
  ecrn_list TEXT[],
  scrn_list TEXT[],
  kayit_saati TEXT,
  max_deneme INTEGER,
  retry_aralik DOUBLE PRECISION,
  gecikme_buffer DOUBLE PRECISION,
  created_at TIMESTAMPTZ
)
LANGUAGE sql
SECURITY DEFINER
AS $$
  SELECT id, name, ecrn_list, scrn_list, kayit_saati, max_deneme, retry_aralik, gecikme_buffer, created_at
  FROM user_presets
  WHERE clerk_user_id = p_clerk_user_id
  ORDER BY created_at DESC;
$$;
