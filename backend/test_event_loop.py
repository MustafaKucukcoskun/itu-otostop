"""Event loop'un bloke olmaması — servisin yanıt veremez hale gelmesinin
bir numaralı sebebi.

Tek uvicorn worker'ı var. Bir async uç içinde SENKRON bir ağ çağrısı yapılırsa
o süre boyunca servis hiçbir isteğe cevap veremez:

  - WebSocket'ler susar (geri sayım donar)
  - /internal/heartbeat cevapsız kalır → konteynerler "ulaşılamıyor" görür
  - izolasyon denetleyicisi çalışamaz → T-8s devir penceresi KAÇABİLİR
  - Cloud Run sağlık yoklaması zaman aşımına uğrarsa instance yeniden başlar
    ve bekleyen bütün kayıtlar ölür

`search_courses` önbellek boşken 41 senkron OBS isteği atıyor (1 bölüm listesi
+ 40 bölüm) ve bu doğrudan handler içinde çalışıyordu.

ÖLÇÜM YÖNTEMİ: loop'un kendi tepkiselliğini bir bekçi görevle izliyoruz.
Bekçi 20ms'lik uykular yapar; loop bloke olursa bu uykulardan biri blokaj
kadar uzun sürer. İsteğin süresini ölçmek yanıltıcıydı — ölçümden önceki
`await` blokajı kendi içine soğuruyordu.
"""

import asyncio
import time

import pytest
from httpx2 import ASGITransport, AsyncClient

import main
from obs_course_service import CourseInfo


def _ders(crn="12345"):
    return CourseInfo(
        crn=crn, course_code="AKM 204", course_name="Akışkanlar Mekaniği",
        instructor="X", teaching_method="Örgün", capacity=30, enrolled=10,
    )


class LoopBekcisi:
    """Event loop'un en uzun durma süresini ölçer."""

    def __init__(self, adim=0.02):
        self.adim = adim
        self.en_uzun = 0.0
        self._dur = asyncio.Event()
        self._gorev = None

    async def _kos(self):
        while not self._dur.is_set():
            t = time.perf_counter()
            await asyncio.sleep(self.adim)
            gecikme = time.perf_counter() - t - self.adim
            self.en_uzun = max(self.en_uzun, gecikme)

    def basla(self):
        self._gorev = asyncio.create_task(self._kos())
        return self

    async def bitir(self):
        self._dur.set()
        if self._gorev:
            await self._gorev
        return self.en_uzun


@pytest.mark.asyncio
async def test_slow_search_does_not_stall_the_event_loop(monkeypatch):
    """ASIL GÜVENCE: yavaş bir arama loop'u durdurmamalı."""
    GECIKME = 0.5

    class YavasServis:
        def search_courses(self, q, limit=60):
            time.sleep(GECIKME)  # senkron OBS taramasını taklit eder
            return []

    monkeypatch.setattr(main, "get_obs_service", lambda: YavasServis())

    bekci = LoopBekcisi().basla()
    await asyncio.sleep(0.05)  # bekçi ölçmeye başlasın

    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/search-courses?q=akiskanlar")
    assert r.status_code == 200

    durma = await bekci.bitir()
    assert durma < GECIKME / 2, (
        f"event loop {durma*1000:.0f}ms durdu (arama {GECIKME*1000:.0f}ms) — "
        f"senkron çağrı handler içinde çalışıyor"
    )


@pytest.mark.asyncio
async def test_watchdog_actually_detects_a_stall():
    """Bekçinin körlük yapmadığını kanıtlar — yoksa yukarıdaki test
    hiçbir şey ölçmeden hep geçerdi."""
    bekci = LoopBekcisi().basla()
    await asyncio.sleep(0.05)
    time.sleep(0.3)  # loop'u kasten durdur
    await asyncio.sleep(0.05)
    durma = await bekci.bitir()
    assert durma > 0.2, f"bekçi 300ms'lik durmayı göremedi ({durma*1000:.0f}ms)"


