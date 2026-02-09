"""
OBS Ders Kayıt API — FastAPI Backend
Kayıt motorunu kontrol eden REST + WebSocket API.
Session bazlı izolasyon: her browser tab kendi bağımsız state'ine sahiptir.
"""

import asyncio
import json
import os
import time
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware

from models import (
    ConfigRequest, ConfigResponse, CalibrationResult,
    RegistrationState, TokenTestResult, CRNResultItem, CRNStatus,
)
from engine import RegistrationEngine
from obs_course_service import get_obs_service, CourseInfo as OBSCourseInfo


# ── Session-based state ──

@dataclass
class SessionState:
    token: str = ""
    ecrn_list: list[str] = field(default_factory=list)
    scrn_list: list[str] = field(default_factory=list)
    kayit_saati: str = ""
    max_deneme: int = 60
    retry_aralik: float = 3.0
    gecikme_buffer: float = 0.005
    dry_run: bool = False
    engine: Optional[RegistrationEngine] = None
    engine_thread: Optional[threading.Thread] = None
    poll_task: Optional[asyncio.Task] = None
    ws_clients: list = field(default_factory=list)  # list[WebSocket]
    last_active: float = 0.0


sessions: dict[str, SessionState] = {}
MAX_SESSIONS = 100
SESSION_TIMEOUT = 7200  # 2 saat


def _cleanup_sessions():
    """Timeout olan ve engine çalışmayan session'ları temizle."""
    now = time.time()
    expired = [
        sid for sid, s in sessions.items()
        if now - s.last_active > SESSION_TIMEOUT
        and (not s.engine or not s.engine.is_running)
    ]
    for sid in expired:
        s = sessions[sid]
        # Temizlik: çalışan engine varsa iptal et
        if s.engine and s.engine.is_running:
            s.engine.cancel()
        if s.poll_task and not s.poll_task.done():
            s.poll_task.cancel()
        del sessions[sid]


def get_session(session_id: str) -> SessionState:
    """Session ID'ye göre state al veya oluştur."""
    if session_id not in sessions:
        if len(sessions) >= MAX_SESSIONS:
            _cleanup_sessions()
            if len(sessions) >= MAX_SESSIONS:
                raise HTTPException(503, "Maksimum oturum sayısına ulaşıldı")
        sessions[session_id] = SessionState()
    s = sessions[session_id]
    s.last_active = time.time()
    return s


def get_session_id(request: Request) -> str:
    """Request'ten session ID'yi çıkar (header veya query param)."""
    sid = request.headers.get("X-Session-ID", "")
    if not sid:
        sid = request.query_params.get("session_id", "")
    if not sid:
        raise HTTPException(400, "X-Session-ID header gerekli")
    if len(sid) > 128:
        raise HTTPException(400, "Geçersiz session ID")
    return sid


# ── App ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Shutdown: cancel all running engines
    for sid, s in sessions.items():
        if s.engine and s.engine.is_running:
            s.engine.cancel()

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


# ── WebSocket broadcast (session bazlı) ──

async def broadcast(session_id: str, event: dict):
    session = sessions.get(session_id)
    if not session:
        return
    msg = json.dumps(event, ensure_ascii=False)
    disconnected = []
    for ws in session.ws_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        session.ws_clients.remove(ws)


async def poll_engine_events(session_id: str):
    """Engine event kuyruğunu sürekli okuyup WebSocket'e yayınla."""
    session = sessions.get(session_id)
    while session and session.engine and (session.engine.is_running or not session.engine._events.empty()):
        events = session.engine.get_events()
        for event in events:
            await broadcast(session_id, event)
        await asyncio.sleep(0.1)
        session = sessions.get(session_id)  # Session silinmiş olabilir
    # Son eventleri gönder
    session = sessions.get(session_id)
    if session and session.engine:
        events = session.engine.get_events()
        for event in events:
            await broadcast(session_id, event)


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
async def set_config(req: ConfigRequest, request: Request):
    session_id = get_session_id(request)
    session = get_session(session_id)

    # Token sadece gönderildiğinde güncellenir (partial update)
    if req.token is not None and req.token != "":
        session.token = req.token
    session.ecrn_list = req.ecrn_list
    session.scrn_list = req.scrn_list
    session.kayit_saati = req.kayit_saati
    session.max_deneme = req.max_deneme
    session.retry_aralik = req.retry_aralik
    session.gecikme_buffer = req.gecikme_buffer
    session.dry_run = req.dry_run
    return _config_response(session)


@app.get("/api/config", response_model=ConfigResponse)
async def get_config(request: Request):
    session_id = get_session_id(request)
    session = get_session(session_id)
    return _config_response(session)


def _config_response(session: SessionState) -> ConfigResponse:
    preview = ""
    if session.token:
        preview = session.token[:20] + "..." + session.token[-10:]
    return ConfigResponse(
        ecrn_list=session.ecrn_list,
        scrn_list=session.scrn_list,
        kayit_saati=session.kayit_saati,
        max_deneme=session.max_deneme,
        retry_aralik=session.retry_aralik,
        gecikme_buffer=session.gecikme_buffer,
        token_set=bool(session.token),
        token_preview=preview,
        dry_run=session.dry_run,
    )


