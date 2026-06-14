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