@pytest.mark.asyncio
async def test_search_still_returns_results(monkeypatch):
    """Thread'e taşımak sonucu bozmamalı."""
    class Servis:
        def search_courses(self, q, limit=60):
            return [_ders()]

    monkeypatch.setattr(main, "get_obs_service", lambda: Servis())
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/search-courses?q=akiskanlar")
    assert r.status_code == 200
    assert r.json()[0]["crn"] == "12345"


@pytest.mark.asyncio
async def test_search_failure_returns_502_and_service_survives(monkeypatch):
    """OBS patlarsa uç düzgün hata vermeli, servis ayakta kalmalı."""
    class Patlak:
        def search_courses(self, q, limit=60):
            raise RuntimeError("obs yok")

    monkeypatch.setattr(main, "get_obs_service", lambda: Patlak())
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/search-courses?q=akiskanlar")
        assert r.status_code == 502
        # servis hâlâ cevap veriyor
        assert (await c.get("/api/health")).status_code == 200


@pytest.mark.asyncio
async def test_concurrent_searches_are_bounded(monkeypatch):
    """Eşzamanlı arama sayısı sınırlı olmalı.

    Sınırsız olsaydı 40 kullanıcının aynı anda araması thread havuzunu
    tüketir ve asyncio.to_thread kullanan DİĞER işler — konteyner başlatma
    dahil — sıraya girerdi.
    """
    ayni_anda = {"simdi": 0, "en_yuksek": 0}

    class Sayan:
        def search_courses(self, q, limit=60):
            ayni_anda["simdi"] += 1
            ayni_anda["en_yuksek"] = max(ayni_anda["en_yuksek"], ayni_anda["simdi"])
            time.sleep(0.12)
            ayni_anda["simdi"] -= 1
            return []

    monkeypatch.setattr(main, "get_obs_service", lambda: Sayan())
    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        await asyncio.gather(*[
            c.get(f"/api/search-courses?q=sorgu{i}") for i in range(12)
        ])
    assert ayni_anda["en_yuksek"] <= main.SEARCH_CONCURRENCY, ayni_anda


