"""Normalize the legacy SIH26170 wide CSVs into HOPIUM's long CSV schema.

The source files contain generated burn-in trajectories.  In particular,
``nasa_real_dataset.csv`` starts with NASA PCoE-derived device baselines but then
generates its 24h, 96h and 168h trajectories.  The adapter preserves that
distinction in companion metadata so it cannot be presented as a real-world
prediction benchmark.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List


CANONICAL_FIELDS = [
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

# Legacy source units are explicitly documented in SIH26170's extractor.
# Values are converted to HOPIUM's canonical units before model use.
PARAMETER_MAPPINGS = (
    ("iddq", "Iddq", "uA", 1000.0, 0.0, 5000.0),
    ("lc", "leakage_current", "nA", 1000.0, 0.0, 50000.0),
    ("pd", "propagation_delay", "ps", 1000.0, 0.0, 120000.0),
)


def convert_wide_rows(source_path: str | Path) -> List[Dict[str, object]]:
    """Convert a legacy 37-column SIH CSV into HOPIUM long trajectory rows."""
    path = Path(source_path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Source CSV has no header: {path}")

        required = {"lot_id", "component_id"}
        for prefix, *_ in PARAMETER_MAPPINGS:
            required.update(f"{prefix}_{time}h" for time in (0, 24, 96, 168))
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise ValueError(f"Source CSV is missing required columns: {missing}")

        converted: List[Dict[str, object]] = []
        for row_index, source in enumerate(reader, start=2):
            for prefix, parameter, unit, factor, spec_min, spec_max in PARAMETER_MAPPINGS:
                try:
                    values = {
                        f"value_{time}h": float(source[f"{prefix}_{time}h"]) * factor
                        for time in (0, 24, 96, 168)
                    }
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Invalid {prefix} trajectory at source row {row_index} in {path.name}"
                    ) from exc

                converted.append({
                    "lot_id": source["lot_id"],
                    "component_id": source["component_id"],
                    "parameter_name": parameter,
                    "unit": unit,
                    **values,
                    "synthetic_spec_min": spec_min,
                    "synthetic_spec_max": spec_max,
                })
    return converted


def _canonical_csv_bytes(rows: Iterable[Dict[str, object]]) -> bytes:
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CANONICAL_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        formatted = {
            key: f"{float(row[key]):.6f}"
            if key.startswith("value_") or key.startswith("synthetic_spec_")
            else row[key]
            for key in CANONICAL_FIELDS
        }
        writer.writerow(formatted)
    return buffer.getvalue().rstrip("\n").encode("utf-8") + b"\n"


def export_converted_dataset(
    source_path: str | Path,
    output_csv: str | Path,
    output_meta: str | Path,
    *,
    dataset_id: str,
    source_description: str,
    lot_split_eligible: bool,
) -> Dict[str, object]:
    """Write converted data plus auditable synthetic/provenance metadata."""
    source = Path(source_path)
    csv_path = Path(output_csv)
    meta_path = Path(output_meta)
    rows = convert_wide_rows(source)
    canonical = _canonical_csv_bytes(rows)
    content_hash = hashlib.sha256(canonical).hexdigest()
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_bytes(canonical)

    metadata: Dict[str, object] = {
        "is_synthetic": True,
        "generator_version": "sih26170-wide-to-hopium-adapter-v1.0.0",
        "random_seed": 26170,
        "dataset_id": dataset_id,
        "content_hash_sha256": content_hash,
        "num_lots": len({str(row["lot_id"]) for row in rows}),
        "components_per_lot": "variable",
        "total_rows": len(rows),
        "source_dataset": {
            "filename": source.name,
            "sha256": source_hash,
            "description": source_description,
            "trajectory_status": "generated / synthetic",
        },
        "unit_transformations": {
            "iddq_mA_to_uA": 1000.0,
            "lc_uA_to_leakage_current_nA": 1000.0,
            "pd_ns_to_propagation_delay_ps": 1000.0,
        },
        "lot_split_eligible": lot_split_eligible,
        "disclaimer": (
            "SYNTHETIC / DERIVED DATASET. This converted dataset is not real ISRO or "
            "industrial screening data and must not be used to claim real-world accuracy."
        ),
    }
    if not lot_split_eligible:
        metadata["model_selection_restriction"] = (
            "Not eligible for Model Lab training or selection because it has fewer than "
            "three independent lots required for train/validation/locked-blind splitting."
        )

    meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata
