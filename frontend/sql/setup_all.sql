-- ═══════════════════════════════════════════════════════════════
-- İTÜ Otostop — Supabase Tek Seferlik Kurulum (GÜVENLİ / Clerk JWT)
--
-- Yeni Supabase projesinde: Dashboard → SQL Editor → bu dosyanın
-- tamamını yapıştır → RUN.
--
-- ÖN KOŞUL (panel ayarları — bu SQL'den önce yapın):
--   1) Clerk Dashboard → Integrations → Supabase'i etkinleştir
--      (session token'a role="authenticated" claim'i ekler)
--   2) Supabase Dashboard → Authentication → Third-Party Auth → Clerk ekle
--      (Clerk domain: moved-rattler-15.clerk.accounts.dev)
--
-- GÜVENLİK: Kimlik client'tan GELMEZ. RPC'ler kullanıcı ID'sini
-- auth.jwt()->>'sub' ile token'dan türetir; anon EXECUTE kaldırılmıştır.
-- Böylece bir kullanıcı yalnızca KENDİ verisine erişebilir (IDOR kapalı).
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

-- ── 2) RLS — direkt tablo erişimini tamamen kapat ──────────────
-- Tüm erişim SECURITY DEFINER RPC'leri üzerinden; doğrudan tablo erişimi yok.

ALTER TABLE user_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_presets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "deny_direct_access_configs" ON user_configs;
DROP POLICY IF EXISTS "deny_direct_access_presets" ON user_presets;

CREATE POLICY "deny_direct_access_configs" ON user_configs
  FOR ALL USING (false) WITH CHECK (false);

CREATE POLICY "deny_direct_access_presets" ON user_presets
  FOR ALL USING (false) WITH CHECK (false);

