"""
Engine timing/yardımcı fonksiyonları için birim testleri (Faz 4 — test başlangıcı).

Çalıştırma (backend/ içinden):
    venv/Scripts/python -m pytest -q          # Windows
    venv/bin/python -m pytest -q              # Unix
"""

import pytest

from engine import TrendAnalyzer, ChangeDetector, RegistrationEngine, EVENT_QUEUE_MAX
from main import _token_preview


# ── TrendAnalyzer — lineer regresyon (offset/RTT trend tahmini) ──


def test_trend_too_few_points():
    t = TrendAnalyzer()
    assert t.calculate_linear_trend() == (0.0, 0.0)  # 0 nokta
    t.add_measurement(0.0, 5.0)
    assert t.calculate_linear_trend() == (0.0, 0.0)  # 1 nokta


def test_trend_perfect_line():
    # y = 2x + 1
    t = TrendAnalyzer()
    for x in range(5):
        t.add_measurement(float(x), 2.0 * x + 1.0)
    slope, intercept = t.calculate_linear_trend()
    assert slope == pytest.approx(2.0, abs=1e-9)
    assert intercept == pytest.approx(1.0, abs=1e-9)


def test_trend_flat_line():
    t = TrendAnalyzer()
    for x in range(4):
        t.add_measurement(float(x), 3.0)
    slope, intercept = t.calculate_linear_trend()
    assert slope == pytest.approx(0.0, abs=1e-9)
    assert intercept == pytest.approx(3.0, abs=1e-9)


def test_trend_predict_future():
    t = TrendAnalyzer()
    for x in range(5):
        t.add_measurement(float(x), 2.0 * x + 1.0)
    assert t.predict_value_at_time(10.0) == pytest.approx(21.0, abs=1e-6)


# ── ChangeDetector — 50ms anlamlı değişiklik eşiği ──


def test_change_needs_min_window():
    d = ChangeDetector(threshold=0.050, min_window=3)
    d.add_value(0.0)
    d.add_value(0.5)  # büyük fark ama henüz min_window altında
    assert d.detect_significant_change() is False


def test_change_below_threshold():
    d = ChangeDetector(threshold=0.050)
    for v in [0.10, 0.11, 0.12]:  # son fark 10ms < 50ms
        d.add_value(v)
    assert d.detect_significant_change() is False


def test_change_above_threshold():
    d = ChangeDetector(threshold=0.050)
    for v in [0.10, 0.10, 0.20]:  # son fark 100ms > 50ms
        d.add_value(v)
    assert d.detect_significant_change() is True


# ── token_preview — güvenlik maskesi (tam token asla sızmaz) ──


def test_token_preview_empty():
    assert _token_preview("") == ""


def test_token_preview_short():
    assert _token_preview("abcd") == "••••"  # <= 8 karakter tamamen maskeli


def test_token_preview_long_masks_middle():
    out = _token_preview("eyJhbGc_SECRET_9999")
    assert out == "eyJh…9999"
    assert "SECRET" not in out  # ortadaki gizli kısım sızmamalı


# ── Tetik öncesi hazırlık (eşzamanlılık: tetikten sonra iş kalmamalı) ──


def _body_text(prepped):
    body = prepped.body
    return body.decode() if isinstance(body, bytes) else body


def test_prepare_fire_caches_prepared_request():
    """Tetikten ÖNCE istek inşa edilmeli; tetik anında yalnızca send() kalmalı."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345", "67890"])
    eng._prepare_fire()
    assert eng._prepped is not None
    body = _body_text(eng._prepped)
    assert "12345" in body
    assert "67890" in body


def test_prepare_fire_marks_crns_pending():
    """CRN sonuç sözlüğü de tetikten önce doldurulmalı."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng._prepare_fire()
    assert eng._crn_results["12345"]["status"] == "pending"


def test_prepare_fire_is_idempotent_for_same_crn_list():
    """Aynı CRN listesi için tekrar hazırlık yeni nesne üretmemeli (boşa iş yok)."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng._prepare_fire()
    first = eng._prepped
    eng._prepare_fire()
    assert eng._prepped is first


def test_request_for_returns_cached_when_crn_list_unchanged():
    """CRN listesi değişmediyse hazır istek yeniden inşa edilmemeli."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng._prepare_fire()
    assert eng._request_for(["12345"]) is eng._prepped


