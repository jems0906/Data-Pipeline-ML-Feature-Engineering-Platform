from __future__ import annotations

import csv
import hashlib
import json
import struct
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.feature_store import DatasetVersion


def _masked_crc32c(value: bytes) -> int:
    # Native TFRecord framing uses masked CRC32C checksums.
    crc = 0xFFFFFFFF
    poly = 0x82F63B78
    for byte in value:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ poly
            else:
                crc >>= 1
    crc ^= 0xFFFFFFFF
    masked = (((crc >> 15) | ((crc << 17) & 0xFFFFFFFF)) + 0xA282EAD8) & 0xFFFFFFFF
    return masked


def _write_tfrecord(df: pd.DataFrame, output_path: Path) -> None:
    with output_path.open("wb") as fp:
        for row in df.to_dict(orient="records"):
            payload = json.dumps(row, default=str, separators=(",", ":")).encode("utf-8")
            length = struct.pack("<Q", len(payload))
            fp.write(length)
            fp.write(struct.pack("<I", _masked_crc32c(length)))
            fp.write(payload)
            fp.write(struct.pack("<I", _masked_crc32c(payload)))


def _build_version(df: pd.DataFrame, dataset_name: str) -> str:
    checksum = hashlib.sha256(df.to_csv(index=False).encode("utf-8")).hexdigest()[:12]
    return f"{dataset_name}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{checksum}"


def export_dataset(df: pd.DataFrame, dataset_name: str, fmt: str, db: Session) -> dict:
    exports_dir = Path(settings.exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)

    version = _build_version(df, dataset_name)
    output_path = exports_dir / f"{version}.{fmt}"

    if fmt == "csv":
        df.to_csv(output_path, index=False)
    elif fmt == "parquet":
        df.to_parquet(output_path, index=False)
    elif fmt == "tfrecord":
        _write_tfrecord(df, output_path)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")

    metadata = {
        "row_count": int(len(df.index)),
        "columns": list(df.columns),
        "created_at": datetime.utcnow().isoformat(),
    }

    row = DatasetVersion(
        dataset_name=dataset_name,
        version=version,
        path=str(output_path),
        format=fmt,
        meta_json=metadata,
    )
    db.add(row)
    db.commit()

    return {"version": version, "path": str(output_path), "format": fmt, "metadata": metadata}


def time_based_train_test_split(
    df: pd.DataFrame,
    timestamp_col: str,
    train_ratio: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sorted_df = df.sort_values(timestamp_col)
    split_idx = int(len(sorted_df.index) * train_ratio)
    return sorted_df.iloc[:split_idx].copy(), sorted_df.iloc[split_idx:].copy()


def generate_data_dictionary(df: pd.DataFrame, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=["column", "dtype", "null_rate", "description"])
        writer.writeheader()
        for col in df.columns:
            writer.writerow(
                {
                    "column": col,
                    "dtype": str(df[col].dtype),
                    "null_rate": float(df[col].isna().mean()),
                    "description": "",
                }
            )
