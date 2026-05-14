from __future__ import annotations

import json
from datetime import datetime

import redis
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.feature_store import FeatureDefinition, FeatureUsage, FeatureValue


class FeatureStoreService:
    def __init__(self, db: Session):
        self.db = db
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    def register_feature(self, name: str, entity_key: str, dtype: str, description: str = "") -> FeatureDefinition:
        existing = self.db.scalar(select(FeatureDefinition).where(FeatureDefinition.name == name))
        if existing:
            return existing
        feature = FeatureDefinition(name=name, entity_key=entity_key, dtype=dtype, description=description)
        self.db.add(feature)
        self.db.commit()
        self.db.refresh(feature)
        return feature

    def write_feature_value(
        self,
        feature_name: str,
        entity_id: str,
        event_ts: datetime,
        value: float | str,
        source_run_id: str,
    ) -> None:
        feature = self.db.scalar(select(FeatureDefinition).where(FeatureDefinition.name == feature_name))
        if not feature:
            raise ValueError(f"Unknown feature: {feature_name}")

        row = FeatureValue(
            feature_id=feature.id,
            entity_id=entity_id,
            event_ts=event_ts,
            value_float=float(value) if isinstance(value, (int, float)) else None,
            value_text=str(value) if isinstance(value, str) else None,
            source_run_id=source_run_id,
        )
        self.db.add(row)
        self.db.commit()

        key = f"feature:{feature_name}:{entity_id}"
        payload = {"event_ts": event_ts.isoformat(), "value": value}
        self.redis_client.set(key, json.dumps(payload), ex=feature.freshness_seconds)

    def point_in_time_lookup(self, entity_id: str, feature_names: list[str], as_of: datetime) -> dict[str, float | str | None]:
        result: dict[str, float | str | None] = {}
        for feature_name in feature_names:
            cached = self.redis_client.get(f"feature:{feature_name}:{entity_id}")
            if cached:
                cached_payload = json.loads(cached)
                if datetime.fromisoformat(cached_payload["event_ts"]) <= as_of:
                    result[feature_name] = cached_payload["value"]
                    continue

            stmt = (
                select(FeatureValue, FeatureDefinition)
                .join(FeatureDefinition, FeatureDefinition.id == FeatureValue.feature_id)
                .where(
                    FeatureDefinition.name == feature_name,
                    FeatureValue.entity_id == entity_id,
                    FeatureValue.event_ts <= as_of,
                )
                .order_by(desc(FeatureValue.event_ts))
                .limit(1)
            )
            row = self.db.execute(stmt).first()
            if not row:
                result[feature_name] = None
            else:
                value = row.FeatureValue.value_float
                if value is None:
                    value = row.FeatureValue.value_text
                result[feature_name] = value
        return result

    def list_features(self, search: str = "") -> list[dict]:
        usage_count = func.count(FeatureUsage.id)
        model_count = func.count(func.distinct(FeatureUsage.model_name))
        stmt = (
            select(FeatureDefinition, usage_count.label("usage_count"), model_count.label("model_count"))
            .outerjoin(FeatureUsage, FeatureUsage.feature_name == FeatureDefinition.name)
            .group_by(FeatureDefinition.id)
        )
        if search:
            stmt = stmt.where(FeatureDefinition.name.ilike(f"%{search}%"))
        features = self.db.execute(stmt.order_by(FeatureDefinition.name)).all()
        return [
            {
                "name": feat.FeatureDefinition.name,
                "entity_key": feat.FeatureDefinition.entity_key,
                "dtype": feat.FeatureDefinition.dtype,
                "schema_version": feat.FeatureDefinition.schema_version,
                "freshness_seconds": feat.FeatureDefinition.freshness_seconds,
                "description": feat.FeatureDefinition.description,
                "usage_count": int(feat.usage_count or 0),
                "model_count": int(feat.model_count or 0),
            }
            for feat in features
        ]

    def record_feature_usage(
        self,
        model_name: str,
        feature_name: str,
        usage: str,
        source_run_id: str | None = None,
    ) -> FeatureUsage:
        row = FeatureUsage(
            model_name=model_name,
            feature_name=feature_name,
            usage=usage,
            source_run_id=source_run_id,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_feature_usage(self, model_search: str = "", feature_search: str = "") -> list[dict]:
        stmt = select(FeatureUsage)
        if model_search:
            stmt = stmt.where(FeatureUsage.model_name.ilike(f"%{model_search}%"))
        if feature_search:
            stmt = stmt.where(FeatureUsage.feature_name.ilike(f"%{feature_search}%"))

        rows = self.db.scalars(stmt.order_by(desc(FeatureUsage.created_at)).limit(200)).all()
        return [
            {
                "model_name": row.model_name,
                "feature_name": row.feature_name,
                "usage": row.usage,
                "source_run_id": row.source_run_id,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