def test_request_for_rebuilds_when_crn_list_changed():
    """CRN listesi değiştiyse (başarılı ders düştü) yeni istek inşa edilmeli."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345", "67890"])
    eng._prepare_fire()
    first = eng._prepped
    got = eng._request_for(["67890"])
    assert got is not first
    assert "67890" in _body_text(got)
    assert "12345" not in _body_text(got)


# ── Bitiş sinyali: iptal ile gerçek tamamlanma ayrılmalı ──


def test_done_payload_not_cancelled_by_default():
    """Normal bitişte done olayı cancelled=False taşımalı."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    assert eng._done_payload()["cancelled"] is False


def test_done_payload_marks_cancellation():
    """İptal edildiyse done olayı bunu söylemeli — yoksa arayüz
    'KAYIT TAMAMLANDI' modalını iptalden sonra da gösteriyor."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng.cancel()
    assert eng._done_payload()["cancelled"] is True


def test_done_payload_carries_results():
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng._prepare_fire()
    assert eng._done_payload()["results"]["12345"]["status"] == "pending"


# ── Çekilme (izole konteyner devraldığında) ──


def test_stand_down_is_clear_by_default():
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    assert eng.stood_down is False


def test_stand_down_sets_flag():
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng.stand_down()
    assert eng.stood_down is True


def test_stand_down_is_not_a_cancellation():
    """Kullanıcı iptal etmedi — arayüz 'iptal edildi' ekranı göstermemeli.

    Kullanıcı daha önce gereksiz iptal ekranından şikâyet etmişti; devir
    sessiz olmalı, hata gibi görünmemeli.
    """
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng.stand_down()
    payload = eng._done_payload()
    assert payload["cancelled"] is False
    assert payload["stood_down"] is True


def test_cancel_still_reports_cancelled():
    """Çekilme eklenirken gerçek iptal bozulmamalı."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng.cancel()
    payload = eng._done_payload()
    assert payload["cancelled"] is True
    assert payload["stood_down"] is False


def test_stand_down_stops_the_wait_loop():
    """Çekilen motor busy-wait'e girmemeli — GIL'i boşuna meşgul etmesin."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng.stand_down()
    assert eng._wait_should_continue() is False


def test_wait_loop_continues_when_nothing_set():
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    assert eng._wait_should_continue() is True


def test_stood_down_engine_does_not_announce_completion():
    """Çekilme bitiş DEĞİLDİR — kayıt izole konteynerde sürüyor.

    done yayınlansaydı arayüz "KAYIT TAMAMLANDI" modalını açardı; kullanıcı
    dersi alınmadan alınmış sanırdı.
    """
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng.stand_down()
    assert eng._should_announce_done() is False


def test_normal_finish_announces_completion():
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    assert eng._should_announce_done() is True


def test_cancelled_engine_still_announces_done():
    """İptalde done gitmeli — arayüz 'iptal edildi' ekranını ondan biliyor."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng.cancel()
    assert eng._should_announce_done() is True


# ── Susturma (konteyner devraldığında çift log akışını önler) ──


def test_engine_is_not_muted_by_default():
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng._emit("log", {"message": "merhaba"})
    assert len(eng.get_events()) == 1


def test_muted_engine_emits_nothing():
    """Konteyner sahiplenince yerel motor beklemeye devam eder ama susar.

    Susmasaydı kullanıcı T-180s'den itibaren iki ayrı motorun loglarını iç
    içe görürdü ve faz göstergesi titrerdi.
    """
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng.mute()
    eng._emit("log", {"message": "gorunmemeli"})
    eng._emit("countdown", {"remaining": 5})
    assert eng.get_events() == []


