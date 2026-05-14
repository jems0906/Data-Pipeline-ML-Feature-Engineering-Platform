from __future__ import annotations

import numpy as np
import pandas as pd


def apply_transformations(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    transformed = df.copy()

    filters = rules.get("filters", {})
    for col, condition in filters.items():
        if col in transformed.columns and "min" in condition:
            transformed = transformed[transformed[col] >= condition["min"]]
        if col in transformed.columns and "max" in condition:
            transformed = transformed[transformed[col] <= condition["max"]]

    aggregations = rules.get("aggregations", [])
    for agg in aggregations:
        group_by = agg.get("group_by", [])
        metrics = agg.get("metrics", {})
        if group_by and metrics:
            transformed = transformed.groupby(group_by, as_index=False).agg(metrics)

    feature_defs = rules.get("feature_engineering", [])
    for feature in feature_defs:
        name = feature["name"]
        expression = feature["expression"]
        transformed[name] = transformed.eval(expression)

    return transformed.reset_index(drop=True)


def apply_time_series_features(
    df: pd.DataFrame,
    entity_col: str,
    ts_col: str,
    value_cols: list[str],
    lag_steps: list[int],
    rolling_windows: list[int],
) -> pd.DataFrame:
    out = df.sort_values([entity_col, ts_col]).copy()
    for col in value_cols:
        for step in lag_steps:
            out[f"{col}_lag_{step}"] = out.groupby(entity_col)[col].shift(step)
        for window in rolling_windows:
            out[f"{col}_roll_mean_{window}"] = (
                out.groupby(entity_col)[col].transform(lambda s: s.rolling(window, min_periods=1).mean())
            )
    return out


def join_datasets(base_df: pd.DataFrame, others: list[tuple[pd.DataFrame, list[str], str]]) -> pd.DataFrame:
    current = base_df.copy()
    for other_df, keys, how in others:
        current = current.merge(other_df, on=keys, how=how)
    return current


def handle_missing_and_outliers(df: pd.DataFrame, strategy: str = "median") -> pd.DataFrame:
    cleaned = df.copy()
    numeric_cols = cleaned.select_dtypes(include=[np.number]).columns

    for col in numeric_cols:
        if strategy == "mean":
            fill_value = cleaned[col].mean()
        elif strategy == "zero":
            fill_value = 0
        else:
            fill_value = cleaned[col].median()
        cleaned[col] = cleaned[col].fillna(fill_value)

        q1 = cleaned[col].quantile(0.25)
        q3 = cleaned[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        cleaned[col] = cleaned[col].clip(lower=lower, upper=upper)

    return cleaned
