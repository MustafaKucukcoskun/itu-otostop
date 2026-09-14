"""Token'ın kayıt saatinden ÖNCE dolması — dersi kaçırmanın en sessiz yolu.

Arayüz "6 saat sonra sona erecek" diyor, kullanıcı içi rahat başlatıyor,
motorun başlangıçtaki token kontrolü geçiyor. Saatler sonra ateşleme anında
token ölü oluyor ve OBS 401 dönüyor. Hiçbir uyarı yok, ders gitmiş oluyor.
"""

import base64
import json
import time

from token_expiry import token_exp, expires_before


def _jwt(exp: int | None) -> str:
    """İmzası doğrulanmayan, yalnızca exp taşıyan bir JWT üretir."""
    def b64(o: dict) -> str:
        raw = json.dumps(o).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")
    payload = {"identity": "080210070"}
    if exp is not None:
        payload["exp"] = exp
    return f"{b64({'alg': 'HS256'})}.{b64(payload)}.imza"


# ── exp çözümleme ──


def test_reads_exp_from_token():
    assert token_exp(_jwt(1789437450)) == 1789437450


def test_returns_none_for_token_without_exp():
    assert token_exp(_jwt(None)) is None


def test_returns_none_for_garbage():
    """Çözülemeyen token yüzünden kayıt ENGELLENMEMELİ — belirsizlikte geç."""
    assert token_exp("bu bir jwt degil") is None
    assert token_exp("") is None
    assert token_exp("a.b") is None


def test_tolerates_missing_base64_padding():
    """JWT tabanlı base64 dolgusuz gelir; çözümleme bunu kaldırmalı."""
    t = _jwt(1789437450)
    assert "=" not in t.split(".")[1]
    assert token_exp(t) == 1789437450


# ── Kayıt saatiyle karşılaştırma ──


def test_expiry_before_target_is_caught():
    simdi = time.time()
    hedef = simdi + 6 * 3600          # 6 saat sonra kayıt
    token = _jwt(int(simdi + 3600))   # token 1 saat sonra ölüyor
    assert expires_before(token, hedef) is True


def test_expiry_after_target_is_fine():
    simdi = time.time()
    hedef = simdi + 3600
    token = _jwt(int(simdi + 6 * 3600))
    assert expires_before(token, hedef) is False


def test_expiry_exactly_at_target_is_caught():
    """Tam ateşleme anında dolan token da işe yaramaz; pay bırakılmalı."""
    simdi = time.time()
    hedef = simdi + 3600
    assert expires_before(_jwt(int(hedef)), hedef) is True


def test_small_margin_is_required():
    """Ateşlemeden 30 saniye sonra dolan token yeniden denemelere yetmez."""
    simdi = time.time()
    hedef = simdi + 3600
    assert expires_before(_jwt(int(hedef + 30)), hedef, margin=120) is True
    assert expires_before(_jwt(int(hedef + 300)), hedef, margin=120) is False


def test_undecodable_token_does_not_block():
    """Emin olamadığımız token yüzünden kullanıcıyı engelleme."""
    assert expires_before("cozulemez", time.time() + 3600) is False
