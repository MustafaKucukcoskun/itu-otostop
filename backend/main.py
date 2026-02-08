"""
OBS Ders Kayıt API — FastAPI Backend
Kayıt motorunu kontrol eden REST + WebSocket API.
"""

import asyncio
import json
import os
import time
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import (
    ConfigRequest, ConfigResponse, CalibrationResult,
    RegistrationState, TokenTestResult, CRNResultItem, CRNStatus,
)
from engine import RegistrationEngine
from obs_course_service import get_obs_service, CourseInfo as OBSCourseInfo


# ── Global state ──

class AppState:
    def __init__(self):
        self.token: str = ""
        self.ecrn_list: list[str] = []
        self.scrn_list: list[str] = []
        self.kayit_saati: str = ""
        self.max_deneme: int = 60
        self.retry_aralik: float = 3.0
        self.gecikme_buffer: float = 0.005
        self.dry_run: bool = False
        self.engine: Optional[RegistrationEngine] = None
        self.engine_thread: Optional[threading.Thread] = None
        self.poll_task: Optional[asyncio.Task] = None
        self.ws_clients: list[WebSocket] = []

state = AppState()


# ── App ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Shutdown: cancel any running engine
    if state.engine and state.engine.is_running:
        state.engine.cancel()

app = FastAPI(
    title="İTÜ Otostop API",
    description="İTÜ OBS otomatik ders kayıt sistemi - Otostop",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        *[o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()],
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── WebSocket broadcast ──

async def broadcast(event: dict):
    msg = json.dumps(event, ensure_ascii=False)
    disconnected = []
    for ws in state.ws_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        state.ws_clients.remove(ws)


async def poll_engine_events():
    """Engine event kuyruğunu sürekli okuyup WebSocket'e yayınla."""
    while state.engine and (state.engine.is_running or not state.engine._events.empty()):
        events = state.engine.get_events()
        for event in events:
            await broadcast(event)
        await asyncio.sleep(0.1)
    # Son eventleri gönder
    if state.engine:
        events = state.engine.get_events()
        for event in events:
            await broadcast(event)


def _poll_task_done(task: asyncio.Task):
    """Poll task bittiğinde hata varsa logla."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        import traceback
        traceback.print_exception(type(exc), exc, exc.__traceback__)


# ── REST Endpoints ──

@app.get("/api/health")
async def health():
    return {"status": "ok", "time": time.time()}


@app.post("/api/config", response_model=ConfigResponse)
async def set_config(req: ConfigRequest):
    # Token sadece gönderildiğinde güncellenir (partial update)
    if req.token is not None and req.token != "":
        state.token = req.token
    state.ecrn_list = req.ecrn_list
    state.scrn_list = req.scrn_list
    state.kayit_saati = req.kayit_saati
    state.max_deneme = req.max_deneme
    state.retry_aralik = req.retry_aralik
    state.gecikme_buffer = req.gecikme_buffer
    state.dry_run = req.dry_run
    return _config_response()


@app.get("/api/config", response_model=ConfigResponse)
async def get_config():
    return _config_response()


def _config_response() -> ConfigResponse:
    preview = ""
    if state.token:
        preview = state.token[:20] + "..." + state.token[-10:]
    return ConfigResponse(
        ecrn_list=state.ecrn_list,
        scrn_list=state.scrn_list,
        kayit_saati=state.kayit_saati,
        max_deneme=state.max_deneme,
        retry_aralik=state.retry_aralik,
        gecikme_buffer=state.gecikme_buffer,
        token_set=bool(state.token),
        token_preview=preview,
        dry_run=state.dry_run,
    )


@app.post("/api/test-token", response_model=TokenTestResult)
async def test_token():
    if not state.token:
        raise HTTPException(400, "Token ayarlanmamış")
    engine = RegistrationEngine(
        token=state.token,
        ecrn_list=["00000"],
    )
    result = await asyncio.to_thread(engine.test_token)
    return TokenTestResult(**result)


@app.post("/api/calibrate", response_model=CalibrationResult)
async def calibrate():
    if not state.token:
        raise HTTPException(400, "Token ayarlanmamış")
    engine = RegistrationEngine(
        token=state.token,
        ecrn_list=state.ecrn_list or ["00000"],
    )
    cal = await asyncio.to_thread(engine.calibrate)
    return CalibrationResult(
        server_offset_ms=cal.server_offset * 1000,
        rtt_one_way_ms=cal.rtt_one_way * 1000,
        rtt_full_ms=cal.rtt_one_way * 2000,
        ntp_offset_ms=cal.ntp_offset * 1000,
        server_ntp_diff_ms=(cal.server_offset - cal.ntp_offset) * 1000,
        accuracy_ms=cal.rtt_one_way * 1000,
        source="manual",
    )


@app.post("/api/register/start")
async def start_registration():
    if not state.token:
        raise HTTPException(400, "Token ayarlanmamış")
    if not state.ecrn_list:
        raise HTTPException(400, "CRN listesi boş")
    if not state.kayit_saati:
        raise HTTPException(400, "Kayıt saati ayarlanmamış")

    # Engine gerçekten çalışıyor mu kontrol et (thread alive + flag)
    if state.engine and state.engine.is_running:
        # Thread ölmüşse flag sıkışmıştır — zorla temizle
        if state.engine_thread and not state.engine_thread.is_alive():
            state.engine._running = False
            state.engine = None
            state.engine_thread = None
        else:
            raise HTTPException(409, "Kayıt zaten çalışıyor")

    state.engine = RegistrationEngine(
        token=state.token,
        ecrn_list=state.ecrn_list,
        scrn_list=state.scrn_list,
        kayit_saati=state.kayit_saati,
        max_deneme=state.max_deneme,
        retry_aralik=state.retry_aralik,
        gecikme_buffer=state.gecikme_buffer,
        dry_run=state.dry_run,
    )

    # Engine'i ayrı thread'de başlat
    state.engine_thread = threading.Thread(target=state.engine.run, daemon=True)
    state.engine_thread.start()

    # Event polling'i background task olarak başlat
    state.poll_task = asyncio.create_task(poll_engine_events())
    state.poll_task.add_done_callback(_poll_task_done)

    return {"status": "started", "message": "Kayıt başlatıldı"}


@app.post("/api/register/cancel")
async def cancel_registration():
    if not state.engine or not state.engine.is_running:
        raise HTTPException(404, "Çalışan kayıt yok")
    state.engine.cancel()
    return {"status": "cancelled"}


@app.post("/api/register/reset")
async def reset_registration():
    """Engine state'i zorla sıfırla — sıkışmış durumlarda kullanılır."""
    if state.engine:
        if state.engine.is_running and state.engine_thread and state.engine_thread.is_alive():
            state.engine.cancel()
            # Thread'in bitmesi için kısa süre bekle
            state.engine_thread.join(timeout=3)
        state.engine._running = False
        state.engine = None
    state.engine_thread = None
    if state.poll_task and not state.poll_task.done():
        state.poll_task.cancel()
    state.poll_task = None
    return {"status": "reset", "message": "Engine state sıfırlandı"}


@app.get("/api/register/status", response_model=RegistrationState)
async def registration_status():
    if not state.engine:
        return RegistrationState()

    crn_results = []
    for crn, info in state.engine.crn_results.items():
        try:
            status = CRNStatus(info["status"])
        except ValueError:
            status = CRNStatus.PENDING
        crn_results.append(CRNResultItem(crn=crn, status=status, message=info.get("message", "")))

    cal = None
    if state.engine.calibration:
        c = state.engine.calibration
        cal = CalibrationResult(
            server_offset_ms=c.server_offset * 1000,
            rtt_one_way_ms=c.rtt_one_way * 1000,
            rtt_full_ms=c.rtt_one_way * 2000,
            ntp_offset_ms=c.ntp_offset * 1000,
            server_ntp_diff_ms=(c.server_offset - c.ntp_offset) * 1000,
            accuracy_ms=c.rtt_one_way * 1000,
        )

    remaining = None
    if state.engine.trigger_time:
        remaining = max(0, state.engine.trigger_time - time.time())

    return RegistrationState(
        phase=state.engine.phase,
        running=state.engine.is_running,
        current_attempt=state.engine.current_attempt,
        max_attempts=state.max_deneme,
        crn_results=crn_results,
        calibration=cal,
        countdown_seconds=remaining,
        trigger_time=state.engine.trigger_time,
    )


# ── OBS Ders Programı Proxy ──

def _course_to_dict(c: OBSCourseInfo) -> dict:
    return {
        "crn": c.crn,
        "course_code": c.course_code,
        "course_name": c.course_name,
        "instructor": c.instructor,
        "teaching_method": c.teaching_method,
        "capacity": c.capacity,
        "enrolled": c.enrolled,
        "programmes": c.programmes,
        "sessions": [
            {
                "day": s.day,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "room": s.room,
                "building": s.building,
            }
            for s in c.sessions
        ],
    }


@app.get("/api/departments")
async def get_departments():
    service = get_obs_service()
    return await asyncio.to_thread(service.get_departments)


@app.get("/api/courses/{brans_kodu_id}")
async def get_courses(brans_kodu_id: int):
    service = get_obs_service()
    courses = await asyncio.to_thread(service.get_courses, brans_kodu_id)
    return [_course_to_dict(c) for c in courses]


@app.get("/api/crn-lookup/{crn}")
async def lookup_crn(crn: str):
    service = get_obs_service()
    result = await asyncio.to_thread(service.lookup_crn, crn)
    if result is None:
        raise HTTPException(404, f"CRN {crn} bulunamadı")
    return _course_to_dict(result)


@app.post("/api/crn-lookup")
async def lookup_crns_batch(body: dict):
    crns = body.get("crns", [])
    if not crns:
        raise HTTPException(400, "CRN listesi boş")
    service = get_obs_service()
    results = await asyncio.to_thread(service.lookup_crns, crns)
    return {crn: _course_to_dict(info) if info else None for crn, info in results.items()}


# ── WebSocket ──

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state.ws_clients.append(ws)
    try:
        while True:
            # Ping/pong veya client mesajlarını oku
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        if ws in state.ws_clients:
            state.ws_clients.remove(ws)


# ── Run ──

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