-- ── 3) RPC: get_user_config (kimlik token'dan) ─────────────────
DROP FUNCTION IF EXISTS get_user_config(TEXT);
DROP FUNCTION IF EXISTS get_user_config();
CREATE FUNCTION get_user_config()
RETURNS TABLE (
  ecrn_list TEXT[],
  scrn_list TEXT[],
  kayit_saati TEXT,
  max_deneme INTEGER,
  retry_aralik DOUBLE PRECISION,
  dry_run BOOLEAN,
  updated_at TIMESTAMPTZ
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_uid TEXT := auth.jwt() ->> 'sub';
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'unauthenticated'; END IF;
  RETURN QUERY
    SELECT c.ecrn_list, c.scrn_list, c.kayit_saati, c.max_deneme,
           c.retry_aralik, c.dry_run, c.updated_at
    FROM user_configs c
    WHERE c.clerk_user_id = v_uid
    LIMIT 1;
END $$;

-- ── 4) RPC: save_user_config (upsert, kimlik token'dan) ────────
DROP FUNCTION IF EXISTS save_user_config(TEXT, TEXT[], TEXT[], TEXT, INTEGER, DOUBLE PRECISION, BOOLEAN);
DROP FUNCTION IF EXISTS save_user_config(TEXT[], TEXT[], TEXT, INTEGER, DOUBLE PRECISION, BOOLEAN);
CREATE FUNCTION save_user_config(
  p_ecrn_list TEXT[],
  p_scrn_list TEXT[],
  p_kayit_saati TEXT,
  p_max_deneme INTEGER,
  p_retry_aralik DOUBLE PRECISION,
  p_dry_run BOOLEAN
)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_uid TEXT := auth.jwt() ->> 'sub';
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'unauthenticated'; END IF;
  INSERT INTO user_configs (clerk_user_id, ecrn_list, scrn_list, kayit_saati, max_deneme, retry_aralik, dry_run, updated_at)
  VALUES (v_uid, p_ecrn_list, p_scrn_list, p_kayit_saati, p_max_deneme, p_retry_aralik, p_dry_run, now())
  ON CONFLICT (clerk_user_id)
  DO UPDATE SET
    ecrn_list = EXCLUDED.ecrn_list,
    scrn_list = EXCLUDED.scrn_list,
    kayit_saati = EXCLUDED.kayit_saati,
    max_deneme = EXCLUDED.max_deneme,
    retry_aralik = EXCLUDED.retry_aralik,
    dry_run = EXCLUDED.dry_run,
    updated_at = now();
END $$;

-- ── 5) RPC: get_user_presets (kimlik token'dan) ────────────────
DROP FUNCTION IF EXISTS get_user_presets(TEXT);
DROP FUNCTION IF EXISTS get_user_presets();
CREATE FUNCTION get_user_presets()
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
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_uid TEXT := auth.jwt() ->> 'sub';
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'unauthenticated'; END IF;
  RETURN QUERY
    SELECT p.id, p.name, p.ecrn_list, p.scrn_list, p.kayit_saati,
           p.max_deneme, p.retry_aralik, p.created_at
    FROM user_presets p
    WHERE p.clerk_user_id = v_uid
    ORDER BY p.created_at DESC;
END $$;

-- ── 6) RPC: save_user_preset (kimlik token'dan) ────────────────
DROP FUNCTION IF EXISTS save_user_preset(TEXT, TEXT, TEXT[], TEXT[], TEXT, INTEGER, DOUBLE PRECISION);
DROP FUNCTION IF EXISTS save_user_preset(TEXT, TEXT[], TEXT[], TEXT, INTEGER, DOUBLE PRECISION);
CREATE FUNCTION save_user_preset(
  p_name TEXT,
  p_ecrn_list TEXT[],
  p_scrn_list TEXT[],
  p_kayit_saati TEXT,
  p_max_deneme INTEGER,
  p_retry_aralik DOUBLE PRECISION
)
RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_uid TEXT := auth.jwt() ->> 'sub';
  v_id UUID;
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'unauthenticated'; END IF;
  INSERT INTO user_presets (clerk_user_id, name, ecrn_list, scrn_list, kayit_saati, max_deneme, retry_aralik)
  VALUES (v_uid, p_name, p_ecrn_list, p_scrn_list, p_kayit_saati, p_max_deneme, p_retry_aralik)
  RETURNING id INTO v_id;
  RETURN v_id;
END $$;

-- ── 7) RPC: delete_user_preset (kimlik token'dan) ──────────────
DROP FUNCTION IF EXISTS delete_user_preset(TEXT, UUID);
DROP FUNCTION IF EXISTS delete_user_preset(UUID);
CREATE FUNCTION delete_user_preset(p_preset_id UUID)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_uid TEXT := auth.jwt() ->> 'sub';
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'unauthenticated'; END IF;
  DELETE FROM user_presets WHERE id = p_preset_id AND clerk_user_id = v_uid;
END $$;

-- ── 8) İzinler — anon'dan EXECUTE'ı kaldır, sadece authenticated ─
-- NOT: Supabase yeni fonksiyonlara anon'a DOĞRUDAN grant verir; bu yüzden
-- sadece PUBLIC değil, anon da açıkça revoke edilmeli.
REVOKE EXECUTE ON FUNCTION get_user_config()            FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION save_user_config(TEXT[], TEXT[], TEXT, INTEGER, DOUBLE PRECISION, BOOLEAN) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION get_user_presets()           FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION save_user_preset(TEXT, TEXT[], TEXT[], TEXT, INTEGER, DOUBLE PRECISION) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION delete_user_preset(UUID)     FROM PUBLIC, anon;

GRANT EXECUTE ON FUNCTION get_user_config()             TO authenticated;
GRANT EXECUTE ON FUNCTION save_user_config(TEXT[], TEXT[], TEXT, INTEGER, DOUBLE PRECISION, BOOLEAN) TO authenticated;
GRANT EXECUTE ON FUNCTION get_user_presets()            TO authenticated;
GRANT EXECUTE ON FUNCTION save_user_preset(TEXT, TEXT[], TEXT[], TEXT, INTEGER, DOUBLE PRECISION) TO authenticated;
GRANT EXECUTE ON FUNCTION delete_user_preset(UUID)      TO authenticated;

-- ✓ Kurulum tamam. Kimlik token'dan doğrulanır; başkasının verisine erişim yok.
