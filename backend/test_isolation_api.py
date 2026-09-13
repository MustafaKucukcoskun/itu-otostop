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
        kayit_saati="14:00:00",
    )
    session.engine = RegistrationEngine(
        token="t.o.k", ecrn_list=["12345"], kayit_saati="14:00:00"
    )
    session.engine._running = True  # beklemede gibi davran
    main.sessions[sid] = session
    ticket = main.broker.register(sid, target_epoch=main.time.time() + 900)
    yield sid, ticket, session
    main.sessions.pop(sid, None)
    main.broker.release(sid)
    main._fallback_notified.discard(sid)


# ══════════════════════════════════════════════════════════════
# Yapılandırma çekme
# ══════════════════════════════════════════════════════════════


def test_config_requires_valid_ticket(client, kayit):
    sid, _, _ = kayit
    r = client.post("/internal/config", json={"session_id": sid, "ticket": "yanlis"})
    assert r.status_code == 403


def test_config_returns_registration_data(client, kayit):
    sid, ticket, _ = kayit
    r = client.post("/internal/config", json={"session_id": sid, "ticket": ticket})
    assert r.status_code == 200
    assert r.json()["ecrn_list"] == ["12345"]


def test_config_mirrors_the_local_engine_not_live_session(client, kayit):
    """Konteyner ile yerel motor AYNI listeyi ateşlemeli.

    Kullanıcı başlattıktan sonra CRN'leri değiştirirse yerel motor eski
    listesini kullanmaya devam eder (kendi kopyası var). Konteyner oturumun
    güncel değerini alsaydı ikisi farklı ders alırdı — hangisinin ateşlediğine
    göre sonuç değişirdi. Konteyner motorun anlık görüntüsünü alır.
    """
    sid, ticket, session = kayit
    session.ecrn_list = ["99999"]  # başlattıktan SONRA değiştirildi
    r = client.post("/internal/config", json={"session_id": sid, "ticket": ticket})
    assert r.json()["ecrn_list"] == ["12345"]  # motorun kopyası


def test_config_does_not_transfer_ownership(client, kayit):
    """Token'ı çekmek ateşleme hakkı vermez — sahiplik ayrı adım."""
    sid, ticket, _ = kayit
    client.post("/internal/config", json={"session_id": sid, "ticket": ticket})
    assert main.broker.owner_of(sid) is None


# ══════════════════════════════════════════════════════════════
# Sahiplenme
# ══════════════════════════════════════════════════════════════


def test_claim_grants_ownership(client, kayit):
    sid, ticket, _ = kayit
    r = client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    assert r.json()["granted"] is True
    assert main.broker.owner_of(sid) == "remote"


def test_claim_does_not_stand_down_local_engine_yet(client, kayit):
    """KRİTİK: yerel motor sahiplenme anında çekilMEZ.

    Çekilseydi ve konteyner sonra ölseydi kimse ateşlemezdi. Yerel motor
    ancak hedefe ~8s kala, konteynerin nabzı doğrulandıktan sonra çekilir.
    """
    sid, ticket, session = kayit
    client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    assert session.engine.stood_down is False


def test_second_claim_is_refused(client, kayit):
    sid, ticket, _ = kayit
    client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    r = client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    assert r.json()["granted"] is False


def test_claim_with_bad_ticket_refused(client, kayit):
    sid, _, _ = kayit
    r = client.post("/internal/claim", json={"session_id": sid, "ticket": "yanlis"})
    assert r.json()["granted"] is False
    assert main.broker.owner_of(sid) is None


def test_claim_after_reset_is_refused(client, kayit):
    """Sıfırlanan kayıt, geç kalkan konteyner tarafından ateşlenemez."""
    sid, ticket, _ = kayit
    main.broker.release(sid)
    r = client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    assert r.json()["granted"] is False


# ══════════════════════════════════════════════════════════════
# Nabız
# ══════════════════════════════════════════════════════════════


