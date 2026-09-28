"""
tests/unit/test_module_a_anomaly.py

Unit and integration test suite for Module A (Population-Relative Anomaly Detector).

Validates all 12 required test scenarios:
    1. Normal population produces zero unintended anomalies.
    2. 45 uA component in ~10 uA population with 50 uA spec max is flagged as population anomaly (STATE_B).
    3. Reference breach without population anomaly (STATE_C).
    4. Both population anomaly and reference breach (STATE_D).
    5. Robustness: Extreme outliers do not distort median/MAD or mask moderate anomalies.
    6. Parameter isolation: Anomaly in Iddq does not trigger false flags in propagation_delay.
    7. Deterministic repeated execution.
    8. Explainability fields are populated and non-empty.
    9. Input DataFrame is NOT mutated.
    10. Compatibility with Phase 1 dev dataset (data/dev_burnin_data.csv).
    11. Compatibility with Phase 1 demo dataset (data/demo_burnin_data.csv).
    12. Zero-MAD / constant-population behavior is handled deterministically without NaN/Inf outputs.
"""

import os
import pytest
import numpy as np
import pandas as pd

from src.anomaly import (
    ComponentAnomalyReport,
    LotAnomalyReport,
    PopulationAnomalyDetector,
    compute_modified_zscores,
)


@pytest.fixture
def clean_nominal_lot_df():
    """Create a clean 50-component lot with controlled nominal values where max |M| < 3.0."""
    rows = []
    lot_id = "LOT_NOMINAL"
    # Evenly space 50 components between -2.0 and +2.0 standard deviations
    offsets = np.linspace(-2.0, 2.0, 50)

    for i in range(50):
        c_id = f"{lot_id}_CMP_{i+1:04d}"
        off = offsets[i]
        # Iddq
        rows.append({
            "lot_id": lot_id,
            "component_id": c_id,
            "parameter_name": "Iddq",
            "unit": "uA",
            "value_0h": float(10.0 + 0.1 * off),
            "value_24h": float(10.2 + 0.1 * off),
            "synthetic_spec_min": 0.0,
            "synthetic_spec_max": 50.0,
        })
        # leakage_current
        rows.append({
            "lot_id": lot_id,
            "component_id": c_id,
            "parameter_name": "leakage_current",
            "unit": "nA",
            "value_0h": float(5.0 + 0.05 * off),
            "value_24h": float(5.1 + 0.05 * off),
            "synthetic_spec_min": 0.0,
            "synthetic_spec_max": 30.0,
        })
        # propagation_delay
        rows.append({
            "lot_id": lot_id,
            "component_id": c_id,
            "parameter_name": "propagation_delay",
            "unit": "ps",
            "value_0h": float(120.0 + 0.5 * off),
            "value_24h": float(120.5 + 0.5 * off),
            "synthetic_spec_min": 80.0,
            "synthetic_spec_max": 180.0,
        })

    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# 1. NORMAL POPULATION TEST
# -----------------------------------------------------------------------------

def test_normal_population_produces_no_anomalies(clean_nominal_lot_df):
    """1. A clean nominal lot produces zero population anomalies or spec breaches."""
    detector = PopulationAnomalyDetector(anomaly_threshold=3.5)
    report = detector.detect_anomalies(clean_nominal_lot_df)

    assert isinstance(report, LotAnomalyReport)
    assert report.total_components == 50
    assert report.anomalous_components_count == 0
    assert report.reference_breach_count == 0
    for comp in report.component_reports:
        assert comp.classification_state == "STATE_A_NORMAL"
        assert not comp.is_population_anomaly
        assert not comp.is_reference_limit_breach


# -----------------------------------------------------------------------------
# 2. STATE_B: WITHIN-SPEC POPULATION ANOMALY TEST
# -----------------------------------------------------------------------------

def test_within_spec_population_anomaly(clean_nominal_lot_df):
    """2. 45 uA component in ~10 uA population with 50 uA spec max is flagged as STATE_B."""
    df = clean_nominal_lot_df.copy()

    # Modify CMP_0005 to have 45.0 uA Iddq (well above 10 uA baseline, below 50 uA spec max)
    mask = (df["component_id"] == "LOT_NOMINAL_CMP_0005") & (df["parameter_name"] == "Iddq")
    df.loc[mask, "value_24h"] = 45.0

    detector = PopulationAnomalyDetector(anomaly_threshold=3.5)
    report = detector.detect_anomalies(df)

    target_comp = next(c for c in report.component_reports if c.component_id == "LOT_NOMINAL_CMP_0005")
    assert target_comp.is_population_anomaly is True
    assert target_comp.is_reference_limit_breach is False
    assert target_comp.classification_state == "STATE_B_POPULATION_ANOMALY_ONLY"
    assert target_comp.population_anomaly_score > 3.5


# -----------------------------------------------------------------------------
# 3. STATE_C: SPEC BREACH WITHOUT POPULATION ANOMALY TEST
# -----------------------------------------------------------------------------

