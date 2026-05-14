from datetime import datetime

from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    source_type: str = Field(description="api|database|warehouse")
    source_name: str
    config: dict = Field(default_factory=dict)


class PipelineRunRequest(BaseModel):
    run_id: str
    source: IngestionRequest
    transformations: dict = Field(default_factory=dict)


class QualityReport(BaseModel):
    row_count: int
    missing_rates: dict[str, float]
    outlier_rates: dict[str, float]
    distributions: dict[str, list[dict[str, float | int]] | list[dict[str, str]]] = Field(default_factory=dict)
    validation_errors: list[str] = Field(default_factory=list)


class BackfillRequest(BaseModel):
    run_id_prefix: str = Field(default="backfill")
    start_date: datetime
    end_date: datetime
    window_days: int = Field(default=1, ge=1, le=30)
    source: IngestionRequest
    transformations: dict = Field(default_factory=dict)


class TrainingJobRequest(BaseModel):
    source_run_id: str
    drift_scores: dict[str, float] = Field(default_factory=dict)
    force: bool = False


class TrainingJobResponse(BaseModel):
    id: int
    source_run_id: str
    status: str
    trigger_reason: str
    artifact_path: str | None = None
    created_at: datetime


class ScaleProofRequest(BaseModel):
    model_count: int = Field(default=120, ge=1, le=5000)
    feature_pool_size: int = Field(default=300, ge=1, le=10000)
    features_per_model: int = Field(default=20, ge=1, le=200)
    synthetic_rows: int = Field(default=200000, ge=1000, le=5000000)
    synthetic_partitions: int = Field(default=8, ge=1, le=128)


class WarehouseValidationCheck(BaseModel):
    source_name: str = Field(description="bigquery|snowflake")
    query: str
    config: dict = Field(default_factory=dict)


class WarehouseValidationRequest(BaseModel):
    checks: list[WarehouseValidationCheck]
    fail_fast: bool = False


class FeatureLookupRequest(BaseModel):
    entity_id: str
    feature_names: list[str]
    as_of: datetime


class FeatureUsageRequest(BaseModel):
    model_name: str
    feature_name: str
    usage: str = Field(default="training")
    source_run_id: str | None = None


class RealtimeIngestionRequest(BaseModel):
    run_id: str
    source_name: str = Field(default="realtime-api")
    event: dict
    stream_name: str = Field(default="feature-events")