def test_heartbeat_requires_valid_ticket(client, kayit):
    sid, _, _ = kayit
    r = client.post("/internal/heartbeat", json={"session_id": sid, "ticket": "yanlis"})
    assert r.status_code == 403


def test_heartbeat_returns_flags(client, kayit):
    sid, ticket, _ = kayit
    r = client.post("/internal/heartbeat", json={"session_id": sid, "ticket": ticket})
    assert r.status_code == 200
    assert r.json() == {"cancelled": False, "revoked": False}


def test_heartbeat_reports_cancellation_to_container(client, kayit):
    """Konteyner iptali böyle öğrenir ve kendini durdurur."""
    sid, ticket, _ = kayit
    main.broker.request_cancel(sid)
    r = client.post("/internal/heartbeat", json={"session_id": sid, "ticket": ticket})
    assert r.json()["cancelled"] is True


# ══════════════════════════════════════════════════════════════
# İptal — konteyner devraldıktan sonra da çalışmalı
# ══════════════════════════════════════════════════════════════


def test_cancel_works_after_local_engine_stood_down(client, kayit):
    """HATA SENARYOSU: konteyner devralınca yerel motor durur; eski kod
    'Çalışan kayıt yok' diye 404 dönüyordu ve kullanıcı iptal edemiyordu —
    konteyner yine de kaydediyordu."""
    sid, ticket, session = kayit
    client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    session.engine.stand_down()
    session.engine._running = False  # çekilen motor durur

    r = client.post("/api/register/cancel", headers={"X-Session-ID": sid})
    assert r.status_code == 200
    assert main.broker.is_cancelled(sid) is True


def test_cancel_does_not_delete_entry_so_container_can_learn(client, kayit):
    """Kayıt silinseydi konteyner nabız atamaz, iptali öğrenemez ve
    kullanıcının iptal ettiği dersi yine alırdı."""
    sid, ticket, _ = kayit
    client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    client.post("/api/register/cancel", headers={"X-Session-ID": sid})
    r = client.post("/internal/heartbeat", json={"session_id": sid, "ticket": ticket})
    assert r.status_code == 200
    assert r.json()["cancelled"] is True


def test_cancel_without_any_registration_is_404(client):
    sid = "33333333-3333-4333-8333-333333333333"
    main.sessions[sid] = main.SessionState()
    try:
        r = client.post("/api/register/cancel", headers={"X-Session-ID": sid})
        assert r.status_code == 404
    finally:
        main.sessions.pop(sid, None)


def test_reset_fully_removes_the_registration(client, kayit):
    """Sıfırlama iptalden farklı: bilet de ölür, konteyner tamamen dışlanır."""
    sid, ticket, _ = kayit
    client.post("/api/register/reset", headers={"X-Session-ID": sid})
    r = client.post("/internal/heartbeat", json={"session_id": sid, "ticket": ticket})
    assert r.status_code == 403


# ══════════════════════════════════════════════════════════════
# Olay aktarımı
# ══════════════════════════════════════════════════════════════


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


# ══════════════════════════════════════════════════════════════
# Tanılama ucu — kayıt günü "ne oluyor" sorusunu cevaplar
# ══════════════════════════════════════════════════════════════


def test_diag_disabled_without_key(client, monkeypatch):
    """Anahtar tanımlı değilse uç kapalı — kimin kayıt yaptığı sızmamalı."""
    monkeypatch.setattr(main, "ISOLATION_DIAG_KEY", "")
    assert client.get("/internal/diag").status_code == 404


def test_diag_requires_correct_key(client, monkeypatch):
    monkeypatch.setattr(main, "ISOLATION_DIAG_KEY", "gizli")
    assert client.get("/internal/diag").status_code == 403
    assert client.get("/internal/diag", headers={"X-Diag-Key": "yanlis"}).status_code == 403


