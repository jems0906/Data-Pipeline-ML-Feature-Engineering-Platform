from __future__ import annotations

from pathlib import Path

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.feature_store import TrainingJob


def schedule_training_job(
    db: Session,
    source_run_id: str,
    trigger_reason: str,
    payload: dict,
    status: str = "scheduled",
) -> TrainingJob:
    processed_dir = Path(settings.processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = processed_dir / f"{source_run_id}-training-job.json"
    artifact_path.write_text(str(payload), encoding="utf-8")

    row = TrainingJob(
        source_run_id=source_run_id,
        status=status,
        trigger_reason=trigger_reason,
        artifact_path=str(artifact_path),
        payload=payload,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_training_jobs(db: Session, limit: int = 50) -> list[dict]:
    rows = db.scalars(
        select(TrainingJob).order_by(desc(TrainingJob.created_at)).limit(max(1, min(limit, 500)))
    ).all()
    return [
        {
            "id": row.id,
            "source_run_id": row.source_run_id,
            "status": row.status,
            "trigger_reason": row.trigger_reason,
            "artifact_path": row.artifact_path,
            "payload": row.payload,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]