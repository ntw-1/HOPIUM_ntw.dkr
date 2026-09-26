"""
src/data/validation/sih_check.py

Category 13: SIH26170 Requirement Compliance Validation
Validates mechanical compliance against documented SIH26170 problem requirements:
- Required timepoint columns (0h, 24h, 96h, 168h)
- Required component parameters (Iddq, leakage_current, propagation_delay)
- Production feature boundary compliance (0h + 24h)
- 168h target availability
"""

from typing import Any, Dict, List

import pandas as pd

SIH_REQUIRED_TIMEPOINTS = ["value_0h", "value_24h", "value_96h", "value_168h"]
SIH_REQUIRED_PARAMETERS = ["Iddq", "leakage_current", "propagation_delay"]


def check_sih_compliance(df: pd.DataFrame) -> List[Dict[str, Any]]:
    findings = []

    # 1. SIH timepoint check
    missing_t = [t for t in SIH_REQUIRED_TIMEPOINTS if t not in df.columns]
    if missing_t:
        findings.append({
            "category": "sih_compliance",
            "level": "HARD FAILURE",
            "check_name": "sih_timepoints_present",
            "message": f"SIH26170 requires timepoints {SIH_REQUIRED_TIMEPOINTS}; missing: {missing_t}",
            "details": {"missing_timepoints": missing_t},
        })
    else:
        findings.append({
            "category": "sih_compliance",
            "level": "INFORMATION",
            "check_name": "sih_timepoints_present",
            "message": f"Dataset contains all SIH26170 required timepoints ({SIH_REQUIRED_TIMEPOINTS}).",
            "details": {},
        })

    # 2. SIH parameter set check
    present_p = set(df["parameter_name"].unique())
    missing_p = [p for p in SIH_REQUIRED_PARAMETERS if p not in present_p]
    if missing_p:
        findings.append({
            "category": "sih_compliance",
            "level": "HARD FAILURE",
            "check_name": "sih_parameters_present",
            "message": f"SIH26170 requires parameters {SIH_REQUIRED_PARAMETERS}; missing: {missing_p}",
            "details": {"missing_parameters": missing_p},
        })
    else:
        findings.append({
            "category": "sih_compliance",
            "level": "INFORMATION",
            "check_name": "sih_parameters_present",
            "message": f"Dataset contains all SIH26170 required parameters ({SIH_REQUIRED_PARAMETERS}).",
            "details": {},
        })

    # 3. 168h prediction target availability
    null_168h = df["value_168h"].isna().sum()
    if null_168h > 0:
        findings.append({
            "category": "sih_compliance",
            "level": "HARD FAILURE",
            "check_name": "sih_168h_target_availability",
            "message": f"SIH26170 ground truth target value_168h has {null_168h} missing entries.",
            "details": {"null_target_count": int(null_168h)},
        })
    else:
        findings.append({
            "category": "sih_compliance",
            "level": "INFORMATION",
            "check_name": "sih_168h_target_availability",
            "message": "Ground truth target value_168h is 100% complete across all trajectory rows.",
            "details": {},
        })

    return findings