def test_diag_reports_broker_state(client, kayit, monkeypatch):
    monkeypatch.setattr(main, "ISOLATION_DIAG_KEY", "gizli")
    sid, ticket, _ = kayit
    client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    r = client.get("/internal/diag", headers={"X-Diag-Key": "gizli"})
    assert r.status_code == 200
    kayitlar = {k["session_id"]: k for k in r.json()["kayitlar"]}
    assert kayitlar[sid]["owner"] == "remote"


def test_diag_never_leaks_tickets_or_tokens(client, kayit, monkeypatch):
    """Bilet, OBS token'ını çekme yetkisidir — teşhis çıktısında yeri yok."""
    monkeypatch.setattr(main, "ISOLATION_DIAG_KEY", "gizli")
    sid, ticket, _ = kayit
    body = client.get("/internal/diag", headers={"X-Diag-Key": "gizli"}).text
    assert ticket not in body
    assert "t.o.k" not in body


def test_claim_mutes_local_engine(client, kayit):
    """Sahiplenmeden sonra kullanıcının gördüğü akış konteynerindir."""
    sid, ticket, session = kayit
    client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    assert session.engine.muted is True
    assert session.engine.stood_down is False  # hâlâ görevde, sadece sessiz


# ══════════════════════════════════════════════════════════════
# Sayfa yenilenince konteynerin durumu görünmeli
# ══════════════════════════════════════════════════════════════


def test_status_reflects_container_progress_after_refresh(client, kayit):
    """Konteyner devraldıysa /api/register/status ONUN durumunu vermeli.

    Aksi halde kullanıcı sayfayı yenilediğinde susturulmuş yerel motorun
    eski halini görür: "waiting, sonuç yok" — konteyner dersi almış olsa bile.
    """
    sid, ticket, _ = kayit
    client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    client.post("/internal/events", json={
        "session_id": sid, "ticket": ticket,
        "events": [
            {"type": "state", "data": {"phase": "registering", "running": True}},
            {"type": "crn_update", "data": {"results": {
                "12345": {"status": "success", "message": "Ders alındı"}}}},
        ],
    })
    r = client.get("/api/register/status", headers={"X-Session-ID": sid})
    body = r.json()
    assert body["phase"] == "registering"
    assert body["running"] is True
    assert body["crn_results"][0]["crn"] == "12345"
    assert body["crn_results"][0]["status"] == "success"


def test_status_reports_container_completion(client, kayit):
    """Kayıt bitince yenilenen sayfa sonucu göstermeli."""
    sid, ticket, _ = kayit
    client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    client.post("/internal/events", json={
        "session_id": sid, "ticket": ticket,
        "events": [{"type": "done", "data": {
            "cancelled": False, "stood_down": False,
            "results": {"12345": {"status": "success", "message": "Ders alındı"}}}}],
    })
    body = client.get("/api/register/status", headers={"X-Session-ID": sid}).json()
    assert body["phase"] == "done"
    assert body["running"] is False


def test_status_uses_local_engine_when_no_container_owns(client, kayit):
    """Konteyner devralmadıysa davranış bugünküyle aynı kalmalı."""
    sid, _, session = kayit
    session.engine._phase = "waiting"
    body = client.get("/api/register/status", headers={"X-Session-ID": sid}).json()
    assert body["phase"] == "waiting"


def test_new_registration_clears_previous_container_results(client, kayit):
    """Önceki kaydın sonuçları yeni kayıtta görünmemeli."""
    sid, ticket, session = kayit
    client.post("/internal/claim", json={"session_id": sid, "ticket": ticket})
    client.post("/internal/events", json={
        "session_id": sid, "ticket": ticket,
        "events": [{"type": "done", "data": {"cancelled": False, "results": {
            "12345": {"status": "success", "message": "eski"}}}}],
    })
    assert session.remote_results != {}

    client.post("/api/register/reset", headers={"X-Session-ID": sid})
    assert session.remote_results == {}
    assert session.remote_phase == ""
