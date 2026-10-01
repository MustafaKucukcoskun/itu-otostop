"""Ders bırakma (SCRN) — ekle-bırak döneminin yarısı.

İstek her zaman {"ECRN": [...], "SCRN": [...]} gönderiyordu ama yalnızca
`ecrnResultList` okunuyordu: öğrenci bir dersi bırakıp bırakmadığını
arayüzde HİÇ göremiyordu, başarıyla bırakılmış ders her yeniden denemede
tekrar gönderiliyordu.

Yanıt şekli: OBS bırakma sonuçlarını `scrnResultList` altında, ekleme
listesiyle aynı alanlarla (`crn`, `resultCode`) döndürüyor — bağımsız bir
OBS kayıt aracı da aynı anahtarı okuyor (omerfarukaydin61/ITU-KEPLER-DERS-
KAYIT, main.py:341). Yine de OBS bu listeyi göndermezse motor GÜVENLİ
kalmalı: döngüyü yalnızca ekleme listesi yönetir.
"""
import json

import engine


class _Yanit:
    status_code = 200

    def __init__(self, govde):
        self._g = govde

    def json(self):
        return self._g


def _motor(monkeypatch, yanitlar, max_deneme=1):
    """Sırayla `yanitlar` döndüren sahte OBS ile motor kurar.

    Döndürür: (motor, istek_cagrilari, uykular, gonderim_sayaci)
    """
    m = engine.RegistrationEngine(
        token="t", ecrn_list=["11111"], scrn_list=["22222"],
        kayit_saati="23:59:00", max_deneme=max_deneme,
    )
    istekler = []
    uykular = []
    gonderim = {"n": 0}

    def _request_for(ecrn, scrn=None):
        istekler.append((list(ecrn), None if scrn is None else list(scrn)))
        return object()

    monkeypatch.setattr(m, "_request_for", _request_for)
    monkeypatch.setattr(engine.time, "sleep", lambda s: uykular.append(s))

    class S:
        def prepare_request(self, req):
            return object()

        def send(self, *a, **k):
            i = gonderim["n"]
            gonderim["n"] += 1
            return _Yanit(yanitlar[min(i, len(yanitlar) - 1)])

    monkeypatch.setattr(m, "session", S())
    return m, istekler, uykular, gonderim


def _ok(crn):
    return {"crn": crn, "statusCode": 0, "resultCode": "SUCCESS", "resultData": None}


def _kod(crn, rc, rd=None):
    return {"crn": crn, "statusCode": 1, "resultCode": rc, "resultData": rd}


# ── Görünürlük ──

def test_drop_is_listed_as_pending_before_fire():
    """Arayüz bırakılacak dersi ateşten önce de görebilmeli."""
    m = engine.RegistrationEngine(token="t", ecrn_list=["11111"],
                                  scrn_list=["22222"], kayit_saati="23:59:00")
    m._prepare_fire()
    assert m._crn_results["22222"]["status"] == "pending"
    govde = json.loads(m._prepped.body)
    assert govde == {"ECRN": ["11111"], "SCRN": ["22222"]}


def test_successful_drop_is_marked_dropped(monkeypatch):
    m, *_ = _motor(monkeypatch, [{
        "ecrnResultList": [_ok("11111")],
        "scrnResultList": [_ok("22222")],
    }])
    m._kayit_yap()
    assert m._crn_results["22222"]["status"] == "dropped"
    assert m._crn_results["11111"]["status"] == "success"


def test_failed_drop_is_not_silent(monkeypatch):
    m, *_ = _motor(monkeypatch, [{
        "ecrnResultList": [_ok("11111")],
        "scrnResultList": [_kod("22222", "VAL07")],
    }])
    m._kayit_yap()
    r = m._crn_results["22222"]
    assert r["status"] == "error"
    assert "VAL07" in r["message"]
    assert "ırak" in r["message"], f"bırakma hatası olduğu belli değil: {r!r}"


def test_failed_drop_keeps_obs_explanation(monkeypatch):
    m, *_ = _motor(monkeypatch, [{
        "ecrnResultList": [_ok("11111")],
        "scrnResultList": [_kod("22222", "VAL99", {"mesaj": "Bu dersi bırakamazsınız"})],
    }])
    m._kayit_yap()
    assert "Bu dersi bırakamazsınız" in m._crn_results["22222"]["message"]


# ── Yeniden deneme ──

