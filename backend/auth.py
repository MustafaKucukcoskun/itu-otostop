"""Clerk oturum doğrulaması.

Backend şimdiye kadar `--allow-unauthenticated` ile tamamen açıktı: adresi bilen
herkes oturum açabiliyordu. Oturum havuzu sınırlı olduğu için (MAX_SESSIONS) bu,
kayıt anında gerçek kullanıcıların dışarıda kalmasına yol açabilecek bir açıktı.

Burada Clerk'in imzaladığı oturum token'ı RS256 ile doğrulanır ve kullanıcı
kimliği (`sub`) çıkarılır. Kimlik, backend oturumunun anahtarı olur — böylece
bir kişi kaç cihazdan girerse girsin tek slot tutar.
"""

import json
import threading
import time
import urllib.request
from typing import Any, Callable, Optional

import jwt


class ClerkVerifier:
    """Clerk JWT'sini JWKS ile doğrular ve kullanıcı kimliğini döndürür.

    `jwks_fetcher` testlerde enjekte edilebilir; üretimde Clerk'in
    `/.well-known/jwks.json` ucundan çekilir ve süreli olarak önbelleklenir.
    """

    def __init__(
        self,
        issuer: str,
        jwks_fetcher: Optional[Callable[[], dict]] = None,
        cache_ttl: float = 600.0,
        leeway: float = 10.0,
        timeout: float = 5.0,
    ):
        self.issuer = issuer.rstrip("/")
        self._fetch = jwks_fetcher or self._default_fetcher
        self._cache_ttl = cache_ttl
        self._leeway = leeway
        self._timeout = timeout
        self._jwks: Optional[dict] = None
        self._jwks_at = 0.0
        self._lock = threading.Lock()

    # ── JWKS ──

    def _default_fetcher(self) -> dict:
        url = f"{self.issuer}/.well-known/jwks.json"
        with urllib.request.urlopen(url, timeout=self._timeout) as r:
            return json.load(r)

    def _keys(self, force: bool = False) -> dict:
        now = time.time()
        with self._lock:
            stale = self._jwks is None or (now - self._jwks_at) > self._cache_ttl
            if force or stale:
                self._jwks = self._fetch()
                self._jwks_at = now
            return self._jwks or {}

    @staticmethod
    def _find_key(jwks: dict, kid: Optional[str]) -> Optional[dict]:
        for k in (jwks or {}).get("keys", []):
            if kid is None or k.get("kid") == kid:
                return k
        return None

    # ── Doğrulama ──

    def user_id_from_token(self, token: Any) -> Optional[str]:
        """Geçerliyse Clerk kullanıcı kimliğini, değilse None döndürür.

        Hiçbir durumda exception sızdırmaz: doğrulanamayan istek reddedilir,
        ama Clerk'e ulaşılamaması servisi çökertmez.
        """
        if not token or not isinstance(token, str):
            return None

        try:
            kid = jwt.get_unverified_header(token).get("kid")
        except Exception:
            return None

        key = None
        for force in (False, True):
            # Anahtar döndürülmüş olabilir; ilk denemede bulunamazsa bir kez tazele
            try:
                key = self._find_key(self._keys(force=force), kid)
            except Exception:
                return None
            if key is not None:
                break
        if key is None:
            return None

        try:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=self.issuer,
                leeway=self._leeway,
                options={
                    "require": ["exp", "iat", "sub"],
                    "verify_aud": False,  # Clerk oturum token'ında aud yok
                },
            )
        except Exception:
            return None

        sub = claims.get("sub")
        return sub if isinstance(sub, str) and sub else None
