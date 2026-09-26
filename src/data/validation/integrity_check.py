"""
src/data/validation/integrity_check.py

Category 2: Completeness / Integrity Validation
Verifies missing values, duplicate rows, duplicate keys, missing lot/component IDs,
and trajectory completeness across parameters per component.
"""

from typing import Any, Dict, List

import pandas as pd


def check_integrity(df: pd.DataFrame) -> List[Dict[str, Any]]:
    findings = []

    # 1. Missing / Null values in production input features (value_0h, value_24h)
    null_inputs = df[df["value_0h"].isna() | df["value_24h"].isna()]
    if not null_inputs.empty:
        findings.append({
            "category": "completeness",
            "level": "HARD FAILURE",
            "check_name": "null_production_inputs",
            "message": f"Found {len(null_inputs)} rows with NULL values in production input features (value_0h or value_24h).",
            "details": {"null_row_count": len(null_inputs)},
        })
    else:
        findings.append({
            "category": "completeness",
            "level": "INFORMATION",
            "check_name": "null_production_inputs",
            "message": "Zero NULL values found in production input features (value_0h, value_24h).",
            "details": {},
        })

    # 2. Missing values in target/reference columns
    null_targets = df[df["value_96h"].isna() | df["value_168h"].isna()]
    if not null_targets.empty:
        findings.append({
            "category": "completeness",
            "level": "WARNING",
            "check_name": "null_ground_truth_timepoints",
            "message": f"Found {len(null_targets)} rows with NULL values in reference timepoints (value_96h or value_168h).",
            "details": {"null_row_count": len(null_targets)},
        })

    # 3. Missing or empty string IDs
    if "lot_id" in df.columns and "component_id" in df.columns:
        empty_lot_ids = df[df["lot_id"].astype(str).str.strip() == ""]
        empty_comp_ids = df[df["component_id"].astype(str).str.strip() == ""]

        if not empty_lot_ids.empty or not empty_comp_ids.empty:
            findings.append({
                "category": "completeness",
                "level": "HARD FAILURE",
                "check_name": "empty_identifiers",
                "message": f"Found empty identifier strings: {len(empty_lot_ids)} empty lot_ids, {len(empty_comp_ids)} empty component_ids.",
                "details": {
                    "empty_lot_id_count": len(empty_lot_ids),
                    "empty_component_id_count": len(empty_comp_ids),
                },
            })

    # 4. Duplicate (lot_id, component_id, parameter_name) tuples
    if all(c in df.columns for c in ["lot_id", "component_id", "parameter_name"]):
        dup_keys = df[df.duplicated(subset=["lot_id", "component_id", "parameter_name"], keep=False)]
        if not dup_keys.empty:
            findings.append({
                "category": "completeness",
                "level": "HARD FAILURE",
                "check_name": "duplicate_component_parameter_keys",
                "message": f"Found {len(dup_keys)} duplicate rows sharing (lot_id, component_id, parameter_name) keys.",
                "details": {"duplicate_row_count": len(dup_keys)},
            })
        else:
            findings.append({
                "category": "completeness",
                "level": "INFORMATION",
                "check_name": "duplicate_component_parameter_keys",
                "message": "All (lot_id, component_id, parameter_name) keys are strictly unique.",
                "details": {},
            })

        # 5. Trajectory completeness per component (each component should have all 3 parameters)
        comp_param_counts = df.groupby(["lot_id", "component_id"])["parameter_name"].nunique()
        incomplete_comps = comp_param_counts[comp_param_counts < 3]
        if not incomplete_comps.empty:
            findings.append({
                "category": "completeness",
                "level": "HARD FAILURE",
                "check_name": "incomplete_component_trajectories",
                "message": f"Found {len(incomplete_comps)} components missing one or more of the 3 required parameter trajectories.",
                "details": {"incomplete_component_count": len(incomplete_comps)},
            })
        else:
            findings.append({
                "category": "completeness",
                "level": "INFORMATION",
                "check_name": "incomplete_component_trajectories",
                "message": "All components have complete parameter trajectory sets (all 3 parameters present).",
                "details": {},
            })


    return findings
