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

# Ana servise bu kadar süredir ulaşılamıyorsa loga bir uyarı düşülür.
# Ateşlemeyi ENGELLEMEZ: servis çökmüşse yerel motor da ölmüştür ve çekilmek
# kesin ders kaybı olur (bkz. heartbeat_loop).
HEARTBEAT_MAX_AGE = float(os.getenv("OTOSTOP_HEARTBEAT_MAX_AGE", "10"))

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


# Yapılandırma çekme denemeleri. Konteyner hedeften ~15 dakika önce açıldığı
# için bolca vakit var; ilk denemede ulaşamamak vazgeçme sebebi değil.
CONFIG_DENEME = int(os.getenv("OTOSTOP_CONFIG_DENEME", "5"))
CONFIG_BEKLE = float(os.getenv("OTOSTOP_CONFIG_BEKLE", "3"))


def fetch_config() -> dict | None:
    """Yapılandırmayı (OBS token dahil) ana servisten çeker. Sahiplik ALMAZ.

    Geçici hatada yeniden dener; 403 gibi NET bir ret alınca hemen bırakır.
    Sonunda başaramazsa None döner ve konteyner kapanır — yerel motor zaten
    görevde olduğu için kullanıcı kaydı yine yapılır, sadece izolasyonsuz.
    """
    for deneme in range(1, CONFIG_DENEME + 1):
        try:
            r = _post("/internal/config", {})
        except Exception as e:
            log(f"config isteği başarısız ({deneme}/{CONFIG_DENEME}): {e}")
            if deneme < CONFIG_DENEME:
                time.sleep(CONFIG_BEKLE)
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code in (400, 401, 403, 404):
            # Net cevap: bilet geçersiz ya da oturum yok. Tekrar denemek anlamsız.
            log(f"config reddedildi: HTTP {r.status_code}")
            return None
        log(f"config cevapsız ({deneme}/{CONFIG_DENEME}): HTTP {r.status_code}")
        if deneme < CONFIG_DENEME:
            time.sleep(CONFIG_BEKLE)
    return None


# Sahiplenme isteğinin üç olası sonucu. "Reddedildi" ile "ulaşamadım" AYNI
# ŞEY DEĞİLDİR ve eskiden ikisi de çekilmeye yol açıyordu — ana servis
# çöktüğünde yerel motor da öldüğü için bu kesin ders kaybı demekti.
CLAIM_VERILDI = "verildi"
CLAIM_REDDEDILDI = "reddedildi"
CLAIM_ULASILAMADI = "ulasilamadi"


def claim() -> str:
    """Ateşleme sözü iste.

    CLAIM_VERILDI      → söz bizde, ateşle
    CLAIM_REDDEDILDI   → ana servis ulaşılabilir ve "hayır" dedi (yerel motor
                         devralmış ya da kayıt sıfırlanmış) — çekil
    CLAIM_ULASILAMADI  → cevap alınamadı; servis çökmüş olabilir, o hâlde yerel
                         motor da ölüdür. Ateşle.
    """
    try:
        r = _post("/internal/claim", {})
    except Exception as e:
        log(f"claim isteği başarısız ({e}) — ana servis çökmüş olabilir")
        return CLAIM_ULASILAMADI
    if r.status_code == 200:
        return CLAIM_VERILDI if r.json().get("granted") else CLAIM_REDDEDILDI
    if r.status_code == 403:
        log("claim reddedildi: kayıt tanınmıyor (sıfırlanmış)")
        return CLAIM_REDDEDILDI
    log(f"claim cevapsız: HTTP {r.status_code} — ulaşılamadı sayılıyor")
    return CLAIM_ULASILAMADI


def ateslemeli(sonuc: str) -> bool:
    """Yalnızca AÇIK ret ateşlemeyi durdurur; belirsizlikte ateşlenir."""
    return sonuc != CLAIM_REDDEDILDI


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
    uyarildi = False
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
            uyarildi = False
            if st.get("cancelled"):
                log("kullanıcı iptal etti — motor durduruluyor")
                engine.cancel()
                return
            if st.get("revoked"):
                log("söz geri alındı (ana servis devraldı) — motor durduruluyor")
                engine.cancel()
                return
        else:
            # ULAŞILAMIYOR — ama SÖZÜMÜZÜ TUTUYORUZ.
            #
            # İlk tasarımda burada çekiliyorduk ("10sn rapor veremediysem geri
            # alınmış olmalıyım"). Yanlıştı: ana servis ÇÖKTÜYSE yerel motor da
            # onunla birlikte ölmüştür ve çekilmek kesin ders kaybı demektir.
            #
            #   servis çöktü + çekilirsek  → %100 kayıp
            #   servis sağlam + ikimiz de ateşlersek → ilki dersi alır,
            #     ikincisi VAL03 ("zaten kayıtlısın") alır, ders yine alınmış olur
            #
            # Hiç ateşlememenin geri dönüşü yok, iki kez ateşlemenin var.
            # Açık iptal (403 / cancelled / revoked) hâlâ bizi durdurur; onlar
            # ana servise ULAŞABİLDİĞİMİZ durumlardır ve belirsizlik içermez.
            yas = time.time() - son_basarili
            if yas > HEARTBEAT_MAX_AGE and not uyarildi:
                uyarildi = True
                log(f"{yas:.0f}sn'dir ana servise ulaşılamıyor — sözü tutup "
                    f"ateşlemeye devam ediyorum (çekilmek kesin kayıp olurdu)")

        stop.wait(HEARTBEAT_INTERVAL)


def hazirlik_loglarini_at(engine) -> None:
    """Sahiplenme öncesi birikmiş olayları at.

    Konteyner açılışta kalibre olurken motorun kuyruğuna onlarca olay yazıyor,
    ama olay akışı ancak sahiplenmeden SONRA başlıyor. Bu birikmiş yığın
    kullanıcının canlı loguna toplu ve GERİYE DÖNÜK zaman damgalarıyla
    düşüyordu ("kaydı üstlendi" satırından sonra 8 saniye öncesine ait
    satırlar). Kullanıcı zaten tek satırlık özeti aldı; detay konteynerin
    kendi Cloud Run logunda duruyor.
    """
    try:
        engine.get_events()
    except Exception:
        pass


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

    sonuc = claim()
    if not ateslemeli(sonuc):
        log("söz verilemedi (ana servis devralmış) — çekiliyorum")
        return 0

    if sonuc == CLAIM_ULASILAMADI:
        log(f"ana servise ulaşılamadı — yine de ateşliyorum, hedefe "
            f"{target - time.time():.1f}s (çekilmek kesin kayıp olurdu)")
    else:
        log(f"sahiplik alındı, hedefe {target - time.time():.1f}s")

    # ── Ateşle ──
    # Hazırlık kalibrasyonunun biriken logları kullanıcıya sırasız akmasın
    hazirlik_loglarini_at(engine)

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
