from datetime import UTC, datetime
from pathlib import Path
import json

import pandas as pd

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.pipeline import (
    BackfillRequest,
    PipelineRunRequest,
    QualityReport,
    RealtimeIngestionRequest,
    ScaleProofRequest,
    TrainingJobRequest,
    WarehouseValidationRequest,
)
from app.services.automation import detect_data_drift, detect_schema_changes, should_trigger_retraining, suggest_new_features
from app.services.alerts import dispatch_recent_alerts
from app.services.dataset_export import export_dataset, generate_data_dictionary, time_based_train_test_split
from app.services.feature_store import FeatureStoreService
from app.services.ingestion import IngestionService
from app.services.lineage import list_lineage_events, track_lineage
from app.services.proofs import (
    build_lineage_graph,
    run_feature_reuse_benchmark,
    run_transformation_benchmark,
    run_warehouse_validation,
    write_proof_report,
)
from app.services.training import list_training_jobs, schedule_training_job
from app.services.transformation import (
    apply_time_series_features,
    apply_transformations,
    handle_missing_and_outliers,
)
from app.services.validation import compute_missing_rates, compute_numeric_distributions, detect_outlier_rates, validate_ranges, validate_schema


router = APIRouter(prefix="/pipelines", tags=["pipelines"])


def _persist_alert(db: Session, run_id: str, alert_type: str, severity: str, details: dict) -> None:
    db.execute(
        text(
            """
            INSERT INTO quality_alerts(run_id, alert_type, severity, details)
            VALUES (:run_id, :alert_type, :severity, CAST(:details AS JSONB))
            """
        ),
        {
            "run_id": run_id,
            "alert_type": alert_type,
            "severity": severity,
            "details": json.dumps(details),
        },
    )


def _persist_quality_alerts(
    db: Session,
    run_id: str,
    missing_rates: dict[str, float],
    outlier_rates: dict[str, float],
    validation_errors: list[str],
) -> int:
    alerts = 0

    if validation_errors:
        _persist_alert(
            db,
            run_id,
            "schema_validation",
            "high",
            {"validation_errors": validation_errors},
        )
        alerts += 1

    for col, rate in missing_rates.items():
        if rate >= settings.missing_rate_alert_threshold:
            _persist_alert(
                db,
                run_id,
                "missing_rate",
                "medium",
                {"column": col, "rate": rate, "threshold": settings.missing_rate_alert_threshold},
            )
            alerts += 1

    for col, rate in outlier_rates.items():
        if rate >= settings.outlier_rate_alert_threshold:
            _persist_alert(
                db,
                run_id,
                "outlier_rate",
                "medium",
                {"column": col, "rate": rate, "threshold": settings.outlier_rate_alert_threshold},
            )
            alerts += 1

    return alerts


def _update_freshness_and_alerts(
    db: Session,
    run_id: str,
    transformed: pd.DataFrame,
    feature_defs: list[dict],
) -> int:
    if transformed.empty or "event_ts" not in transformed.columns:
        return 0

    now_ts = datetime.now(UTC)
    alerts = 0
    for feat in feature_defs:
        feature_name = feat["name"]
        if feature_name not in transformed.columns:
            continue

        event_series = pd.to_datetime(transformed["event_ts"], utc=True, errors="coerce").dropna()
        if event_series.empty:
            continue

        last_seen = event_series.max().to_pydatetime()
        lag_seconds = int((now_ts - last_seen).total_seconds())
        status = "breach" if lag_seconds > settings.default_freshness_lag_seconds else "ok"

        db.execute(
            text(
                """
                INSERT INTO freshness_slos(feature_name, max_lag_seconds, last_seen_at, status, updated_at)
                VALUES (:feature_name, :max_lag_seconds, :last_seen_at, :status, NOW())
                ON CONFLICT (feature_name)
                DO UPDATE SET
                  max_lag_seconds = EXCLUDED.max_lag_seconds,
                  last_seen_at = EXCLUDED.last_seen_at,
                  status = EXCLUDED.status,
                  updated_at = NOW()
                """
            ),
            {
                "feature_name": feature_name,
                "max_lag_seconds": settings.default_freshness_lag_seconds,
                "last_seen_at": last_seen,
                "status": status,
            },
        )

        if status == "breach":
            _persist_alert(
                db,
                run_id,
                "freshness_slo",
                "medium",
                {
                    "feature_name": feature_name,
                    "lag_seconds": lag_seconds,
                    "max_lag_seconds": settings.default_freshness_lag_seconds,
                },
            )
            alerts += 1

    return alerts


