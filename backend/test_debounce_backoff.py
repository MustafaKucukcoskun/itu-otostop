# -*- coding: utf-8 -*-
"""VAL16 alan bir deneme, aynı hızda tekrar denenmemeli.

CANLI OLAY (17 Eylül 10:00, zmxzl): ilk istek 10sn'de zaman aşımına düştü,
ardından BEŞ deneme üst üste VAL16 (debounce) aldı ve gerçek cevap ancak
28 saniye sonra geldi. Denemeler arası ölçülen süreler:

    +3.171s → VAL16      +3.044s → VAL16
    +3.042s → VAL16      +3.040s → VAL16
    +3.040s → VAL16      +3.078s → GERÇEK CEVAP

Hepsi 3 saniyelik debounce sınırının hemen üstünde; hangisinin geçeceği
tesadüfe kalmış. VAL16'nın söylediği şey "çok erken geldin" — o hâlde
aynı hızda tekrar denemek denemeyi ziyan etmektir. Debounce görüldüğünde
daha uzun beklenmeli.

(30sn'lik yeni okuma sınırı bu duruma düşmeyi zaten büyük ölçüde
engelliyor; bu, ikinci savunma hattı.)
"""

import engine
import models


class _Yanit:
    status_code = 200

    def __init__(self, kodlar):
        self._k = kodlar

    def json(self):
        return {"ecrnResultList": [
            {"crn": "12345", "statusCode": 1, "resultCode": k} for k in self._k
        ]}


def _uykular(monkeypatch, kod_dizisi):
    """Motoru sürer, her denemeden sonra uyunan süreleri toplar."""
    m = engine.RegistrationEngine(token="t", ecrn_list=["12345"],
                                  kayit_saati="23:59:00", max_deneme=3,
                                  retry_aralik=3.5)
    monkeypatch.setattr(m, "_prepare_fire", lambda: None)
    monkeypatch.setattr(m, "_request_for", lambda c: object())
    uykular = []
    monkeypatch.setattr(engine.time, "sleep", lambda s: uykular.append(s))
    tur = {"n": 0}

    class S:
        def send(self, *a, **k):
            i = min(tur["n"], len(kod_dizisi) - 1)
            tur["n"] += 1
            return _Yanit(kod_dizisi[i])
    monkeypatch.setattr(m, "session", S())
    m._kayit_yap()
    return uykular


def test_debounce_waits_longer_than_the_normal_retry(monkeypatch):
    """ASIL HATA: VAL16'dan sonra aynı aralıkla tekrar denenip yine VAL16."""
    val16 = _uykular(monkeypatch, [["VAL16"]])
    val02 = _uykular(monkeypatch, [["VAL02"]])
    assert val16 and val02
    assert val16[0] > val02[0], (
        f"debounce sonrası {val16[0]}s, normal tekrar {val02[0]}s — fark yok")


def test_debounce_wait_clears_the_three_second_window(monkeypatch):
    """Ölçülen 3.04-3.17s aralıkları yetmiyordu; belirgin pay olmalı."""
    assert _uykular(monkeypatch, [["VAL16"]])[0] >= 5.0


def test_normal_retry_is_not_slowed_down(monkeypatch):
    """VAL02 (kayıt henüz açılmadı) yolu yavaşlatılmamalı."""
    assert _uykular(monkeypatch, [["VAL02"]])[0] == 3.5


def test_schema_raises_unsafe_values_instead_of_refusing_them():
    """3.0s tam debounce sınırında; güvenli değere YÜKSELTİLMELİ.

    Bu test önce "3.0 reddedilmeli" diyordu ve şema öyle yazıldı — sonuç:
    frontend'in varsayılanı 3.0 olduğu için canlıda her config kaydı 422
    döndü ve kullanıcı 20 Eylül 05:44'te "Ayarlar sunucuya kaydedilemiyor"
    hatası aldı. Daha önce geçerli olan bir değeri geçersiz kılmak istemciyi
    kırar; doğrusu kabul edip güvenli tabana çekmek.
    """
    c = models.ConfigRequest(token="t", ecrn_list=["12345"],
                             kayit_saati="10:00:00", retry_aralik=3.0)
    assert c.retry_aralik == 3.5