@pytest.mark.asyncio
async def test_reset_does_not_stall_the_event_loop():
    """/api/register/reset motor thread'ini SENKRON bekliyordu.

    `engine_thread.join(timeout=3)` bir async handler içindeydi. İptal
    bayrağı kalibrasyon sırasında (7 saniyelik ağ çağrısı) kontrol
    edilmediği için join tam 3 saniye bloke edebiliyordu — ve reset,
    frontend tarafından 409 durumunda OTOMATİK çağrılıyor. Kayıt anında
    3 saniyelik bir donma; nabızlar cevapsız kalır, devir penceresi kaçabilir.
    """
    import threading
    from engine import RegistrationEngine

    sid = "77777777-7777-4777-8777-777777777777"
    session = main.SessionState(token="t.o.k", ecrn_list=["12345"])
    eng = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    eng._running = True

    dur = threading.Event()

    def yavas_motor():
        dur.wait(1.5)          # iptal bayrağına geç tepki veren motoru taklit eder
        eng._running = False

    th = threading.Thread(target=yavas_motor, daemon=True)
    th.start()
    session.engine = eng
    session.engine_thread = th
    main.sessions[sid] = session

    bekci = LoopBekcisi().basla()
    await asyncio.sleep(0.05)
    try:
        transport = ASGITransport(app=main.app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.post("/api/register/reset", headers={"X-Session-ID": sid})
        assert r.status_code == 200
        durma = await bekci.bitir()
        assert durma < 0.5, f"event loop {durma*1000:.0f}ms durdu — join handler içinde"
    finally:
        dur.set()
        main.sessions.pop(sid, None)
        main.broker.release(sid)


# ══════════════════════════════════════════════════════════════
# Kalıcılık (GCS) çağrıları loop'u bloke etmemeli
# ══════════════════════════════════════════════════════════════
#
# PendingStore senkron `requests` kullanıyor (10 sn zaman aşımı). start,
# cancel, reset ve izolasyon denetleyicisi onu async gövdeden doğrudan
# çağırıyordu. En kötüsü denetleyici: yavaş bir silme aynı turdaki 8
# saniyelik devir penceresini kaçırtabilir. start ise tam kayıt anında geç
# kalanlar tarafından çağrılıyor.

def _yavas(sure=0.4):
    def f(*a, **k):
        time.sleep(sure)
        return True
    return f


def _jwt(saniye_sonra):
    import base64, json
    def b64(o):
        return base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip("=")
    return (b64({"alg": "HS256"}) + "." +
            b64({"exp": int(time.time()) + saniye_sonra}) + ".imza")


@pytest.mark.asyncio
@pytest.mark.parametrize("uc", ["start", "cancel", "reset"])
async def test_disk_writes_do_not_stall_the_event_loop(monkeypatch, uc):
    import datetime, zoneinfo
    from engine import RegistrationEngine

    monkeypatch.setattr(main, "ISOLATION_ENABLED", True)
    monkeypatch.setattr(main.pending_store, "save", _yavas())
    monkeypatch.setattr(main.pending_store, "delete", _yavas())
    monkeypatch.setattr(RegistrationEngine, "run", lambda self: None)

    sid = "88888888-8888-4888-8888-888888888888"
    t = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Istanbul")) + \
        datetime.timedelta(seconds=1800)
    s = main.SessionState(token=_jwt(7200), ecrn_list=["12345"],
                          kayit_saati=t.strftime("%H:%M:%S"))
    if uc == "cancel":
        s.engine = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
        s.engine._running = True
    main.sessions[sid] = s

    bekci = LoopBekcisi().basla()
    await asyncio.sleep(0.05)
    try:
        transport = ASGITransport(app=main.app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.post(f"/api/register/{uc}", headers={"X-Session-ID": sid})
        assert r.status_code == 200, r.text
        durma = await bekci.bitir()
        assert durma < 0.2, f"{uc}: event loop {durma*1000:.0f}ms durdu — GCS çağrısı handler içinde"
    finally:
        s2 = main.sessions.pop(sid, None)
        if s2 and s2.engine:
            s2.engine.cancel()
        main.broker.release(sid)


def test_no_sync_disk_call_inside_any_async_function():
    """Bekçi: main.py'de HİÇBİR async fonksiyon store'u senkron çağırmasın.

    Yukarıdaki test yalnızca üç ucu yokluyor; denetleyici sonsuz döngü ve
    testte sürülemiyor. Bu tarama yeni bir çağrı yerinin de aynı hatayı
    yapmasını yakalar.
    """
    import ast
    import pathlib
    agac = ast.parse(pathlib.Path(main.__file__).read_text(encoding="utf-8"))
    ihlaller = []
    for fn in ast.walk(agac):
        if not isinstance(fn, ast.AsyncFunctionDef):
            continue
        for d in ast.walk(fn):
            if (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                    and isinstance(d.func.value, ast.Name)
                    and d.func.value.id == "pending_store"
                    and d.func.attr in ("save", "delete", "list_pending",
                                        "save_result", "load_result",
                                        "delete_result")):
                ihlaller.append(f"{fn.name}:{d.lineno} pending_store.{d.func.attr}()")
    assert not ihlaller, "senkron GCS çağrısı async gövdede: " + ", ".join(ihlaller)


async def _arka_plani_bitir():
    """Arka plana atılmış disk işlerinin bitmesini bekle."""
    for _ in range(50):
        if not main._arka_plan:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("arka plan disk işleri bitmedi")


@pytest.mark.asyncio
async def test_cancel_right_after_start_cannot_leave_a_record_on_disk(monkeypatch):
    """İptal, kendinden önceki yazmayı GEÇMEMELİ.

    Disk çağrıları thread'e taşınınca başlat→iptal art arda geldiğinde silme
    yazmadan önce bitebilir: diskte iptal edilmiş, token'lı bir kayıt kalır
    ve servis yeniden başlarsa geri yüklenip ATEŞLENİR.
    """
    import datetime, zoneinfo
    from engine import RegistrationEngine

    sira = []

    def yavas_kaydet(sid, kayit):
        time.sleep(0.3)
        sira.append("save")
        return True

    def hizli_sil(sid):
        sira.append("delete")
        return True

    monkeypatch.setattr(main, "ISOLATION_ENABLED", True)
    monkeypatch.setattr(main.pending_store, "save", yavas_kaydet)
    monkeypatch.setattr(main.pending_store, "delete", hizli_sil)
    monkeypatch.setattr(RegistrationEngine, "run", lambda self: None)

    sid = "99999999-9999-4999-8999-999999999999"
    t = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Istanbul")) + \
        datetime.timedelta(seconds=1800)
    main.sessions[sid] = main.SessionState(
        token=_jwt(7200), ecrn_list=["12345"], kayit_saati=t.strftime("%H:%M:%S"))
    try:
        transport = ASGITransport(app=main.app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            h = {"X-Session-ID": sid}
            baslat = asyncio.create_task(c.post("/api/register/start", headers=h))
            await asyncio.sleep(0.1)          # yazma sürerken iptal gelsin
            # Motorun run'ı etkisiz; iptalin 404 dönmemesi için çalışıyor say
            main.sessions[sid].engine._running = True
            r_iptal = await c.post("/api/register/cancel", headers=h)
            r_baslat = await baslat
        assert r_baslat.status_code == 200, r_baslat.text
        assert r_iptal.status_code == 200, r_iptal.text
        assert sira == ["save", "delete"], f"silme yazmayı geçti: {sira}"
    finally:
        s2 = main.sessions.pop(sid, None)
        if s2 and s2.engine:
            s2.engine.cancel()
        main.broker.release(sid)


@pytest.mark.asyncio
async def test_finished_local_registration_is_removed_from_disk(monkeypatch):
    """Kayıt bitince disk kopyası HEMEN silinmeli ("iş biter bitmez SİL").

    Eskiden hedeften 5 dk sonra siliniyordu; arada servis yeniden başlarsa
    geri yükleme (1 saat tolerans) BİTMİŞ kaydı yeniden ateşlerdi.
    """
    from engine import RegistrationEngine

    silinen = []
    monkeypatch.setattr(main.pending_store, "delete",
                        lambda sid: silinen.append(sid) or True)
    sid = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    s = main.SessionState(token="t.o.k", ecrn_list=["12345"])
    s.engine = RegistrationEngine(token="t.o.k", ecrn_list=["12345"])
    s.engine._emit("done", {"results": {}, "cancelled": False, "stood_down": False})
    main.sessions[sid] = s
    try:
        await main.poll_engine_events(sid)
        await _arka_plani_bitir()
        assert silinen == [sid]
    finally:
        main.sessions.pop(sid, None)


@pytest.mark.asyncio
async def test_finished_remote_registration_is_removed_from_disk(monkeypatch):
    silinen = []
    monkeypatch.setattr(main.pending_store, "delete",
                        lambda sid: silinen.append(sid) or True)
    sid = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    bilet = main.broker.register(sid, time.time() + 60)
    try:
        transport = ASGITransport(app=main.app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            r = await c.post("/internal/events", json={
                "session_id": sid, "ticket": bilet,
                "events": [{"type": "done", "data": {"results": {}}}],
            })
        assert r.status_code == 200, r.text
        await _arka_plani_bitir()
        assert silinen == [sid]
    finally:
        main.broker.release(sid)


def test_a_second_registration_is_cleaned_up_too():
    """`_disk_silindi` oturumu hiç bırakmıyordu: aynı kullanıcının İKİNCİ
    kaydının token'lı kopyası hedeften 5 dk sonra değil ~1 saat sonra
    (purge) siliniyordu."""
    main._disk_silindi.add("u:ikinci")
    main._yeni_kayit_disk_durumu("u:ikinci")
    assert "u:ikinci" not in main._disk_silindi
