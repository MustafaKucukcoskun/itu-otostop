-- ═══════════════════════════════════════════════════════════════
-- İTÜ Otostop — Supabase Tek Seferlik Kurulum (TÜMÜ)
-- Yeni bir Supabase projesinde: Dashboard → SQL Editor → bu dosyanın
-- tamamını yapıştır → RUN. Tablolar + RLS + 5 RPC fonksiyonu kurulur.
-- ═══════════════════════════════════════════════════════════════

-- ── 1) Tablolar ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clerk_user_id TEXT NOT NULL UNIQUE,
  ecrn_list TEXT[] DEFAULT '{}',
  scrn_list TEXT[] DEFAULT '{}',
  kayit_saati TEXT DEFAULT '',
  max_deneme INTEGER DEFAULT 60,
  retry_aralik DOUBLE PRECISION DEFAULT 3.0,
  gecikme_buffer DOUBLE PRECISION DEFAULT 0.005,
  dry_run BOOLEAN DEFAULT FALSE,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_presets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clerk_user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  ecrn_list TEXT[] DEFAULT '{}',
  scrn_list TEXT[] DEFAULT '{}',
  kayit_saati TEXT DEFAULT '',
  max_deneme INTEGER DEFAULT 60,
  retry_aralik DOUBLE PRECISION DEFAULT 3.0,
  gecikme_buffer DOUBLE PRECISION DEFAULT 0.005,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_configs_clerk ON user_configs(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_user_presets_clerk ON user_presets(clerk_user_id);

-- ── 2) Row Level Security — direkt tablo erişimini kapat ───────
-- Tüm erişim SECURITY DEFINER RPC fonksiyonları üzerinden, clerk_user_id ile filtreli.

ALTER TABLE user_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_presets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "deny_direct_access_configs" ON user_configs;
DROP POLICY IF EXISTS "deny_direct_access_presets" ON user_presets;

CREATE POLICY "deny_direct_access_configs" ON user_configs
  FOR ALL USING (false) WITH CHECK (false);

CREATE POLICY "deny_direct_access_presets" ON user_presets
  FOR ALL USING (false) WITH CHECK (false);

-- ── 3) RPC: get_user_config ────────────────────────────────────
DROP FUNCTION IF EXISTS get_user_config;
CREATE FUNCTION get_user_config(p_clerk_user_id TEXT)
RETURNS TABLE (
  ecrn_list TEXT[],
  scrn_list TEXT[],
  kayit_saati TEXT,
  max_deneme INTEGER,
  retry_aralik DOUBLE PRECISION,
  dry_run BOOLEAN,
  updated_at TIMESTAMPTZ
)
LANGUAGE sql SECURITY DEFINER AS $$
  SELECT ecrn_list, scrn_list, kayit_saati, max_deneme, retry_aralik, dry_run, updated_at
  FROM user_configs
  WHERE clerk_user_id = p_clerk_user_id
  LIMIT 1;
$$;

-- ── 4) RPC: save_user_config (upsert) ──────────────────────────
DROP FUNCTION IF EXISTS save_user_config;
CREATE FUNCTION save_user_config(
  p_clerk_user_id TEXT,
  p_ecrn_list TEXT[],
  p_scrn_list TEXT[],
  p_kayit_saati TEXT,
  p_max_deneme INTEGER,
  p_retry_aralik DOUBLE PRECISION,
  p_dry_run BOOLEAN
)
RETURNS void
LANGUAGE sql SECURITY DEFINER AS $$
  INSERT INTO user_configs (clerk_user_id, ecrn_list, scrn_list, kayit_saati, max_deneme, retry_aralik, dry_run, updated_at)
  VALUES (p_clerk_user_id, p_ecrn_list, p_scrn_list, p_kayit_saati, p_max_deneme, p_retry_aralik, p_dry_run, now())
  ON CONFLICT (clerk_user_id)
  DO UPDATE SET
    ecrn_list = EXCLUDED.ecrn_list,
    scrn_list = EXCLUDED.scrn_list,
    kayit_saati = EXCLUDED.kayit_saati,
    max_deneme = EXCLUDED.max_deneme,
    retry_aralik = EXCLUDED.retry_aralik,
    dry_run = EXCLUDED.dry_run,
    updated_at = now();
$$;

-- ── 5) RPC: get_user_presets ───────────────────────────────────
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
  created_at TIMESTAMPTZ
)
LANGUAGE sql SECURITY DEFINER AS $$
  SELECT id, name, ecrn_list, scrn_list, kayit_saati, max_deneme, retry_aralik, created_at
  FROM user_presets
  WHERE clerk_user_id = p_clerk_user_id
  ORDER BY created_at DESC;
$$;

-- ── 6) RPC: save_user_preset ───────────────────────────────────
DROP FUNCTION IF EXISTS save_user_preset;
CREATE FUNCTION save_user_preset(
  p_clerk_user_id TEXT,
  p_name TEXT,
  p_ecrn_list TEXT[],
  p_scrn_list TEXT[],
  p_kayit_saati TEXT,
  p_max_deneme INTEGER,
  p_retry_aralik DOUBLE PRECISION
)
RETURNS UUID
LANGUAGE sql SECURITY DEFINER AS $$
  INSERT INTO user_presets (clerk_user_id, name, ecrn_list, scrn_list, kayit_saati, max_deneme, retry_aralik)
  VALUES (p_clerk_user_id, p_name, p_ecrn_list, p_scrn_list, p_kayit_saati, p_max_deneme, p_retry_aralik)
  RETURNING id;
$$;

-- ── 7) RPC: delete_user_preset ─────────────────────────────────
DROP FUNCTION IF EXISTS delete_user_preset;
CREATE FUNCTION delete_user_preset(
  p_clerk_user_id TEXT,
  p_preset_id UUID
)
RETURNS void
LANGUAGE sql SECURITY DEFINER AS $$
  DELETE FROM user_presets
  WHERE id = p_preset_id AND clerk_user_id = p_clerk_user_id;
$$;

-- ✓ Kurulum tamam. Frontend artık get/save config + preset RPC'lerini çağırabilir.
