# -*- coding: utf-8 -*-
"""Bekleyen kayıtlar servis yeniden başlayınca kaybolmamalı.

SORUN: broker ve motor bellekte. Kullanıcı "başlat"a basıp gidiyor; konteyner
ISOLATION_LEAD'den önce açılmadığı için o pencerede kayıt YALNIZCA ana
servisin belleğinde duruyor. Servis yeniden başlarsa (deploy, instance
değişimi, çökme) kayıt tamamen kayboluyor ve kimse ateşlemiyor.

Ölçüldü (17 Eylül): kullanıcılar 3.5 / 3 / 2.8 / 2.7 / 2.6 / 2 / 2 saat
önceden başlattı. lead=3600 ile 1 saatten erken başlayan herkes açıkta.

ÇÖZÜM: kaydı diske (GCS) yaz, açılışta geri yükle, iş bitince SİL.

Güvenlik: OBS token'ı da yazılıyor — kayıt onsuz geri yüklenemez. Bedeli
bilinçli olarak kabul edildi. Azaltıcılar: kova özel, kayıt biter bitmez
siliniyor, token zaten ~6 saatlik ve kovada 1 günlük yaşam döngüsü kuralı var.

EN ÖNEMLİ KURAL: kalıcılık bir EMNİYET AĞI. Depolama çökerse kayıt yine
çalışmalı — bu modülden dışarı asla istisna sızmamalı.
"""

import json
import time

import persistence


class SahteYanit:
    def __init__(self, kod=200, govde=None):
        self.status_code = kod
        self._g = govde if govde is not None else {}
        self.text = json.dumps(self._g)

    def json(self):
        return self._g

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class SahteTasima:
    """Ağa çıkmaz; yapılan çağrıları kaydeder."""

    def __init__(self, yanitlar=None, patla=False):
        self.cagrilar = []
        self.yanitlar = yanitlar or {}
        self.patla = patla

    def _yap(self, metot, url, **kw):
        self.cagrilar.append((metot, url, kw))
        if self.patla:
            raise OSError("ag yok")
        return self.yanitlar.get(metot, SahteYanit())

    def get(self, url, **kw):
        return self._yap("GET", url, **kw)

    def post(self, url, **kw):
        return self._yap("POST", url, **kw)

    def delete(self, url, **kw):
        return self._yap("DELETE", url, **kw)


def _depo(tasima):
    return persistence.PendingStore(bucket="test-kova", transport=tasima,
                                    token_fn=lambda: "sahte-token")


KAYIT = {
    "target_epoch": time.time() + 3600,
    "ticket": "bilet-123",
    "token": "obs.jwt.token",
    "ecrn_list": ["12345", "23456"],
    "scrn_list": [],
    "kayit_saati": "14:00:00",
    "max_deneme": 60,
    "retry_aralik": 3.5,
    "dry_run": False,
}


def test_save_writes_one_object_per_session():
    t = SahteTasima()
    _depo(t).save("u:user_abc", KAYIT)
    metotlar = [m for m, _, _ in t.cagrilar]
    assert "POST" in metotlar
    url = next(u for m, u, _ in t.cagrilar if m == "POST")
    assert "test-kova" in url and "user_abc" in url


def test_saved_record_round_trips():
    t = SahteTasima()
    _depo(t).save("u:user_abc", KAYIT)
    _, _, kw = next(c for c in t.cagrilar if c[0] == "POST")
    geri = json.loads(kw["data"].decode() if isinstance(kw["data"], bytes) else kw["data"])
    for alan in KAYIT:
        assert geri[alan] == KAYIT[alan], alan


def test_delete_removes_the_object():
    t = SahteTasima()
    _depo(t).delete("u:user_abc")
    assert any(m == "DELETE" and "user_abc" in u for m, u, _ in t.cagrilar)


def test_storage_failure_never_raises():
    """EN ÖNEMLİ: depolama çökse de kayıt çalışmaya devam etmeli."""
    t = SahteTasima(patla=True)
    d = _depo(t)
    d.save("u:x", KAYIT)          # patlamamalı
    d.delete("u:x")               # patlamamalı
    assert d.list_pending() == []  # patlamamalı, bos donmeli


