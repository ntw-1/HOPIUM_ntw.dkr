"""
src/data/validation/statistical_check.py

Category 5: Distribution / Statistical Sanity Validation
Calculates lot counts, component counts, summary statistics, and checks for extreme values.
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd


def check_statistical(df: pd.DataFrame) -> List[Dict[str, Any]]:
    findings = []

    lots = df["lot_id"].unique() if "lot_id" in df.columns else []
    comps = df["component_id"].unique() if "component_id" in df.columns else []
    total_rows = len(df)

    # 1. General counts
    findings.append({
        "category": "statistical_sanity",
        "level": "INFORMATION",
        "check_name": "dataset_counts",
        "message": f"Dataset contains {len(lots)} lots, {len(comps)} unique components, and {total_rows} total rows.",
        "details": {
            "num_lots": len(lots),
            "num_components": len(comps),
            "total_rows": total_rows,
        },
    })

    # 2. Per-parameter summary statistics
    if "parameter_name" in df.columns:
        param_stats = {}
        for param in df["parameter_name"].unique():
            subset = df[df["parameter_name"] == param]
            v0 = subset["value_0h"] if "value_0h" in subset.columns else pd.Series()
            v24 = subset["value_24h"] if "value_24h" in subset.columns else pd.Series()
            v168 = subset["value_168h"] if "value_168h" in subset.columns else pd.Series()

            param_stats[param] = {
                "count": len(subset),
                "value_0h_mean": float(v0.mean()) if not v0.empty else None,
                "value_0h_std": float(v0.std()) if not v0.empty else None,
                "value_0h_min": float(v0.min()) if not v0.empty else None,
                "value_0h_max": float(v0.max()) if not v0.empty else None,
                "value_24h_mean": float(v24.mean()) if not v24.empty else None,
                "value_168h_mean": float(v168.mean()) if not v168.empty else None,
            }

        findings.append({
            "category": "statistical_sanity",
            "level": "INFORMATION",
            "check_name": "parameter_summary_statistics",
            "message": "Computed per-parameter summary statistics across all timepoints.",
            "details": {"parameter_statistics": param_stats},
        })

    # 3. Extreme value check (> 6 sigma from global parameter mean) - WARNING
    if "parameter_name" in df.columns and "value_0h" in df.columns:
        extreme_count = 0
        for param in df["parameter_name"].unique():
            subset = df[df["parameter_name"] == param]
            mean_v0 = subset["value_0h"].mean()
            std_v0 = subset["value_0h"].std()
            if pd.notna(std_v0) and std_v0 > 0:
                z_scores = (subset["value_0h"] - mean_v0).abs() / std_v0
                extreme = subset[z_scores > 6.0]
                extreme_count += len(extreme)

        if extreme_count > 0:
            findings.append({
                "category": "statistical_sanity",
                "level": "WARNING",
                "check_name": "extreme_value_outliers",
                "message": f"Found {extreme_count} parameter rows with value_0h > 6 sigma from parameter mean. Review recommended.",
                "details": {"extreme_outlier_count": extreme_count},
            })
        else:
            findings.append({
                "category": "statistical_sanity",
                "level": "INFORMATION",
                "check_name": "extreme_value_outliers",
                "message": "No extreme outliers (>6 sigma from global mean) observed.",
                "details": {},
            })

    return findings

