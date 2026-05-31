"""Smoke test for the app skeleton. The eval + safety red-team suites (docs/DESIGN.md
§6.6) live alongside these and gate CI in Phase 0+."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