def _record_usage_entries(store: FeatureStoreService, feature_defs: list[dict], run_id: str, transformations: dict) -> int:
    usage_entries = transformations.get("usage_tracking", [])
    if usage_entries:
        for item in usage_entries:
            store.record_feature_usage(
                model_name=item.get("model_name", "pipeline-builder"),
                feature_name=item["feature_name"],
                usage=item.get("usage", "training"),
                source_run_id=run_id,
            )
        return len(usage_entries)

    for feat in feature_defs:
        store.record_feature_usage(
            model_name="pipeline-builder",
            feature_name=feat["name"],
            usage="training+inference",
            source_run_id=run_id,
        )
    return len(feature_defs)


def _materialize_feature_values(
    store: FeatureStoreService,
    transformed: pd.DataFrame,
    feature_defs: list[dict],
    run_id: str,
) -> int:
    if transformed.empty or not feature_defs:
        return 0

    writes = 0
    for feat in feature_defs:
        feature_name = feat["name"]
        entity_key = feat.get("entity_key", "entity_id")
        if feature_name not in transformed.columns or entity_key not in transformed.columns:
            continue

        for row in transformed.itertuples(index=False):
            row_values = row._asdict()
            entity_id = row_values.get(entity_key)
            feature_value = row_values.get(feature_name)

            if entity_id is None or pd.isna(feature_value):
                continue

            raw_ts = row_values.get("event_ts")
            if raw_ts is None or pd.isna(raw_ts):
                event_ts = datetime.now(UTC)
            else:
                parsed = pd.to_datetime(raw_ts, utc=True, errors="coerce")
                if pd.isna(parsed):
                    event_ts = datetime.now(UTC)
                else:
                    event_ts = parsed.to_pydatetime()

            store.write_feature_value(
                feature_name=feature_name,
                entity_id=str(entity_id),
                event_ts=event_ts,
                value=feature_value,
                source_run_id=run_id,
            )
            writes += 1

    return writes


def _execute_pipeline(payload: PipelineRunRequest, db: Session) -> dict:
    ingestion_service = IngestionService(db)
    store = FeatureStoreService(db)

    raw_df = ingestion_service.run_ingestion(
        run_id=payload.run_id,
        source_type=payload.source.source_type,
        source_name=payload.source.source_name,
        config=payload.source.config,
    )
    track_lineage(db, payload.run_id, "ingestion_complete", {"rows": int(len(raw_df.index)), "source": payload.source.source_name})

    validation_errors = validate_schema(raw_df, payload.transformations.get("required_columns", []))
    validation_errors.extend(validate_ranges(raw_df, payload.transformations.get("range_checks", {})))

    transformed = apply_transformations(raw_df, payload.transformations)

    ts_cfg = payload.transformations.get("time_series", {})
    if ts_cfg:
        transformed = apply_time_series_features(
            transformed,
            entity_col=ts_cfg["entity_col"],
            ts_col=ts_cfg["ts_col"],
            value_cols=ts_cfg["value_cols"],
            lag_steps=ts_cfg.get("lag_steps", [1, 7]),
            rolling_windows=ts_cfg.get("rolling_windows", [7, 30]),
        )

    join_targets = payload.transformations.get("joins", [])
    if join_targets:
        track_lineage(db, payload.run_id, "join_config_detected", {"joins": len(join_targets)})

    transformed = handle_missing_and_outliers(transformed, strategy=payload.transformations.get("impute", "median"))

    if "event_ts" in transformed.columns:
        train_df, test_df = time_based_train_test_split(
            transformed,
            timestamp_col="event_ts",
            train_ratio=settings.default_train_ratio,
        )
    else:
        train_df = transformed.sample(frac=settings.default_train_ratio, random_state=42)
        test_df = transformed.drop(train_df.index)

    train_export = export_dataset(train_df, f"{payload.run_id}-train", "parquet", db)
    test_export = export_dataset(test_df, f"{payload.run_id}-test", "parquet", db)

    dict_path = Path(settings.metadata_dir) / f"{payload.run_id}-dictionary.csv"
    generate_data_dictionary(transformed, str(dict_path))

    feature_defs = payload.transformations.get("register_features", [])
    for feat in feature_defs:
        store.register_feature(
            name=feat["name"],
            entity_key=feat.get("entity_key", "entity_id"),
            dtype=feat.get("dtype", "float"),
            description=feat.get("description", ""),
        )

    materialized_feature_values = _materialize_feature_values(
        store=store,
        transformed=transformed,
        feature_defs=feature_defs,
        run_id=payload.run_id,
    )
    usage_records = _record_usage_entries(
        store=store,
        feature_defs=feature_defs,
        run_id=payload.run_id,
        transformations=payload.transformations,
    )

    schema_changes = detect_schema_changes(transformed, payload.transformations.get("previous_schema", {}))
    suggested_features = suggest_new_features(transformed)
    missing_rates = compute_missing_rates(transformed)
    outlier_rates = detect_outlier_rates(transformed, settings.outlier_zscore_threshold)
    distributions = compute_numeric_distributions(transformed)
    drift_reference = raw_df.select_dtypes(include=["number"])
    drift_live = transformed.select_dtypes(include=["number"])
    drift_scores = detect_data_drift(drift_reference, drift_live) if not drift_reference.empty and not drift_live.empty else {}
    trigger_retraining = should_trigger_retraining(drift_scores)

    alert_count = _persist_quality_alerts(
        db=db,
        run_id=payload.run_id,
        missing_rates=missing_rates,
        outlier_rates=outlier_rates,
        validation_errors=validation_errors,
    )
    alert_count += _update_freshness_and_alerts(
        db=db,
        run_id=payload.run_id,
        transformed=transformed,
        feature_defs=feature_defs,
    )

    training_job = None
    if trigger_retraining:
        training_job = schedule_training_job(
            db=db,
            source_run_id=payload.run_id,
            trigger_reason="drift_threshold_exceeded",
            payload={"drift_scores": drift_scores, "feature_count": len(feature_defs)},
        )

    db.commit()

    track_lineage(
        db,
        payload.run_id,
        "pipeline_complete",
        {
            "train_version": train_export["version"],
            "test_version": test_export["version"],
            "dictionary": str(dict_path),
            "trigger_retraining": trigger_retraining,
        },
    )

    return {
        "run_id": payload.run_id,
        "train_export": train_export,
        "test_export": test_export,
        "data_dictionary": str(dict_path),
        "quality": {
            "row_count": int(len(transformed.index)),
            "missing_rates": missing_rates,
            "outlier_rates": outlier_rates,
            "distributions": distributions,
            "validation_errors": validation_errors,
        },
        "automation": {
            "schema_changes": schema_changes,
            "suggested_features": suggested_features,
            "drift_scores": drift_scores,
            "trigger_retraining": trigger_retraining,
            "training_job_id": training_job.id if training_job else None,
        },
        "feature_store": {
            "registered_features": len(feature_defs),
            "materialized_values": materialized_feature_values,
            "usage_records": usage_records,
        },
        "alerts": {
            "created": alert_count,
        },
    }


