"""
src/data/validation/structure_check.py

Category 6: Correlation / Structure Sanity Validation
Inspects empirical cross-parameter correlation structure at 0h and compares against
configured expectation. Reports as WARNING/INFO rather than hard failure.
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

PARAMETERS = ["Iddq", "leakage_current", "propagation_delay"]


def check_structure(df: pd.DataFrame, config: dict = None) -> List[Dict[str, Any]]:
    findings = []

    # 1. Pivot dataframe to component level for correlation calculation
    try:
        pivot_0h = df.pivot(index=["lot_id", "component_id"], columns="parameter_name", values="value_0h")
    except Exception as exc:
        findings.append({
            "category": "correlation_structure",
            "level": "WARNING",
            "check_name": "empirical_correlation_matrix",
            "message": f"Cannot compute empirical correlation matrix due to pivot error: {exc}",
            "details": {},
        })
        return findings

    # Ensure all parameters exist in pivot
    missing_p = [p for p in PARAMETERS if p not in pivot_0h.columns]
    if missing_p:
        findings.append({
            "category": "correlation_structure",
            "level": "WARNING",
            "check_name": "empirical_correlation_matrix",
            "message": f"Cannot compute empirical correlation matrix; missing parameters: {missing_p}",
            "details": {},
        })
        return findings


    # Compute empirical correlation matrix R_emp
    corr_matrix = pivot_0h[PARAMETERS].corr()
    r_emp = corr_matrix.to_dict()

    findings.append({
        "category": "correlation_structure",
        "level": "INFORMATION",
        "check_name": "empirical_correlation_matrix",
        "message": "Computed empirical cross-parameter correlation matrix R_emp at 0h.",
        "details": {"empirical_correlation_matrix": r_emp},
    })

    # 2. Compare against R_config if config is provided
    if config and "cross_parameter_correlation" in config:
        try:
            r_cfg = np.array(config["cross_parameter_correlation"]["R_matrix"])
            r_actual = corr_matrix.values

            diff = np.abs(r_actual - r_cfg)
            max_diff = float(np.max(diff))

            if max_diff > 0.35:
                findings.append({
                    "category": "correlation_structure",
                    "level": "WARNING",
                    "check_name": "correlation_matrix_deviation",
                    "message": f"Empirical correlation matrix R_emp deviates from configured R_matrix (max diff = {max_diff:.3f}).",
                    "details": {"max_absolute_difference": max_diff},
                })
            else:
                findings.append({
                    "category": "correlation_structure",
                    "level": "INFORMATION",
                    "check_name": "correlation_matrix_deviation",
                    "message": f"Empirical correlation matrix matches configured structure well (max diff = {max_diff:.3f}).",
                    "details": {"max_absolute_difference": max_diff},
                })
        except Exception as e:
            findings.append({
                "category": "correlation_structure",
                "level": "WARNING",
                "check_name": "correlation_matrix_deviation",
                "message": f"Could not compare empirical correlation with config: {e}",
                "details": {},
            })

    return findings
