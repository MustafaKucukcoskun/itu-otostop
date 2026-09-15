"""İzole konteynerin nabız/iptal mantığı — ağa çıkmayan testler.

Burada sınanan tek şey şu soru: konteyner hangi durumda ateşler, hangi
durumda çekilir? Yanlış cevap ya dersi kaybettirir (kimse ateşlemez) ya da
VAL16 çakışması yaratır (ikisi birden ateşler).
"""

import threading

import pytest

import isolated_runner as ir


class SahteMotor:
    """engine.cancel() çağrıldı mı, onu izler."""

    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class SahteSaat:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


@pytest.fixture
def ortam(monkeypatch):
    """Saat ve nabız çağrısı enjekte edilir; gerçek bekleme yapılmaz."""
    saat = SahteSaat()
    monkeypatch.setattr(ir.time, "time", saat)
    monkeypatch.setattr(ir.time, "sleep", lambda s: None)
    return saat


def _kos(engine, target, beat_sonuclari, saat, tik=2.0, max_tur=60):
    """heartbeat_loop'u gerçek thread açmadan, kontrollü saatle çalıştırır."""
    tur = {"n": 0}

    def sahte_beat():
        i = min(tur["n"], len(beat_sonuclari) - 1)
        return beat_sonuclari[i]

    def sahte_wait(sure):
        tur["n"] += 1
        saat.advance(tik)
        return tur["n"] >= max_tur  # True → stop.is_set() gibi davran, döngü biter

    stop = threading.Event()
    stop.wait = sahte_wait  # type: ignore[method-assign]
    ir.beat = sahte_beat  # type: ignore[assignment]
    ir.heartbeat_loop(engine, target, stop)
    return tur["n"]


# ══════════════════════════════════════════════════════════════
# Nabız tetiğe yaklaşınca susmalı
# ══════════════════════════════════════════════════════════════


def test_heartbeat_stops_before_busy_wait(ortam):
    """Motor son 50ms'de busy-wait'e giriyor; o sırada uyanan bir thread
    GIL'i kapıp tetiği kaydırabilir. Nabız hedefe 2s kala susmalı."""
    motor = SahteMotor()
    cagri = _kos(motor, target=ortam() + 1.0, beat_sonuclari=[{"cancelled": False, "revoked": False}], saat=ortam)
    assert cagri == 0  # hiç nabız atmadan çıktı
    assert motor.cancelled is False


def test_heartbeat_runs_while_target_is_far(ortam):
    motor = SahteMotor()
    tur = _kos(motor, target=ortam() + 100, beat_sonuclari=[{"cancelled": False, "revoked": False}], saat=ortam, max_tur=5)
    assert tur >= 1
    assert motor.cancelled is False


# ══════════════════════════════════════════════════════════════
# İptal ve geri alma konteynere ulaşmalı
# ══════════════════════════════════════════════════════════════


def test_cancel_flag_stops_the_engine(ortam):
    motor = SahteMotor()
    _kos(motor, target=ortam() + 100, beat_sonuclari=[{"cancelled": True, "revoked": False}], saat=ortam)
    assert motor.cancelled is True


def test_revoked_flag_stops_the_engine(ortam):
    """Ana servis sözü geri aldıysa yerel motor ateşleyecek —
    konteyner de ateşlerse VAL16 çakışması olur."""
    motor = SahteMotor()
    _kos(motor, target=ortam() + 100, beat_sonuclari=[{"cancelled": False, "revoked": True}], saat=ortam)
    assert motor.cancelled is True


# ══════════════════════════════════════════════════════════════
# Ağ kopması — asıl tehlikeli senaryo
# ══════════════════════════════════════════════════════════════


def test_brief_network_blip_does_not_abandon_the_registration(ortam):
    """Tek bir başarısız nabız çekilme sebebi DEĞİL.

    Ana servis hâlâ nabzı taze sayıyor olabilir; konteyner burada pes
    ederse yerel motor da çekilmiş olacağı için kimse ateşlemez.
    """
    motor = SahteMotor()
    sonuclar = [None, {"cancelled": False, "revoked": False}]
    _kos(motor, target=ortam() + 100, beat_sonuclari=sonuclar, saat=ortam, max_tur=2)
    assert motor.cancelled is False


def test_prolonged_outage_does_NOT_abandon_the_registration(ortam):
    """Ana servise ulaşılamıyorsa konteyner SÖZÜNÜ TUTAR.

    İlk tasarımda tersiydi: "10sn rapor veremediysem geri alınmış olmalıyım"
    diye çekiliyordu. Ama ana servis ÇÖKTÜYSE yerel motor da ölmüştür ve
    çekilmek kesin ders kaybı demektir.

    Sonuçları tartınca yön netleşti:
      - servis çöktü, konteyner çekilir  → %100 kayıp
      - servis sağlam, ikisi de ateşler  → ilki dersi alır, ikincisi VAL03
        ("zaten kayıtlısın") alır, sonuç yine ders alınmış olur
    Hiç ateşlememenin geri dönüşü yok; iki kez ateşlemenin var.
    """
    motor = SahteMotor()
    _kos(motor, target=ortam() + 100, beat_sonuclari=[None], saat=ortam, tik=2.0, max_tur=10)
    assert motor.cancelled is False