@app.post("/api/test-token", response_model=TokenTestResult)
async def test_token(request: Request):
    session_id = get_session_id(request)
    session = get_session(session_id)

    if not session.token:
        raise HTTPException(400, "Token ayarlanmamış")
    engine = RegistrationEngine(
        token=session.token,
        ecrn_list=["00000"],
    )
    result = await asyncio.to_thread(engine.test_token)
    return TokenTestResult(**result)


@app.post("/api/calibrate", response_model=CalibrationResult)
async def calibrate(request: Request):
    session_id = get_session_id(request)
    session = get_session(session_id)

    if not session.token:
        raise HTTPException(400, "Token ayarlanmamış")
    engine = RegistrationEngine(
        token=session.token,
        ecrn_list=session.ecrn_list or ["00000"],
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
async def start_registration(request: Request):
    session_id = get_session_id(request)
    session = get_session(session_id)

    if not session.token:
        raise HTTPException(400, "Token ayarlanmamış")
    if not session.ecrn_list:
        raise HTTPException(400, "CRN listesi boş")
    if not session.kayit_saati:
        raise HTTPException(400, "Kayıt saati ayarlanmamış")

    # Engine gerçekten çalışıyor mu kontrol et (thread alive + flag)
    if session.engine and session.engine.is_running:
        # Thread ölmüşse flag sıkışmıştır — zorla temizle
        if session.engine_thread and not session.engine_thread.is_alive():
            session.engine._running = False
            session.engine = None
            session.engine_thread = None
        else:
            raise HTTPException(409, "Kayıt zaten çalışıyor")

    session.engine = RegistrationEngine(
        token=session.token,
        ecrn_list=session.ecrn_list,
        scrn_list=session.scrn_list,
        kayit_saati=session.kayit_saati,
        max_deneme=session.max_deneme,
        retry_aralik=session.retry_aralik,
        gecikme_buffer=session.gecikme_buffer,
        dry_run=session.dry_run,
    )

    # Engine'i ayrı thread'de başlat
    session.engine_thread = threading.Thread(target=session.engine.run, daemon=True)
    session.engine_thread.start()

    # Event polling'i background task olarak başlat
    session.poll_task = asyncio.create_task(poll_engine_events(session_id))
    session.poll_task.add_done_callback(_poll_task_done)

    return {"status": "started", "message": "Kayıt başlatıldı"}


@app.post("/api/register/cancel")
async def cancel_registration(request: Request):
    session_id = get_session_id(request)
    session = get_session(session_id)

    if not session.engine or not session.engine.is_running:
        raise HTTPException(404, "Çalışan kayıt yok")
    session.engine.cancel()
    return {"status": "cancelled"}


@app.post("/api/register/reset")
async def reset_registration(request: Request):
    """Engine state'i zorla sıfırla — sıkışmış durumlarda kullanılır."""
    session_id = get_session_id(request)
    session = get_session(session_id)

    if session.engine:
        if session.engine.is_running and session.engine_thread and session.engine_thread.is_alive():
            session.engine.cancel()
            # Thread'in bitmesi için kısa süre bekle
            session.engine_thread.join(timeout=3)
        session.engine._running = False
        session.engine = None
    session.engine_thread = None
    if session.poll_task and not session.poll_task.done():
        session.poll_task.cancel()
    session.poll_task = None
    return {"status": "reset", "message": "Engine state sıfırlandı"}


@app.get("/api/register/status", response_model=RegistrationState)
async def registration_status(request: Request):
    session_id = get_session_id(request)
    session = get_session(session_id)

    if not session.engine:
        return RegistrationState()

    crn_results = []
    for crn, info in session.engine.crn_results.items():
        try:
            status = CRNStatus(info["status"])
        except ValueError:
            status = CRNStatus.PENDING
        crn_results.append(CRNResultItem(crn=crn, status=status, message=info.get("message", "")))

    cal = None
    if session.engine.calibration:
        c = session.engine.calibration
        cal = CalibrationResult(
            server_offset_ms=c.server_offset * 1000,
            rtt_one_way_ms=c.rtt_one_way * 1000,
            rtt_full_ms=c.rtt_one_way * 2000,
            ntp_offset_ms=c.ntp_offset * 1000,
            server_ntp_diff_ms=(c.server_offset - c.ntp_offset) * 1000,
            accuracy_ms=c.rtt_one_way * 1000,
        )

    remaining = None
    if session.engine.trigger_time:
        remaining = max(0, session.engine.trigger_time - time.time())

    return RegistrationState(
        phase=session.engine.phase,
        running=session.engine.is_running,
        current_attempt=session.engine.current_attempt,
        max_attempts=session.max_deneme,
        crn_results=crn_results,
        calibration=cal,
        countdown_seconds=remaining,
        trigger_time=session.engine.trigger_time,
    )


# ── OBS Ders Programı Proxy (session-agnostic) ──

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
async def websocket_endpoint(ws: WebSocket, session_id: str = Query(...)):
    await ws.accept()
    session = get_session(session_id)
    session.ws_clients.append(ws)
    try:
        while True:
            # Ping/pong veya client mesajlarını oku
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        session = sessions.get(session_id)
        if session and ws in session.ws_clients:
            session.ws_clients.remove(ws)


# ── Run ──

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
