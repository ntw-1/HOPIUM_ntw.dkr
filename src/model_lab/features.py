"""
src/model_lab/features.py

Production feature matrix builder for Module B (Phase 3).

Production Feature Boundary (ML_CONTRACT.md + AGENTS.md):
    ALLOWED INPUTS:  value_0h, value_24h, delta_24_0
    TARGET (y only): value_168h
    STRICTLY FORBIDDEN FROM X: value_96h, value_168h, any ground-truth labels

Design notes:
    - The source CSV legitimately contains value_96h and value_168h.
      This module does NOT reject the source dataframe for containing those columns.
    - Instead, X is built from an explicit PRODUCTION_FEATURE_ALLOWLIST.
      Only the columns in the allowlist (after delta computation) enter X.
    - A runtime guard asserts the returned X has exactly the allowed columns.
    - value_168h is extracted separately and returned as y (for training/evaluation).
    - Ground-truth label columns are never passed into this module; they live in
      the separate groundtruth.json file and must never enter the feature pipeline.
"""

from typing import List, Tuple

import numpy as np
import pandas as pd

# Explicit production feature allowlist. Only these columns may appear in X.
PRODUCTION_FEATURE_ALLOWLIST: List[str] = ["value_0h", "value_24h", "delta_24_0"]

# Columns that must never appear in X — enforced by final assertion.
FORBIDDEN_IN_X: List[str] = [
    "value_96h",
    "value_168h",
    "behavioral_state",
    "is_latent_degrader",
    "is_population_anomaly",
    "is_reference_limit_breach",
    "anomaly_attributes",
    "early_detectability",
    "true_value_168h",
    "true_drift_168h",
]


def build_feature_matrix(
    df: pd.DataFrame,
    parameter: str,
    lot_filter: List[str],
) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Build the production feature matrix X and target y for one parameter.

    The source dataframe is in LONG format (one row per component-parameter pair).
    This function:
        1. Filters to the specified parameter and lot partition.
        2. Computes delta_24_0 = value_24h - value_0h.
        3. Constructs X using PRODUCTION_FEATURE_ALLOWLIST only.
        4. Extracts y = value_168h separately (for training/evaluation use).
        5. Asserts X contains exactly the allowed features and none of the
           forbidden features.

    Args:
        df:           Full long-format source DataFrame (may contain all columns).
        parameter:    One of: 'Iddq', 'leakage_current', 'propagation_delay'.
        lot_filter:   List of lot_ids to include (train, val, or blind partition).

    Returns:
        X (pd.DataFrame):      Feature matrix with columns [value_0h, value_24h, delta_24_0].
        y (pd.Series):         Target series of value_168h values.
        component_ids (pd.Series): Component identifiers aligned with X/y rows.
    """
    # Step 1: Filter rows for this parameter and lot partition
    mask = (df["parameter_name"] == parameter) & (df["lot_id"].isin(lot_filter))
    subset = df[mask].copy()

    if subset.empty:
        raise ValueError(
            f"No rows found for parameter='{parameter}' in lots={lot_filter[:3]}..."
        )

    # Step 2: Compute derived early feature
    subset["delta_24_0"] = subset["value_24h"] - subset["value_0h"]

    # Step 3: Build X using explicit allowlist ONLY — no column from source
    #         dataframe enters X unless it is in PRODUCTION_FEATURE_ALLOWLIST.
    X = subset[PRODUCTION_FEATURE_ALLOWLIST].copy()

    # Step 4: Extract y separately (target, not a feature)
    y = subset["value_168h"].copy()

    # Step 5: Component identifiers for traceability
    component_ids = subset["component_id"].copy()

    # Step 6: Runtime leakage guard — assert X has exactly the allowed columns
    #         and none of the forbidden ones.
    _assert_feature_boundary(X)

    return X.reset_index(drop=True), y.reset_index(drop=True), component_ids.reset_index(drop=True)


def _assert_feature_boundary(X: pd.DataFrame) -> None:
    """
    Hard runtime assertion: X must contain exactly PRODUCTION_FEATURE_ALLOWLIST columns.

    Raises ValueError if:
      - Any column outside PRODUCTION_FEATURE_ALLOWLIST is present in X.
      - Any known forbidden column (value_96h, value_168h, ground-truth labels) is in X.
      - Any required feature column is missing from X.
    """
    actual_cols = set(X.columns.tolist())
    allowed_cols = set(PRODUCTION_FEATURE_ALLOWLIST)
    forbidden_cols = set(FORBIDDEN_IN_X)

    # Check for forbidden columns
    found_forbidden = actual_cols & forbidden_cols
    if found_forbidden:
        raise ValueError(
            f"PRODUCTION FEATURE LEAKAGE DETECTED: "
            f"Forbidden columns found in feature matrix X: {sorted(found_forbidden)}. "
            f"Only {PRODUCTION_FEATURE_ALLOWLIST} are permitted."
        )

    # Check for unexpected columns beyond allowlist
    unexpected = actual_cols - allowed_cols
    if unexpected:
        raise ValueError(
            f"Feature matrix X contains columns outside the production allowlist: "
            f"{sorted(unexpected)}. Allowed: {PRODUCTION_FEATURE_ALLOWLIST}"
        )

    # Check all required features are present
    missing = allowed_cols - actual_cols
    if missing:
        raise ValueError(
            f"Feature matrix X is missing required production features: {sorted(missing)}"
        )
