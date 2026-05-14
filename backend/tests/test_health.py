from app.api.routes import health


def test_overall_status_ok() -> None:
    assert health._overall_status([{"status": "ok"}, {"status": "ok"}]) == "ok"


def test_overall_status_degraded() -> None:
    assert health._overall_status([{"status": "ok"}, {"status": "degraded"}]) == "degraded"


def test_overall_status_error() -> None:
    assert health._overall_status([{"status": "ok"}, {"status": "error"}]) == "error"


def test_dependency_health_aggregates_checks(monkeypatch) -> None:
    monkeypatch.setattr(health, "_check_postgres", lambda: {"status": "ok", "detail": "reachable"})
    monkeypatch.setattr(health, "_check_redis", lambda: {"status": "ok", "detail": "reachable"})
    monkeypatch.setattr(
        health,
        "_check_bootstrap_tables",
        lambda: {"status": "degraded", "detail": "missing tables: freshness_slos"},
    )

    payload = health.dependency_health()

    assert payload["status"] == "degraded"
    assert payload["dependencies"]["postgres"]["status"] == "ok"
    assert payload["dependencies"]["redis"]["status"] == "ok"
    assert payload["dependencies"]["bootstrap_tables"]["status"] == "degraded"
    assert "checked_at" in payload
