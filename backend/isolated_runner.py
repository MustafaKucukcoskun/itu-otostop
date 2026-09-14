"""İzole kayıt konteynerinin giriş noktası (Cloud Run Job görevi).

Tek bir kullanıcının kaydını tek başına yürütür. Konteynerde başka kimse
olmadığı için GIL çekişmesi yoktur: busy-wait döngüsü yalnız çalışır.

SAHİPLENME ZAMANLAMASI — tasarımın en önemli kısmı.

Konteyner hedeften ~15 dk önce açılır ama kaydı HEMEN üstlenmez. Önce kalibre
olup hazır olduğunu kanıtlar, boşta bekler ve T-CLAIM_LEAD anında sahipliği
alır. Kalibrasyonu tutmayan ya da hiç kalkamayan konteyner söz vermemiş olur;
ana servisteki yerel motor bugünkü gibi ateşler.

Sahiplenmek "ateşleme hakkı" değil "ateşleme SÖZÜ"dür. Söz verdikten sonra
konteyner nabız atmak zorundadır: nabız kesilirse ana servis sözü geri alır ve
yerel motora devreder. Ateşleyenin hiç olmaması, iki kez ateşlemekten kötüdür.

Nabız ayrıca iptali taşır: kullanıcı iptal ederse konteyner bunu nabız
yanıtından öğrenip kendini durdurur.
"""

from __future__ import annotations

import os
import sys
import threading
import time

import requests

from engine import RegistrationEngine

# Sahipliğin alınacağı an. Ana servisin devir eşiği 8s, sahiplenme alt sınırı
# 20s; 180s ikisine de geniş pay bırakır.
CLAIM_LEAD = float(os.getenv("OTOSTOP_CLAIM_LEAD", "180"))

# Nabız aralığı ve kesme noktası. Hedefe 2s kala nabız durur: motor son 50ms'de
# busy-wait'e giriyor ve o sırada başka bir thread'in GIL'i kapması tetiği
# kaydırabilir. 2s öncesine kadar motor time.sleep() içinde, GIL serbest.
HEARTBEAT_INTERVAL = float(os.getenv("OTOSTOP_HEARTBEAT_INTERVAL", "2"))
HEARTBEAT_STOP = float(os.getenv("OTOSTOP_HEARTBEAT_STOP", "2"))

# Ana servisin nabzı ölü saydığı yaş ve devir eşiği. Bu iki sayı isolation.py
# ile AYNI olmalı: konteyner "ana servis beni ölü saymış olmalı" kararını bu
# simetriyle verir.
HEARTBEAT_MAX_AGE = float(os.getenv("OTOSTOP_HEARTBEAT_MAX_AGE", "10"))
HANDOVER_GUARD = float(os.getenv("OTOSTOP_HANDOVER_GUARD", "8"))

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
    """Ateşleme sözü ver. False → ana servis devralmış, çekiliyoruz."""
    try:
        r = _post("/internal/claim", {})
    except Exception as e:
        log(f"claim isteği başarısız: {e}")
        return False
    if r.status_code == 200:
        return bool(r.json().get("granted"))
    log(f"claim reddedildi: HTTP {r.status_code}")
    return False


# Ana servis "bu kaydı tanımıyorum" dedi (403). Ağ kopmasından AYRI tutulur:
# burada belirsizlik yok, kayıt sıfırlanmış demektir.
REDDEDILDI = "reddedildi"


def beat():
    """Tek nabız.

    dict        → başarılı, durum bayrakları içinde
    REDDEDILDI  → ana servis kaydı tanımıyor (sıfırlanmış)
    None        → ulaşılamadı (belirsiz)
    """
    try:
        r = _post("/internal/heartbeat", {}, timeout=5.0)
    except Exception:
        return None
    if r.status_code == 403:
        return REDDEDILDI
    if r.status_code != 200:
        return None
    return r.json()


def notify(kind: str, data: dict) -> None:
    """Tek seferlik durum bildirimi — hatası ateşlemeyi engellemez."""
    try:
        _post("/internal/events", {"events": [{"type": kind, "data": data,
                                               "timestamp": time.time()}]})
    except Exception as e:
        log(f"bildirim gönderilemedi ({kind}): {e}")


