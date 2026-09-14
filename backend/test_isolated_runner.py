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


def test_prolonged_outage_makes_container_stand_down(ortam):
    """SİMETRİ KURALI: ana servis 10sn nabız gelmezse sözü geri alıp yerel
    motora devrediyor. Konteyner de 10sn rapor veremediyse geri alındığını
    VARSAYMALI — yoksa ikisi birden ateşler ve OBS ikisini de VAL16'lar.
    """
    motor = SahteMotor()
    _kos(motor, target=ortam() + 100, beat_sonuclari=[None], saat=ortam, tik=2.0, max_tur=10)
    assert motor.cancelled is True


def test_outage_after_handover_point_does_not_abandon(ortam):
    """Devir anı geçtiyse karar verilmiştir: yerel motor çekildi.

    Konteyner bu noktadan sonra ağ yüzünden pes ederse kimse ateşlemez.
    Sözünü tutup ateşlemeli.
    """
    motor = SahteMotor()
    # Önce sağlam bir nabız, sonra ağ kopuyor. Hedef 16s ötede: kopma 10sn'yi
    # aştığında hedefe yalnızca 4s kalmış olur — devir eşiğinin (8s) içinde.
    _kos(motor, target=ortam() + 16,
         beat_sonuclari=[{"cancelled": False, "revoked": False}, None],
         saat=ortam, tik=2.0, max_tur=20)
    assert motor.cancelled is False


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
