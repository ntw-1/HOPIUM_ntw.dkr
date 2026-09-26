"""
src/data/validation/split_check.py

Category 12: Split-Readiness Validation
Verifies lot-level partitioning prerequisites: minimum lot count >= 3
and balanced lot component counts for Train / Validation / Locked Blind-Test splitting.
"""

from typing import Any, Dict, List

import pandas as pd


def check_split(df: pd.DataFrame) -> List[Dict[str, Any]]:
    findings = []

    if "lot_id" not in df.columns:
        return findings

    lots = df["lot_id"].unique()
    num_lots = len(lots)


    # 1. Minimum lot count check (need at least 3 lots for train/val/test split)
    if num_lots < 3:
        findings.append({
            "category": "split_readiness",
            "level": "HARD FAILURE",
            "check_name": "minimum_lot_count_for_split",
            "message": f"Dataset contains only {num_lots} lots. Minimum 3 lots required for lot-level train/validation/locked-blind-test splitting.",
            "details": {"lot_count": num_lots},
        })
    else:
        findings.append({
            "category": "split_readiness",
            "level": "INFORMATION",
            "check_name": "minimum_lot_count_for_split",
            "message": f"Dataset contains {num_lots} distinct lots, meeting the lot-level partitioning requirement.",
            "details": {"lot_count": num_lots},
        })

    # 2. Lot balance check
    comps_per_lot = df.groupby("lot_id")["component_id"].nunique()
    min_comps = comps_per_lot.min()
    max_comps = comps_per_lot.max()

    if min_comps < 5:
        findings.append({
            "category": "split_readiness",
            "level": "WARNING",
            "check_name": "lot_size_balance",
            "message": f"Some lots have very few components (min = {min_comps}). Recommended min = 10 components/lot.",
            "details": {"min_components_per_lot": int(min_comps), "max_components_per_lot": int(max_comps)},
        })
    else:
        findings.append({
            "category": "split_readiness",
            "level": "INFORMATION",
            "check_name": "lot_size_balance",
            "message": f"Lot size distribution is balanced (range: {min_comps} to {max_comps} components/lot).",
            "details": {"min_components_per_lot": int(min_comps), "max_components_per_lot": int(max_comps)},
        })

    return findings