def heartbeat_loop(engine: RegistrationEngine, target: float,
                   stop: threading.Event) -> None:
    """Sözü tuttuğumuzu bildirir, iptal/geri-alma haberini dinler.

    Hedefe HEARTBEAT_STOP kala durur: motorun busy-wait'i sırasında bu
    thread'in uyanması tetiği kaydırabilir.
    """
    son_basarili = time.time()
    while not stop.is_set():
        if (target - time.time()) <= HEARTBEAT_STOP:
            log("nabız durduruldu (tetik yaklaştı)")
            return

        st = beat()
        if st is REDDEDILDI or st == REDDEDILDI:
            # Kesin cevap: kayıt yok. Devir eşiği koruması UYGULANMAZ —
            # beklersek kullanıcının sıfırladığı kayıt ateşlenebilir.
            log("ana servis kaydı tanımıyor (sıfırlanmış) — motor durduruluyor")
            engine.cancel()
            return
        if isinstance(st, dict):
            son_basarili = time.time()
            if st.get("cancelled"):
                log("kullanıcı iptal etti — motor durduruluyor")
                engine.cancel()
                return
            if st.get("revoked"):
                log("söz geri alındı (ana servis devraldı) — motor durduruluyor")
                engine.cancel()
                return
        else:
            # SİMETRİ: ana servis HEARTBEAT_MAX_AGE nabızsız kalınca sözü geri
            # alıp yerel motora devrediyor. O kadar süredir rapor veremiyorsak
            # geri alınmış SAYMALIYIZ; yoksa ikimiz de ateşler ve OBS her iki
            # isteği de VAL16 ile düşürür.
            simdi = time.time()
            yas = simdi - son_basarili
            if yas > HEARTBEAT_MAX_AGE and (target - simdi) > HANDOVER_GUARD:
                log(f"{yas:.0f}sn'dir ana servise ulaşılamıyor — geri alınmış "
                    f"sayılıp çekiliyorum (yerel motor ateşleyecek)")
                engine.cancel()
                return
            # Devir anı geçtiyse çekilme YOK: karar verilmiş, yerel motor
            # çoktan durmuş olabilir. Sözü tutup ateşlemek tek doğru davranış.

        stop.wait(HEARTBEAT_INTERVAL)


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


def wait_until_claim_time(target: float) -> bool:
    """Sahiplenme anına kadar bekle. False → kayıt iptal edilmiş, çık.

    Boşta beklerken de nabız atılır; böylece iptal edilen kayıt için konteyner
    hedefi beklemeden kapanır ve boşuna CPU yakmaz.
    """
    while True:
        kalan = target - time.time()
        if kalan <= CLAIM_LEAD:
            return True
        st = beat()
        if st == REDDEDILDI:
            log("bekleme sırasında kayıt sıfırlanmış — çıkılıyor")
            return False
        if isinstance(st, dict) and (st.get("cancelled") or st.get("revoked")):
            log("bekleme sırasında iptal edildi — çıkılıyor")
            return False
        time.sleep(min(10.0, max(0.5, kalan - CLAIM_LEAD)))


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
    # Kalibrasyon tutmazsa sahiplenme YAPILMAZ; yerel motor görevde kalır.
    try:
        t0 = time.time()
        cal = engine.calibrate(source="izole-hazirlik")
        engine._prewarm()
        log(f"hazır: offset={cal.server_offset*1000:+.1f}ms "
            f"rtt={cal.rtt_one_way*2000:.0f}ms ({(time.time()-t0)*1000:.0f}ms)")
    except Exception as e:
        log(f"kalibrasyon başarısız, sahiplenilmiyor: {e}")
        notify("log", {"message": "İzole konteyner kalibre olamadı, "
                                  "kayıt ana sunucudan yapılacak", "level": "warning"})
        return 1

    # Hedef epoch servisten gelir: sahiplenme ve devir zamanlamasında ikisinin
    # aynı sayıyı kullanması şart. Ateşleme anını yine motor kendi hesaplar.
    target = cfg.get("target_epoch") or engine._saat_to_epoch(cfg["kayit_saati"])
    notify("log", {
        "message": f"İzole konteyner hazır ve kalibre "
                   f"(offset {cal.server_offset*1000:+.1f}ms, "
                   f"RTT {cal.rtt_one_way*2000:.0f}ms)",
        "level": "success",
    })

    if not wait_until_claim_time(target):
        return 0

    if not claim():
        log("söz verilemedi (ana servis devralmış) — çekiliyorum")
        return 0

    log(f"sahiplik alındı, hedefe {target - time.time():.1f}s")

    # ── Ateşle ──
    stop = threading.Event()
    hb = threading.Thread(
        target=heartbeat_loop, args=(engine, target, stop), daemon=True
    )
    hb.start()

    thread = threading.Thread(target=engine.run, daemon=True)
    thread.start()
    stream_events(engine, thread)
    stop.set()
    thread.join(timeout=30)
    log("tamamlandı")
    return 0


if __name__ == "__main__":
    sys.exit(main())
