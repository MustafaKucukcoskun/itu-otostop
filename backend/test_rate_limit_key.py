"""Hız limitinin kime uygulandığı — kayıt gününde ders kaybettirebilecek bir ayrıntı.

Limit IP başınaydı. Kampüs WiFi'si, yurt ağı ve mobil operatörlerin CGNAT'ı
yüzünden ONLARCA öğrenci aynı çıkış IP'sinden çıkar. /api/register/start
dakikada 6 istekle sınırlı olduğu için aynı dakikada başlatan 7. öğrenci
429 alır ve kaydı HİÇ başlamaz.

Limit kimliğe bağlanınca her öğrencinin kendi kotası olur.
"""

import types

import main


class SahteRequest:
    def __init__(self, ip="1.2.3.4", auth=None):
        self.headers = {} if auth is None else {"Authorization": auth}
        self.client = types.SimpleNamespace(host=ip)
        self.scope = {"client": (ip, 12345), "headers": [], "type": "http"}
        self.query_params = {}


def test_same_ip_different_users_get_separate_quotas(monkeypatch):
    """ASIL MESELE: aynı ağdan giren iki öğrenci birbirinin kotasını yemez."""
    monkeypatch.setattr(main, "clerk_user_id",
                        lambda auth, q="": auth.replace("Bearer ", "") if auth else None)
    a = main.rate_limit_key(SahteRequest(ip="10.0.0.1", auth="Bearer user_aaa"))
    b = main.rate_limit_key(SahteRequest(ip="10.0.0.1", auth="Bearer user_bbb"))
    assert a != b


def test_same_user_shares_one_quota(monkeypatch):
    """Bir kişi kaç cihazdan girerse girsin tek kota — kötüye kullanım kapalı."""
    monkeypatch.setattr(main, "clerk_user_id",
                        lambda auth, q="": auth.replace("Bearer ", "") if auth else None)
    a = main.rate_limit_key(SahteRequest(ip="10.0.0.1", auth="Bearer user_aaa"))
    b = main.rate_limit_key(SahteRequest(ip="99.99.99.99", auth="Bearer user_aaa"))
    assert a == b


def test_falls_back_to_ip_without_identity(monkeypatch):
    """Kimlik yoksa IP'ye düşer; anonim istekler yine sınırlanır."""
    monkeypatch.setattr(main, "clerk_user_id", lambda auth, q="": None)
    k = main.rate_limit_key(SahteRequest(ip="10.0.0.7"))
    assert "10.0.0.7" in k


def test_identity_key_is_distinct_from_ip_key(monkeypatch):
    """Kimlik anahtarı ile IP anahtarı çakışmamalı."""
    monkeypatch.setattr(main, "clerk_user_id",
                        lambda auth, q="": "1.2.3.4" if auth else None)
    kimlikli = main.rate_limit_key(SahteRequest(ip="9.9.9.9", auth="Bearer x"))
    ipli = main.rate_limit_key(SahteRequest(ip="1.2.3.4"))
    assert kimlikli != ipli


def test_broken_identity_check_does_not_crash(monkeypatch):
    """Clerk'e ulaşılamazsa istek reddedilmemeli, IP'ye düşülmeli."""
    def patla(auth, q=""):
        raise RuntimeError("clerk yok")
    monkeypatch.setattr(main, "clerk_user_id", patla)
    k = main.rate_limit_key(SahteRequest(ip="10.0.0.9"))
    assert "10.0.0.9" in k
