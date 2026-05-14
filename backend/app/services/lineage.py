from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.feature_store import LineageEvent


def track_lineage(db: Session, run_id: str, event_type: str, payload: dict) -> None:
    row = LineageEvent(run_id=run_id, event_type=event_type, payload={**payload, "tracked_at": datetime.utcnow().isoformat()})
    db.add(row)
    db.commit()


def list_lineage_events(db: Session, run_id: str = "", limit: int = 100) -> list[dict]:
    stmt = select(LineageEvent)
    if run_id:
        stmt = stmt.where(LineageEvent.run_id == run_id)

    rows = db.scalars(stmt.order_by(desc(LineageEvent.created_at)).limit(max(1, min(limit, 500)))).all()
    return [
        {
            "run_id": row.run_id,
            "event_type": row.event_type,
            "payload": row.payload,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
