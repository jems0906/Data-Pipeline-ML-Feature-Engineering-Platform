from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.feature_store import FeatureStoreService
from app.services.ingestion import IngestionService
from app.services.lineage import list_lineage_events
from app.services.transformation import apply_time_series_features, apply_transformations, handle_missing_and_outliers


def run_transformation_benchmark(row_count: int, partitions: int) -> dict:
    rows_per_partition = max(1, row_count // max(1, partitions))
    frames: list[pd.DataFrame] = []
    now = datetime.now(UTC)

    for partition in range(partitions):
        offsets = np.arange(rows_per_partition)
        frame = pd.DataFrame(
            {
                "entity_id": [f"entity-{partition}-{value % 25000}" for value in offsets],
                "event_ts": pd.to_datetime(now) + pd.to_timedelta(offsets, unit="s"),
                "amount": np.random.rand(rows_per_partition) * 1000,
                "feature_b": np.random.rand(rows_per_partition) * 25,
            }
        )
        frames.append(frame)

    source = pd.concat(frames, ignore_index=True)

    start = perf_counter()
    transformed = apply_transformations(
        source,
        {
            "feature_engineering": [
                {"name": "amount_x2", "expression": "amount * 2"},
                {"name": "amount_ratio", "expression": "amount / (feature_b + 1e-6)"},
            ]
        },
    )
    transformed = apply_time_series_features(
        transformed,
        entity_col="entity_id",
        ts_col="event_ts",
        value_cols=["amount", "amount_x2"],
        lag_steps=[1, 7],
        rolling_windows=[7, 30],
    )
    transformed = handle_missing_and_outliers(transformed)
    duration_seconds = max(perf_counter() - start, 1e-6)

    rows_processed = int(len(transformed.index))
    rows_per_second = rows_processed / duration_seconds

    bytes_per_row = max(1.0, float(source.memory_usage(deep=True).sum()) / max(1, len(source.index)))
    bytes_per_second = bytes_per_row * rows_per_second
    projected_petabyte_seconds = (1024**5) / bytes_per_second

    return {
        "rows_processed": rows_processed,
        "duration_seconds": duration_seconds,
        "rows_per_second": rows_per_second,
        "bytes_per_second": bytes_per_second,
        "projected_petabyte_hours": projected_petabyte_seconds / 3600,
    }


def run_feature_reuse_benchmark(
    db: Session,
    model_count: int,
    feature_pool_size: int,
    features_per_model: int,
    source_run_id: str,
) -> dict:
    store = FeatureStoreService(db)
    features = [f"feature_{idx:04d}" for idx in range(feature_pool_size)]

    for feature_name in features:
        store.register_feature(name=feature_name, entity_key="entity_id", dtype="float", description="benchmark")

    start = perf_counter()
    for model_index in range(model_count):
        model_name = f"model_{model_index:04d}"
        offset = model_index % feature_pool_size
        chosen_features = [features[(offset + step) % feature_pool_size] for step in range(features_per_model)]
        for feature_name in chosen_features:
            store.record_feature_usage(
                model_name=model_name,
                feature_name=feature_name,
                usage="training+inference",
                source_run_id=source_run_id,
            )
    duration_seconds = max(perf_counter() - start, 1e-6)

    total_records = model_count * features_per_model
    reuse_ratio = total_records / max(1, feature_pool_size)

    return {
        "model_count": model_count,
        "feature_pool_size": feature_pool_size,
        "features_per_model": features_per_model,
        "total_usage_records_written": total_records,
        "duration_seconds": duration_seconds,
        "writes_per_second": total_records / duration_seconds,
        "average_models_per_feature": (model_count * features_per_model) / max(1, feature_pool_size),
        "reuse_ratio": reuse_ratio,
        "target_100_models_met": model_count >= 100,
    }


def run_warehouse_validation(db: Session, checks: list[dict], fail_fast: bool = False) -> dict:
    service = IngestionService(db)
    results: list[dict] = []

    skipped = 0

    for check in checks:
        source_name = str(check["source_name"]).lower()
        query = check["query"]
        config = dict(check.get("config", {}))
        config["allow_demo_fallback"] = False

        started = perf_counter()
        try:
            frame = service.ingest_warehouse_batch(source=source_name, query=query, config=config)
            duration = max(perf_counter() - started, 1e-6)
            results.append(
                {
                    "source_name": source_name,
                    "status": "ok",
                    "row_count": int(len(frame.index)),
                    "duration_seconds": duration,
                    "columns": list(frame.columns),
                }
            )
        except Exception as exc:  # noqa: BLE001
            duration = max(perf_counter() - started, 1e-6)
            error_text = str(exc)
            is_missing_credentials = (
                "default credentials were not found" in error_text.lower()
                or "missing required connection fields" in error_text.lower()
            )

            if is_missing_credentials:
                skipped += 1
                results.append(
                    {
                        "source_name": source_name,
                        "status": "skipped",
                        "duration_seconds": duration,
                        "error": error_text,
                        "reason": "missing_credentials",
                    }
                )
                continue

            results.append(
                {
                    "source_name": source_name,
                    "status": "failed",
                    "duration_seconds": duration,
                    "error": error_text,
                }
            )
            if fail_fast:
                break

    success_count = sum(1 for item in results if item["status"] == "ok")
    failed_count = sum(1 for item in results if item["status"] == "failed")
    return {
        "checks_total": len(results),
        "checks_passed": success_count,
        "checks_failed": failed_count,
        "checks_skipped": skipped,
        "results": results,
    }


def build_lineage_graph(db: Session, run_id: str = "", limit: int = 500) -> dict:
    events = list_lineage_events(db, run_id=run_id, limit=limit)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        grouped[event["run_id"]].append(event)

    required_event_types = {
        "ingestion_complete",
        "pipeline_complete",
        "realtime_event_ingested",
        "training_job_scheduled",
        "backfill_window_complete",
    }

    nodes: list[dict] = []
    edges: list[dict] = []
    observed_event_types: set[str] = set()

    for grouped_run_id, run_events in grouped.items():
        run_node_id = f"run:{grouped_run_id}"
        nodes.append({"id": run_node_id, "label": grouped_run_id, "type": "run"})

        ordered = sorted(run_events, key=lambda item: item["created_at"])
        previous_event_node = ""
        for index, event in enumerate(ordered):
            event_node_id = f"event:{grouped_run_id}:{index}"
            observed_event_types.add(event["event_type"])
            nodes.append(
                {
                    "id": event_node_id,
                    "label": event["event_type"],
                    "type": "event",
                    "created_at": event["created_at"],
                }
            )
            edges.append({"from": run_node_id, "to": event_node_id, "type": "contains"})
            if previous_event_node:
                edges.append({"from": previous_event_node, "to": event_node_id, "type": "sequence"})
            previous_event_node = event_node_id

    coverage = len(required_event_types.intersection(observed_event_types)) / len(required_event_types)
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "runs_covered": len(grouped),
            "events_covered": len(events),
            "required_event_types": sorted(required_event_types),
            "observed_event_types": sorted(observed_event_types),
            "event_type_coverage": coverage,
        },
    }


def write_proof_report(report_name: str, payload: dict) -> str:
    metadata_dir = Path(settings.metadata_dir)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    file_path = metadata_dir / f"{report_name}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.json"
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(file_path)
