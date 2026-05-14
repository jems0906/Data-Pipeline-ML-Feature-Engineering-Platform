from __future__ import annotations

import numpy as np
import pandas as pd


def compute_missing_rates(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {}
    return {col: float(df[col].isna().mean()) for col in df.columns}


def detect_outlier_rates(df: pd.DataFrame, zscore_threshold: float = 3.0) -> dict[str, float]:
    rates: dict[str, float] = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        series = df[col].dropna()
        if series.empty or float(series.std()) == 0:
            rates[col] = 0.0
            continue
        zscores = (series - series.mean()) / series.std()
        rates[col] = float((zscores.abs() > zscore_threshold).mean())
    return rates


def compute_numeric_distributions(df: pd.DataFrame, bins: int = 8) -> dict[str, list[dict[str, float | int]]]:
    distributions: dict[str, list[dict[str, float | int]]] = {}
    numeric_cols = list(df.select_dtypes(include=[np.number]).columns[:6])
    for col in numeric_cols:
        series = df[col].dropna()
        if series.empty:
            distributions[col] = []
            continue
        hist, edges = np.histogram(series, bins=min(bins, max(1, len(series))))
        buckets: list[dict[str, float | int]] = []
        for index, count in enumerate(hist):
            buckets.append(
                {
                    "bin_start": float(edges[index]),
                    "bin_end": float(edges[index + 1]),
                    "count": int(count),
                }
            )
        distributions[col] = buckets
    return distributions


def validate_schema(df: pd.DataFrame, required_columns: list[str]) -> list[str]:
    errors: list[str] = []
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
    return errors


def validate_ranges(df: pd.DataFrame, ranges: dict[str, tuple[float, float]]) -> list[str]:
    errors: list[str] = []
    for col, (min_value, max_value) in ranges.items():
        if col not in df.columns:
            continue
        invalid_count = ((df[col] < min_value) | (df[col] > max_value)).sum()
        if invalid_count > 0:
            errors.append(f"Column {col} has {invalid_count} values outside [{min_value}, {max_value}]")
    return errors