@router.post("/run")
def run_pipeline(payload: PipelineRunRequest, db: Session = Depends(get_db)) -> dict:
    return _execute_pipeline(payload, db)


@router.post("/quality-report", response_model=QualityReport)
def quality_report(sample_rows: int = 1000, db: Session = Depends(get_db)) -> QualityReport:
    _ = db
    synthetic = {
        "event_ts": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "feature_a": [1.0, None, 50.0],
        "feature_b": [10.0, 12.0, 11.5],
    }
    import pandas as pd

    df = pd.DataFrame(synthetic).head(sample_rows)
    return QualityReport(
        row_count=int(len(df.index)),
        missing_rates=compute_missing_rates(df),
        outlier_rates=detect_outlier_rates(df, settings.outlier_zscore_threshold),
        distributions=compute_numeric_distributions(df),
        validation_errors=[],
    )


@router.post("/backfill")
def backfill_pipeline(payload: BackfillRequest, db: Session = Depends(get_db)) -> dict:
    runs: list[dict] = []
    current = payload.start_date
    window_index = 0
    while current <= payload.end_date:
        window_end = min(payload.end_date, current + pd.Timedelta(days=payload.window_days))
        config = dict(payload.source.config)
        config["backfill_window"] = {
            "start": current.isoformat(),
            "end": window_end.isoformat(),
        }
        run_payload = PipelineRunRequest(
            run_id=f"{payload.run_id_prefix}-{window_index:03d}",
            source={
                "source_type": payload.source.source_type,
                "source_name": payload.source.source_name,
                "config": config,
            },
            transformations=payload.transformations,
        )
        result = _execute_pipeline(run_payload, db)
        runs.append(
            {
                "run_id": result["run_id"],
                "start": current.isoformat(),
                "end": window_end.isoformat(),
                "row_count": result["quality"]["row_count"],
            }
        )
        track_lineage(db, result["run_id"], "backfill_window_complete", runs[-1])
        current = window_end + pd.Timedelta(seconds=1)
        window_index += 1

    return {
        "run_count": len(runs),
        "runs": runs,
    }


