-- ═══════════════════════════════════════════════════
-- delete_user_preset: Kullanıcının şablonunu siler
-- ═══════════════════════════════════════════════════
DROP FUNCTION IF EXISTS delete_user_preset;

CREATE FUNCTION delete_user_preset(
  p_clerk_user_id TEXT,
  p_preset_id UUID
)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
AS $$
  DELETE FROM user_presets
  WHERE id = p_preset_id AND clerk_user_id = p_clerk_user_id;
$$;
