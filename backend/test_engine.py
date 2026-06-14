"""
Engine timing/yardımcı fonksiyonları için birim testleri (Faz 4 — test başlangıcı).

Çalıştırma (backend/ içinden):
    venv/Scripts/python -m pytest -q          # Windows
    venv/bin/python -m pytest -q              # Unix
"""

import pytest

from engine import TrendAnalyzer, ChangeDetector
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


# ── calibrate() offset seçimi — OBS NTP-senkron değilse erken atışı önle ──
#
# KRİTİK: OBS tarihsel olarak ~2sn geriydeydi. NTP "senkron" derken OBS 2sn geride
# olursa, NTP'ye güvenmek tetik'i sunucu açılmadan atar → VAL02 + 3sn ceza → kontenjan
# biter. Engine, NTP-Date çelişkisini (2 ölçümle teyitli) yakalayıp GERÇEK OBS saatini
# (Date offset) kullanmalı. Bu testler o davranışı kilitler.

from unittest.mock import Mock  # noqa: E402
from engine import RegistrationEngine  # noqa: E402


def _make_calib_engine():
    """Ağa dokunan metotları mock'layıp calibrate()'in offset seçim mantığını izole eder."""
    eng = RegistrationEngine(token="dummy.jwt.token", ecrn_list=["00000"])
    eng.session = Mock()                       # warmup POST → no-op
    eng._rtt_olc = lambda n=5: 0.044           # medyan RTT 44ms
    eng._log = lambda *a, **k: None
    eng._emit = lambda *a, **k: None
    eng._set_phase = lambda *a, **k: None
    eng._update_trend_analysis = lambda *a, **k: None
    return eng


def test_calibrate_obs_synced_uses_ntp():
    """OBS NTP-senkron (NTP≈Date) → NTP offset korunur, Date override etmez."""
    eng = _make_calib_engine()
    eng._ntp_calibrate = lambda: (0.005, 0.008)   # NTP: OBS yerelden 5ms geride
    eng._measure_date_offset = lambda: 0.003      # Date ~aynı (fark 2ms < 100ms eşik)
    cal = eng.calibrate()
    assert cal.server_offset == pytest.approx(-0.005, abs=1e-6)  # = -ntp_offset_raw


def test_calibrate_obs_2s_behind_uses_date():
    """FELAKET ÖNLEME: OBS 2sn geride; NTP 0 der ama Date +2s (2 ölçümle teyit).
    Engine NTP'ye güvenmemeli (2sn erken = VAL02), Date offset'i kullanmalı."""
    eng = _make_calib_engine()
    eng._ntp_calibrate = lambda: (0.0, 0.008)                # NTP: yanlışlıkla senkron sanıyor
    eng._measure_date_offset = Mock(side_effect=[2.0, 2.0])  # Date: OBS 2sn geride
    cal = eng.calibrate()
    assert cal.server_offset == pytest.approx(2.0, abs=1e-3)  # NTP(0) değil → Date(+2s)
    assert eng._measure_date_offset.call_count == 2           # teyit için 2. ölçüm yapıldı


def test_calibrate_noisy_date_keeps_ntp():
    """Tek gürültülü Date ölçümü NTP'yi EZMEMELİ — 2. ölçüm teyit etmezse NTP korunur."""
    eng = _make_calib_engine()
    eng._ntp_calibrate = lambda: (0.0, 0.008)
    eng._measure_date_offset = Mock(side_effect=[2.0, 0.001])  # 1. büyük, 2. küçük → teyit YOK
    cal = eng.calibrate()
    assert cal.server_offset == pytest.approx(0.0, abs=1e-6)    # NTP korundu (override yok)
