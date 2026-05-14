import pandas as pd

from app.services.transformation import (
    apply_time_series_features,
    apply_transformations,
    handle_missing_and_outliers,
)


def test_apply_transformations_feature_expression() -> None:
    df = pd.DataFrame({"amount": [10.0, 20.0, 30.0], "category": ["a", "a", "b"]})
    out = apply_transformations(
        df,
        {
            "feature_engineering": [{"name": "amount_x2", "expression": "amount * 2"}],
            "filters": {"amount": {"min": 15}},
        },
    )
    assert "amount_x2" in out.columns
    assert out["amount_x2"].iloc[0] == 40.0


def test_time_series_and_cleaning() -> None:
    df = pd.DataFrame(
        {
            "entity_id": ["u1", "u1", "u1"],
            "event_ts": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "value": [1.0, None, 100.0],
        }
    )
    ts = apply_time_series_features(df, "entity_id", "event_ts", ["value"], [1], [2])
    cleaned = handle_missing_and_outliers(ts)
    assert "value_lag_1" in cleaned.columns
    assert cleaned["value"].isna().sum() == 0
