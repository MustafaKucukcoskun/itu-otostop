# -*- coding: utf-8 -*-
"""Açılışta geri yükleme — servis yeniden başlasa da kayıt ayakta kalmalı.

Bu, kalıcılığın en riskli parçası: servis AÇILIRKEN çalışıyor. Buradaki bir
hata servisi hiç başlatmayabilir, ya da daha kötüsü, kullanıcının sildiği bir
kaydı geri getirip istemediği dersi aldırabilir.
"""

import time
import pytest
import main


class SahteDepo:
    def __init__(self, kayitlar=None, patla=False):
        self.kayitlar = kayitlar or []
        self.patla = patla
        self.silinenler = []
        self.enabled = True

    def list_pending(self):
        if self.patla:
            raise RuntimeError("depo coktu")
        return list(self.kayitlar)

    def save(self, sid, k):
        return True

    def delete(self, sid):
        self.silinenler.append(sid)
        return True


def _kayit(sid="u:test_restore", **ek):
    d = {
        "session_id": sid,
        "target_epoch": time.time() + 1800,
        "ticket": "orijinal-bilet",
        "token": "obs.jwt.token",
        "ecrn_list": ["12345"],
        "scrn_list": [],
        "kayit_saati": "23:59:00",
        "max_deneme": 60,
        "retry_aralik": 3.5,
        "dry_run": True,
    }
    d.update(ek)
    return d


@pytest.fixture(autouse=True)
def temiz():
    yield
    for sid in list(main.sessions):
        if sid.startswith("u:test_restore"):
            s = main.sessions[sid]
            if s.engine:
                s.engine.cancel()
            main.sessions.pop(sid, None)
            main.broker.release(sid)
            main.broker._mezar.pop(sid, None)


def test_restores_session_engine_and_broker(monkeypatch):
    monkeypatch.setattr(main, "pending_store", SahteDepo([_kayit()]))
    assert main._restore_pending() == 1
    s = main.sessions["u:test_restore"]
    assert s.token == "obs.jwt.token"
    assert s.ecrn_list == ["12345"]
    assert s.engine is not None


def test_original_ticket_survives(monkeypatch):
    """Yeniden başlatmadan sağ çıkan konteynerin bileti geçerli kalmalı."""
    monkeypatch.setattr(main, "ISOLATION_ENABLED", True)
    monkeypatch.setattr(main, "pending_store", SahteDepo([_kayit()]))
    main._restore_pending()
    assert main.broker.verify_ticket("u:test_restore", "orijinal-bilet")


def test_does_not_restart_a_running_registration(monkeypatch):
    """Zaten çalışan kayda ikinci motor takılmamalı."""
    monkeypatch.setattr(main, "pending_store", SahteDepo([_kayit()]))
    main._restore_pending()
    ilk = main.sessions["u:test_restore"].engine
    main._restore_pending()
    assert main.sessions["u:test_restore"].engine is ilk


def test_store_failure_never_blocks_startup(monkeypatch):
    """EN ÖNEMLİ: depo çökse de servis açılmalı."""
    monkeypatch.setattr(main, "pending_store", SahteDepo(patla=True))
    with pytest.raises(Exception):
        SahteDepo(patla=True).list_pending()      # depo gercekten patliyor
    try:
        main._restore_pending()
    except Exception as e:
        pytest.fail(f"geri yukleme istisna sizdirdi: {e}")


def test_incomplete_record_is_skipped(monkeypatch):
    """Token'sız kayıt geri yüklenemez — ateşleyemez, boşuna motor açma."""
    monkeypatch.setattr(main, "pending_store", SahteDepo([_kayit(token="")]))
    assert main._restore_pending() == 0
    assert "u:test_restore" not in main.sessions or main.sessions["u:test_restore"].engine is None


def test_one_bad_record_does_not_stop_the_others(monkeypatch):
    bozuk = _kayit("u:test_restore_bozuk", target_epoch="tarih-degil")
    iyi = _kayit("u:test_restore_iyi")
    monkeypatch.setattr(main, "pending_store", SahteDepo([bozuk, iyi]))
    assert main._restore_pending() >= 1
    assert "u:test_restore_iyi" in main.sessions


def test_disabled_store_restores_nothing(monkeypatch):
    d = SahteDepo([_kayit()]); d.enabled = False
    monkeypatch.setattr(main, "pending_store", d)
    assert main._restore_pending() == 0
