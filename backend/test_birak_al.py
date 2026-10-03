# -*- coding: utf-8 -*-
"""Bırak-al: mevcut dersi (A) bırak, başka dersi (B) dene, alınamazsa A'yı
Ekle listesinde B'nin ALTINA yazarak geri al.  Bırak: [A], Ekle: [B, A].

Bu testler davranış DEĞİŞTİRMEZ; mevcut motorun bu akışta ne yaptığını
sabitler. OBS'in bırakma/eklemeyi hangi sırayla işlediğini motor bilmez —
o OBS'in kararı; motor yalnızca isteği gönderir ve cevabı okur.
"""
import json

import engine

A, B = "11111", "22222"


class _Yanit:
    status_code = 200

    def __init__(self, govde):
        self._g = govde

    def json(self):
        return self._g


def _ok(crn):
    return {"crn": crn, "statusCode": 0, "resultCode": "SUCCESS", "resultData": None}


def _kod(crn, rc):
    return {"crn": crn, "statusCode": 1, "resultCode": rc, "resultData": None}


def _motor(monkeypatch, yanitlar, max_deneme=3):
    m = engine.RegistrationEngine(token="t", ecrn_list=[B, A], scrn_list=[A],
                                  kayit_saati="23:59:00", max_deneme=max_deneme)
    gonderilen = []

    class S:
        def prepare_request(self, req):
            return req.json      # gövdeyi olduğu gibi taşı

        def send(self, govde, **k):
            gonderilen.append(json.loads(json.dumps(govde)))
            return _Yanit(yanitlar[min(len(gonderilen) - 1, len(yanitlar) - 1)])

    monkeypatch.setattr(m, "session", S())
    monkeypatch.setattr(engine.time, "sleep", lambda s: None)
    return m, gonderilen


def test_first_request_carries_both_lists_in_the_users_order(monkeypatch):
    m, gonderilen = _motor(monkeypatch, [{
        "ecrnResultList": [_kod(B, "VAL06"), _ok(A)],
        "scrnResultList": [_ok(A)],
    }])
    m._kayit_yap()
    assert gonderilen[0] == {"ECRN": [B, A], "SCRN": [A]}


def test_dropped_and_readded_course_is_not_dropped_again_on_retry(monkeypatch):
    """A bırakıldı ve geri alındı, B debounce yedi → B yeniden denenirken
    istekte SCRN:[A] OLMAMALI; olsaydı geri alınan A tekrar bırakılırdı."""
    m, gonderilen = _motor(monkeypatch, [
        {"ecrnResultList": [_kod(B, "VAL16"), _ok(A)], "scrnResultList": [_ok(A)]},
        {"ecrnResultList": [_kod(B, "VAL06")], "scrnResultList": []},
    ])
    m._kayit_yap()
    assert len(gonderilen) == 2
    assert gonderilen[1] == {"ECRN": [B], "SCRN": []}, gonderilen


def test_while_obs_is_closed_both_lists_are_resent_unchanged(monkeypatch):
    """Sistem açılmadıysa (VAL02) iki liste de olduğu gibi tekrar gider."""
    m, gonderilen = _motor(monkeypatch, [
        {"ecrnResultList": [_kod(B, "VAL02"), _kod(A, "VAL02")],
         "scrnResultList": [_kod(A, "VAL02")]},
        {"ecrnResultList": [_ok(B), _kod(A, "VAL09")], "scrnResultList": [_ok(A)]},
    ])
    m._kayit_yap()
    assert gonderilen == [{"ECRN": [B, A], "SCRN": [A]},
                          {"ECRN": [B, A], "SCRN": [A]}]
