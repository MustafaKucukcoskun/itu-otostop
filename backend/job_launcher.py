"""Kayıt başına izole Cloud Run Job konteyneri açar.

Konteynere OBS token'ı GÖNDERİLMEZ. Çalıştırma isteğindeki env değişkenleri
Cloud Run'ın execution kaydında günlerce okunabilir durur; oraya kullanıcı
token'ı koymak CLAUDE.md'deki "token asla diske/buluta yazılmaz" kuralını
bozardı. Bunun yerine tek kullanımlık bir bilet gönderilir, konteyner
yapılandırmayı ana servisten HTTPS ile çeker ve bellekte tutar.

Ölçüm notu (europe-west3, 2026-09-13): 40 eşzamanlı çalıştırma isteğinin
hepsi kabul edildi (0 hata), ama konteynerler ~70 saniyeye yayılarak kalktı.
Bu yüzden başlatma hedeften ~15 dk önce yapılır; anında kalkma varsayılmaz.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

import requests

RUN_API = "https://run.googleapis.com/v2"
METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/"
    "service-accounts/default/token"
)


@dataclass
class JobLauncherConfig:
    project: str
    region: str
    job_name: str
    control_url: str

    @classmethod
    def from_env(cls) -> Optional["JobLauncherConfig"]:
        """Ortamdan oku; eksikse None → izolasyon kapalı, yerel motor çalışır."""
        project = os.getenv("GCP_PROJECT", "").strip()
        region = os.getenv("GCP_REGION", "").strip()
        job_name = os.getenv("ISOLATED_JOB_NAME", "").strip()
        control_url = os.getenv("CONTROL_URL", "").strip().rstrip("/")
        if not all((project, region, job_name, control_url)):
            return None
        return cls(project, region, job_name, control_url)


def build_run_request(
    cfg: JobLauncherConfig,
    session_id: str,
    ticket: str,
    task_timeout: int,
) -> tuple[str, dict]:
    """(url, gövde) — ağa çıkmadan test edilebilsin diye ayrı tutuldu."""
    url = (
        f"{RUN_API}/projects/{cfg.project}/locations/{cfg.region}"
        f"/jobs/{cfg.job_name}:run"
    )
    body = {
        "overrides": {
            "taskCount": 1,
            "timeout": f"{int(task_timeout)}s",
            "containerOverrides": [
                {
                    "env": [
                        {"name": "OTOSTOP_SESSION_ID", "value": session_id},
                        {"name": "OTOSTOP_TICKET", "value": ticket},
                        {"name": "OTOSTOP_CONTROL_URL", "value": cfg.control_url},
                    ]
                }
            ],
        }
    }
    return url, body


class JobLauncher:
    """Run Admin API v2 istemcisi. Erişim token'ını metadata sunucusundan alır."""

    def __init__(self, cfg: JobLauncherConfig, timeout: float = 15.0):
        self.cfg = cfg
        self._timeout = timeout
        self._token = ""
        self._token_exp = 0.0
        self._lock = threading.Lock()

    def _access_token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._token_exp - 60:
                return self._token
            r = requests.get(
                METADATA_TOKEN_URL,
                headers={"Metadata-Flavor": "Google"},
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            self._token = data["access_token"]
            self._token_exp = time.time() + float(data.get("expires_in", 3600))
            return self._token

    def launch(self, session_id: str, ticket: str, task_timeout: int = 1800) -> str:
        """Konteyneri açar; çalıştırma adını döndürür. Hata fırlatabilir."""
        url, body = build_run_request(self.cfg, session_id, ticket, task_timeout)
        r = requests.post(
            url,
            json=body,
            headers={"Authorization": f"Bearer {self._access_token()}"},
            timeout=self._timeout,
        )
        r.raise_for_status()
        return r.json().get("name", "")