def test_successful_drop_is_not_sent_again(monkeypatch):
    """Bırakılmış ders sonraki isteklerde SCRN'de olmamalı."""
    m, istekler, *_ = _motor(monkeypatch, [
        {"ecrnResultList": [_kod("11111", "VAL16")],
         "scrnResultList": [_ok("22222")]},
        {"ecrnResultList": [_ok("11111")], "scrnResultList": []},
    ], max_deneme=2)
    m._kayit_yap()
    son_ecrn, son_scrn = istekler[-1]
    assert son_ecrn == ["11111"]
    assert son_scrn == [], f"bırakılmış ders yeniden gönderildi: {istekler}"
    assert m._crn_results["22222"]["status"] == "dropped"


def test_undecided_drop_is_still_sent(monkeypatch):
    """Sistem açılmadıysa (VAL02) bırakma da bir sonraki istekte durmalı."""
    m, istekler, *_ = _motor(monkeypatch, [
        {"ecrnResultList": [_kod("11111", "VAL02")],
         "scrnResultList": [_kod("22222", "VAL02")]},
        {"ecrnResultList": [_ok("11111")], "scrnResultList": [_ok("22222")]},
    ], max_deneme=2)
    m._kayit_yap()
    for _, scrn in istekler:
        assert scrn in (None, ["22222"]), istekler
    assert m._crn_results["22222"]["status"] == "dropped"


# ── Güvenlik: OBS bırakma listesini göndermezse ──

def test_missing_drop_list_does_not_keep_the_loop_alive(monkeypatch):
    """Eklemeler bitince döngü BİTER — bırakma cevabı gelmese bile.

    Aksi halde eklemeler bittikten sonra bekleme yolu (`if kalan`) kapanır ve
    motor OBS'e beklemesiz onlarca istek atar.
    """
    m, _, _, gonderim = _motor(monkeypatch, [
        {"ecrnResultList": [_ok("11111")]},
    ], max_deneme=60)
    m._kayit_yap()
    assert gonderim["n"] == 1


def test_unreported_drop_is_closed_honestly(monkeypatch):
    """Sonucu bilinmeyen bırakma 'Bekliyor'da kalmamalı, başarılı da sayılmamalı."""
    m, *_ = _motor(monkeypatch, [{"ecrnResultList": [_ok("11111")]}])
    m._kayit_yap()
    r = m._crn_results["22222"]
    assert r["status"] not in ("pending", "dropped"), r
    assert "ÖBS" in r["message"], r


def test_drop_results_do_not_change_retry_pacing(monkeypatch):
    """Bekleme süresi yalnızca ekleme kodlarından hesaplanır (kanıtlı davranış).

    Ekleme VAL02 iken bırakma başka bir kod alırsa motor 50ms'lik hızlı
    tekrara düşmemeli — bu, açılmamış sisteme istek yağdırmak olur.
    """
    m, _, uykular, _ = _motor(monkeypatch, [
        {"ecrnResultList": [_kod("11111", "VAL02")],
         "scrnResultList": [_kod("22222", "VAL07")]},
        {"ecrnResultList": [_ok("11111")]},
    ], max_deneme=2)
    m._kayit_yap()
    assert uykular == [m.retry_aralik], uykular


# ── İptal ──

def test_cancelled_drop_is_cancelled_not_dropped():
    """İptal edilen kayıtta bırakma 'Bırakıldı' görünmemeli."""
    m = engine.RegistrationEngine(token="t", ecrn_list=["11111"],
                                  scrn_list=["22222"], kayit_saati="23:59:00")
    m._prepare_fire()
    m.cancel()
    m._finalize_all()
    assert m._crn_results["22222"]["status"] == "cancelled"
    assert m._crn_results["11111"]["status"] == "cancelled"


# ── Dry run ──

def test_dry_run_does_not_raise_a_false_alarm_for_drops(monkeypatch):
    """Simülasyonda bırakma kırmızı 'ÖBS'den kontrol edin' diye kapanmamalı.

    Eklemeler simüle başarı alıyor; bırakma hiç simüle edilmezse sondaki
    _finalize_all onu "sonuç bildirilmedi" diye hataya çeviriyor —
    gerçek kayıtta olmayacak bir alarm.
    """
    m = engine.RegistrationEngine(token="t", ecrn_list=["11111"],
                                  scrn_list=["22222"], kayit_saati="23:59:00",
                                  dry_run=True)
    m._prepare_fire()

    class S:
        def post(self, *a, **k):
            raise engine.requests.exceptions.ConnectionError("ag yok")
    monkeypatch.setattr(m, "session", S())
    monkeypatch.setattr(engine.time, "sleep", lambda s: None)

    m._kayit_yap_dry_run()
    m._finalize_all()
    r = m._crn_results["22222"]
    assert r["status"] == "dropped", r
    assert "DRY RUN" in r["message"], r
