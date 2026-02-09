-- ═══════════════════════════════════════════════════
-- İTÜ Otostop — Supabase Tablo Oluşturma
-- Supabase SQL Editor'de çalıştırın
-- ═══════════════════════════════════════════════════

-- 1) Kullanıcı Ayarları (1 satır per user)
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

-- 2) Ders Şablonları (presets — N satır per user)
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

-- Index for fast lookups by user
CREATE INDEX IF NOT EXISTS idx_user_configs_clerk ON user_configs(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_user_presets_clerk ON user_presets(clerk_user_id);

-- 3) Row Level Security — direkt tablo erişimini engelle
ALTER TABLE user_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_presets ENABLE ROW LEVEL SECURITY;

-- Tüm veri erişimi SECURITY DEFINER RPC fonksiyonları üzerinden yapılır.
-- RPC fonksiyonları (get_user_config, save_user_config, get_user_presets, vb.)
-- clerk_user_id parametresi ile filtreleme yapar ve SECURITY DEFINER ile
-- RLS'i bypass eder. Anon key ile direkt tablo erişimi KAPATILDI.

-- NOT: Mevcut "anon_full_access_*" policy'leri varsa önce silin:
-- DROP POLICY IF EXISTS "anon_full_access_configs" ON user_configs;
-- DROP POLICY IF EXISTS "anon_full_access_presets" ON user_presets;

CREATE POLICY "deny_direct_access_configs" ON user_configs
  FOR ALL USING (false) WITH CHECK (false);

CREATE POLICY "deny_direct_access_presets" ON user_presets
  FOR ALL USING (false) WITH CHECK (false);
