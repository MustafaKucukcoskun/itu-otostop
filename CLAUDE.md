# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ITU OBS course registration automation tool. Full-stack app (FastAPI + Next.js) that fires HTTP requests to `obs.itu.edu.tr/api/ders-kayit/v21` with millisecond timing precision. The user provides a JWT Bearer token from OBS, configures CRNs to add/drop, and the system calibrates against the server clock, then fires at exactly the right moment.

## Commands

### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py                    # or: uvicorn main:app --reload
# → http://localhost:8000
```

### Frontend
```bash
cd frontend
bun install                       # or: npm install
bun run dev                       # or: npm run dev
# → http://localhost:3000
```

### Lint (Frontend)
```bash
cd frontend
bun run lint                      # next lint
```

### Build (Frontend)
```bash
cd frontend
bun run build
```

No test suite exists. Use dry-run mode (`dry_run: true` in settings) to test timing without actual registration.

## Architecture

**Backend** (Python, FastAPI):
- `main.py` — REST endpoints + WebSocket `/ws` + global `AppState` singleton
- `engine.py` — Registration engine: calibration, busy-wait countdown, retry loop. Runs in a daemon thread, communicates via event queue → WebSocket broadcast
- `models.py` — Pydantic v2 models (ConfigRequest, RegistrationState, CalibrationResult, WSEvent, CRNStatus enum)
- `obs_course_service.py` — OBS public API proxy with LRU cache + TTL. Parses HTML course tables (BeautifulSoup). Searches popular departments first for fast CRN lookups

**Frontend** (Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui):
- `src/components/dashboard.tsx` — Main orchestrator (~900 lines). All state lives here (no Redux/Zustand). Auto-saves config to backend (500ms debounce) + Supabase cloud
- `src/hooks/use-websocket.ts` — WebSocket hook with auto-reconnect, ping/pong latency, event dispatching (log, state, countdown, crn_update, calibration, done)
- `src/hooks/use-notification.ts` — Browser notifications + sound effects on completion
- `src/lib/api.ts` — Typed fetch wrapper for all backend endpoints
- `src/lib/config-service.ts`, `preset-service.ts`, `supabase.ts` — Supabase RPC for cloud config/presets (Clerk user-gated)
- `src/app/` — App Router with Clerk auth (sign-in/sign-up catch-all routes)
- `frontend/sql/` — Supabase table schemas + RPC function definitions

**Communication**: REST for config/actions, WebSocket for real-time log streaming + state updates + calibration data + countdown.

## Critical Domain Knowledge

**Timing formula**: `tetik = hedef_epoch + server_offset - rtt_tek_yon + buffer`
- OBS server clock is ~2 seconds behind NTP. Using NTP would cause VAL02 (period not open yet).
- The Date header transition technique measures the exact server clock offset to ±3ms.
- Final 50ms uses tight busy-wait loop (`perf_counter`, no `sleep`) for microsecond precision.
- Windows: `timeBeginPeriod(1)` reduces timer resolution from ~15.6ms to 1ms; process/thread priority boosted to HIGH.

**Calibration strategy**: Best-sample-pool — always uses the measurement with lowest RTT (most reliable). Token-based history (max 20 samples per token, keyed by hash). Continuous recalibration every 30s during wait phase + final full calibration 35-45s before target.

**3-second debounce**: OBS silently drops requests from the same session within <3 seconds (VAL16). Retry interval must be ≥3s.

**OBS response codes**: statusCode 0=success, VAL02=period closed, VAL03=already enrolled, VAL06=full, VAL09=conflict, VAL16=debounce, VAL22=upgrade conflict.

**Timezone**: Must use `ZoneInfo("Europe/Istanbul")` for target time conversion. Previous timezone bug caused wrong countdown values.

## Key Patterns

- **Adding a new endpoint**: Edit `backend/main.py` + add typed function in `frontend/src/lib/api.ts`
- **Adding a WebSocket event**: Emit in `backend/engine.py` → handle in `frontend/src/hooks/use-websocket.ts`
- **Adding a UI component**: Create in `frontend/src/components/` → import in `dashboard.tsx`
- **Adding Supabase RPC**: SQL in `frontend/sql/` → service function in `frontend/src/lib/*-service.ts`
- **Engine phases**: `idle` → `token_check` → `calibrating` → `waiting` → `registering` → `done`
- **409 auto-reset**: Frontend detects stuck engine state (409 from `/register/start`), calls `/register/reset`, retries automatically
- **Token security**: Never persisted to disk or cloud. Only held in-memory during session. Cloud config excludes token field.

## Environment Variables

Frontend requires `NEXT_PUBLIC_API_URL` (default: `http://localhost:8000`), plus Clerk keys (`NEXT_PUBLIC_CLERK_*`) and Supabase keys in `.env.local`.

## Language

User-facing text, variable names in backend (e.g., `sunucu_offset_olc`, `kayit_yap`, `tetik`), and log messages are in Turkish.