def test_outage_near_the_target_does_not_abandon(ortam):
    """Hedefe yakın bir kopmada da söz tutulur — hangi anda olursa olsun."""
    motor = SahteMotor()
    _kos(motor, target=ortam() + 16,
         beat_sonuclari=[{"cancelled": False, "revoked": False}, None],
         saat=ortam, tik=2.0, max_tur=20)
    assert motor.cancelled is False


def test_explicit_signals_still_stop_the_container(ortam):
    """Kural çevrildi ama AÇIK iptaller hâlâ durdurur: onlar ana servise
    ULAŞABİLDİĞİMİZ durumlardır, belirsizlik içermezler."""
    for bayrak in ({"cancelled": True, "revoked": False},
                   {"cancelled": False, "revoked": True}):
        motor = SahteMotor()
        _kos(motor, target=ortam() + 100, beat_sonuclari=[bayrak], saat=ortam)
        assert motor.cancelled is True, bayrak


# ══════════════════════════════════════════════════════════════
# Sahiplenme öncesi bekleme
# ══════════════════════════════════════════════════════════════


def test_wait_returns_true_when_claim_time_reached(ortam, monkeypatch):
    monkeypatch.setattr(ir, "beat", lambda: {"cancelled": False, "revoked": False})
    assert ir.wait_until_claim_time(ortam() + 10) is True


def test_wait_aborts_when_cancelled_during_idle(ortam, monkeypatch):
    """İptal edilen kayıt için konteyner hedefi beklemeden kapanmalı —
    boşuna CPU yakmasın."""
    monkeypatch.setattr(ir, "beat", lambda: {"cancelled": True, "revoked": False})
    assert ir.wait_until_claim_time(ortam() + 5000) is False


def test_wait_tolerates_unreachable_control_service(ortam, monkeypatch):
    """Bekleme sırasında ağ koparsa konteyner vazgeçmemeli; sahiplenme
    anında zaten yeniden denenecek."""
    calls = {"n": 0}

    def bazen_none():
        calls["n"] += 1
        if calls["n"] > 3:
            ortam.advance(10_000)  # sahiplenme anına atla
        return None

    monkeypatch.setattr(ir, "beat", bazen_none)
    assert ir.wait_until_claim_time(ortam() + 5000) is True


# ══════════════════════════════════════════════════════════════
# 403 (kayıt yok) ile ağ kopması AYNI ŞEY DEĞİL
# ══════════════════════════════════════════════════════════════


def test_rejected_heartbeat_stands_down_immediately(ortam):
    """403 kesin bir cevaptır: ana servis bu kaydı tanımıyor (sıfırlandı).

    Ağ kopmasından farkı, belirsizlik olmaması. Hemen çekilmeli — 10 saniye
    beklenirse ve bu arada hedef gelirse, kullanıcının SİLDİĞİ kayıt ateşlenir.
    """
    motor = SahteMotor()
    _kos(motor, target=ortam() + 100, beat_sonuclari=[ir.REDDEDILDI], saat=ortam, max_tur=1)
    assert motor.cancelled is True


def test_rejected_heartbeat_ignores_the_handover_guard(ortam):
    """HATA SENARYOSU: kullanıcı hedefe 5sn kala sıfırladı.

    Ağ belirsizliği koruması burada uygulanmamalı; aksi halde konteyner
    sıfırlanmış kaydı ateşler.
    """
    motor = SahteMotor()
    _kos(motor, target=ortam() + 5, beat_sonuclari=[ir.REDDEDILDI], saat=ortam,
         tik=0.2, max_tur=3)
    assert motor.cancelled is True


def test_network_outage_still_respects_the_guard(ortam):
    """Ağ kopmasında belirsizlik var; devir anı geçtiyse söz tutulur."""
    motor = SahteMotor()
    _kos(motor, target=ortam() + 16,
         beat_sonuclari=[{"cancelled": False, "revoked": False}, None],
         saat=ortam, tik=2.0, max_tur=20)
    assert motor.cancelled is False


# ══════════════════════════════════════════════════════════════
# Sahiplenme isteği: "reddedildi" ile "ulaşamadım" AYNI ŞEY DEĞİL
# ══════════════════════════════════════════════════════════════
#
# Aynı ilke: ana servise ulaşamıyorsak servis çökmüş olabilir, o zaman yerel
# motor da ölüdür ve çekilmek kesin ders kaybıdır. Açık ret ise belirsizlik
# içermez — ulaşabildik ve "hayır" dedi.


class SahteYanit:
    def __init__(self, kod, govde=None):
        self.status_code = kod
        self._govde = govde or {}

    def json(self):
        return self._govde


