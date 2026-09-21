# -*- coding: utf-8 -*-
"""Bekleyen kayıtları servis yeniden başlasa da kaybetmemek.

SORUN
─────
Broker ve motor bellekte duruyor. Kullanıcı "başlat"a basıp gidiyor;
konteyner ancak `ISOLATION_LEAD` kadar önce açılıyor ve o ana kadar kayıt
YALNIZCA ana servisin belleğinde. Servis yeniden başlarsa (deploy, instance
değişimi, çökme) kayıt tamamen kaybolur ve kimse ateşlemez.

Ölçüldü (17 Eylül): gerçek kullanıcılar hedeften 3.5 / 3 / 2.8 / 2.7 / 2.6 /
2 / 2 saat önce başlattı. lead=3600 ile bir saatten erken başlayan herkes bu
pencerede açıkta kalıyor.

ÇÖZÜM
─────
Kaydı GCS'e yaz, açılışta geri yükle, iş biter bitmez SİL.

Yeni bağımlılık YOK: `job_launcher` zaten metadata sunucusundan erişim
token'ı alıp Google API'sine REST ile gidiyor; aynı desen burada da kullanıldı.

GÜVENLİK
────────
OBS token'ı da yazılıyor — kayıt onsuz geri yüklenemez, ateşleyecek istek o
token'la imzalanıyor. Bedeli bilinçli kabul edildi. Azaltıcılar:
  - kova özel (uniform erişim, herkese açık okuma yok)
  - kayıt biter/iptal edilir edilmez siliniyor
  - OBS token'ı zaten ~6 saatlik
  - kovada 1 günlük yaşam döngüsü kuralı: temizlik yolu bozulsa bile
    token sonsuza kadar durmaz

EN ÖNEMLİ KURAL
───────────────
Kalıcılık bir EMNİYET AĞI, bir bağımlılık değil. Depolama çökerse, yetki
yoksa, kova yoksa — kayıt yine çalışmalı. Bu modülden dışarı asla istisna
sızmaz; her yol sessizce devre dışı kalır.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable, Optional
from urllib.parse import quote

import requests

METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/"
    "instance/service-accounts/default/token"
)
GCS_UPLOAD = "https://storage.googleapis.com/upload/storage/v1/b"
GCS_API = "https://storage.googleapis.com/storage/v1/b"
ONEK = "pending/"

# Hedefi bu kadar saniyeden fazla geçmiş kayıt geri YÜKLENMEZ: motor kapalı
# pencereye altmış kez ateşler ve kullanıcı "başlatıldı" yazısını gördükten
# sonra hiçbir şey olmaz. Birkaç dakika gecikme ise gerçek bir kurtarma
# vakası (bkz. main.GECMIS_HEDEF_TOLERANSI, aynı gerekçe).
GERI_YUKLEME_TOLERANSI = float(os.getenv("RESTORE_PAST_TOLERANCE", "3600"))


def metadata_token(timeout: float = 5.0) -> str:
    r = requests.get(METADATA_TOKEN_URL,
                     headers={"Metadata-Flavor": "Google"}, timeout=timeout)
    r.raise_for_status()
    return r.json()["access_token"]


class PendingStore:
    """Bekleyen kayıtların GCS'teki kopyası. Hiçbir metodu istisna fırlatmaz."""

    def __init__(self, bucket: str = "", transport=None,
                 token_fn: Optional[Callable[[], str]] = None,
                 timeout: float = 10.0):
        self.bucket = (bucket or "").strip()
        self._t = transport or requests
        self._token_fn = token_fn or metadata_token
        self._timeout = timeout
        self._lock = threading.Lock()
        self._token = ""
        self._token_exp = 0.0

    @property
    def enabled(self) -> bool:
        """Kova ayarlanmamışsa sessizce devre dışı — kurulum zorunlu olmasın."""
        return bool(self.bucket)

    # ── içeriden ──

    def _basliklar(self) -> dict:
        with self._lock:
            if not self._token or time.time() >= self._token_exp - 60:
                self._token = self._token_fn()
                self._token_exp = time.time() + 3300
            return {"Authorization": f"Bearer {self._token}"}

    def _ad(self, session_id: str) -> str:
        return f"{ONEK}{session_id}.json"

    def _indir(self, ad: str) -> Optional[dict]:
        url = f"{GCS_API}/{quote(self.bucket, safe='')}/o/{quote(ad, safe='')}?alt=media"
        r = self._t.get(url, headers=self._basliklar(), timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    # ── dışarıya ──

    def save(self, session_id: str, kayit: dict) -> bool:
        """Kaydı yaz. Başarısızlık sessiz: kayıt yine çalışır."""
        if not self.enabled:
            return False
        try:
            govde = json.dumps({**kayit, "session_id": session_id,
                                "saved_at": time.time()}).encode("utf-8")
            url = (f"{GCS_UPLOAD}/{quote(self.bucket, safe='')}/o"
                   f"?uploadType=media&name={quote(self._ad(session_id), safe='')}")
            r = self._t.post(url, data=govde,
                             headers={**self._basliklar(),
                                      "Content-Type": "application/json"},
                             timeout=self._timeout)
            r.raise_for_status()
            return True
        except Exception as e:
            print(f"[kalicilik] yazilamadi ({session_id[:12]}): {e}", flush=True)
            return False

    def delete(self, session_id: str) -> bool:
        """Kaydı sil — iş bitti, token'ın orada durmasına gerek yok."""
        if not self.enabled:
            return False
        try:
            url = (f"{GCS_API}/{quote(self.bucket, safe='')}/o/"
                   f"{quote(self._ad(session_id), safe='')}")
            r = self._t.delete(url, headers=self._basliklar(), timeout=self._timeout)
            if r.status_code not in (200, 204, 404):
                r.raise_for_status()
            return True
        except Exception as e:
            print(f"[kalicilik] silinemedi ({session_id[:12]}): {e}", flush=True)
            return False

    def list_pending(self) -> list[dict]:
        """Geri yüklenmeye değer kayıtlar. Hata olursa BOŞ döner."""
        if not self.enabled:
            return []
        try:
            url = (f"{GCS_API}/{quote(self.bucket, safe='')}/o"
                   f"?prefix={quote(ONEK, safe='')}")
            r = self._t.get(url, headers=self._basliklar(), timeout=self._timeout)
            r.raise_for_status()
            nesneler = (r.json() or {}).get("items") or []
        except Exception as e:
            print(f"[kalicilik] listelenemedi: {e}", flush=True)
            return []

        simdi = time.time()
        sonuc = []
        for n in nesneler:
            ad = n.get("name") or ""
            try:
                kayit = self._indir(ad)
            except Exception as e:
                print(f"[kalicilik] okunamadi ({ad}): {e}", flush=True)
                continue
            if not isinstance(kayit, dict):
                continue
            hedef = float(kayit.get("target_epoch") or 0)
            if (simdi - hedef) > GERI_YUKLEME_TOLERANSI:
                continue          # çoktan geçmiş; geri yüklemek boşuna ateşler
            sonuc.append(kayit)
        return sonuc
