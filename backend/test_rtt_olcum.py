# -*- coding: utf-8 -*-
"""RTT ölçümü gerçek kayıt ucuna POST atmamalı.

`_rtt_olc()` ve `_rtt_stats()` ağ gecikmesini ölçmek için OBS'in GERÇEK kayıt
ucuna `ECRN:["00000"]` ile POST atıyordu. Kayıt başına ~37 sahte kayıt isteği
ediyor; 40 kullanıcılık bir dalgada ~1500. Üniversitenin kayıt ucuna bu
hacimde sahte istek, aracın engellenmesine yol açabilecek bir ürün riski.

ÖLÇÜLDÜ (19 Eylül, Frankfurt, n=120, dönüşümlü):

    HEAD kayıt ucu : min 36.1  medyan 36.5  p90 36.8 ms   (HTTP 405)
    POST kayıt ucu : min 36.1  medyan 36.6  p90 37.0 ms   (HTTP 401)
    POST min − HEAD min = +0.0 ms

Birebir aynı. HEAD kayıt ucunda 405 ile yönlendirme katmanında kesiliyor,
yani uygulamaya hiç girmiyor ve yine aynı RTT'yi veriyor — ölçtüğümüz şey
saf ağ transiti. Üretimdeki gerçek token'lı POST'un min'i ise 38.0ms; aradaki
1.9ms OBS'in kimlik+kayıt mantığı maliyeti, yani `rtt_one_way`'e yanlışlıkla
eklediğimiz pay. Formül saf transit istiyor, dolayısıyla HEAD daha DOĞRU.
"""

import engine


class _SahteOturum:
    """Hangi metotla, nereye istek atıldığını kaydeder."""

    def __init__(self):
        self.cagrilar = []

    def _kaydet(self, metot, url):
        self.cagrilar.append((metot, url))

        class R:
            status_code = 405
        return R()

    def head(self, url, **kw):
        return self._kaydet("HEAD", url)

    def post(self, url, **kw):
        return self._kaydet("POST", url)

    def get(self, url, **kw):
        return self._kaydet("GET", url)


def _motor(monkeypatch):
    m = engine.RegistrationEngine(token="t", ecrn_list=["12345"],
                                  kayit_saati="23:59:00")
    o = _SahteOturum()
    monkeypatch.setattr(m, "session", o)
    return m, o


def test_rtt_olc_does_not_post_to_the_registration_endpoint(monkeypatch):
    m, o = _motor(monkeypatch)
    m._rtt_olc(3)
    postlar = [u for metot, u in o.cagrilar if metot == "POST"]
    assert not postlar, f"kayit ucuna {len(postlar)} POST atildi"


def test_rtt_stats_does_not_post_to_the_registration_endpoint(monkeypatch):
    m, o = _motor(monkeypatch)
    m._rtt_stats(4)
    postlar = [u for metot, u in o.cagrilar if metot == "POST"]
    assert not postlar, f"kayit ucuna {len(postlar)} POST atildi"


def test_rtt_olc_still_measures(monkeypatch):
    """Ölçüm yapılmaya devam etmeli — POST'u kaldırmak ölçümü kaldırmak değil."""
    m, o = _motor(monkeypatch)
    sonuc = m._rtt_olc(3)
    assert len(o.cagrilar) == 3
    assert sonuc > 0


def test_rtt_stats_still_returns_all_fields(monkeypatch):
    m, o = _motor(monkeypatch)
    d = m._rtt_stats(5)
    for alan in ("median", "jitter", "min", "max", "count", "trend"):
        assert alan in d, f"{alan} kayboldu"
    assert d["count"] == 5


def test_measurement_uses_head(monkeypatch):
    m, o = _motor(monkeypatch)
    m._rtt_olc(2)
    m._rtt_stats(2)
    assert o.cagrilar and all(metot == "HEAD" for metot, _ in o.cagrilar), o.cagrilar


# ══════════════════════════════════════════════════════════════
# Isıtma da POST atmamalı — hem yalan söylüyordu hem latent risk
# ══════════════════════════════════════════════════════════════
#
# `_prewarm(head_only=True)` adına rağmen POST atıyordu: bayrak yalnızca
# İKİNCİ POST'u atlıyordu. Üstelik "Bağlantı hazır (HEAD only)" diye
# logluyordu ve çağrıldığı yerdeki yorum "HEAD ile, debounce riski sıfır"
# diyordu. Üçü de yanlıştı.
#
# Şu ana dek zararsızdı çünkü son tam kalibrasyon T-20s'de bitip ısıtma
# T-13s'ye düşüyordu. Ama latent: calibrate() bir kez 9004ms sürdü ve OBS
# yavaşlayabiliyor. Kalibrasyon 17 saniye sürerse ısıtma POST'u T-3s'ye
# düşer — debounce penceresinin içine — ve GERÇEK istek VAL16 alır.


def test_prewarm_never_posts_to_the_registration_endpoint(monkeypatch):
    m, o = _motor(monkeypatch)
    m._prewarm()
    m._prewarm(head_only=True)
    postlar = [u for metot, u in o.cagrilar if metot == "POST"]
    assert not postlar, f"isitma {len(postlar)} POST atti"


def test_prewarm_still_warms_the_connection(monkeypatch):
    """POST'u kaldırmak ısıtmayı kaldırmak değil."""
    m, o = _motor(monkeypatch)
    m._prewarm()
    assert o.cagrilar, "hic istek atilmadi"
    assert all(metot == "HEAD" for metot, _ in o.cagrilar)


def test_head_only_sends_fewer_requests(monkeypatch):
    """Bayrak artık gerçekten bir şey yapmalı: tek istek, çift değil."""
    m, o = _motor(monkeypatch)
    m._prewarm(head_only=True)
    tek = len(o.cagrilar)
    o.cagrilar.clear()
    m._prewarm(head_only=False)
    assert len(o.cagrilar) > tek


def test_calibrate_warmup_does_not_post(monkeypatch):
    """calibrate() de bağlantıyı POST'la ısıtıyordu."""
    m, o = _motor(monkeypatch)
    monkeypatch.setattr(m, "_ntp_calibrate", lambda: None)
    monkeypatch.setattr(m, "_measure_date_offset", lambda: None)
    try:
        m.calibrate(source="test")
    except Exception:
        pass
    postlar = [u for metot, u in o.cagrilar if metot == "POST"]
    assert not postlar, f"kalibrasyon {len(postlar)} POST atti"
