-- ═══════════════════════════════════════════════════════════════
-- İTÜ Otostop — Migration 002: kullanıcı verisi buluta taşınıyor
--
-- Supabase Dashboard → SQL Editor → bu dosyanın tamamını yapıştır → RUN.
-- (setup_all.sql çalıştırıldıktan SONRA. Tekrar çalıştırmak güvenlidir.)
--
-- NEDEN:
--   1) Ders planı yalnızca localStorage'daydı. Kullanıcı telefondan girdiğinde
--      bilgisayardaki planını göremiyordu — cihaz başına ayrı plan.
--   2) Şablon silme "yapışıyordu". Sebep: ilk göçte yerel şablonlar buluta
--      yükleniyor ama DÖNEN bulut id'si yerelde saklanmıyordu. Yerelde eski
--      rastgele id kalıyor, silme o id ile buluta gidiyor, bulutta karşılığı
--      olmadığı için hiçbir şey silinmiyordu; sayfa yenilenince bulut kopyası
--      geri geliyordu. delete_user_preset artık SİLİNEN SATIR SAYISINI döndürür,
--      böylece istemci "bu bulutta yokmuş" durumunu görebilir.
--
-- TASARIM: `user_data` anahtar/JSONB tablosu. Ders planı, CRN etiketleri ve
-- ileride eklenecek her kullanıcı tercihi buraya sığar; her yeni alan için
-- ayrı tablo ve ayrı migration gerekmez.
--
-- GÜVENLİK: setup_all.sql ile aynı model — RLS her şeyi kapatır, erişim
-- yalnızca SECURITY DEFINER RPC'lerden ve kimlik auth.jwt()->>'sub'dan gelir.
-- ═══════════════════════════════════════════════════════════════

-- ── 1) Tablo ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_data (
  clerk_user_id TEXT NOT NULL,
  key           TEXT NOT NULL,
  value         JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at    TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (clerk_user_id, key)
);

CREATE INDEX IF NOT EXISTS idx_user_data_clerk ON user_data(clerk_user_id);

-- ── 2) RLS — doğrudan tablo erişimi tamamen kapalı ─────────────

ALTER TABLE user_data ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "deny_direct_access_user_data" ON user_data;
CREATE POLICY "deny_direct_access_user_data" ON user_data
  FOR ALL USING (false) WITH CHECK (false);

-- ── 3) RPC: get_user_data ──────────────────────────────────────

DROP FUNCTION IF EXISTS get_user_data(TEXT);
CREATE FUNCTION get_user_data(p_key TEXT)
RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_uid TEXT := auth.jwt() ->> 'sub';
  v_val JSONB;
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'unauthenticated'; END IF;
  SELECT d.value INTO v_val
  FROM user_data d
  WHERE d.clerk_user_id = v_uid AND d.key = p_key;
  RETURN v_val;  -- kayıt yoksa NULL
END $$;

-- ── 4) RPC: save_user_data ─────────────────────────────────────

DROP FUNCTION IF EXISTS save_user_data(TEXT, JSONB);
CREATE FUNCTION save_user_data(p_key TEXT, p_value JSONB)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_uid TEXT := auth.jwt() ->> 'sub';
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'unauthenticated'; END IF;
  INSERT INTO user_data (clerk_user_id, key, value, updated_at)
  VALUES (v_uid, p_key, p_value, now())
  ON CONFLICT (clerk_user_id, key) DO UPDATE SET
    value = EXCLUDED.value,
    updated_at = now();
END $$;

-- ── 5) RPC: delete_user_data ───────────────────────────────────

DROP FUNCTION IF EXISTS delete_user_data(TEXT);
CREATE FUNCTION delete_user_data(p_key TEXT)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_uid TEXT := auth.jwt() ->> 'sub';
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'unauthenticated'; END IF;
  DELETE FROM user_data WHERE clerk_user_id = v_uid AND key = p_key;
END $$;

-- ── 6) delete_user_preset artık SİLİNEN SATIR SAYISINI döndürür ─
-- Eski hâli void döndürüyordu, yani "id bulutta yok" ile "silindi" ayırt
-- edilemiyordu ve silme sessizce başarısız oluyordu.

DROP FUNCTION IF EXISTS delete_user_preset(UUID);
CREATE FUNCTION delete_user_preset(p_preset_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_uid TEXT := auth.jwt() ->> 'sub';
  v_count INTEGER;
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'unauthenticated'; END IF;
  DELETE FROM user_presets WHERE id = p_preset_id AND clerk_user_id = v_uid;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count;
END $$;

-- ── 7) RPC: delete_user_presets_by_name ────────────────────────
-- Onarım yolu: id'si yerelde kaybolmuş / ayrışmış şablonlar ada göre silinsin.
-- "Ne kadar silersem sileyim gitmiyor" durumunun tek tıkla çözümü.

DROP FUNCTION IF EXISTS delete_user_presets_by_name(TEXT);
CREATE FUNCTION delete_user_presets_by_name(p_name TEXT)
RETURNS INTEGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_uid TEXT := auth.jwt() ->> 'sub';
  v_count INTEGER;
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'unauthenticated'; END IF;
  DELETE FROM user_presets WHERE clerk_user_id = v_uid AND name = p_name;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count;
END $$;

-- ── 8) İzinler — anon kesinlikle dışarıda ──────────────────────
-- NOT: Supabase yeni fonksiyonlara anon'a doğrudan grant verir; açıkça revoke şart.

REVOKE EXECUTE ON FUNCTION get_user_data(TEXT)                  FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION save_user_data(TEXT, JSONB)          FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION delete_user_data(TEXT)               FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION delete_user_preset(UUID)             FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION delete_user_presets_by_name(TEXT)    FROM PUBLIC, anon;

GRANT EXECUTE ON FUNCTION get_user_data(TEXT)                   TO authenticated;
GRANT EXECUTE ON FUNCTION save_user_data(TEXT, JSONB)           TO authenticated;
GRANT EXECUTE ON FUNCTION delete_user_data(TEXT)                TO authenticated;
GRANT EXECUTE ON FUNCTION delete_user_preset(UUID)              TO authenticated;
GRANT EXECUTE ON FUNCTION delete_user_presets_by_name(TEXT)     TO authenticated;

-- ✓ Migration tamam.
