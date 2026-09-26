"""
src/data/validation/prevalence_check.py

Categories 7 & 8: Anomaly Prevalence & Latent-Degradation Sanity Validation
Evaluates ground-truth scenario distributions and early-detectability spectrum
without introducing arbitrary hard failure thresholds on single trajectory deltas.
"""

from typing import Any, Dict, List

import pandas as pd


def check_prevalence(df: pd.DataFrame, groundtruth: dict = None) -> List[Dict[str, Any]]:
    findings = []

    if not groundtruth or "component_level" not in groundtruth:
        findings.append({
            "category": "anomaly_prevalence",
            "level": "INFORMATION",
            "check_name": "ground_truth_prevalence",
            "message": "No companion groundtruth dictionary provided; skipping ground-truth prevalence check.",
            "details": {},
        })
        return findings

    comp_gt = groundtruth["component_level"]
    total_comps = len(comp_gt)

    if total_comps == 0:
        findings.append({
            "category": "anomaly_prevalence",
            "level": "HARD FAILURE",
            "check_name": "empty_ground_truth",
            "message": "Ground truth component_level list is empty.",
            "details": {},
        })
        return findings

    # 1. Ground truth prevalence counts
    nominal_cnt = sum(1 for c in comp_gt if c.get("behavioral_state") == "nominal")
    latent_cnt = sum(1 for c in comp_gt if c.get("is_latent_degrader", False))
    pop_anomaly_cnt = sum(1 for c in comp_gt if c.get("is_population_anomaly", False))
    ref_breach_cnt = sum(1 for c in comp_gt if c.get("is_reference_limit_breach", False))

    findings.append({
        "category": "anomaly_prevalence",
        "level": "INFORMATION",
        "check_name": "ground_truth_prevalence_summary",
        "message": (
            f"Ground truth prevalence — "
            f"Nominal: {nominal_cnt}/{total_comps} ({nominal_cnt/total_comps*100:.1f}%), "
            f"Latent Degradation: {latent_cnt}/{total_comps} ({latent_cnt/total_comps*100:.1f}%), "
            f"Population Anomaly: {pop_anomaly_cnt}/{total_comps} ({pop_anomaly_cnt/total_comps*100:.1f}%), "
            f"Reference Breach: {ref_breach_cnt}/{total_comps} ({ref_breach_cnt/total_comps*100:.1f}%)."
        ),
        "details": {
            "total_components": total_comps,
            "nominal_count": nominal_cnt,
            "latent_degradation_count": latent_cnt,
            "population_anomaly_count": pop_anomaly_cnt,
            "reference_limit_breach_count": ref_breach_cnt,
        },
    })

    # 2. Category 8: Latent Detectability Spectrum Validation (Correction 1)
    # - missing/invalid early_detectability labels -> HARD FAILURE
    # - clearly inconsistent detectability distribution -> WARNING
    # - descriptive Delta_24_0 statistics -> INFORMATION
    latent_comps = [c for c in comp_gt if c.get("is_latent_degrader", False)]
    if latent_comps:
        valid_ed_levels = {"hidden", "subtle", "moderate", "strong"}
        missing_ed = [c["component_id"] for c in latent_comps if c.get("early_detectability") not in valid_ed_levels]

        if missing_ed:
            findings.append({
                "category": "latent_detectability",
                "level": "HARD FAILURE",
                "check_name": "early_detectability_labels",
                "message": f"Found {len(missing_ed)} latent degradation components with missing or invalid early_detectability labels.",
                "details": {"invalid_component_ids": missing_ed},
            })
        else:
            findings.append({
                "category": "latent_detectability",
                "level": "INFORMATION",
                "check_name": "early_detectability_labels",
                "message": "All latent degradation components carry valid early_detectability labels.",
                "details": {},
            })

        # Check detectability distribution
        ed_counts = {}
        for level in valid_ed_levels:
            ed_counts[level] = sum(1 for c in latent_comps if c.get("early_detectability") == level)

        # Warning if hidden degraders are completely absent in a large latent set (>10)
        if len(latent_comps) >= 10 and ed_counts.get("hidden", 0) == 0:
            findings.append({
                "category": "latent_detectability",
                "level": "WARNING",
                "check_name": "detectability_spectrum_distribution",
                "message": "Latent degradation set contains zero 'hidden' early_detectability components. Spectrum may be incomplete.",
                "details": {"early_detectability_counts": ed_counts},
            })
        else:
            findings.append({
                "category": "latent_detectability",
                "level": "INFORMATION",
                "check_name": "detectability_spectrum_distribution",
                "message": f"Latent detectability distribution across levels: {ed_counts}",
                "details": {"early_detectability_counts": ed_counts},
            })

        # Calculate descriptive Delta_24_0 statistics for latent degraders (INFORMATION)
        latent_ids = {c["component_id"] for c in latent_comps}
        latent_df = df[df["component_id"].isin(latent_ids)]
        if not latent_df.empty:
            delta_24_0 = (latent_df["value_24h"] - latent_df["value_0h"]).abs()
            findings.append({
                "category": "latent_detectability",
                "level": "INFORMATION",
                "check_name": "latent_early_delta_descriptive_stats",
                "message": f"Latent degraders early delta (0h->24h) descriptive statistics — mean: {delta_24_0.mean():.4f}, std: {delta_24_0.std():.4f}, max: {delta_24_0.max():.4f}.",
                "details": {
                    "mean_delta_24_0": float(delta_24_0.mean()),
                    "std_delta_24_0": float(delta_24_0.std()),
                    "max_delta_24_0": float(delta_24_0.max()),
                },
            })

    return findings
