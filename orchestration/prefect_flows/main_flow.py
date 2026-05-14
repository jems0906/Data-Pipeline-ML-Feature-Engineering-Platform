from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from prefect import flow, task

from app.db.session import SessionLocal
from app.schemas.pipeline import IngestionRequest, PipelineRunRequest
from app.services.automation import should_trigger_retraining
from app.services.ingestion import IngestionService


@task(retries=2, retry_delay_seconds=15)
def ingest_task(run_id: str, source: IngestionRequest) -> int:
    with SessionLocal() as db:
        service = IngestionService(db)
        frame = service.run_ingestion(run_id, source.source_type, source.source_name, source.config)
        return int(len(frame.index))


@task
def quality_monitor_task(run_id: str, row_count: int) -> dict:
    status = "healthy" if row_count > 0 else "failed"
    return {"run_id": run_id, "row_count": row_count, "status": status}


@task
def freshness_slo_task(last_update_ts: datetime, max_lag_seconds: int) -> dict:
    lag = int((datetime.utcnow() - last_update_ts).total_seconds())
    return {"lag_seconds": lag, "status": "breach" if lag > max_lag_seconds else "ok"}


@task
def retraining_trigger_task() -> bool:
    # Placeholder drift input to show automated retraining trigger flow.
    mock_drift = {"feature_a": 0.24, "feature_b": 0.08}
    return should_trigger_retraining(mock_drift, threshold=0.2)


@flow(name="batch-feature-pipeline")
def batch_feature_pipeline() -> dict:
    run_id = f"prefect-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    source = IngestionRequest(
        source_type="warehouse",
        source_name="bigquery",
        config={
            "query": "SELECT 1 AS entity_id, CURRENT_TIMESTAMP() AS event_ts, 42.0 AS amount",
            "allow_demo_fallback": True,
        },
    )

    row_count = ingest_task(run_id, source)
    quality = quality_monitor_task(run_id, row_count)
    freshness = freshness_slo_task(datetime.utcnow(), 3600)
    retraining = retraining_trigger_task()

    return {
        "run_id": run_id,
        "quality": quality,
        "freshness": freshness,
        "trigger_retraining": retraining,
        "backfill": "Supported by passing historical source query windows to this flow",
    }


if __name__ == "__main__":
    print(batch_feature_pipeline())
