"""Clerk oturum doğrulaması için birim testleri.

Ağa çıkmaz: test içinde bir RSA anahtar çifti üretilir ve JWKS enjekte edilir.
"""

import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from auth import ClerkVerifier

ISSUER = "https://moved-rattler-15.clerk.accounts.dev"
KID = "test-key-1"


def _keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    return key, {"keys": [jwk]}


def _token(key, **claims):
    payload = {
        "sub": "user_abc123",
        "iss": ISSUER,
        "iat": int(time.time()) - 5,
        "exp": int(time.time()) + 600,
    }
    payload.update(claims)
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": KID})


@pytest.fixture
def verifier_and_key():
    key, jwks = _keypair()
    v = ClerkVerifier(issuer=ISSUER, jwks_fetcher=lambda: jwks)
    return v, key


def test_valid_token_returns_subject(verifier_and_key):
    v, key = verifier_and_key
    assert v.user_id_from_token(_token(key)) == "user_abc123"


def test_garbage_token_rejected(verifier_and_key):
    v, _ = verifier_and_key
    assert v.user_id_from_token("bu bir jwt degil") is None
    assert v.user_id_from_token("") is None


def test_token_signed_by_another_key_rejected(verifier_and_key):
    """Saldırgan kendi anahtarıyla token üretemesin."""
    v, _ = verifier_and_key
    other, _unused = _keypair()
    assert v.user_id_from_token(_token(other)) is None


def test_expired_token_rejected(verifier_and_key):
    v, key = verifier_and_key
    expired = _token(key, exp=int(time.time()) - 60, iat=int(time.time()) - 600)
    assert v.user_id_from_token(expired) is None


def test_wrong_issuer_rejected(verifier_and_key):
    """Başka bir Clerk uygulamasının token'ı kabul edilmesin."""
    v, key = verifier_and_key
    assert v.user_id_from_token(_token(key, iss="https://baska-uygulama.clerk.accounts.dev")) is None


def test_token_without_subject_rejected(verifier_and_key):
    v, key = verifier_and_key
    token = jwt.encode(
        {"iss": ISSUER, "iat": int(time.time()) - 5, "exp": int(time.time()) + 600},
        key,
        algorithm="RS256",
        headers={"kid": KID},
    )
    assert v.user_id_from_token(token) is None


def test_jwks_fetch_failure_does_not_crash(verifier_and_key):
    """Clerk'e ulaşılamazsa istek reddedilir ama servis çökmez."""
    def boom():
        raise RuntimeError("ağ yok")

    v = ClerkVerifier(issuer=ISSUER, jwks_fetcher=boom)
    _, key = verifier_and_key
    assert v.user_id_from_token(_token(key)) is None