def test_unmute_restores_emission():
    """Söz geri alınırsa yerel motor yeniden görünür olmalı — yoksa
    kullanıcı ateşlemeyi hiç göremez."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng.mute()
    eng.unmute()
    eng._emit("log", {"message": "geri geldi"})
    assert len(eng.get_events()) == 1


def test_mute_does_not_stop_the_wait_loop():
    """Susmak çekilmek DEĞİLDİR: motor beklemeye devam eder ki konteyner
    ölürse ateşleyebilsin."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng.mute()
    assert eng._wait_should_continue() is True
    assert eng.stood_down is False


# ── Geri sayım yayın hızı ──
# Bekleme döngüsü son 5 saniyede saniyede ~180 tur atıyor ve her turda olay
# yayınlıyordu: tek motorda 902 olay. 32 konteynerde ana servise saniyede
# ~5800 olay demek — hem boşa iş, hem de DEVİR KARARININ verilmesi gereken
# anda event loop'a yük. Arayüz saniyede 10'dan fazlasını zaten kullanamaz.


def test_countdown_is_rate_limited():
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    t = 1000.0
    assert eng._countdown_due(t) is True          # ilki hep geçer
    assert eng._countdown_due(t + 0.01) is False  # 10ms sonra hayır
    assert eng._countdown_due(t + 0.05) is False  # 50ms sonra hâlâ hayır


def test_countdown_allowed_after_the_interval():
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    t = 1000.0
    eng._countdown_due(t)
    assert eng._countdown_due(t + 0.1) is True


def test_countdown_rate_cuts_the_final_burst():
    """Son 5 saniyedeki olay sayısı bir büyüklük mertebesi azalmalı."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    t = 1000.0
    kalan, gecen = 5.0, 0.0
    ham = gecti = 0
    while kalan > 0.05:
        ham += 1
        if eng._countdown_due(t + gecen):
            gecti += 1
        adim = max(0, kalan - 0.05) if kalan <= 0.5 else (0.005 if kalan <= 5 else 1.0)
        kalan -= adim
        gecen += adim
    assert ham > 800, ham          # döngü gerçekten hızlı dönüyor
    assert gecti <= 60, gecti      # ama yayın 10 Hz ile sınırlı
    assert gecti >= 40, gecti      # ve arayüz akıcı kalacak kadar sık


def test_countdown_limiter_does_not_touch_other_events():
    """Log, crn_update, done gibi olaylar kısılmamalı — onlar seyrek ve önemli."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    for _ in range(50):
        eng._emit("log", {"message": "x"})
    assert len(eng.get_events()) == 50


# ══════════════════════════════════════════════════════════════
# Koruma sınırı yerel saat hatasına karşı sağlam olmalı
# ══════════════════════════════════════════════════════════════
#
# Gerçek davranış: formül hedeften ~8ms ÖNCE ateşlemek istiyor ama koruma
# alt sınırı tetiği hedef+1ms'ye çekiyor; istek OBS'e hedef+20ms'de varıyor.
# Bu bilinçli ve doğru bir seçim (erken varış 3sn ceza demek).
#
# AMA sınır BİZİM saatimize göreydi. Saatimiz ileri giderse gerçek zamanda
# erken ateşleriz; geri kalırsa gereksiz geç kalırız. İkisini de ölçülen
# server_offset ile düzeltiyoruz — normal durumda (offset~0) davranış aynı.


def _motor():
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng._last_val02_delay = -999
    return eng


def test_floor_unchanged_when_clock_is_accurate():
    """Saat doğruysa bugünkü davranış birebir korunmalı."""
    eng = _motor()
    hedef = 1_000_000.0
    tetik = eng._apply_advanced_protection(hedef - 0.0083, hedef, server_offset=0.0)
    assert abs(tetik - (hedef + 0.001)) < 1e-9


def test_floor_moves_later_when_our_clock_runs_fast():
    """Saatimiz 25ms ileriyse hedef+1ms'de ateşlemek GERÇEKTE hedef-24ms'dir
    ve istek erken varır → VAL02. Sınır ileri kaymalı."""
    eng = _motor()
    hedef = 1_000_000.0
    offset = 0.025  # server_offset = bizim saat - gerçek zaman
    tetik = eng._apply_advanced_protection(hedef - 0.0083, hedef, server_offset=offset)
    gercek_atesleme = tetik - offset
    assert abs(gercek_atesleme - (hedef + 0.001)) < 1e-9


