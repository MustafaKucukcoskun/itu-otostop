"""
Engine timing/yardımcı fonksiyonları için birim testleri (Faz 4 — test başlangıcı).

Çalıştırma (backend/ içinden):
    venv/Scripts/python -m pytest -q          # Windows
    venv/bin/python -m pytest -q              # Unix
"""

import pytest

from engine import TrendAnalyzer, ChangeDetector, RegistrationEngine
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
