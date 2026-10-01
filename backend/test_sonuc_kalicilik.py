# -*- coding: utf-8 -*-
"""Kayıt SONUCU servis yeniden başlasa da görünmeli.

"Başlatıp giden" kullanıcı (bkz. persistence.py) geri döndüğünde — çoğu
zaman başka bir cihazdan — ne olduğunu görmek istiyor. Sonuçlar yalnızca
bellekteydi; servis örneği değişince (ölçek sıfır, yeni sürüm) dönen
kullanıcı boş bir ekran görüyordu.

Kurallar:
  - Sonuç token İÇERMEZ (ayrı önek, ayrı nesne).
  - Dry run ve iptal SAKLANMAZ: dönen kullanıcı simülasyonu gerçek sanmasın.
  - Durum ucu diske oturum başına en fazla BİR kez bakar.
  - Yeni kayıt ve sıfırlama eski sonucu siler.
"""
import asyncio
import json

import pytest
from httpx2 import ASGITransport, AsyncClient

import main
import persistence
from test_persistence import SahteTasima, SahteYanit, _depo


# ── Depo ──

def test_result_lives_under_its_own_prefix():
    t = SahteTasima()
    assert _depo(t).save_result("u:abc", {"results": {}})
    metot, url, _ = t.cagrilar[-1]
    assert metot == "POST"
    assert "name=results%2Fu%3Aabc.json" in url


def test_result_round_trips():
    govde = {"results": {"12345": {"status": "success", "message": "ok"}}}
    t = SahteTasima({"GET": SahteYanit(200, govde)})
    assert _depo(t).load_result("u:abc") == govde


def test_missing_result_is_none_not_an_error():
    t = SahteTasima({"GET": SahteYanit(404)})
    assert _depo(t).load_result("u:abc") is None


def test_result_storage_failure_never_raises():
    d = _depo(SahteTasima(patla=True))
    assert d.save_result("u:abc", {"results": {}}) is False
    assert d.load_result("u:abc") is None
    assert d.delete_result("u:abc") is False


def test_results_are_not_restored_as_pending_registrations():
    """Geri yükleme yalnızca pending/ önekini listelemeli."""
    t = SahteTasima({"GET": SahteYanit(200, {"items": []})})
    _depo(t).list_pending()
    _, url, _ = t.cagrilar[-1]
    assert "prefix=pending%2F" in url


# ── Servis ──

def _baglan(sid, **kw):
    s = main.SessionState(**kw)
    main.sessions[sid] = s
    return s


async def _get_status(sid):
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        return await c.get("/api/register/status", headers={"X-Session-ID": sid})


async def _arka_plani_bitir():
    for _ in range(50):
        if not main._arka_plan:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("arka plan disk işleri bitmedi")


@pytest.mark.asyncio
async def test_status_after_restart_shows_the_saved_result(monkeypatch):
    sid = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    monkeypatch.setattr(main.pending_store, "load_result", lambda s: {
        "results": {"12345": {"status": "success", "message": "Kayıt başarılı"},
                    "23456": {"status": "full", "message": "Kontenjan dolu"}},
    })
    _baglan(sid)
    try:
        r = await _get_status(sid)
        g = r.json()
        assert g["phase"] == "done" and g["running"] is False
        durum = {x["crn"]: x["status"] for x in g["crn_results"]}
        assert durum == {"12345": "success", "23456": "full"}
    finally:
        main.sessions.pop(sid, None)


@pytest.mark.asyncio
async def test_status_without_a_saved_result_is_idle(monkeypatch):
    sid = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    monkeypatch.setattr(main.pending_store, "load_result", lambda s: None)
    _baglan(sid)
    try:
        g = (await _get_status(sid)).json()
        assert g["phase"] == "idle" and g["crn_results"] == []
    finally:
        main.sessions.pop(sid, None)


@pytest.mark.asyncio
async def test_status_asks_the_disk_at_most_once(monkeypatch):
    sid = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
    sayac = {"n": 0}

    def yukle(s):
        sayac["n"] += 1
        return None
    monkeypatch.setattr(main.pending_store, "load_result", yukle)
    _baglan(sid)
    try:
        for _ in range(3):
            await _get_status(sid)
        assert sayac["n"] == 1
    finally:
        main.sessions.pop(sid, None)


