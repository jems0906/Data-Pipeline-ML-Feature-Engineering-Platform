import pandas as pd

from app.services.validation import compute_missing_rates, detect_outlier_rates, validate_schema


def test_compute_missing_rates() -> None:
    df = pd.DataFrame({"a": [1, None, 3], "b": [1, 2, 3]})
    rates = compute_missing_rates(df)
    assert rates["a"] == 1 / 3
    assert rates["b"] == 0.0


def test_validate_schema() -> None:
    df = pd.DataFrame({"entity_id": [1], "event_ts": ["2026-01-01"]})
    errors = validate_schema(df, ["entity_id", "event_ts", "feature_a"])
    assert len(errors) == 1
    assert "feature_a" in errors[0]


def test_detect_outlier_rates() -> None:
    df = pd.DataFrame({"x": [1, 2, 2, 3, 100]})
    rates = detect_outlier_rates(df, zscore_threshold=1.5)
    assert rates["x"] > 0