def test_claim_granted(monkeypatch):
    monkeypatch.setattr(ir, "_post", lambda *a, **k: SahteYanit(200, {"granted": True}))
    assert ir.claim() == ir.CLAIM_VERILDI


def test_claim_explicitly_refused(monkeypatch):
    """Ana servis ulaşılabilir ve 'hayır' diyor — yerel motor devralmış."""
    monkeypatch.setattr(ir, "_post", lambda *a, **k: SahteYanit(200, {"granted": False}))
    assert ir.claim() == ir.CLAIM_REDDEDILDI


def test_claim_refused_on_403(monkeypatch):
    """Kayıt sıfırlanmış — net cevap, ateşlenmemeli."""
    monkeypatch.setattr(ir, "_post", lambda *a, **k: SahteYanit(403))
    assert ir.claim() == ir.CLAIM_REDDEDILDI


def test_claim_unreachable_on_network_error(monkeypatch):
    """Ana servis çökmüş olabilir → yerel motor da ölü → ATEŞLEMELİYİZ."""
    def patla(*a, **k):
        raise OSError("baglanti yok")
    monkeypatch.setattr(ir, "_post", patla)
    assert ir.claim() == ir.CLAIM_ULASILAMADI


def test_claim_unreachable_on_server_error(monkeypatch):
    """5xx de ulaşılamama sayılır: servis ayakta ama cevap veremiyor."""
    monkeypatch.setattr(ir, "_post", lambda *a, **k: SahteYanit(503))
    assert ir.claim() == ir.CLAIM_ULASILAMADI


def test_claim_result_decides_firing():
    """main() bu üç sonucu ayırt etmeli: yalnızca açık ret ateşlemeyi durdurur."""
    assert ir.ateslemeli(ir.CLAIM_VERILDI) is True
    assert ir.ateslemeli(ir.CLAIM_ULASILAMADI) is True
    assert ir.ateslemeli(ir.CLAIM_REDDEDILDI) is False


# ══════════════════════════════════════════════════════════════
# Yapılandırma çekme: geçici aksaklıkta pes etme
# ══════════════════════════════════════════════════════════════


def test_config_retries_on_transient_failure(ortam, monkeypatch):
    """Konteyner hedeften 15 dakika önce açılıyor; ilk denemede ulaşamamak
    vazgeçme sebebi değil. Pes ederse o kullanıcı izolasyonsuz kalır."""
    denemeler = {"n": 0}

    def bazen(*a, **k):
        denemeler["n"] += 1
        if denemeler["n"] < 3:
            raise OSError("gecici hata")
        return SahteYanit(200, {"token": "t", "ecrn_list": ["12345"],
                                "kayit_saati": "14:00:00"})

    monkeypatch.setattr(ir, "_post", bazen)
    cfg = ir.fetch_config()
    assert cfg is not None
    assert cfg["ecrn_list"] == ["12345"]
    assert denemeler["n"] == 3


def test_config_gives_up_eventually(ortam, monkeypatch):
    """Sonsuza kadar denemez — yerel motor zaten görevde."""
    def hep_patla(*a, **k):
        raise OSError("yok")
    monkeypatch.setattr(ir, "_post", hep_patla)
    assert ir.fetch_config() is None


def test_config_does_not_retry_on_explicit_refusal(ortam, monkeypatch):
    """403 net bir cevap: bilet geçersiz. Tekrar denemek anlamsız."""
    denemeler = {"n": 0}

    def reddet(*a, **k):
        denemeler["n"] += 1
        return SahteYanit(403)

    monkeypatch.setattr(ir, "_post", reddet)
    assert ir.fetch_config() is None
    assert denemeler["n"] == 1


# ══════════════════════════════════════════════════════════════
# Hazırlık logları kullanıcıya sırasız akmamalı
# ══════════════════════════════════════════════════════════════
#
# Konteyner açılışta kalibre olurken motorunun kuyruğuna onlarca olay yazıyor,
# ama olay akışı ancak SAHİPLENMEDEN SONRA başlıyor. Sonuç: canlı logda
# 05:43:19'daki "kaydı üstlendi" satırından sonra 05:43:11'e ait satırlar
# geliyordu — kullanıcı için okunmaz bir karışıklık.
#
# Kullanıcı zaten tek satırlık özeti alıyor ("hazır ve kalibre, offset X").
# Hazırlık detayı konteynerin kendi Cloud Run logunda duruyor.


class KuyrukluMotor:
    def __init__(self):
        self.olaylar = [{"type": "log", "data": {"message": f"hazirlik {i}"}}
                        for i in range(25)]

    def get_events(self):
        o, self.olaylar = self.olaylar, []
        return o


def test_readiness_logs_are_discarded_before_streaming():
    m = KuyrukluMotor()
    ir.hazirlik_loglarini_at(m)
    assert m.get_events() == []


def test_discard_is_safe_on_an_empty_queue():
    m = KuyrukluMotor()
    m.olaylar = []
    ir.hazirlik_loglarini_at(m)   # patlamamali
