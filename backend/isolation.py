"""Kayıt ateşlemesinin sahipliğini ve izole konteyner devrini yönetir.

NEDEN VAR: Tek konteynerde N kullanıcı aynı anda ateşlediğinde Python GIL
busy-wait thread'lerini sıraya sokuyor ve son kullanıcının isteği gecikiyor
(ölçüm: 15 kullanıcı 1.8ms, 100 kullanıcı 47ms en kötü sapma). Her kayda ayrı
Cloud Run konteyneri vermek bu sıralamayı tamamen ortadan kaldırır.

Ama izole konteyner *ek* bir yol; mevcut yerel motor yedek olarak durur.
İki yol olunca tek bir tehlike doğar: aynı kaydın iki yerden ateşlenmesi.
OBS aynı oturumdan 3sn içinde gelen ikinci isteği VAL16 ile düşürür, yani
çift ateşleme kullanıcıya ders kaybettirir.

Bu modül o tehlikeyi tek bir atomik sahiplenme (claim) ile keser: bir kaydı
ilk sahiplenen ateşler, diğeri sessizce çekilir. Ana servis tek instance
çalıştığı için (maxScale=1) bu kilit süreç içi olmak zorunda değil.
"""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

# Hedeften ne kadar önce izole konteyner açılsın.
# Ölçüm (europe-west3, 40 eşzamanlı): provisioning ~70s'ye yayılıyor,
# üstüne kalibrasyon 7s + ısınma 1s. 900s bunun 10 katından fazla pay bırakır.
DEFAULT_LEAD = 900.0

# Konteyner bu süre kala hâlâ sahiplenmediyse ana servis devralır.
# Yerel motorun kalibrasyon+ısınması da ~8s sürdüğü için 120s rahat yeter.
DEFAULT_READY_DEADLINE = 120.0


@dataclass
class _Entry:
    session_id: str
    target_epoch: float
    ticket: str
    launched: bool = False
    launched_at: float = 0.0
    owner: Optional[str] = None  # None | "remote" | "local"
    launch_error: str = ""


@dataclass
class IsolationBroker:
    lead: float = DEFAULT_LEAD
    ready_deadline: float = DEFAULT_READY_DEADLINE
    clock: Callable[[], float] = time.time
    _entries: dict[str, _Entry] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # ── Kayıt ──

    def register(self, session_id: str, target_epoch: float) -> str:
        """Kaydı sıraya al, konteynerin kimliğini kanıtlayacağı bileti üret.

        Bilet aynı zamanda kullanıcının OBS token'ını çekme yetkisidir; bu
        yüzden kriptografik rastgelelikle üretilir ve asla loglanmaz.
        """
        ticket = secrets.token_urlsafe(32)
        with self._lock:
            self._entries[session_id] = _Entry(
                session_id=session_id, target_epoch=target_epoch, ticket=ticket
            )
        return ticket

    def release(self, session_id: str) -> None:
        with self._lock:
            self._entries.pop(session_id, None)

    def target_of(self, session_id: str) -> Optional[float]:
        e = self._entries.get(session_id)
        return e.target_epoch if e else None

    def owner_of(self, session_id: str) -> Optional[str]:
        e = self._entries.get(session_id)
        return e.owner if e else None

    # ── Sahiplenme (tek ateşleyici garantisi) ──

    def verify_ticket(self, session_id: str, ticket: str) -> bool:
        """Bileti doğrular ama SAHİPLİK VERMEZ.

        Konteyner yapılandırmayı (OBS token dahil) çekerken ve olay akışını
        gönderirken bunu kullanır; sahiplenme ayrı ve tek seferlik bir adımdır.
        """
        with self._lock:
            e = self._entries.get(session_id)
            if e is None:
                return False
            return hmac.compare_digest(e.ticket, ticket or "")

    def claim_remote(self, session_id: str, ticket: str) -> bool:
        """İzole konteyner kaydı üstlenir. Yalnızca ilk çağrı True döner."""
        with self._lock:
            e = self._entries.get(session_id)
            if e is None or e.owner is not None:
                return False
            # Sabit zamanlı karşılaştırma: bilet tahmin saldırısına zaman sızdırmasın
            if not hmac.compare_digest(e.ticket, ticket or ""):
                return False
            e.owner = "remote"
            return True

    def claim_local(self, session_id: str) -> bool:
        """Ana servis yedek olarak üstlenir. Konteyner önce aldıysa False."""
        with self._lock:
            e = self._entries.get(session_id)
            if e is None or e.owner is not None:
                return False
            e.owner = "local"
            return True

    # ── Zamanlama ──

    def due_for_launch(self) -> list[tuple[str, str]]:
        """Konteyneri şimdi açılması gereken (session_id, bilet) çiftleri."""
        now = self.clock()
        with self._lock:
            return [
                (e.session_id, e.ticket)
                for e in self._entries.values()
                if not e.launched
                and e.owner is None
                and (e.target_epoch - now) <= self.lead
            ]

    def mark_launched(self, session_id: str, error: str = "") -> None:
        with self._lock:
            e = self._entries.get(session_id)
            if e is not None:
                e.launched = True
                e.launched_at = self.clock()
                e.launch_error = error

    def fallback_due(self) -> list[str]:
        """Ana servisin devralması gereken kayıtlar.

        `launched` bayrağına BAKILMAZ: başlatma isteği hiç gitmemiş olsa da
        (Run API hatası, geç kayıt) sahibi yoksa ve süre dolduysa yerel motor
        üstlenir. Kullanıcının hiç ateşlenmemesi, geç ateşlenmesinden kötüdür.
        """
        now = self.clock()
        with self._lock:
            return [
                e.session_id
                for e in self._entries.values()
                if e.owner is None and (e.target_epoch - now) <= self.ready_deadline
            ]

    def snapshot(self) -> list[dict]:
        """Teşhis için durum dökümü — bilet asla dışarı verilmez."""
        now = self.clock()
        with self._lock:
            return [
                {
                    "session_id": e.session_id,
                    "kalan_sn": round(e.target_epoch - now, 1),
                    "launched": e.launched,
                    "owner": e.owner,
                    "launch_error": e.launch_error,
                }
                for e in self._entries.values()
            ]
