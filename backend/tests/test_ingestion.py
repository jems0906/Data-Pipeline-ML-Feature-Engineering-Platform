import pandas as pd

from app.services.ingestion import IngestionService


class DummyDb:
    def add(self, _value) -> None:
        return None

    def commit(self) -> None:
        return None

    def refresh(self, _value) -> None:
        return None


def test_build_api_request_kwargs_bearer_auth() -> None:
    service = IngestionService(DummyDb())
    request_kwargs = service._build_api_request_kwargs(
        {
            "params": {"page": 1},
            "auth": {"type": "bearer", "token": "abc123"},
            "headers": {"X-Trace": "run-1"},
        }
    )

    assert request_kwargs["params"] == {"page": 1}
    assert request_kwargs["headers"]["Authorization"] == "Bearer abc123"
    assert request_kwargs["headers"]["X-Trace"] == "run-1"


def test_coerce_payload_to_frame_with_records_path() -> None:
    service = IngestionService(DummyDb())
    frame = service._coerce_payload_to_frame(
        {"result": {"items": [{"entity_id": "u1", "amount": 10.0}]}},
        records_path="result.items",
    )

    assert list(frame.columns) == ["entity_id", "amount"]
    assert frame.iloc[0]["entity_id"] == "u1"


def test_ingest_warehouse_batch_demo_fallback() -> None:
    service = IngestionService(DummyDb())
    frame = service.ingest_warehouse_batch(
        source="bigquery",
        query="SELECT 1",
        config={"allow_demo_fallback": True},
    )

    assert isinstance(frame, pd.DataFrame)
    assert not frame.empty
    assert "entity_id" in frame.columns


def test_ingest_warehouse_batch_rejects_unknown_source() -> None:
    service = IngestionService(DummyDb())

    try:
        service.ingest_warehouse_batch(source="databricks", query="SELECT 1", config={})
    except ValueError as exc:
        assert "Unsupported warehouse source" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected ValueError for unsupported warehouse source")