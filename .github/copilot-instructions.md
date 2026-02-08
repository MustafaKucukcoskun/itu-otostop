# Copilot instructions

> **Not**: Bu dosya GitHub Copilot'a proje hakkında bağlamsal bilgi sağlar. GitHub Copilot kullanımı **GitHub Copilot aboneliğinizdeki kotayı** kullanır, Claude Pro hesabınızdaki kotayı değil. Detaylı bilgi için [COPILOT-QUOTA-FAQ.md](COPILOT-QUOTA-FAQ.md) dökümanına bakınız.

## Project overview

- Single-file Python tool that automates ITU OBS course registration via `https://obs.itu.edu.tr/api/ders-kayit/v21`.
- Main (and only) file: `claudeai2-optimal.py (standalone, not in repo)` - self-contained, auto-installs dependencies.

## Architecture

- `requests` Session with keep-alive + `HTTPAdapter` for connection pooling.
- Auth: JWT `Authorization` + `LoginCookie` in `HEADERS` (must be refreshed before each registration session).
- Constants: `OBS_URL`, `OBS_BASE`, `HEADERS`, `ECRN_LIST`, `SCRN_LIST`, `KAYIT_SAATI`.
- Timing: `sunucu_offset_olc()` measures server clock via HTTP `Date` header transitions (+-RTT/2 accuracy). NTP is used only for comparison logging, NOT for timing.
- Auto-install: `_ensure_package()` runs `pip install -q` for missing packages at startup.

## Key functions

| Function | Purpose |
|---|---|
| `_ensure_package()` | Auto-install missing pip packages |
| `sunucu_offset_olc()` | Measure OBS server clock offset via Date header transitions |
| `_rtt_olc(n)` | Measure n RTT samples, return median |
| `ntp_offset_olc()` | NTP offset (info only, cross-platform: w32tm / ntplib) |
| `prewarm_connection()` | Warm TCP+TLS + API POST route |
| `build_prepared_request()` | Pre-build POST PreparedRequest for zero-overhead first request |
| `check_rate_limit()` | Read rate limit headers from response |
| `kayit_yap()` | Main registration loop with dynamic VAL02 retry |
| `otomatik_kayit()` | Orchestrator: measure - warm - calculate trigger - busy-wait - fire |
| `_saat_to_epoch()` | Convert HH:MM:SS to today's epoch float |

## Timing formula

`tetik = hedef_epoch + server_offset - rtt_tek_yon`

This ensures the request arrives at the server at exactly the target time (e.g., 14:00:00.000).

## Server clock measurement

OBS server is ~2 seconds behind NTP. Using NTP for timing would cause 2s early fire - VAL02.
The Date header transition technique polls HEAD requests rapidly and detects the exact moment
the server's Date header changes seconds, measuring the offset to +-3ms accuracy.

## Conventions

- Inline emoji-based status logging (no structured logging).
- VAL02 retry: burst mode (RTT*0.8) for first 5 attempts, then sustained (RTT*3).
- Successful CRNs removed from list, PreparedRequest rebuilt only when list changes.
- Rate limit: HTTP 429 detection + adaptive backoff up to `RETRY_ARALIK_MAX`.
- Response codes: statusCode 0=success, VAL02=period closed, VAL03=already enrolled, VAL06=full, VAL09=conflict, VAL22=upgrade conflict.

## Workflow

- No tests or build steps.
- Run directly: `python claudeai2-optimal.py (standalone, not in repo)`
- Requires valid JWT + LoginCookie in HEADERS (login to OBS web, copy tokens).
- Run 2-5 minutes before `KAYIT_SAATI` - calibration takes ~30-40 seconds.
