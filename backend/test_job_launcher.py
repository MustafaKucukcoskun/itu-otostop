"""İzole konteyner başlatma isteğinin gövdesi — ağa çıkmayan testler."""

import pytest

from job_launcher import build_run_request, JobLauncherConfig


@pytest.fixture
def cfg():
    return JobLauncherConfig(
        project="itu-otostop-2026",
        region="europe-west3",
        job_name="itu-otostop-kayit",
        control_url="https://api.example.run.app",
    )


def test_endpoint_targets_correct_job(cfg):
    url, _ = build_run_request(cfg, "sess-1", "bilet-xyz", task_timeout=1800)
    assert url == (
        "https://run.googleapis.com/v2/projects/itu-otostop-2026"
        "/locations/europe-west3/jobs/itu-otostop-kayit:run"
    )


def test_single_task_per_registration(cfg):
    """Bir kayıt = bir konteyner; fazlası çift ateşleme riski demek."""
    _, body = build_run_request(cfg, "sess-1", "bilet-xyz", task_timeout=1800)
    assert body["overrides"]["taskCount"] == 1


def test_timeout_uses_api_duration_format(cfg):
    _, body = build_run_request(cfg, "sess-1", "bilet-xyz", task_timeout=1800)
    assert body["overrides"]["timeout"] == "1800s"


def _env(body):
    return {
        e["name"]: e["value"]
        for e in body["overrides"]["containerOverrides"][0]["env"]
    }


def test_container_receives_identity_and_ticket(cfg):
    _, body = build_run_request(cfg, "sess-1", "bilet-xyz", task_timeout=1800)
    env = _env(body)
    assert env["OTOSTOP_SESSION_ID"] == "sess-1"
    assert env["OTOSTOP_TICKET"] == "bilet-xyz"


def test_container_knows_where_to_call_back(cfg):
    _, body = build_run_request(cfg, "sess-1", "bilet-xyz", task_timeout=1800)
    assert _env(body)["OTOSTOP_CONTROL_URL"] == "https://api.example.run.app"


def test_obs_token_is_never_placed_in_env(cfg):
    """OBS token'ı env'e konsa Cloud Run çalıştırma kaydında günlerce durur.

    Token yerine bilet gönderilir; konteyner token'ı HTTPS üzerinden çeker ve
    yalnızca bellekte tutar (CLAUDE.md: token asla diske/buluta yazılmaz).
    """
    _, body = build_run_request(cfg, "sess-1", "bilet-xyz", task_timeout=1800)
    blob = str(body).lower()
    assert "token" not in blob or "OTOSTOP_TICKET" in str(body)
    assert all(k != "OTOSTOP_TOKEN" for k in _env(body))
