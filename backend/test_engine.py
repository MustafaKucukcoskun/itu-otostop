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


# ── calibrate() offset + OBS↔NTP skew düzeltmesi ──
#
# KRİTİK: NTP, OBS'nin NTP-senkron olduğunu VARSAYAR. Gerçekte OBS NTP'den kayabilir
# (canlı ölçüm: ~90ms geride). Düzeltilmezse engine OBS açılmadan ~kayma kadar ERKEN
# atar → VAL02 + 3sn ceza → kontenjan biter. Doğru tasarım: server_offset NTP'de STABİL
# kalır; OBS↔NTP skew'i robust Date (min) ile ölçülüp _obs_clock_offset'e konur ve tetik
# formülünde telafi edilir. (Önceki "server_offset'i Date ile ez" yaklaşımı GCP'de date
# gürültüsüne kapıldığı için terk edildi — bu testler doğru davranışı kilitler.)

from unittest.mock import Mock  # noqa: E402
from engine import RegistrationEngine  # noqa: E402


def _make_calib_engine():
    """Ağa dokunan metotları mock'layıp calibrate()'in offset mantığını izole eder."""
    eng = RegistrationEngine(token="dummy.jwt.token", ecrn_list=["00000"])
    eng.session = Mock()                       # warmup POST → no-op
    eng._rtt_olc = lambda n=5: 0.044           # medyan RTT 44ms
    eng._log = lambda *a, **k: None
    eng._emit = lambda *a, **k: None
    eng._set_phase = lambda *a, **k: None
    eng._update_trend_analysis = lambda *a, **k: None
    return eng


def test_calibrate_obs_synced_no_skew():
    """OBS NTP-senkron → server_offset=NTP, OBS skew düzeltmesi ~0."""
    eng = _make_calib_engine()
    eng._ntp_calibrate = lambda: (0.0, 0.008)                 # GCP saati NTP-senkron
    eng._measure_date_offset = lambda n_transitions=1: 0.0    # local-OBS ~0 → OBS=NTP
    cal = eng.calibrate()
    assert cal.server_offset == pytest.approx(0.0, abs=1e-6)         # NTP
    assert eng._obs_clock_offset == pytest.approx(0.0, abs=2e-3)     # skew yok


def test_calibrate_obs_behind_corrected_by_skew():
    """KRİTİK: OBS 90ms NTP-geride. server_offset NTP'de STABİL kalmalı (gürültüye
    kapılmamalı); düzeltme _obs_clock_offset üzerinden uygulanmalı (erken atış önlenir)."""
    eng = _make_calib_engine()
    eng._ntp_calibrate = lambda: (0.0, 0.008)                  # GCP NTP-senkron
    eng._measure_date_offset = lambda n_transitions=1: 0.090   # local-OBS=+90ms → OBS 90ms geride
    cal = eng.calibrate()
    assert cal.server_offset == pytest.approx(0.0, abs=1e-6)         # NTP stabil (ezilmez)
    # skew = -(date + ntp) = -(0.090 + 0) = -0.090 → tetik 90ms geç atar, erken atmaz
    assert eng._obs_clock_offset == pytest.approx(-0.090, abs=2e-3)


def test_calibrate_date_fails_no_correction():
    """Date ölçülemezse OBS skew düzeltmesi yok (NTP=OBS varsayımı), server_offset=NTP."""
    eng = _make_calib_engine()
    eng._ntp_calibrate = lambda: (0.002, 0.008)
    eng._measure_date_offset = lambda n_transitions=1: None
    cal = eng.calibrate()
    assert cal.server_offset == pytest.approx(-0.002, abs=1e-6)
    assert eng._obs_clock_offset == 0.0
