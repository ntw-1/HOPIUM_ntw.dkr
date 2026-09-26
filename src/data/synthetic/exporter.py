"""
src/data/synthetic/exporter.py

Exports synthetic burn-in trajectory data to CSV and companion .meta.json files.

Canonical provenance design (as per approved Phase 1 Specification Rev 3, §6):
    1. CSV is written with standard machine-readable format (no embedded metadata).
    2. CSV bytes are canonicalized: UTF-8, LF line endings, trailing blank lines stripped.
    3. SHA-256 is computed over the canonical CSV byte stream.
    4. Hash and all provenance metadata are stored in a companion .meta.json file.
    5. The CSV file itself is NOT modified after hash computation.

Ground truth is exported to a separate JSON file and NEVER included in the
production inference CSV.
"""

import csv
import dataclasses
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import List

from .schema import (
    ComponentGroundTruth,
    DatasetMetadata,
    ParameterGroundTruth,
    TrajectoryRow,
)

# CSV column order — exactly matches DATA_CONTRACT.md schema
CSV_FIELDNAMES = [
    "lot_id",
    "component_id",
    "parameter_name",
    "unit",
    "value_0h",
    "value_24h",
    "value_96h",
    "value_168h",
    "synthetic_spec_min",
    "synthetic_spec_max",
]

# Number of decimal places for float fields
FLOAT_PRECISION = 6


def _format_float(v: float) -> str:
    return f"{v:.{FLOAT_PRECISION}f}"


def _canonicalize_csv(rows: List[TrajectoryRow]) -> bytes:
    """
    Produce a canonical UTF-8 byte string from trajectory rows.

    Canonicalization rules (deterministic reproducibility):
        1. Write header + rows using csv.writer with LF line terminator.
        2. Normalize all line endings to LF.
        3. Strip trailing blank lines.
        4. Encode as UTF-8.

    Parameters
    ----------
    rows : list of TrajectoryRow

    Returns
    -------
    bytes
        Canonical byte stream used as SHA-256 input.
    """
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=CSV_FIELDNAMES,
        lineterminator="\n",   # Canonical LF
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "lot_id": row.lot_id,
            "component_id": row.component_id,
            "parameter_name": row.parameter_name,
            "unit": row.unit,
            "value_0h": _format_float(row.value_0h),
            "value_24h": _format_float(row.value_24h),
            "value_96h": _format_float(row.value_96h),
            "value_168h": _format_float(row.value_168h),
            "synthetic_spec_min": _format_float(row.synthetic_spec_min),
            "synthetic_spec_max": _format_float(row.synthetic_spec_max),
        })

    content = buf.getvalue()
    # Normalize line endings and strip trailing blank lines
    content = content.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"
    return content.encode("utf-8")


def compute_sha256(canonical_bytes: bytes) -> str:
    """
    Compute SHA-256 hex digest of canonical CSV bytes.

    Parameters
    ----------
    canonical_bytes : bytes
        Output of _canonicalize_csv().

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest string.
    """
    return hashlib.sha256(canonical_bytes).hexdigest()


def export_dataset(
    rows: List[TrajectoryRow],
    component_gt: List[ComponentGroundTruth],
    parameter_gt: List[ParameterGroundTruth],
    csv_path: str,
    meta_path: str,
    groundtruth_path: str,
    dataset_id: str,
    generator_version: str,
    random_seed: int,
    config_snapshot: dict,
) -> DatasetMetadata:
    """
    Export a complete synthetic dataset to:
        <csv_path>           — machine-readable trajectory CSV
        <meta_path>          — canonical provenance .meta.json
        <groundtruth_path>   — ground truth JSON (never used in production inference)

    Returns the DatasetMetadata object written to <meta_path>.

    Parameters
    ----------
    rows : list of TrajectoryRow
    component_gt : list of ComponentGroundTruth
    parameter_gt : list of ParameterGroundTruth
    csv_path : str
    meta_path : str
    groundtruth_path : str
    dataset_id : str
    generator_version : str
    random_seed : int
    config_snapshot : dict
        Lightweight snapshot of key generation config for traceability.
    """
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)

    # ---- Step 1: Canonicalize and compute SHA-256 BEFORE writing CSV -------
    canonical_bytes = _canonicalize_csv(rows)
    content_hash = compute_sha256(canonical_bytes)

    # ---- Step 2: Write canonical CSV (unmodified after hash computation) ---
    with open(csv_path, "wb") as f:
        f.write(canonical_bytes)

    # ---- Step 3: Write companion .meta.json (contains the hash) ------------
    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Derive lot/component counts from config snapshot for metadata
    num_lots = config_snapshot.get("num_lots", "?")
    components_per_lot = config_snapshot.get("components_per_lot", "?")

    metadata = DatasetMetadata(
        is_synthetic=True,
        generator_version=generator_version,
        random_seed=random_seed,
        dataset_id=dataset_id,
        content_hash_sha256=content_hash,
        num_lots=num_lots,
        components_per_lot=components_per_lot,
        total_rows=len(rows),
        generation_timestamp_utc=timestamp_utc,
    )

    meta_dict = {
        "is_synthetic": metadata.is_synthetic,
        "generator_version": metadata.generator_version,
        "random_seed": metadata.random_seed,
        "dataset_id": metadata.dataset_id,
        "content_hash_sha256": metadata.content_hash_sha256,
        "num_lots": metadata.num_lots,
        "components_per_lot": metadata.components_per_lot,
        "total_rows": metadata.total_rows,
        "generation_timestamp_utc": metadata.generation_timestamp_utc,
        "config_snapshot": config_snapshot,
        "disclaimer": metadata.disclaimer,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_dict, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # ---- Step 4: Write ground truth (separate; NEVER in production CSV) ----
    gt_dict = {
        "component_level": [dataclasses.asdict(c) for c in component_gt],
        "parameter_level": [dataclasses.asdict(p) for p in parameter_gt],
    }
    with open(groundtruth_path, "w", encoding="utf-8") as f:
        json.dump(gt_dict, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return metadata
