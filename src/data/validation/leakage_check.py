"""
src/data/validation/leakage_check.py

Category 11: Feature Boundary & Target Isolation Contract Validation
Validates documented feature-boundary contract:
- Verifies dataset CSV contains required 0h/24h inputs and 96h/168h target/history fields
- Verifies ground-truth classification fields are NOT embedded in the dataset CSV
- Documents that Phase 3 Model Lab must independently enforce feature boundary
  when building model feature matrices.
"""

from typing import Any, Dict, List

import pandas as pd

# Ground-truth classification fields that must NEVER appear in the raw CSV
FORBIDDEN_GT_COLUMNS_IN_CSV = [
    "behavioral_state",
    "is_latent_degrader",
    "is_population_anomaly",
    "is_reference_limit_breach",
    "anomaly_attributes",
    "severity_level",
    "early_detectability",
    "true_value_168h",
    "true_drift_168h",
]


def check_leakage(df: pd.DataFrame) -> List[Dict[str, Any]]:
    findings = []

    # 1. Check if any ground truth classification columns are embedded in the CSV
    found_gt_cols = [c for c in FORBIDDEN_GT_COLUMNS_IN_CSV if c in df.columns]
    if found_gt_cols:
        findings.append({
            "category": "feature_leakage",
            "level": "HARD FAILURE",
            "check_name": "ground_truth_embedded_in_csv",
            "message": f"Ground-truth classification columns found inside dataset CSV: {found_gt_cols}. Ground truth must be stored separately!",
            "details": {"forbidden_columns_found": found_gt_cols},
        })
    else:
        findings.append({
            "category": "feature_leakage",
            "level": "INFORMATION",
            "check_name": "ground_truth_embedded_in_csv",
            "message": "Zero ground-truth classification fields found in dataset CSV.",
            "details": {},
        })

    # 2. Verify presence of early production input columns (value_0h, value_24h) and target fields (value_96h, value_168h)
    has_inputs = "value_0h" in df.columns and "value_24h" in df.columns
    has_targets = "value_96h" in df.columns and "value_168h" in df.columns

    if not has_inputs or not has_targets:
        findings.append({
            "category": "feature_leakage",
            "level": "HARD FAILURE",
            "check_name": "trajectory_field_structure",
            "message": "CSV must contain both early production inputs (value_0h, value_24h) and target timepoints (value_96h, value_168h).",
            "details": {"has_inputs": has_inputs, "has_targets": has_targets},
        })
    else:
        findings.append({
            "category": "feature_leakage",
            "level": "INFORMATION",
            "check_name": "trajectory_field_structure",
            "message": (
                "CSV structure contains required 0h/24h production input fields and 96h/168h reference/target fields. "
                "Phase 3 Model Lab must independently isolate [value_0h, value_24h] during feature extraction."
            ),
            "details": {},
        })

    return findings