def test_list_returns_saved_records():
    icerik = json.dumps({**KAYIT, "session_id": "u:user_abc"})
    t = SahteTasima(yanitlar={
        "GET": SahteYanit(200, {"items": [{"name": "pending/u:user_abc.json"}]}),
    })
    d = persistence.PendingStore(bucket="k", transport=t, token_fn=lambda: "t")
    d._indir = lambda ad: json.loads(icerik)
    kayitlar = d.list_pending()
    assert len(kayitlar) == 1
    assert kayitlar[0]["session_id"] == "u:user_abc"


def test_long_past_records_are_skipped():
    """Hedefi saatlerce geçmiş kayıt geri yüklenmemeli — boşuna ateşler."""
    eski = {**KAYIT, "target_epoch": time.time() - 6 * 3600, "session_id": "u:eski"}
    t = SahteTasima(yanitlar={
        "GET": SahteYanit(200, {"items": [{"name": "pending/u:eski.json"}]}),
    })
    d = persistence.PendingStore(bucket="k", transport=t, token_fn=lambda: "t")
    d._indir = lambda ad: eski
    assert d.list_pending() == []


def test_a_slightly_past_record_is_still_restored():
    """Birkaç dakika geçmiş hedef kurtarma vakası — atılmamalı."""
    gec = {**KAYIT, "target_epoch": time.time() - 120, "session_id": "u:gec"}
    t = SahteTasima(yanitlar={
        "GET": SahteYanit(200, {"items": [{"name": "pending/u:gec.json"}]}),
    })
    d = persistence.PendingStore(bucket="k", transport=t, token_fn=lambda: "t")
    d._indir = lambda ad: gec
    assert len(d.list_pending()) == 1


def test_disabled_when_no_bucket_configured():
    """Kova ayarlanmamışsa sessizce devre dışı — kurulum zorunluluğu olmasın."""
    d = persistence.PendingStore(bucket="", transport=SahteTasima(), token_fn=lambda: "t")
    assert d.enabled is False
    d.save("u:x", KAYIT)
    assert d.list_pending() == []


# ══════════════════════════════════════════════════════════════
# Geri yükleme ORİJİNAL bileti korumalı
# ══════════════════════════════════════════════════════════════
#
# Yeniden başlatmadan önce açılmış bir konteyner, yeniden başlatmadan SAĞ
# ÇIKAR (soğuk başlangıç toleransı sayesinde sözünü tutar). Elinde eski bilet
# var. Geri yüklerken `register()` çağırmak YENİ bilet üretir ve o konteynerin
# nabzı geçersizleşir — yani kurtarmaya çalışırken hayatta olanı öldürürüz.


def test_restore_keeps_the_original_ticket():
    import isolation
    b = isolation.IsolationBroker()
    b.restore("u:x", target_epoch=9e9, ticket="eski-bilet")
    assert b.verify_ticket("u:x", "eski-bilet")


def test_restore_does_not_mint_a_new_ticket():
    import isolation
    b = isolation.IsolationBroker()
    b.restore("u:x", target_epoch=9e9, ticket="eski-bilet")
    assert not b.verify_ticket("u:x", "baska-bilet")


def test_restored_entry_is_launchable():
    """Geri yüklenen kayıt için konteyner yeniden açılabilmeli: orijinali
    ölmüşse ikinci şans, sağsa ikincisi 'söz verilemedi' deyip çekilir."""
    import isolation, time as _t
    b = isolation.IsolationBroker()
    b.restore("u:x", target_epoch=_t.time() + 300, ticket="bilet")
    assert ("u:x", "bilet") in b.due_for_launch()


def test_restore_clears_any_tombstone():
    """Aynı oturum daha önce sıfırlanmışsa mezar taşı yeni kaydı gömmemeli."""
    import isolation
    b = isolation.IsolationBroker()
    b.register("u:x", 9e9)
    b.release("u:x")
    b.restore("u:x", target_epoch=9e9, ticket="bilet")
    assert not b.deliberately_released("u:x")
