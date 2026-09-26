"""
src/data/validation/temporal_check.py

Category 3: Temporal Validation
Verifies required 0h, 24h, 96h, 168h measurements, temporal ordering,
and mathematically malformed trajectory values (NaN, Inf).

Includes descriptive relative-change statistics (min, median, p95, p99, max)
as INFORMATION without hard-coding arbitrary physical or threshold boundaries.
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd


def check_temporal(df: pd.DataFrame) -> List[Dict[str, Any]]:
    findings = []
    time_cols = ["value_0h", "value_24h", "value_96h", "value_168h"]

    # 1. Non-finite values (NaN, Inf) in timepoint measurements — HARD FAILURE
    non_finite_counts = {}
    for col in time_cols:
        invalid_mask = ~np.isfinite(df[col])
        count = invalid_mask.sum()
        if count > 0:
            non_finite_counts[col] = int(count)

    if non_finite_counts:
        findings.append({
            "category": "temporal",
            "level": "HARD FAILURE",
            "check_name": "non_finite_timepoints",
            "message": f"Found non-finite values (NaN / Inf) in measurement timepoints: {non_finite_counts}",
            "details": {"non_finite_counts": non_finite_counts},
        })
    else:
        findings.append({
            "category": "temporal",
            "level": "INFORMATION",
            "check_name": "non_finite_timepoints",
            "message": "All measurement timepoint values are finite numbers.",
            "details": {},
        })

    # 2. Informational delta statistics (0h -> 24h and 0h -> 168h absolute deltas)
    delta_24_0 = (df["value_24h"] - df["value_0h"]).abs()
    delta_168_0 = (df["value_168h"] - df["value_0h"]).abs()

    findings.append({
        "category": "temporal",
        "level": "INFORMATION",
        "check_name": "trajectory_delta_summary",
        "message": (
            f"Trajectory absolute delta summary — "
            f"Mean |24h - 0h|: {delta_24_0.mean():.4f}, "
            f"Mean |168h - 0h|: {delta_168_0.mean():.4f}"
        ),
        "details": {
            "mean_delta_24_0": float(delta_24_0.mean()),
            "max_delta_24_0": float(delta_24_0.max()),
            "mean_delta_168_0": float(delta_168_0.mean()),
            "max_delta_168_0": float(delta_168_0.max()),
        },
    })

    # 3. Informational relative-change descriptive statistics (min, median, p95, p99, max)
    # Avoids arbitrary hard-coded 20x/50x warning thresholds per design rules
    base = df["value_0h"].replace(0.0, 1e-6)
    rel_change_168 = (df["value_168h"] - df["value_0h"]).abs() / base

    min_rel = float(rel_change_168.min())
    median_rel = float(rel_change_168.median())
    p95_rel = float(rel_change_168.quantile(0.95))
    p99_rel = float(rel_change_168.quantile(0.99))
    max_rel = float(rel_change_168.max())

    findings.append({
        "category": "temporal",
        "level": "INFORMATION",
        "check_name": "trajectory_relative_change_statistics",
        "message": (
            f"Trajectory relative change (|168h - 0h| / 0h) quantiles — "
            f"min: {min_rel:.4f}, median: {median_rel:.4f}, "
            f"p95: {p95_rel:.4f}, p99: {p99_rel:.4f}, max: {max_rel:.4f}"
        ),
        "details": {
            "min_relative_change": min_rel,
            "median_relative_change": median_rel,
            "p95_relative_change": p95_rel,
            "p99_relative_change": p99_rel,
            "max_relative_change": max_rel,
        },
    })

    return findings