@router.get("/lineage")
def get_lineage(run_id: str = "", limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    return list_lineage_events(db, run_id=run_id, limit=limit)


@router.get("/lineage/graph")
def get_lineage_graph(run_id: str = "", limit: int = 500, db: Session = Depends(get_db)) -> dict:
    graph = build_lineage_graph(db, run_id=run_id, limit=limit)
    report_path = write_proof_report("lineage-graph", graph)
    return {
        **graph,
        "report_path": report_path,
    }


@router.post("/proofs/scale")
def run_scale_proof(payload: ScaleProofRequest, db: Session = Depends(get_db)) -> dict:
    proof_run_id = f"scale-proof-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    transform = run_transformation_benchmark(payload.synthetic_rows, payload.synthetic_partitions)
    reuse = run_feature_reuse_benchmark(
        db=db,
        model_count=payload.model_count,
        feature_pool_size=payload.feature_pool_size,
        features_per_model=payload.features_per_model,
        source_run_id=proof_run_id,
    )

    summary = {
        "proof_run_id": proof_run_id,
        "transformation_benchmark": transform,
        "feature_reuse_benchmark": reuse,
        "claims": {
            "target_100_models_met": reuse["target_100_models_met"],
            "projected_petabyte_hours": transform["projected_petabyte_hours"],
            "benchmark_based_projection": True,
        },
    }
    report_path = write_proof_report("scale-proof", summary)
    return {
        **summary,
        "report_path": report_path,
    }


@router.post("/proofs/warehouse-validation")
def validate_production_warehouses(payload: WarehouseValidationRequest, db: Session = Depends(get_db)) -> dict:
    result = run_warehouse_validation(
        db=db,
        checks=[{"source_name": check.source_name, "query": check.query, "config": check.config} for check in payload.checks],
        fail_fast=payload.fail_fast,
    )
    report_path = write_proof_report("warehouse-validation", result)
    return {
        **result,
        "report_path": report_path,
    }


@router.get("/training-jobs")
def get_training_jobs(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    return list_training_jobs(db, limit=limit)


@router.post("/training-jobs/trigger")
def trigger_training_job(payload: TrainingJobRequest, db: Session = Depends(get_db)) -> dict:
    should_schedule = payload.force or should_trigger_retraining(payload.drift_scores)
    if not should_schedule:
        return {
            "scheduled": False,
            "reason": "drift_below_threshold",
            "source_run_id": payload.source_run_id,
        }

    job = schedule_training_job(
        db=db,
        source_run_id=payload.source_run_id,
        trigger_reason="manual_force" if payload.force else "drift_threshold_exceeded",
        payload={"drift_scores": payload.drift_scores, "forced": payload.force},
    )
    track_lineage(
        db,
        payload.source_run_id,
        "training_job_scheduled",
        {"training_job_id": job.id, "reason": job.trigger_reason},
    )
    return {
        "scheduled": True,
        "training_job": {
            "id": job.id,
            "source_run_id": job.source_run_id,
            "status": job.status,
            "trigger_reason": job.trigger_reason,
            "artifact_path": job.artifact_path,
            "created_at": job.created_at.isoformat(),
        },
    }


@router.post("/realtime-event")
def ingest_realtime_event(payload: RealtimeIngestionRequest, db: Session = Depends(get_db)) -> dict:
    service = IngestionService(db)
    output_path = service.ingest_realtime_event(
        run_id=payload.run_id,
        source_name=payload.source_name,
        event=payload.event,
    )
    stream_id = service.publish_realtime_event(payload.stream_name, payload.event)
    track_lineage(
        db,
        payload.run_id,
        "realtime_event_ingested",
        {
            "stream_name": payload.stream_name,
            "stream_id": stream_id,
            "output_path": str(output_path),
        },
    )
    return {
        "run_id": payload.run_id,
        "status": "accepted",
        "raw_path": str(output_path),
        "stream_name": payload.stream_name,
        "stream_id": stream_id,
    }


@router.get("/alerts")
def list_alerts(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT run_id, alert_type, severity, details, created_at
            FROM quality_alerts
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": max(1, min(limit, 500))},
    ).mappings()
    return [
        {
            "run_id": row["run_id"],
            "alert_type": row["alert_type"],
            "severity": row["severity"],
            "details": row["details"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


@router.post("/alerts/dispatch")
def dispatch_alerts(limit: int = 20, db: Session = Depends(get_db)) -> dict:
    channels = [part.strip() for part in settings.alert_channels_csv.split(",") if part.strip()]
    if not channels:
        return {"alerts_considered": 0, "notifications_sent": 0, "channels": [], "notifications": []}
    return dispatch_recent_alerts(db=db, channels=channels, limit=limit)
