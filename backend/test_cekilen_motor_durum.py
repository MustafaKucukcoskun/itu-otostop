# -*- coding: utf-8 -*-
"""Çekilen yerel motor arayüzü "Hedefe kalan" ekranında kilitlememeli.

CANLI OLAY (2 Ekim 16:55, hedef 14:00): arayüz "HEDEFE KALAN 14:00:00" ve
İptal butonunda takılı; İptal → "Çalışan kayıt yok".

Zincir:
  1. İzole konteyner kaydı devraldı; yerel motor `run()`'dan `return` ile
     çekildi. Çekilme bitiş değil, o yüzden "done" yaymıyor — fazı
     "waiting"te DONUYOR.
  2. Konteyner kaydı yaptı; sonuç oturuma yansıdı (remote_*).
  3. Broker kaydı hedef+1 saatte temizlendi (purge_finished).
  4. /status artık "remote" dalına girmiyor, çekilen motora düşüp
     phase="waiting" dönüyordu → arayüz aktif fazda kilitli.
  5. İptal: yerel motor çalışmıyor, broker kaydı yok → 404.
"""
import time

import pytest
from fastapi.testclient import TestClient

import main
from engine import RegistrationEngine

SONUC = {"12345": {"status": "success", "message": "Kayıt başarılı"}}


@pytest.fixture
def client():
    return TestClient(main.app)


def _cekilmis_oturum(sid, remote_phase="done", remote_running=False):
    s = main.SessionState(token="t.o.k", ecrn_list=["12345"])
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng._phase = "waiting"        # çekilmeden önceki son faz
    eng.stand_down()
    eng._running = False
    s.engine = eng
    s.remote_phase = remote_phase
    s.remote_running = remote_running
    s.remote_results = dict(SONUC)
    main.sessions[sid] = s
    return s


def _durum(client, sid):
    return client.get("/api/register/status", headers={"X-Session-ID": sid}).json()


def test_after_broker_forgets_status_shows_the_containers_result(client):
    sid = "15151515-1515-4151-8151-151515151515"
    _cekilmis_oturum(sid)
    main.broker.release(sid)          # hedef+1 saat: kayıt temizlendi
    try:
        g = _durum(client, sid)
        assert g["phase"] == "done", f"arayüz aktif fazda kilitlenir: {g['phase']}"
        assert g["running"] is False
        assert {r["crn"]: r["status"] for r in g["crn_results"]} == {"12345": "success"}
    finally:
        main.sessions.pop(sid, None)


def test_a_lost_container_cannot_lock_the_ui_forever(client):
    """Konteyner 'done'u hiç gelmediyse (çöktü, olaylar düştü) bile broker
    kaydı unuttuğunda aktif faz gösterilmemeli."""
    sid = "16161616-1616-4161-8161-161616161616"
    _cekilmis_oturum(sid, remote_phase="registering", remote_running=True)
    main.broker.release(sid)
    try:
        g = _durum(client, sid)
        assert g["phase"] not in ("token_check", "calibrating", "waiting", "registering")
        assert g["running"] is False
    finally:
        main.sessions.pop(sid, None)


def test_while_the_container_is_working_status_is_still_live(client):
    """Kayıt sürerken (broker kaydı duruyor) konteynerin canlı fazı görünmeli."""
    sid = "17171717-1717-4171-8171-171717171717"
    s = _cekilmis_oturum(sid, remote_phase="registering", remote_running=True)
    bilet = main.broker.register(sid, time.time() + 60)
    assert main.broker.claim_remote(sid, bilet)
    try:
        g = _durum(client, sid)
        assert g["phase"] == "registering"
        assert g["running"] is True
    finally:
        main.sessions.pop(sid, None)
        main.broker.release(sid)
