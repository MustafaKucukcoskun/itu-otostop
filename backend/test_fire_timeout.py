# -*- coding: utf-8 -*-
"""OBS açılış anında saniyelerce cevap vermiyor; 10sn'lik sınır dardı.

CANLI OLAY (19 Eylül 12:00, wsqj2): kayıt İLK istekte tamamlanmıştı — sonraki
denemede yedi dersin hepsi "Zaten alınmış" döndü. Ama ilk isteğin cevabı
10sn'de kesildiği için bunu bilemedik; motor art arda SEKİZ kez 10sn zaman
aşımına düştü, gerçeği 123 saniye sonra öğrendi ve bu arada OBS'e sekiz
mükerrer kayıt isteği attı.

Aynı gün ölçülen OBS cevap süreleri: 304ms, 1523ms, 2076ms, 7046ms, 9845ms.
Yani 9845ms sınıra kıl payı sığmış; biraz daha yavaş olsaydı o kayıt da
"zaman aşımı" sayılacaktı. Sınır, ölçülen tavanın belirgin üstünde olmalı.

Bağlantı kurma süresi AYRI ve kısa kalmalı: sunucu gerçekten erişilemezse
30 saniye beklemenin anlamı yok — orada tekrar denemek istiyoruz.
"""

import engine


class _Yakalayici:
    def __init__(self):
        self.timeouts = []

    def send(self, prepped, timeout=None, **kw):
        self.timeouts.append(timeout)
        raise engine.requests.exceptions.ReadTimeout("test")


def _motor(monkeypatch):
    m = engine.RegistrationEngine(token="t", ecrn_list=["12345"],
                                  kayit_saati="23:59:00", max_deneme=1)
    y = _Yakalayici()
    monkeypatch.setattr(m, "session", y)
    monkeypatch.setattr(m, "_prepare_fire", lambda: None)
    monkeypatch.setattr(m, "_request_for", lambda c: object())
    monkeypatch.setattr(engine.time, "sleep", lambda s: None)
    return m, y


def test_read_timeout_is_well_above_the_measured_obs_ceiling(monkeypatch):
    """ASIL HATA: 9845ms'lik gerçek cevap 10sn sınırına kıl payı sığmıştı."""
    m, y = _motor(monkeypatch)
    m._kayit_yap()
    assert y.timeouts, "istek hiç gönderilmedi"
    _, okuma = y.timeouts[0]
    assert okuma >= 25, f"okuma sınırı {okuma}s — ölçülen tavan 9.8s'ye çok yakın"


def test_connect_timeout_stays_short(monkeypatch):
    """Sunucuya hiç bağlanamıyorsak beklemek değil, tekrar denemek isteriz."""
    m, y = _motor(monkeypatch)
    m._kayit_yap()
    baglanti, _ = y.timeouts[0]
    assert baglanti <= 10, f"bağlantı sınırı {baglanti}s — ölü sunucuda boşuna beklenir"


def test_timeout_is_a_pair_not_one_number(monkeypatch):
    """Tek sayı ikisini birden yönetir; bunlar farklı şeyler."""
    m, y = _motor(monkeypatch)
    m._kayit_yap()
    assert isinstance(y.timeouts[0], tuple), "timeout tek sayı olarak geçiliyor"