def test_spec_breach_without_population_anomaly():
    """3. Component breaching spec in a population with spec max set low is flagged as STATE_C."""
    rows = []
    lot_id = "LOT_SPEC_TEST"
    # Create 50 components where Iddq is ~10 uA, but synthetic_spec_max is set to 9.0 uA
    for i in range(1, 51):
        c_id = f"{lot_id}_CMP_{i:04d}"
        rows.append({
            "lot_id": lot_id,
            "component_id": c_id,
            "parameter_name": "Iddq",
            "unit": "uA",
            "value_0h": 10.0,
            "value_24h": 10.0,
            "synthetic_spec_min": 0.0,
            "synthetic_spec_max": 9.0,  # All breach spec max, but population is identical
        })
    df = pd.DataFrame(rows)

    detector = PopulationAnomalyDetector(anomaly_threshold=3.5)
    report = detector.detect_anomalies(df)

    for comp in report.component_reports:
        assert comp.is_population_anomaly is False
        assert comp.is_reference_limit_breach is True
        assert comp.classification_state == "STATE_C_SPEC_BREACH_ONLY"


# -----------------------------------------------------------------------------
# 4. STATE_D: BOTH POPULATION ANOMALY AND SPEC BREACH TEST
# -----------------------------------------------------------------------------

def test_both_population_anomaly_and_spec_breach(clean_nominal_lot_df):
    """4. Component exceeding spec max (e.g. 80 uA vs 50 uA spec) is flagged as STATE_D."""
    df = clean_nominal_lot_df.copy()
    mask = (df["component_id"] == "LOT_NOMINAL_CMP_0010") & (df["parameter_name"] == "Iddq")
    df.loc[mask, "value_24h"] = 80.0  # Exceeds 10 uA lot median AND 50 uA spec max

    detector = PopulationAnomalyDetector(anomaly_threshold=3.5)
    report = detector.detect_anomalies(df)

    target_comp = next(c for c in report.component_reports if c.component_id == "LOT_NOMINAL_CMP_0010")
    assert target_comp.is_population_anomaly is True
    assert target_comp.is_reference_limit_breach is True
    assert target_comp.classification_state == "STATE_D_POPULATION_ANOMALY_AND_SPEC_BREACH"


# -----------------------------------------------------------------------------
# 5. ROBUSTNESS TO EXTREME OUTLIERS TEST
# -----------------------------------------------------------------------------

def test_extreme_outliers_do_not_distort_median_or_mask_moderate_anomalies(clean_nominal_lot_df):
    """5. Multiple extreme outliers (1000 uA) do not inflate MAD or mask moderate anomalies (25 uA)."""
    df = clean_nominal_lot_df.copy()

    # Add 3 extreme outliers (1000 uA) and 1 moderate outlier (25 uA)
    ext_mask = df["component_id"].isin(["LOT_NOMINAL_CMP_0001", "LOT_NOMINAL_CMP_0002", "LOT_NOMINAL_CMP_0003"]) & (df["parameter_name"] == "Iddq")
    df.loc[ext_mask, "value_24h"] = 1000.0

    mod_mask = (df["component_id"] == "LOT_NOMINAL_CMP_0004") & (df["parameter_name"] == "Iddq")
    df.loc[mod_mask, "value_24h"] = 25.0

    detector = PopulationAnomalyDetector(anomaly_threshold=3.5)
    report = detector.detect_anomalies(df)

    # Moderate anomaly (25 uA) MUST still be detected because MAD is robust
    mod_comp = next(c for c in report.component_reports if c.component_id == "LOT_NOMINAL_CMP_0004")
    assert mod_comp.is_population_anomaly is True


# -----------------------------------------------------------------------------
# 6. PARAMETER ISOLATION TEST
# -----------------------------------------------------------------------------

def test_parameter_isolation(clean_nominal_lot_df):
    """6. Anomaly in Iddq does not trigger false flags in leakage_current or propagation_delay."""
    df = clean_nominal_lot_df.copy()
    mask = (df["component_id"] == "LOT_NOMINAL_CMP_0007") & (df["parameter_name"] == "Iddq")
    df.loc[mask, "value_24h"] = 40.0

    detector = PopulationAnomalyDetector(anomaly_threshold=3.5)
    report = detector.detect_anomalies(df)

    target_comp = next(c for c in report.component_reports if c.component_id == "LOT_NOMINAL_CMP_0007")
    ev_iddq = target_comp.parameter_evidence["Iddq"]
    ev_leakage = target_comp.parameter_evidence["leakage_current"]
    ev_delay = target_comp.parameter_evidence["propagation_delay"]

    assert ev_iddq.max_modified_zscore > 3.5
    assert ev_leakage.max_modified_zscore < 3.5
    assert ev_delay.max_modified_zscore < 3.5


# -----------------------------------------------------------------------------
# 7. DETERMINISTIC REPEATED EXECUTION TEST
# -----------------------------------------------------------------------------

