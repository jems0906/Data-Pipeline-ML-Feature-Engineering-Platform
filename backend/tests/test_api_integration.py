from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import features as features_routes
from app.api.routes import pipelines as pipelines_routes
from app.db.session import get_db


class DummyDb:
    def execute(self, _stmt, _params=None):
        sql = str(_stmt)
        if "FROM quality_alerts" in sql and "SELECT id" in sql:
            class Result:
                def mappings(self):
                    return [
                        {
                            "id": 1,
                            "run_id": "run-1",
                            "alert_type": "missing_rate",
                            "severity": "medium",
                            "details": {"column": "amount", "rate": 0.3},
                            "created_at": None,
                        }
                    ]

            return Result()

        if "FROM quality_alerts" in sql:
            class Result:
                def mappings(self):
                    return [
                        {
                            "run_id": "run-1",
                            "alert_type": "missing_rate",
                            "severity": "medium",
                            "details": {"column": "amount", "rate": 0.3},
                            "created_at": None,
                        }
                    ]

            return Result()

        class EmptyResult:
            def mappings(self):
                return []

        return EmptyResult()

    def commit(self):
        return None

    def add(self, _row):
        return None

    def refresh(self, _row):
        return None


class FakeFeatureStore:
    records: list[dict] = []

    def __init__(self, _db):
        pass

    def list_feature_usage(self, model_search="", feature_search=""):
        _ = model_search
        _ = feature_search
        return list(self.records)

    def record_feature_usage(self, model_name, feature_name, usage, source_run_id=None):
        row = {
            "model_name": model_name,
            "feature_name": feature_name,
            "usage": usage,
            "source_run_id": source_run_id,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        self.records.append(row)

        class Record:
            pass

        rec = Record()
        rec.model_name = model_name
        rec.feature_name = feature_name
        rec.usage = usage
        rec.source_run_id = source_run_id

        class Created:
            def isoformat(self):
                return "2026-01-01T00:00:00+00:00"

        rec.created_at = Created()
        return rec


class FakeIngestionService:
    def __init__(self, _db):
        pass

    def ingest_realtime_event(self, run_id, source_name, event):
        _ = source_name
        _ = event
        return f"../data/raw/{run_id}.jsonl"

    def publish_realtime_event(self, stream_name, event):
        _ = stream_name
        _ = event
        return "1778-0"


class FakeTrainingJob:
    id = 99
    source_run_id = "run-train-1"
    status = "scheduled"
    trigger_reason = "drift_threshold_exceeded"
    artifact_path = "../data/processed/run-train-1-training-job.json"

    class Created:
        def isoformat(self):
            return "2026-01-01T00:00:00+00:00"

    created_at = Created()


def _override_get_db() -> Iterator[DummyDb]:
    yield DummyDb()


def _build_client(monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(features_routes.router, prefix="/api/v1")
    app.include_router(pipelines_routes.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _override_get_db

    monkeypatch.setattr(features_routes, "FeatureStoreService", FakeFeatureStore)
    monkeypatch.setattr(pipelines_routes, "IngestionService", FakeIngestionService)
    monkeypatch.setattr(pipelines_routes, "track_lineage", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        pipelines_routes,
        "list_lineage_events",
        lambda db, run_id="", limit=100: [
            {
                "run_id": run_id or "run-1",
                "event_type": "pipeline_complete",
                "payload": {"rows": 3},
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(
        pipelines_routes,
        "list_training_jobs",
        lambda db, limit=50: [
            {
                "id": 99,
                "source_run_id": "run-train-1",
                "status": "scheduled",
                "trigger_reason": "drift_threshold_exceeded",
                "artifact_path": "../data/processed/run-train-1-training-job.json",
                "payload": {"drift_scores": {"feature_a": 0.4}},
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ],
    )
    monkeypatch.setattr(pipelines_routes, "schedule_training_job", lambda *args, **kwargs: FakeTrainingJob())
    monkeypatch.setattr(
        pipelines_routes,
        "_execute_pipeline",
        lambda payload, db: {
            "run_id": payload.run_id,
            "quality": {"row_count": 2},
        },
    )

    return TestClient(app)


def test_feature_usage_create_and_list(monkeypatch) -> None:
    FakeFeatureStore.records = []
    client = _build_client(monkeypatch)

    create_res = client.post(
        "/api/v1/features/usage",
        json={"model_name": "fraud-v1", "feature_name": "amount", "usage": "inference"},
    )
    list_res = client.get("/api/v1/features/usage")

    assert create_res.status_code == 200
    assert list_res.status_code == 200
    assert list_res.json()[0]["feature_name"] == "amount"


def test_realtime_event_endpoint(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    response = client.post(
        "/api/v1/pipelines/realtime-event",
        json={
            "run_id": "rt-1",
            "source_name": "webhook",
            "stream_name": "feature-events",
            "event": {"entity_id": "u1", "amount": 10.0},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["stream_id"] == "1778-0"


def test_alerts_endpoint(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    response = client.get("/api/v1/pipelines/alerts?limit=5")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["alert_type"] == "missing_rate"


def test_alerts_dispatch_endpoint(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    response = client.post("/api/v1/pipelines/alerts/dispatch?limit=5")

    assert response.status_code == 200
    body = response.json()
    assert body["alerts_considered"] == 1
    assert body["notifications_sent"] + body["notifications_simulated"] >= 1


def test_quality_report_includes_distributions(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    response = client.post("/api/v1/pipelines/quality-report")

    assert response.status_code == 200
    body = response.json()
    assert "distributions" in body
    assert "feature_a" in body["distributions"]


def test_lineage_endpoint(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    response = client.get("/api/v1/pipelines/lineage?run_id=run-abc")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["run_id"] == "run-abc"
    assert body[0]["event_type"] == "pipeline_complete"


def test_training_jobs_trigger_endpoint(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    response = client.post(
        "/api/v1/pipelines/training-jobs/trigger",
        json={"source_run_id": "run-train-1", "drift_scores": {"feature_a": 0.4}, "force": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scheduled"] is True
    assert body["training_job"]["id"] == 99


def test_backfill_endpoint(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    response = client.post(
        "/api/v1/pipelines/backfill",
        json={
            "run_id_prefix": "bf",
            "start_date": "2026-01-01T00:00:00Z",
            "end_date": "2026-01-02T00:00:00Z",
            "window_days": 1,
            "source": {
                "source_type": "warehouse",
                "source_name": "bigquery",
                "config": {"query": "SELECT 1", "allow_demo_fallback": True},
            },
            "transformations": {},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_count"] >= 1
    assert body["runs"][0]["run_id"].startswith("bf-")
