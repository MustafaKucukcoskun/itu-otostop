"""Yeniden başlamış servis "kesin hayır" diyememeli.

CANLI OLAYDAN ÇIKTI (15 Eylül 05:49): kayıt beklerken yeni bir revizyon
yayına girdi. Bellekteki broker sıfırlandı; çalışan konteynerin nabzı 403
aldı ("kayıt tanınmıyor") ve konteyner kendini durdurdu. O sefer eski
instance hayatta kaldığı için yerel motor ateşledi. Tamamen kapansaydı
KİMSE ateşlemeyecekti.

Yeni başlamış bir servis, bilmediği bir bileti "silinmiş" sayamaz — çünkü
hiçbir şey hatırlamıyor. Belirsizlik, kesin ret gibi davranmamalı.
"""

import time

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def temiz():
    """Testler arasında hiçbir iz bırakma.

    release() artık mezar taşı bırakıyor (kasıtlı silme hatırlanır), bu yüzden
    testi temizlemek için mezar taşını da kaldırmak gerekiyor — yoksa bir test
    diğerinin "hiç bilmiyorum" durumunu yok eder.
    """
    yield
    main.broker.release("hayalet")
    main.broker._mezar.pop("hayalet", None)


def test_unknown_ticket_gets_503_right_after_startup(client, monkeypatch):
    """Servis az önce başladıysa: 'bilmiyorum' (503), 'yok' (403) DEĞİL."""
    monkeypatch.setattr(main, "_STARTED_AT", time.time())
    r = client.post("/internal/heartbeat", json={"session_id": "hayalet", "ticket": "x"})
    assert r.status_code == 503


def test_unknown_ticket_gets_403_once_grace_has_passed(client, monkeypatch):
    """Uzun süredir ayaktaysa bilinmeyen bilet gerçekten yok demektir —
    sıfırlanan bir kaydın konteyneri durdurulabilmeli."""
    monkeypatch.setattr(main, "_STARTED_AT", time.time() - main.COLD_START_GRACE - 10)
    r = client.post("/internal/heartbeat", json={"session_id": "hayalet", "ticket": "x"})
    assert r.status_code == 403


def test_claim_is_not_refused_during_grace(client, monkeypatch):
    """Sahiplenme de aynı: yeni başlamış servis 'granted: false' diyemez,
    konteyner bunu kesin ret sayıp çekilir."""
    monkeypatch.setattr(main, "_STARTED_AT", time.time())
    r = client.post("/internal/claim", json={"session_id": "hayalet", "ticket": "x"})
    assert r.status_code == 503


def test_claim_refused_normally_after_grace(client, monkeypatch):
    monkeypatch.setattr(main, "_STARTED_AT", time.time() - main.COLD_START_GRACE - 10)
    r = client.post("/internal/claim", json={"session_id": "hayalet", "ticket": "x"})
    assert r.status_code == 200
    assert r.json()["granted"] is False


def test_known_ticket_is_unaffected_during_grace(client, monkeypatch):
    """Tanınan bilet normal cevabını almalı — grace her şeyi 503 yapmaz."""
    monkeypatch.setattr(main, "_STARTED_AT", time.time())
    sid = "bilinen-oturum"
    t = main.broker.register(sid, target_epoch=time.time() + 600)
    try:
        r = client.post("/internal/heartbeat", json={"session_id": sid, "ticket": t})
        assert r.status_code == 200
        assert r.json() == {"cancelled": False, "revoked": False}
    finally:
        main.broker.release(sid)


def test_wrong_ticket_for_a_known_session_is_still_refused(client, monkeypatch):
    """Oturumu TANIYORSAK amnezi yok: yanlış bilet kesin rettir."""
    monkeypatch.setattr(main, "_STARTED_AT", time.time())
    sid = "bilinen-oturum-2"
    main.broker.register(sid, target_epoch=time.time() + 600)
    try:
        r = client.post("/internal/heartbeat", json={"session_id": sid, "ticket": "yanlis"})
        assert r.status_code == 403
    finally:
        main.broker.release(sid)


# ══════════════════════════════════════════════════════════════
# Kasıtlı silme, amnezi DEĞİLDİR
# ══════════════════════════════════════════════════════════════
#
# Tolerans penceresi "hatırlamıyorum" durumunu kapsamalı, "sildim"
# durumunu DEĞİL. Kullanıcı sıfırla'ya bastığında konteyner durmalı;
# aksi halde istemediği bir kayıt yapılır. Broker silmeyi hatırladığı
# sürece cevap kesindir.


def test_reset_is_definitive_even_during_grace(client, monkeypatch):
    """Sıfırlanan kayıt: bunu biz sildik, unutmuş değiliz → 403."""
    monkeypatch.setattr(main, "_STARTED_AT", time.time())
    bilet = main.broker.register("hayalet", time.time() + 600)
    main.broker.release("hayalet")
    r = client.post("/internal/heartbeat",
                    json={"session_id": "hayalet", "ticket": bilet})
    assert r.status_code == 403


def test_claim_after_reset_is_refused_during_grace(client, monkeypatch):
    """Geç kalkan konteyner, sıfırlanmış kaydı tolerans penceresinde de alamaz."""
    monkeypatch.setattr(main, "_STARTED_AT", time.time())
    bilet = main.broker.register("hayalet", time.time() + 600)
    main.broker.release("hayalet")
    r = client.post("/internal/claim",
                    json={"session_id": "hayalet", "ticket": bilet})
    assert r.status_code == 200
    assert r.json()["granted"] is False


def test_reregistering_clears_the_tombstone(client, monkeypatch):
    """Aynı kullanıcı yeniden başlatırsa eski mezar taşı yeni kaydı gömmemeli."""
    monkeypatch.setattr(main, "_STARTED_AT", time.time())
    main.broker.register("hayalet", time.time() + 600)
    main.broker.release("hayalet")
    yeni = main.broker.register("hayalet", time.time() + 600)
    r = client.post("/internal/heartbeat",
                    json={"session_id": "hayalet", "ticket": yeni})
    assert r.status_code == 200
