"""İzole kayıt konteynerinin giriş noktası (Cloud Run Job görevi).

Kendi başına tek bir kullanıcının kaydını yürütür. Konteynerde başka kimse
olmadığı için GIL çekişmesi yoktur: busy-wait döngüsü tek başına çalışır.

SAHİPLENME ZAMANLAMASI — tasarımın en önemli kısmı.

Konteyner hedeften ~15 dk önce açılır ama kaydı HEMEN üstlenmez. Önce
kalibre olup hazır olduğunu kanıtlar, sonra boşta bekler ve ancak
T-CLAIM_LEAD anında sahipliği alır. Sebebi:

  - Erken sahiplenseydi, konteyner 15 dakikanın herhangi bir yerinde ölünce
    ana servis bunu bilemez ve kimse ateşlemez → kullanıcı dersi kaybeder.
  - Geç sahiplendiği için, ölen konteyner sahipliği hiç almamış olur; ana
    servis T-120s'de sahipsiz kaydı görüp yerel motorla devralır.

Yani "hazırım" demeden önce hiçbir şeye söz vermez. Sahiplenme başarısızsa
(ana servis çoktan devraldıysa) sessizce çekilir — çift ateşleme olmaz.
"""

from __future__ import annotations

import os
import sys
import threading
import time

import requests

from engine import RegistrationEngine

# Sahipliğin alınacağı an. Ana servisin yedek eşiği 120s; 180s seçilerek
# devralma kararı için 60 saniyelik net pay bırakıldı.
CLAIM_LEAD = float(os.getenv("OTOSTOP_CLAIM_LEAD", "180"))

SESSION_ID = os.getenv("OTOSTOP_SESSION_ID", "")
TICKET = os.getenv("OTOSTOP_TICKET", "")
CONTROL = os.getenv("OTOSTOP_CONTROL_URL", "").rstrip("/")


def log(msg: str) -> None:
    print(f"[izole {time.time():.3f}] {msg}", flush=True)


def _post(path: str, payload: dict, timeout: float = 10.0) -> requests.Response:
    return requests.post(
        f"{CONTROL}{path}",
        json={"session_id": SESSION_ID, "ticket": TICKET, **payload},
        timeout=timeout,
    )


def fetch_config() -> dict | None:
    """Yapılandırmayı (OBS token dahil) ana servisten çeker. Sahiplik ALMAZ."""
    try:
        r = _post("/internal/config", {})
    except Exception as e:
        log(f"config isteği başarısız: {e}")
        return None
    if r.status_code != 200:
        log(f"config reddedildi: HTTP {r.status_code}")
        return None
    return r.json()


def claim() -> bool:
    """Kaydı üstlen. False → ana servis devralmış, çekiliyoruz."""
    try:
        r = _post("/internal/claim", {})
    except Exception as e:
        log(f"claim isteği başarısız: {e}")
        return False
    if r.status_code == 200:
        return bool(r.json().get("granted"))
    log(f"claim reddedildi: HTTP {r.status_code}")
    return False


def notify(kind: str, data: dict) -> None:
    """Ana servise tek seferlik durum bildirimi — hata ateşlemeyi engellemez."""
    try:
        _post("/internal/events", {"events": [{"type": kind, "data": data,
                                               "timestamp": time.time()}]})
    except Exception as e:
        log(f"bildirim gönderilemedi ({kind}): {e}")


def stream_events(engine: RegistrationEngine, thread: threading.Thread) -> None:
    """Motorun olay kuyruğunu ana servise aktarır (WebSocket'e oradan gider).

    Ağ hatası yutulur: rapor akışının kopması ateşlemeyi ASLA durdurmamalı.
    Kullanıcı canlı log göremez ama dersi alınır.
    """
    while True:
        events = engine.get_events()
        if events:
            try:
                _post("/internal/events", {"events": events}, timeout=5.0)
            except Exception as e:
                log(f"olay aktarımı başarısız ({len(events)} olay düştü): {e}")
        if not engine.is_running and engine._events.empty() and not thread.is_alive():
            break
        time.sleep(0.1)

    for ev in engine.get_events():  # son kalanlar
        try:
            _post("/internal/events", {"events": [ev]}, timeout=5.0)
        except Exception:
            pass


def main() -> int:
    if not all((SESSION_ID, TICKET, CONTROL)):
        log("HATA: OTOSTOP_SESSION_ID / OTOSTOP_TICKET / OTOSTOP_CONTROL_URL eksik")
        return 1

    log(f"başladı — oturum {SESSION_ID[:12]}…")

    cfg = fetch_config()
    if cfg is None:
        return 1

    engine = RegistrationEngine(
        token=cfg["token"],
        ecrn_list=cfg["ecrn_list"],
        scrn_list=cfg.get("scrn_list", []),
        kayit_saati=cfg["kayit_saati"],
        max_deneme=cfg.get("max_deneme", 60),
        retry_aralik=cfg.get("retry_aralik", 3.0),
        dry_run=cfg.get("dry_run", False),
    )

    # ── Hazır olduğunu kanıtla ──
    # Kalibrasyon tutmazsa sahiplenme YAPILMAZ; ana servis yedeğe geçer.
    try:
        t0 = time.time()
        cal = engine.calibrate(source="izole-hazirlik")
        engine._prewarm()
        log(f"hazır: offset={cal.server_offset*1000:+.1f}ms "
            f"rtt={cal.rtt_one_way*2000:.0f}ms ({(time.time()-t0)*1000:.0f}ms)")
    except Exception as e:
        log(f"kalibrasyon başarısız, sahiplenilmiyor: {e}")
        notify("log", {"message": "İzole konteyner kalibre olamadı, "
                                  "ana sunucuya devredildi", "level": "warning"})
        return 1

    target = engine._saat_to_epoch(cfg["kayit_saati"])
    notify("log", {
        "message": f"İzole konteyner hazır ve kalibre "
                   f"(offset {cal.server_offset*1000:+.1f}ms, "
                   f"RTT {cal.rtt_one_way*2000:.0f}ms)",
        "level": "success",
    })

    # ── Sahiplenme anına kadar boşta bekle ──
    while True:
        kalan = target - time.time()
        if kalan <= CLAIM_LEAD:
            break
        time.sleep(min(5.0, kalan - CLAIM_LEAD))

    if not claim():
        log("sahiplik alınamadı (ana servis devralmış) — çekiliyorum")
        return 0

    log(f"sahiplik alındı, hedefe {target - time.time():.1f}s")

    # ── Ateşle ──
    thread = threading.Thread(target=engine.run, daemon=True)
    thread.start()
    stream_events(engine, thread)
    thread.join(timeout=30)
    log("tamamlandı")
    return 0


if __name__ == "__main__":
    sys.exit(main())
