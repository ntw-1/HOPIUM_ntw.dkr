"""
src/data/validation/domain_check.py

Category 4: Range / Domain Validation
Verifies parameter-specific non-negativity (for Iddq, leakage_current, propagation_delay)
and synthetic reference limit consistency (spec_min < spec_max).
"""

from typing import Any, Dict, List

import pandas as pd

# Parameters requiring non-negative values
NON_NEGATIVE_PARAMS = ["Iddq", "leakage_current", "propagation_delay"]
TIME_COLS = ["value_0h", "value_24h", "value_96h", "value_168h"]


def check_domain(df: pd.DataFrame) -> List[Dict[str, Any]]:
    findings = []

    # 1. Non-negativity check
    neg_rows_count = 0
    for col in TIME_COLS:
        neg_mask = (df["parameter_name"].isin(NON_NEGATIVE_PARAMS)) & (df[col] < 0.0)
        neg_rows_count += int(neg_mask.sum())

    if neg_rows_count > 0:
        findings.append({
            "category": "domain",
            "level": "HARD FAILURE",
            "check_name": "non_negative_parameters",
            "message": f"Found {neg_rows_count} negative measurement values in non-negative parameters ({NON_NEGATIVE_PARAMS}).",
            "details": {"negative_value_count": neg_rows_count},
        })
    else:
        findings.append({
            "category": "domain",
            "level": "INFORMATION",
            "check_name": "non_negative_parameters",
            "message": "All measurements for non-negative parameters are >= 0.0.",
            "details": {},
        })

    # 2. Synthetic reference limit consistency (spec_min < spec_max)
    invalid_limits = df[df["synthetic_spec_min"] >= df["synthetic_spec_max"]]
    if not invalid_limits.empty:
        findings.append({
            "category": "domain",
            "level": "HARD FAILURE",
            "check_name": "synthetic_spec_limit_consistency",
            "message": f"Found {len(invalid_limits)} rows where synthetic_spec_min >= synthetic_spec_max.",
            "details": {"invalid_limit_rows": len(invalid_limits)},
        })
    else:
        findings.append({
            "category": "domain",
            "level": "INFORMATION",
            "check_name": "synthetic_spec_limit_consistency",
            "message": "All rows satisfy synthetic_spec_min < synthetic_spec_max.",
            "details": {},
        })

    return findings
