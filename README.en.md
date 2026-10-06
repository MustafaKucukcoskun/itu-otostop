# İTÜ Otostop

**Course-registration automation for Istanbul Technical University's student information system (OBS).** You enter your CRNs and the registration time. The system calibrates its clock, waits, and sends the registration request within milliseconds of the window opening.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE) &nbsp;🇹🇷 [Türkçe README](README.md)

<!-- TODO: add a screenshot or a short GIF of the dashboard, e.g. docs/screenshot.png -->

**Live:** [itu-otostop.vercel.app](https://itu-otostop.vercel.app) (sign-in required; registering needs your own OBS session token)

> Built for educational purposes. It calls the same API as the OBS web interface, using the student's own session token. It never asks for the ITU password.

## What it does

- Registers up to 12 CRNs in one request, and can drop and add courses in the same run.
- Calibrates the local clock against NTP, measures round-trip time to OBS, and fires at `target + clock offset − one-way latency + safety buffer`.
- Retries with a backoff that respects OBS's 3-second debounce (`VAL02`, `VAL16`).
- Streams live logs, the countdown and per-CRN status to the browser over WebSocket.
- Includes course search with prerequisite info, a weekly schedule builder and presets synced to Supabase.
- Refuses to start if the OBS token will expire before the registration time.

## Architecture

```
┌──────────────────────┐   REST + WebSocket   ┌──────────────────────────┐
│ Next.js 16 · React 19│◄────────────────────►│ FastAPI (Cloud Run)      │
│ Clerk auth · Vercel  │                      │ engine · broker · search │
└──────────────────────┘                      └────────────┬─────────────┘
                                                           │ one Cloud Run Job
                                                           │ per registration
                                                           ▼
                                              ┌──────────────────────────┐
                                              │ isolated runner container│
                                              └────────────┬─────────────┘
                                                           │ HTTPS POST
                                                           ▼
                                                   OBS API (obs.itu.edu.tr)
```

## Run locally

Requirements: Python 3.11+, Node.js 18+ or [Bun](https://bun.sh).

```bash
# backend
cd backend
pip install -r requirements.txt
python main.py                 # http://localhost:8000, API docs at /docs

# frontend (second terminal)
cd frontend
cp .env.example .env.local     # then add the Clerk and Supabase keys below
bun install && bun run dev     # http://localhost:3000
```

`npm run dev` in the repository root starts both processes with one command (`scripts/dev.mjs`).

| Variable | File | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` | Backend URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `frontend/.env.local` | Clerk public key |
| `CLERK_SECRET_KEY` | `frontend/.env.local` | Clerk secret key |
| `NEXT_PUBLIC_SUPABASE_URL` | `frontend/.env.local` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `frontend/.env.local` | Supabase anon key |

## Tests

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

402 tests cover the engine (calibration, timing, retry and backoff, drop-and-add), the container hand-off, auth, persistence, token expiry and rate limiting. For the frontend, `bun run lint` and `bun run build` must pass.

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS v4, shadcn/ui, Motion |
| Backend | FastAPI, Uvicorn, Pydantic v2, Requests, WebSocket |
| Auth & data | Clerk (RS256/JWKS verified on the backend), Supabase (PostgreSQL + RPC) |
| Infrastructure | Google Cloud Run (service + per-registration jobs), Vercel |

## Design decisions

- **Build the request before the trigger.** Profiling showed that each concurrent user added about 1.4 ms of delay because requests were built after the trigger fired. Building and warming them beforehand cut the worst-case skew at 15 users from 30.4 ms to 1.8 ms.
- **One container per registration.** With many users in one process, Python's GIL queues the busy-wait threads (47 ms worst case at 100 users). Each registration now gets its own Cloud Run Job container. The container takes over only after it has calibrated and proved it is ready. If it is late or fails, the in-process engine fires as before, and a single broker guarantees exactly one sender. In a load test, 40 users started 5 minutes before the target and all 40 containers took over in time.
- **The OBS token never goes into job config.** Cloud Run keeps job environment variables in execution records for days, so the container fetches its config over HTTPS with a single-use ticket and keeps it in memory only.
- **The safety buffer comes from measurements.** `buffer = N × √(σ_ntp² + σ_rtt² + σ_obs² + σ_asym²)`, recomputed from fresh samples rather than a fixed constant.
- **Check a method before trusting it.** Estimating the OBS clock from HTTP `Date` header transitions looked promising but turned out to be invalid, because the header is generated from a cached clock. The probe stays in `calibration/` to document why.

## Project structure

```
backend/
  main.py                 REST + WebSocket API, isolation supervisor
  engine.py               registration engine: calibration, timing, retry
  isolation.py            ownership hand-off between engine and container
  job_launcher.py         starts one Cloud Run Job per registration
  isolated_runner.py      entry point of the isolated container
  obs_course_service.py   course search proxy with LRU cache
  auth.py · persistence.py · token_expiry.py · models.py
  test_*.py               pytest suite
frontend/
  src/app/                App Router pages (dashboard, /schedule, sign-in)
  src/components/         dashboard, CRN manager, countdown, live logs, ...
  src/hooks/ · src/lib/   WebSocket client, typed API client, Supabase services
  sql/                    Supabase tables and RPC functions
calibration/              clock and RTT measurement tools
```

## License

[Apache License 2.0](LICENSE)
