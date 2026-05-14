from __future__ import annotations

import numpy as np
import pandas as pd


def detect_schema_changes(current_df: pd.DataFrame, previous_schema: dict[str, str]) -> dict:
    current_schema = {col: str(dtype) for col, dtype in current_df.dtypes.items()}
    added = [col for col in current_schema if col not in previous_schema]
    removed = [col for col in previous_schema if col not in current_schema]
    changed = [col for col in current_schema if col in previous_schema and current_schema[col] != previous_schema[col]]
    return {"added": added, "removed": removed, "changed": changed, "current_schema": current_schema}


def suggest_new_features(df: pd.DataFrame) -> list[dict]:
    suggestions: list[dict] = []
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    for col in numeric_cols:
        suggestions.append({"feature_name": f"{col}_zscore", "expression": f"({col} - {col}.mean()) / {col}.std()"})

    if len(numeric_cols) >= 2:
        a, b = numeric_cols[0], numeric_cols[1]
        suggestions.append({"feature_name": f"{a}_to_{b}_ratio", "expression": f"{a} / ({b} + 1e-6)"})

    return suggestions


def detect_data_drift(reference_df: pd.DataFrame, live_df: pd.DataFrame, bins: int = 10) -> dict[str, float]:
    drift_scores: dict[str, float] = {}
    shared_numeric = [
        col
        for col in reference_df.select_dtypes(include=[np.number]).columns
        if col in live_df.select_dtypes(include=[np.number]).columns
    ]

    for col in shared_numeric:
        ref = reference_df[col].dropna()
        liv = live_df[col].dropna()
        if ref.empty or liv.empty:
            drift_scores[col] = 0.0
            continue

        ref_hist, edges = np.histogram(ref, bins=bins, density=True)
        liv_hist, _ = np.histogram(liv, bins=edges, density=True)

        ref_hist = np.clip(ref_hist, 1e-6, None)
        liv_hist = np.clip(liv_hist, 1e-6, None)

        psi = np.sum((liv_hist - ref_hist) * np.log(liv_hist / ref_hist))
        drift_scores[col] = float(psi)

    return drift_scores


def should_trigger_retraining(drift_scores: dict[str, float], threshold: float = 0.2) -> bool:
    return any(score >= threshold for score in drift_scores.values())