async def _bitir(monkeypatch, sid, done_data, dry_run=False):
    from engine import RegistrationEngine
    kaydedilen = []
    monkeypatch.setattr(main.pending_store, "delete", lambda s: True)
    monkeypatch.setattr(main.pending_store, "save_result",
                        lambda s, sonuc: kaydedilen.append((s, sonuc)) or True)
    s = _baglan(sid, token="gizli.obs.token", ecrn_list=["12345"])
    s.engine = RegistrationEngine(token="gizli.obs.token", ecrn_list=["12345"],
                                  dry_run=dry_run)
    s.engine._emit("done", done_data)
    try:
        await main.poll_engine_events(sid)
        await _arka_plani_bitir()
    finally:
        main.sessions.pop(sid, None)
    return kaydedilen


SONUC = {"12345": {"status": "success", "message": "Kayıt başarılı"}}


@pytest.mark.asyncio
async def test_finished_registration_saves_its_result_without_the_token(monkeypatch):
    sid = "ffffffff-ffff-4fff-8fff-ffffffffffff"
    k = await _bitir(monkeypatch, sid, {"results": SONUC, "cancelled": False,
                                        "stood_down": False})
    assert len(k) == 1 and k[0][0] == sid
    assert k[0][1]["results"] == SONUC
    assert "gizli.obs.token" not in json.dumps(k[0][1])


@pytest.mark.asyncio
@pytest.mark.parametrize("ad,veri,dry", [
    ("dry_run", {"results": SONUC, "cancelled": False, "stood_down": False}, True),
    ("iptal", {"results": SONUC, "cancelled": True, "stood_down": False}, False),
    ("cekilme", {"results": SONUC, "cancelled": False, "stood_down": True}, False),
])
async def test_these_endings_are_not_saved(monkeypatch, ad, veri, dry):
    sid = "12121212-1212-4121-8121-121212121212"
    assert await _bitir(monkeypatch, sid, veri, dry_run=dry) == [], ad


@pytest.mark.asyncio
async def test_stood_down_done_does_not_delete_the_pending_record(monkeypatch):
    """Çekilen motorun 'done'u bitiş değil: kayıt konteynerde sürüyor ve
    servis yeniden başlarsa geri yüklenebilmesi için disk kopyası kalmalı."""
    from engine import RegistrationEngine
    silinen = []
    monkeypatch.setattr(main.pending_store, "delete", lambda s: silinen.append(s) or True)
    sid = "13131313-1313-4131-8131-131313131313"
    s = _baglan(sid, token="t", ecrn_list=["12345"])
    s.engine = RegistrationEngine(token="t", ecrn_list=["12345"])
    s.engine._emit("done", {"results": {}, "cancelled": False, "stood_down": True})
    try:
        await main.poll_engine_events(sid)
        await _arka_plani_bitir()
        assert silinen == []
    finally:
        main.sessions.pop(sid, None)


@pytest.mark.asyncio
async def test_reset_forgets_the_saved_result(monkeypatch):
    sid = "14141414-1414-4141-8141-141414141414"
    silinen = []
    monkeypatch.setattr(main.pending_store, "delete", lambda s: True)
    monkeypatch.setattr(main.pending_store, "delete_result",
                        lambda s: silinen.append(s) or True)
    monkeypatch.setattr(main.pending_store, "load_result",
                        lambda s: {"results": SONUC})
    _baglan(sid)
    try:
        transport = ASGITransport(app=main.app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            h = {"X-Session-ID": sid}
            assert (await c.get("/api/register/status", headers=h)).json()["phase"] == "done"
            assert (await c.post("/api/register/reset", headers=h)).status_code == 200
            g = (await c.get("/api/register/status", headers=h)).json()
        assert silinen == [sid]
        assert g["phase"] == "idle", "sıfırlanan sonuç geri geldi"
    finally:
        main.sessions.pop(sid, None)
        main.broker.release(sid)
