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
    validation_errors: list[str] = Field(default_factory=list)


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