def _formul(hedef, server_offset, rtt=0.020, obs_offset=-0.0007, buffer=0.0103):
    """run() içindeki base_trigger hesabının birebir aynısı."""
    return hedef + server_offset - rtt - obs_offset + buffer


def test_floor_moves_earlier_when_our_clock_lags():
    """Saatimiz 25ms geriyse sınır de 25ms geri kaymalı; yoksa gerçek zamanda
    hedef+26ms'de ateşler ve 25ms'yi boşuna kaybederiz."""
    eng = _motor()
    hedef = 1_000_000.0
    offset = -0.025
    tetik = eng._apply_advanced_protection(_formul(hedef, offset), hedef,
                                           server_offset=offset)
    gercek_atesleme = tetik - offset
    assert abs(gercek_atesleme - (hedef + 0.001)) < 1e-9


def test_real_formula_is_always_clamped_at_normal_clock_error():
    """Ölçülen saat hataları (±3ms) hep sınırla karşılanır — yani gerçek
    davranış 'hedef+1ms'de gönder', varış ~hedef+20ms."""
    eng = _motor()
    hedef = 1_000_000.0
    for offset in (-0.003, -0.001, 0.0, 0.001, 0.003):
        tetik = eng._apply_advanced_protection(_formul(hedef, offset), hedef,
                                               server_offset=offset)
        assert abs((tetik - offset) - (hedef + 0.001)) < 1e-9, offset


def test_ceiling_also_follows_the_clock():
    """Üst sınır da aynı mantıkla kaymalı; yoksa saat hatasında erken kesilir."""
    eng = _motor()
    hedef = 1_000_000.0
    offset = 0.030
    tetik = eng._apply_advanced_protection(hedef + 5.0, hedef, server_offset=offset)
    assert abs((tetik - offset) - (hedef + 0.200)) < 1e-9


def test_value_between_bounds_is_untouched():
    eng = _motor()
    hedef = 1_000_000.0
    istenen = hedef + 0.050
    assert eng._apply_advanced_protection(istenen, hedef, server_offset=0.0) == istenen


def test_offset_defaults_to_measured_calibration():
    """Çağıran offset vermezse motor kendi ölçümünü kullanmalı."""
    eng = _motor()
    eng._cal_samples.append((0.012, 0.02, 1.0, "test"))
    hedef = 1_000_000.0
    tetik = eng._apply_advanced_protection(hedef - 0.0083, hedef)
    assert abs((tetik - 0.012) - (hedef + 0.001)) < 1e-9


# ── Olay kuyruğu sınırlı olmalı (OOM koruması) ──
# Kuyruk sınırsızdı. Drenaj (poll_engine_events) herhangi bir sebeple ölürse
# olaylar saatlerce birikir; 40 oturumda bu yüzlerce megabayt eder ve 1 GiB'lık
# konteyner OOM ile ölür — yani bekleyen BÜTÜN kayıtlar kaybolur.
# Olaylar geçicidir: eskisini düşürmek, servisi çökertmekten iyidir.


def test_event_queue_is_bounded():
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    for i in range(EVENT_QUEUE_MAX + 500):
        eng._emit("log", {"message": f"m{i}"})
    assert eng._events.qsize() <= EVENT_QUEUE_MAX


def test_newest_events_survive_when_queue_overflows():
    """Taşmada EN ESKİ olay düşer; kullanıcı en güncel durumu görmeli."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    for i in range(EVENT_QUEUE_MAX + 100):
        eng._emit("log", {"message": f"m{i}"})
    olaylar = eng.get_events()
    son = olaylar[-1]["data"]["message"]
    assert son == f"m{EVENT_QUEUE_MAX + 99}"


def test_overflow_does_not_raise():
    """Taşma ateşlemeyi ASLA bozmamalı — _emit tetik yolunda çağrılıyor."""
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    for i in range(EVENT_QUEUE_MAX * 2):
        eng._emit("countdown", {"remaining": i})  # exception atmamali
    assert eng._events.qsize() <= EVENT_QUEUE_MAX
