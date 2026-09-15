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
