from datetime import datetime

import pandas as pd

from app.api.routes.pipelines import _materialize_feature_values


class StubStore:
    def __init__(self) -> None:
        self.writes: list[dict] = []

    def write_feature_value(self, **kwargs) -> None:
        self.writes.append(kwargs)


def test_materialize_feature_values_writes_rows_for_registered_features() -> None:
    store = StubStore()
    transformed = pd.DataFrame(
        [
            {"entity_id": "demo-1", "event_ts": "2026-01-01T00:00:00Z", "amount": 10.2},
            {"entity_id": "demo-2", "event_ts": "2026-01-02T00:00:00Z", "amount": 7.5},
        ]
    )

    writes = _materialize_feature_values(
        store=store,
        transformed=transformed,
        feature_defs=[{"name": "amount", "entity_key": "entity_id"}],
        run_id="run-1",
    )

    assert writes == 2
    assert len(store.writes) == 2
    assert store.writes[0]["feature_name"] == "amount"
    assert store.writes[0]["entity_id"] == "demo-1"
    assert isinstance(store.writes[0]["event_ts"], datetime)
    assert store.writes[0]["source_run_id"] == "run-1"


def test_materialize_feature_values_skips_missing_feature_values() -> None:
    store = StubStore()
    transformed = pd.DataFrame(
        [
            {"entity_id": "demo-1", "event_ts": "2026-01-01T00:00:00Z", "amount": None},
            {"entity_id": "demo-2", "event_ts": "2026-01-02T00:00:00Z", "amount": 9.1},
        ]
    )

    writes = _materialize_feature_values(
        store=store,
        transformed=transformed,
        feature_defs=[{"name": "amount", "entity_key": "entity_id"}],
        run_id="run-2",
    )

    assert writes == 1
    assert len(store.writes) == 1
    assert store.writes[0]["entity_id"] == "demo-2"
