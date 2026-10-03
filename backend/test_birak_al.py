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


# ══════════════════════════════════════════════════════════════
# Ekranda görünen sonuç: A'nın akıbetine İKİ sonuç birlikte karar verir
# ══════════════════════════════════════════════════════════════
#
# A hem Bırak hem Ekle listesinde. OBS ikisi için ayrı sonuç döndürüyor ama
# motor sonuçları CRN'e göre TEK yerde tutuyordu: sonra işlenen bırakma
# eklemenin üstüne yazıyordu. B dolu çıkıp A geri alındığında ekran A için
# "Bırakıldı" diyordu — öğrenci dersini kaybettiğini sanıyordu.


def _son_gorunen(m):
    """Arayüze en son giden sonuçlar (crn_update olayı)."""
    son = None
    for ev in m.get_events():
        if ev.get("type") == "crn_update":
            son = ev["data"]["results"]
    return son


def test_readded_course_is_shown_as_enrolled_not_dropped(monkeypatch):
    """B dolu, A bırakıldı ve geri alındı → A KAYITLI görünmeli."""
    m, _ = _motor(monkeypatch, [{
        "ecrnResultList": [_kod(B, "VAL06"), _ok(A)],
        "scrnResultList": [_ok(A)],
    }])
    m._kayit_yap()
    gorunen = _son_gorunen(m)
    assert gorunen[A]["status"] == "success", gorunen[A]
    assert "geri alındı" in gorunen[A]["message"]
    assert gorunen[B]["status"] == "full"
    # /status ucu motorun crn_results'ını okuyor — o da aynı şeyi söylemeli
    assert m.crn_results[A]["status"] == "success"


def test_swap_done_course_stays_dropped(monkeypatch):
    """B alındı, A'nın geri eklenmesi çakıştı → A gerçekten BIRAKILDI."""
    m, _ = _motor(monkeypatch, [{
        "ecrnResultList": [_ok(B), _kod(A, "VAL09")],
        "scrnResultList": [_ok(A)],
    }])
    m._kayit_yap()
    gorunen = _son_gorunen(m)
    assert gorunen[B]["status"] == "success"
    assert gorunen[A]["status"] == "dropped", gorunen[A]
    assert "geri alınmadı" in gorunen[A]["message"]


def test_add_processed_before_drop_means_the_course_is_lost(monkeypatch):
    """A eklemesi 'zaten kayıtlı' (VAL03), sonra A bırakıldı → A elde YOK.

    Bu, ekleme bırakmadan ÖNCE işlendiyse olur; "Kayıtlı" göstermek
    öğrenciye dersini koruduğunu söyler ki yanlıştır."""
    m, _ = _motor(monkeypatch, [{
        "ecrnResultList": [_kod(B, "VAL06"), _kod(A, "VAL03")],
        "scrnResultList": [_ok(A)],
    }])
    m._kayit_yap()
    assert _son_gorunen(m)[A]["status"] == "dropped"


def test_failed_drop_wins_over_the_add_result(monkeypatch):
    """A bırakılamadıysa A'nın eklemesi 'zaten kayıtlı' der; asıl haber
    bırakmanın OLMAMASI — takas hiç gerçekleşmedi."""
    m, _ = _motor(monkeypatch, [{
        "ecrnResultList": [_ok(B), _kod(A, "VAL03")],
        "scrnResultList": [_kod(A, "VAL07")],
    }])
    m._kayit_yap()
    a = _son_gorunen(m)[A]
    assert a["status"] == "error"
    assert "Bırakılamadı" in a["message"]


def test_readded_result_survives_later_retries(monkeypatch):
    """İlk yanıtta A bırakılıp geri alındı, B debounce yedi; ikinci yanıtta
    SCRN boş geliyor. A'nın sonucu kaybolmamalı."""
    m, _ = _motor(monkeypatch, [
        {"ecrnResultList": [_kod(B, "VAL16"), _ok(A)], "scrnResultList": [_ok(A)]},
        {"ecrnResultList": [_kod(B, "VAL06")], "scrnResultList": []},
    ])
    m._kayit_yap()
    gorunen = _son_gorunen(m)
    assert gorunen[A]["status"] == "success"
    assert gorunen[B]["status"] == "full"


def _takas_tamam(monkeypatch):
    """B alındı, A'nın geri eklenmesi çakıştı. Ham ekleme sonucu "conflict",
    gerçek akıbet "dropped" — ikisi FARKLI olduğu için ham sonucu okuyan bir
    yol bu senaryoda yakalanır ("geri alındı"da ikisi de "success" der)."""
    m, _ = _motor(monkeypatch, [{
        "ecrnResultList": [_ok(B), _kod(A, "VAL09")],
        "scrnResultList": [_ok(A)],
    }])
    m._kayit_yap()
    return m


def test_status_endpoint_reads_the_combined_result(monkeypatch):
    """/status ucu motorun crn_results'ını okuyor."""
    assert _takas_tamam(monkeypatch).crn_results[A]["status"] == "dropped"


def test_done_payload_carries_the_combined_result(monkeypatch):
    """Bitiş olayı (sonuç ekranı + diske yazılan sonuç) aynı birleşimi taşımalı."""
    assert _takas_tamam(monkeypatch)._done_payload()["results"][A]["status"] == "dropped"


def test_course_only_in_drop_list_is_unchanged(monkeypatch):
    """Düz bırakma (A yalnızca Bırak listesinde) eskisi gibi 'dropped'."""
    m = engine.RegistrationEngine(token="t", ecrn_list=[B], scrn_list=[A],
                                  kayit_saati="23:59:00", max_deneme=1)

    class S:
        def prepare_request(self, req):
            return req.json

        def send(self, govde, **k):
            return _Yanit({"ecrnResultList": [_kod(B, "VAL06")],
                           "scrnResultList": [_ok(A)]})

    monkeypatch.setattr(m, "session", S())
    monkeypatch.setattr(engine.time, "sleep", lambda s: None)
    m._kayit_yap()
    assert _son_gorunen(m)[A]["status"] == "dropped"


def test_unreported_drop_is_not_hidden_behind_the_add_result(monkeypatch):
    """OBS bırakma listesini hiç göndermezse A'nın akıbeti BİLİNMİYOR —
    "Çakışma" yazmak A'nın elde olduğunu ima eder. Bilmediğimizi söyle."""
    m, _ = _motor(monkeypatch, [{
        "ecrnResultList": [_ok(B), _kod(A, "VAL09")],
    }])
    m._kayit_yap()
    a = _son_gorunen(m)[A]
    assert a["status"] == "error"
    assert "ÖBS" in a["message"]


def test_unreported_drop_with_successful_readd_is_enrolled(monkeypatch):
    """A eklenebildiyse A şu an kayıtlı: bırakma sonucu gelmese de belli."""
    m, _ = _motor(monkeypatch, [{
        "ecrnResultList": [_kod(B, "VAL06"), _ok(A)],
    }])
    m._kayit_yap()
    assert _son_gorunen(m)[A]["status"] == "success"