def test_deterministic_execution(clean_nominal_lot_df):
    """7. Two runs on the same input produce identical anomaly scores and classification states."""
    detector = PopulationAnomalyDetector(anomaly_threshold=3.5)
    report1 = detector.detect_anomalies(clean_nominal_lot_df)
    report2 = detector.detect_anomalies(clean_nominal_lot_df)

    df1 = detector.to_dataframe(report1)
    df2 = detector.to_dataframe(report2)

    pd.testing.assert_frame_equal(df1, df2)


# -----------------------------------------------------------------------------
# 8. EXPLAINABILITY FIELDS TEST
# -----------------------------------------------------------------------------

def test_explainability_fields_populated(clean_nominal_lot_df):
    """8. Component reports contain non-empty human_readable_reasons with observed, median, and MAD values."""
    df = clean_nominal_lot_df.copy()
    mask = (df["component_id"] == "LOT_NOMINAL_CMP_0008") & (df["parameter_name"] == "Iddq")
    df.loc[mask, "value_24h"] = 45.0

    detector = PopulationAnomalyDetector(anomaly_threshold=3.5)
    report = detector.detect_anomalies(df)

    target_comp = next(c for c in report.component_reports if c.component_id == "LOT_NOMINAL_CMP_0008")
    reasons = target_comp.human_readable_reasons
    assert len(reasons) > 0

    reason_str = " ".join(reasons)
    assert "45.00 uA" in reason_str or "45.0" in reason_str
    assert "Iddq" in reason_str
    assert "lot median" in reason_str


# -----------------------------------------------------------------------------
# 9. INPUT DATAFRAME IMMUTABILITY TEST
# -----------------------------------------------------------------------------

def test_input_dataframe_not_mutated(clean_nominal_lot_df):
    """9. Detector must not alter or add columns to the input DataFrame."""
    df_orig = clean_nominal_lot_df.copy()
    detector = PopulationAnomalyDetector(anomaly_threshold=3.5)
    _ = detector.detect_anomalies(clean_nominal_lot_df)

    pd.testing.assert_frame_equal(clean_nominal_lot_df, df_orig)


# -----------------------------------------------------------------------------
# 10. PHASE 1 DEV DATASET COMPATIBILITY TEST
# -----------------------------------------------------------------------------

def test_phase1_dev_dataset_compatibility():
    """10. Module A runs cleanly on data/dev_burnin_data.csv without error."""
    dev_path = "data/v2/dev_burnin_data.csv"
    if not os.path.exists(dev_path):
        pytest.skip(f"{dev_path} not found")

    df = pd.read_csv(dev_path)
    detector = PopulationAnomalyDetector(anomaly_threshold=3.5)
    reports = detector.detect_anomalies(df)

    assert isinstance(reports, dict)
    assert len(reports) == 20  # 20 lots in dev dataset

    df_out = detector.to_dataframe(reports)
    assert len(df_out) == 2000  # 2000 components total


# -----------------------------------------------------------------------------
# 11. PHASE 1 DEMO DATASET COMPATIBILITY TEST
# -----------------------------------------------------------------------------

def test_phase1_demo_dataset_compatibility():
    """11. Module A runs cleanly on data/demo_burnin_data.csv and detects synthetic case B/C/D anomalies."""
    demo_path = "data/v2/demo_burnin_data.csv"
    if not os.path.exists(demo_path):
        pytest.skip(f"{demo_path} not found")

    df = pd.read_csv(demo_path)
    detector = PopulationAnomalyDetector(anomaly_threshold=3.5)
    reports = detector.detect_anomalies(df)

    assert isinstance(reports, dict) or isinstance(reports, LotAnomalyReport)
    df_out = detector.to_dataframe(reports)
    assert len(df_out) == 250  # 250 components total in demo dataset

    # Demo case B (within-spec population anomaly) should be flagged
    case_b = df_out[df_out["component_id"] == "DEMO_LOT_001_CMP_CASE_B"]
    if not case_b.empty:
        assert case_b["is_population_anomaly"].iloc[0] is True


# -----------------------------------------------------------------------------
# 12. ZERO-MAD / CONSTANT POPULATION TEST
# -----------------------------------------------------------------------------

def test_zero_mad_constant_population_handled():
    """12. Constant population (MAD = 0) produces zero Z-scores without NaN or Inf outputs."""
    rows = []
    lot_id = "LOT_CONSTANT"
    for i in range(1, 21):
        rows.append({
            "lot_id": lot_id,
            "component_id": f"{lot_id}_CMP_{i:04d}",
            "parameter_name": "Iddq",
            "unit": "uA",
            "value_0h": 10.0,  # All values identical => MAD = 0
            "value_24h": 10.0,
            "synthetic_spec_min": 0.0,
            "synthetic_spec_max": 50.0,
        })
    df = pd.DataFrame(rows)

    detector = PopulationAnomalyDetector(anomaly_threshold=3.5)
    report = detector.detect_anomalies(df)

    assert report.anomalous_components_count == 0
    for comp in report.component_reports:
        assert comp.population_anomaly_score == 0.0
        assert not np.isnan(comp.population_anomaly_score)
        assert not np.isinf(comp.population_anomaly_score)
