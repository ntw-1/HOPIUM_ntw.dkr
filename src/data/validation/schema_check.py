"""
src/data/validation/schema_check.py

Category 1: Schema Validation
Verifies required columns, unexpected/forbidden columns, data types,
allowed parameter names, allowed units, and expected timepoint columns.
"""

from typing import Any, Dict, List

import pandas as pd

REQUIRED_COLUMNS = [
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

ALLOWED_PARAMETERS = ["Iddq", "leakage_current", "propagation_delay"]
ALLOWED_UNITS = ["uA", "nA", "ps"]
PARAM_UNIT_MAP = {
    "Iddq": "uA",
    "leakage_current": "nA",
    "propagation_delay": "ps",
}


def check_schema(df: pd.DataFrame) -> List[Dict[str, Any]]:
    findings = []

    # 1. Required columns
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        findings.append({
            "category": "schema",
            "level": "HARD FAILURE",
            "check_name": "required_columns",
            "message": f"Dataset CSV is missing required columns: {missing_cols}",
            "details": {"missing_columns": missing_cols},
        })
        # Cannot run further column checks if columns are missing
        return findings

    findings.append({
        "category": "schema",
        "level": "INFORMATION",
        "check_name": "required_columns",
        "message": f"All {len(REQUIRED_COLUMNS)} required columns are present.",
        "details": {"required_columns": REQUIRED_COLUMNS},
    })

    # 2. Unexpected columns
    extra_cols = [c for c in df.columns if c not in REQUIRED_COLUMNS]
    if extra_cols:
        findings.append({
            "category": "schema",
            "level": "WARNING",
            "check_name": "unexpected_columns",
            "message": f"Dataset CSV contains unexpected extra columns: {extra_cols}",
            "details": {"extra_columns": extra_cols},
        })

    # 3. Allowed parameter names
    invalid_params = df[~df["parameter_name"].isin(ALLOWED_PARAMETERS)]["parameter_name"].unique().tolist()
    if invalid_params:
        findings.append({
            "category": "schema",
            "level": "HARD FAILURE",
            "check_name": "allowed_parameters",
            "message": f"Dataset contains invalid parameter names: {invalid_params}",
            "details": {"invalid_parameters": invalid_params},
        })
    else:
        findings.append({
            "category": "schema",
            "level": "INFORMATION",
            "check_name": "allowed_parameters",
            "message": f"All parameter names belong to allowed set {ALLOWED_PARAMETERS}.",
            "details": {},
        })

    # 4. Units check
    invalid_units = df[~df["unit"].isin(ALLOWED_UNITS)]["unit"].unique().tolist()
    if invalid_units:
        findings.append({
            "category": "schema",
            "level": "HARD FAILURE",
            "check_name": "allowed_units",
            "message": f"Dataset contains invalid units: {invalid_units}",
            "details": {"invalid_units": invalid_units},
        })

    # 5. Parameter-Unit consistency
    mismatches = []
    for param, expected_unit in PARAM_UNIT_MAP.items():
        subset = df[df["parameter_name"] == param]
        if not subset.empty:
            wrong_units = subset[subset["unit"] != expected_unit]["unit"].unique().tolist()
            if wrong_units:
                mismatches.append(f"{param}: expected {expected_unit}, found {wrong_units}")

    if mismatches:
        findings.append({
            "category": "schema",
            "level": "HARD FAILURE",
            "check_name": "parameter_unit_consistency",
            "message": f"Parameter-unit mismatches found: {mismatches}",
            "details": {"mismatches": mismatches},
        })
    else:
        findings.append({
            "category": "schema",
            "level": "INFORMATION",
            "check_name": "parameter_unit_consistency",
            "message": "All parameters match their designated measurement units.",
            "details": {},
        })

    # 6. Data type numeric checks for measurement columns
    numeric_cols = ["value_0h", "value_24h", "value_96h", "value_168h", "synthetic_spec_min", "synthetic_spec_max"]
    non_numeric = []
    for col in numeric_cols:
        if not pd.api.types.is_numeric_dtype(df[col]):
            non_numeric.append(col)

    if non_numeric:
        findings.append({
            "category": "schema",
            "level": "HARD FAILURE",
            "check_name": "numeric_datatypes",
            "message": f"Columns must be numeric: {non_numeric}",
            "details": {"non_numeric_columns": non_numeric},
        })

    return findings
