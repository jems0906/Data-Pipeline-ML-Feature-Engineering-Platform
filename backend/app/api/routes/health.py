from datetime import UTC, datetime

import redis
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine


router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check() -> dict:
    return {"status": "ok"}


def _check_postgres() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "detail": "reachable"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_redis() -> dict:
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        if client.ping():
            return {"status": "ok", "detail": "reachable"}
        return {"status": "error", "detail": "ping returned false"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_bootstrap_tables() -> dict:
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                        to_regclass('public.quality_alerts') AS quality_alerts,
                        to_regclass('public.freshness_slos') AS freshness_slos
                    """
                )
            ).mappings().one()

        missing = [name for name, value in row.items() if value is None]
        if missing:
            return {
                "status": "degraded",
                "detail": f"missing tables: {', '.join(missing)}",
            }
        return {"status": "ok", "detail": "all expected tables present"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _overall_status(checks: list[dict]) -> str:
    statuses = {check["status"] for check in checks}
    if "error" in statuses:
        return "error"
    if "degraded" in statuses:
        return "degraded"
    return "ok"


@router.get("/dependencies")
def dependency_health() -> dict:
    dependencies = {
        "postgres": _check_postgres(),
        "redis": _check_redis(),
        "bootstrap_tables": _check_bootstrap_tables(),
    }
    overall = _overall_status(list(dependencies.values()))
    return {
        "status": overall,
        "checked_at": datetime.now(UTC).isoformat(),
        "dependencies": dependencies,
    }
