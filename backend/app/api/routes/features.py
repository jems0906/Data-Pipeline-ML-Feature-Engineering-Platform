from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.pipeline import FeatureLookupRequest, FeatureUsageRequest
from app.services.feature_store import FeatureStoreService


router = APIRouter(prefix="/features", tags=["features"])


@router.get("")
def list_features(search: str = Query(default=""), db: Session = Depends(get_db)) -> list[dict]:
    store = FeatureStoreService(db)
    return store.list_features(search=search)


@router.post("/lookup")
def lookup_features(payload: FeatureLookupRequest, db: Session = Depends(get_db)) -> dict:
    store = FeatureStoreService(db)
    values = store.point_in_time_lookup(
        entity_id=payload.entity_id,
        feature_names=payload.feature_names,
        as_of=payload.as_of,
    )
    return {"entity_id": payload.entity_id, "as_of": payload.as_of.isoformat(), "values": values}


@router.get("/usage")
def list_feature_usage(
    model_search: str = Query(default=""),
    feature_search: str = Query(default=""),
    db: Session = Depends(get_db),
) -> list[dict]:
    store = FeatureStoreService(db)
    return store.list_feature_usage(model_search=model_search, feature_search=feature_search)


@router.post("/usage")
def record_feature_usage(payload: FeatureUsageRequest, db: Session = Depends(get_db)) -> dict:
    store = FeatureStoreService(db)
    row = store.record_feature_usage(
        model_name=payload.model_name,
        feature_name=payload.feature_name,
        usage=payload.usage,
        source_run_id=payload.source_run_id,
    )
    return {
        "model_name": row.model_name,
        "feature_name": row.feature_name,
        "usage": row.usage,
        "source_run_id": row.source_run_id,
        "created_at": row.created_at.isoformat(),
    }
