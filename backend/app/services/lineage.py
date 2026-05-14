from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.feature_store import LineageEvent


def track_lineage(db: Session, run_id: str, event_type: str, payload: dict) -> None:
    row = LineageEvent(run_id=run_id, event_type=event_type, payload={**payload, "tracked_at": datetime.utcnow().isoformat()})
    db.add(row)
    db.commit()
