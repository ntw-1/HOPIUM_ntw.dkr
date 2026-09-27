#!/usr/bin/env python3
"""
scripts/run_risk_engine.py

Phase 5 integration script — Dynamic Risk Engine demo run.

Runs the Dynamic Risk Engine against the demo_burnin_data.csv dataset,
combining Module A population anomaly detection and Module B drift predictions
into per-component ComponentRiskAssessments.

PROTOTYPE NOTE: All risk outputs are advisory. Not official acceptance criteria.

Usage:
    python3 scripts/run_risk_engine.py
"""

import os
import sys

import pandas as pd

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.anomaly.detector import PopulationAnomalyDetector
from src.risk.engine import DynamicRiskEngine
from src.risk.explainability import (
    assessments_to_dataframe,
    format_component_assessment,
)
from src.risk.schema import RISK_HIGH, RISK_LOW, RISK_MEDIUM

DEMO_CSV = "data/demo_burnin_data.csv"
REGISTRY_DIR = "models/registered"
RISK_CONFIG = "configs/risk_engine_config.yaml"


def main():
    print("=" * 72)
    print("HOPIUM_sih26170 — Phase 5: Dynamic Risk Engine Integration Demo")
    print("=" * 72)
    print(
        "\n[DISCLAIMER] All risk outputs are PROTOTYPE advisory signals.\n"
        "Not official ISRO safety limits or engineering acceptance criteria.\n"
    )

    # --- Load data ---
    df = pd.read_csv(DEMO_CSV)
    print(f"Loaded: {DEMO_CSV}  ({len(df)} rows, {df['lot_id'].nunique()} lots, "
          f"{df['component_id'].nunique()} unique components)\n")

    # --- Initialise engines ---
    anomaly_detector = PopulationAnomalyDetector()
    risk_engine = DynamicRiskEngine(registry_dir=REGISTRY_DIR, config_path=RISK_CONFIG)
    print("Module A (Population Anomaly Detector) : ready")
    print("Module B (Production Predictors)       : ready for all parameters")
    print("Dynamic Risk Engine                    : ready\n")

    all_assessments = []

    lots = sorted(df["lot_id"].unique())
    for lot_id in lots:
        lot_df = df[df["lot_id"] == lot_id].copy()

        # Module A: detect anomalies for this lot
        lot_report = anomaly_detector.detect_anomalies(lot_df, lot_id=lot_id)

        # Risk engine: assess each component
        assessments = risk_engine.assess_lot(lot_report, lot_df)
        all_assessments.extend(assessments)

    # --- Summarise ---
    total = len(all_assessments)
    low_count = sum(1 for a in all_assessments if a.overall_risk_level == RISK_LOW)
    med_count = sum(1 for a in all_assessments if a.overall_risk_level == RISK_MEDIUM)
    high_count = sum(1 for a in all_assessments if a.overall_risk_level == RISK_HIGH)

    print(f"Risk Assessment Summary ({total} components):")
    print(f"  LOW    : {low_count:4d}  ({low_count/total*100:.1f}%)")
    print(f"  MEDIUM : {med_count:4d}  ({med_count/total*100:.1f}%)")
    print(f"  HIGH   : {high_count:4d}  ({high_count/total*100:.1f}%)")
    print()

    # --- Print one representative sample per risk level ---
    shown = set()
    for level in (RISK_LOW, RISK_MEDIUM, RISK_HIGH):
        for a in all_assessments:
            if a.overall_risk_level == level and level not in shown:
                print(f"\n--- Representative {level} example ---")
                print(format_component_assessment(a))
                shown.add(level)
                break

    # --- Save to reports/ ---
    os.makedirs("reports", exist_ok=True)
    out_df = assessments_to_dataframe(all_assessments)
    out_path = "reports/phase5_risk_assessments.csv"
    out_df.to_csv(out_path, index=False)
    print(f"\nFull risk assessment table saved: {out_path}")
    print(f"Columns: {list(out_df.columns[:8])} ... (+{len(out_df.columns)-8} more)")


if __name__ == "__main__":
    main()
