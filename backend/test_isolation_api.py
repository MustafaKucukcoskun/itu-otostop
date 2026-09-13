"""İzole konteyner uçlarının uçtan uca davranışı (gerçek FastAPI uygulaması).

Ağa çıkmaz: Cloud Run çağrılmaz, yalnızca ana servisin devir mantığı sınanır.
"""

import pytest
from fastapi.testclient import TestClient

import main
from engine import RegistrationEngine


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def kayit(client):
    """Çalışan bir kayıt kur: oturum + motor + bilet."""
    sid = "11111111-1111-4111-8111-111111111111"
    session = main.SessionState(
        token="t.o.k",
        ecrn_list=["12345"],
        kayit_saati="2030-01-01 14:00:00",
    )
    session.engine = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    main.sessions[sid] = session
    ticket = main.broker.register(sid, target_epoch=9999999999.0)
    yield sid, ticket, session
    main.sessions.pop(sid, None)
    main.broker.release(sid)


# ── Yapılandırma çekme ──


def test_config_requires_valid_ticket(client, kayit):
    sid, _, _ = kayit
    r = client.post("/internal/config", json={"session_id": sid, "ticket": "yanlis"})
    assert r.status_code == 403


def test_config_returns_registration_data(client, kayit):
    sid, ticket, _ = kayit
    r = client.post("/internal/config", json={"session_id": sid, "ticket": ticket})
    assert r.status_code == 200
    assert r.json()["ecrn_list"] == ["12345"]
    assert r.json()["kayit_saati"] == "2030-01-01 14:00:00"


def test_config_does_not_transfer_ownership(client, kayit):
    """Token'ı çekmek ateşleme hakkı vermez — sahiplik ayrı adım."""
    sid, ticket, _ = kayit
    client.post("/internal/config", json={"session_id": sid, "ticket": ticket})
    assert main.broker.owner_of(sid) is None


# ── Sahiplik devri ──


def test_claim_grants_and_stands_down_local_engine(client, kayit):
    """Asıl kazanç: konteyner üstlenince yerel motor busy-wait'e girmez."""
    sid, ticket, session = kayit
    assert session.engine.stood_down is False
    r = client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    assert r.json()["granted"] is True
    assert session.engine.stood_down is True


def test_second_claim_is_refused(client, kayit):
    """Cloud Run görevi yeniden denerse ikinci konteyner ateşleyemez."""
    sid, ticket, _ = kayit
    client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    r = client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    assert r.json()["granted"] is False


def test_claim_with_bad_ticket_refused_and_engine_untouched(client, kayit):
    """Yanlış bilet yerel motoru çekemez — aksi halde kayıt sabote edilebilirdi."""
    sid, _, session = kayit
    r = client.post("/internal/claim", json={"session_id": sid, "ticket": "yanlis"})
    assert r.json()["granted"] is False
    assert session.engine.stood_down is False


def test_claim_after_cancel_is_refused(client, kayit):
    """İptal edilen kayıt, geç kalkan konteyner tarafından ateşlenemez."""
    sid, ticket, _ = kayit
    main.broker.release(sid)
    r = client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    assert r.json()["granted"] is False


# ── Olay aktarımı ──


def test_events_require_valid_ticket(client, kayit):
    sid, _, _ = kayit
    r = client.post("/internal/events", json={
        "session_id": sid, "ticket": "yanlis",
        "events": [{"type": "log", "data": {"message": "x"}}],
    })
    assert r.status_code == 403


def test_events_accepted_with_valid_ticket(client, kayit):
    sid, ticket, _ = kayit
    r = client.post("/internal/events", json={
        "session_id": sid, "ticket": ticket,
        "events": [{"type": "log", "data": {"message": "merhaba"}}],
    })
    assert r.status_code == 200


def test_events_rejects_non_list(client, kayit):
    sid, ticket, _ = kayit
    r = client.post("/internal/events", json={
        "session_id": sid, "ticket": ticket, "events": "liste-degil",
    })
    assert r.status_code == 400
