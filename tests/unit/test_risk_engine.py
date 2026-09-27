"""
tests/unit/test_risk_engine.py

Phase 5 unit tests — Dynamic Risk Engine (v2 — scale-aware drift criterion).

Tests cover:
    - LOW risk (normal population, safe future, nominal uncertainty)
    - MEDIUM risk (population anomaly only, high uncertainty, moderate drift,
                   upper bound crosses spec, combined)
    - HIGH risk (reference breach, predicted spec crossing, anomaly + drift,
                 anomaly + predicted crossing)
    - Near-zero early delta: must NOT fire the drift axis on its own
    - Ordinary leakage_current trajectory: small drift/spec_range → LOW drift axis
    - Genuinely concerning future drift (large drift/spec_range → HIGH)
    - Supplementary trajectory ratio: only fires when delta is physically meaningful
    - Escalation rules (combined conditions escalate correctly)
    - Production feature boundary enforcement (value_96h/168h never enter Module B)
    - Deterministic execution (same inputs → same output)
    - Multi-parameter MAX aggregation

IMPORTANT DISCLAIMER:
    These tests verify prototype engineering logic for SIH26170 demo purposes.
    Thresholds are not official ISRO safety limits.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from src.anomaly.schema import (
    ComponentAnomalyReport,
    ParameterAnomalyEvidence,
)
from src.risk.schema import (
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    ComponentRiskAssessment,
    ParameterRiskEvidence,
)
from src.risk.rules import compute_component_risk, evaluate_parameter_risk
from src.risk.explainability import (
    assessment_to_dict,
    assessments_to_dataframe,
    format_component_assessment,
)

# ---------------------------------------------------------------------------
# Default config matching shipped YAML (v2 scale-aware thresholds)
# ---------------------------------------------------------------------------
DEFAULT_CFG = {
    "population_anomaly": {"low_threshold": 3.5, "high_threshold": 6.0},
    "drift": {
        "drift_frac_spec_medium": 0.20,
        "drift_frac_spec_high": 0.60,
        "drift_frac_predicted_medium": 0.20,
        "drift_frac_predicted_high": 0.50,
        "min_delta_fraction_of_spec": 0.02,
        "supplementary_trajectory_ratio": 5.0,
    },
    "uncertainty": {
        "interval_fraction_of_spec_range_high": 0.30,
        "interval_fraction_of_predicted_high": 0.50,
    },
    "risk_escalation_rules": {
        "reference_limit_breach_level": "HIGH",
        "predicted_spec_crossing_level": "HIGH",
        "upper_bound_crosses_spec_max_level": "MEDIUM",
        "strong_population_anomaly_level": "MEDIUM",
        "moderate_population_anomaly_level": "MEDIUM",
        "high_uncertainty_alone_level": "MEDIUM",
        "moderate_drift_level": "MEDIUM",
        "high_drift_level": "HIGH",
        "anomaly_plus_drift_level": "HIGH",
        "anomaly_plus_high_uncertainty_level": "MEDIUM",
    },
}


def _make_ev(
    param: str = "Iddq",
    unit: str = "uA",
    value_0h: float = 10.0,
    value_24h: float = 10.5,
    predicted_168h: float = 11.0,
    lower_bound: float = 10.5,
    upper_bound: float = 11.5,
    pop_score: float = 0.5,
    is_pop_anomaly: bool = False,
    is_ref_breach: bool = False,
    spec_min: float = 0.0,
    spec_max: float = 50.0,      # Iddq default
    classification_state: str = "STATE_A_NORMAL",
) -> ParameterRiskEvidence:
    delta = value_24h - value_0h
    return ParameterRiskEvidence(
        parameter_name=param,
        unit=unit,
        population_anomaly_score=pop_score,
        is_population_anomaly=is_pop_anomaly,
        population_anomaly_classification=classification_state,
        is_reference_limit_breach=is_ref_breach,
        value_0h=value_0h,
        value_24h=value_24h,
        delta_24_0=delta,
        predicted_168h=predicted_168h,
        lower_bound_168h=lower_bound,
        upper_bound_168h=upper_bound,
        uncertainty_width=upper_bound - lower_bound,
        uncertainty_method="test",
        predicted_drift_from_0h=predicted_168h - value_0h,
        predicted_drift_from_24h=predicted_168h - value_24h,
        observed_early_delta=delta,
        synthetic_spec_min=spec_min,
        synthetic_spec_max=spec_max,
        predicted_value_crosses_spec_max=predicted_168h > spec_max,
        predicted_value_crosses_spec_min=predicted_168h < spec_min,
        upper_bound_crosses_spec_max=upper_bound > spec_max,
    )


# ===========================================================================
# SCENARIO 1 — LOW: completely nominal (all axes below thresholds)
# ===========================================================================

def test_scenario_1_low_risk_all_nominal():
    """All signals nominal → LOW.
    Iddq spec_range=50. drift = 11-10 = 1 uA = 2% of spec → below 20% MEDIUM threshold."""
    ev = _make_ev(value_0h=10.0, value_24h=10.5, predicted_168h=11.0,
                  lower_bound=10.0, upper_bound=12.0,
                  pop_score=0.5, is_pop_anomaly=False, is_ref_breach=False,
                  spec_max=50.0)
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_LOW
    assert ev.parameter_risk_level == RISK_LOW


# ===========================================================================
# SCENARIO 2 — MEDIUM: population anomaly only (future drift and spec safe)
# ===========================================================================

def test_scenario_2_medium_population_anomaly_only():
    """Moderate population anomaly; drift = 2/50 = 4% (below 20%), uncertainty small → MEDIUM.
    Verify near-zero drift alone does not escalate."""
    # delta_24_0 = 2.0; predicted_drift = 2.0; drift_frac = 2/50 = 4%
    ev = _make_ev(value_0h=10.0, value_24h=12.0, predicted_168h=12.0,
                  lower_bound=11.0, upper_bound=13.0,
                  pop_score=4.2, is_pop_anomaly=True, is_ref_breach=False,
                  spec_max=50.0, classification_state="STATE_B_POPULATION_ANOMALY_ONLY")
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_MEDIUM
    assert any("population anomaly" in r.lower() for r in reasons)


# ===========================================================================
# SCENARIO 3 — HIGH: observed reference limit breach
# ===========================================================================

def test_scenario_3_high_reference_limit_breach():
    """Observation outside spec limits → HIGH regardless of drift or anomaly score."""
    ev = _make_ev(value_0h=55.0, value_24h=56.0, predicted_168h=57.0,
                  lower_bound=56.0, upper_bound=58.0,
                  pop_score=1.0, is_pop_anomaly=False, is_ref_breach=True,
                  spec_max=50.0)
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_HIGH
    assert any("breaches reference limit" in r for r in reasons)


# ===========================================================================
# SCENARIO 4 — HIGH: predicted future value crosses spec_max
# ===========================================================================

def test_scenario_4_high_predicted_spec_crossing():
    """Module B predicts crossing spec_max at 168h → HIGH."""
    # drift = 52 - 10 = 42/50 = 84% of spec (also triggers HIGH drift axis, but spec crossing is direct)
    ev = _make_ev(value_0h=10.0, value_24h=10.5, predicted_168h=52.0,
                  lower_bound=50.5, upper_bound=53.5,
                  pop_score=1.0, is_pop_anomaly=False, is_ref_breach=False,
                  spec_max=50.0)
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_HIGH
    assert any("crossing" in r.lower() or "crosses" in r.lower() for r in reasons)


# ===========================================================================
# SCENARIO 5 — MEDIUM: upper uncertainty bound crosses spec max, point pred safe
# ===========================================================================

def test_scenario_5_medium_upper_bound_crosses_spec():
    """Point prediction < spec_max but upper bound crosses it → MEDIUM.
    drift = 12 - 10 = 2/50 = 4% (below 20% MEDIUM) so drift axis does not fire.
    upper_bound = 52 > spec_max=50 → upper bound axis fires MEDIUM."""
    ev = _make_ev(value_0h=10.0, value_24h=10.5, predicted_168h=12.0,
                  lower_bound=10.0, upper_bound=52.0,   # upper > 50
                  pop_score=1.0, is_pop_anomaly=False, is_ref_breach=False,
                  spec_max=50.0)
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_MEDIUM


# ===========================================================================
# SCENARIO 6 — HIGH: upper bound crosses spec max AND population anomaly
# ===========================================================================

def test_scenario_6_high_upper_bound_plus_anomaly():
    """Upper bound crosses spec AND population anomalous → HIGH (escalation)."""
    ev = _make_ev(value_0h=10.0, value_24h=12.0, predicted_168h=48.0,
                  lower_bound=46.0, upper_bound=52.0,
                  pop_score=4.0, is_pop_anomaly=True, is_ref_breach=False,
                  spec_max=50.0, classification_state="STATE_B_POPULATION_ANOMALY_ONLY")
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_HIGH


# ===========================================================================
# SCENARIO 7 — MEDIUM: high prediction uncertainty alone
# ===========================================================================

def test_scenario_7_medium_high_uncertainty():
    """Uncertainty width >= 30% of spec range, drift and anomaly low → MEDIUM.
    unc_width = 16, spec_range = 50, 16/50 = 32% > 30%."""
    # drift = 1/50 = 2% (low), delta = 0.2 (tiny, << 2% of spec=1.0), unc_width=16
    ev = _make_ev(value_0h=10.0, value_24h=10.2, predicted_168h=11.0,
                  lower_bound=3.0, upper_bound=19.0,  # width=16, 32% of spec_range=50
                  pop_score=0.5, is_pop_anomaly=False, is_ref_breach=False,
                  spec_max=50.0)
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_MEDIUM
    assert ev.uncertainty_is_high


# ===========================================================================
# SCENARIO 8 — MEDIUM: moderate predicted drift (drift_frac 20–60% of spec range)
# ===========================================================================

def test_scenario_8_medium_moderate_drift_frac_spec():
    """drift_frac = 12/50 = 24% (>= 20% MEDIUM, < 60% HIGH) → MEDIUM.
    Scale-aware: this is the primary drift criterion."""
    # drift = predicted_168h - value_0h = 22 - 10 = 12 uA; 12/50 = 24%
    # delta = 1.0; delta_frac_spec = 1/50 = 2% = exactly min_delta_fraction → supplementary may fire
    # but primary MEDIUM already set from drift_frac
    ev = _make_ev(value_0h=10.0, value_24h=11.0, predicted_168h=22.0,
                  lower_bound=21.0, upper_bound=23.0,
                  pop_score=0.5, is_pop_anomaly=False, is_ref_breach=False,
                  spec_max=50.0)
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_MEDIUM
    assert any("spec range" in r for r in reasons)


# ===========================================================================
# SCENARIO 9 — HIGH: large predicted drift (drift_frac >= 60% of spec range)
# ===========================================================================

def test_scenario_9_high_drift_frac_spec():
    """drift_frac = 32/50 = 64% (>= 60% HIGH threshold) → HIGH.
    Primary scale-aware criterion correctly fires for genuinely large drift."""
    # drift = 42 - 10 = 32 uA; 32/50 = 64%
    ev = _make_ev(value_0h=10.0, value_24h=10.5, predicted_168h=42.0,
                  lower_bound=41.0, upper_bound=43.0,
                  pop_score=0.5, is_pop_anomaly=False, is_ref_breach=False,
                  spec_max=50.0)
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_HIGH
    assert any("spec range" in r and "60%" in r for r in reasons)


# ===========================================================================
# SCENARIO 10 — HIGH: population anomaly + moderate drift combined
# ===========================================================================

def test_scenario_10_high_anomaly_plus_moderate_drift():
    """Population anomaly + moderate drift_frac (24%) → combined escalation to HIGH."""
    ev = _make_ev(value_0h=10.0, value_24h=11.0, predicted_168h=22.0,
                  lower_bound=21.0, upper_bound=23.0,
                  pop_score=4.0, is_pop_anomaly=True, is_ref_breach=False,
                  spec_max=50.0, classification_state="STATE_B_POPULATION_ANOMALY_ONLY")
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_HIGH
    assert any("Combined" in r for r in reasons)


# ===========================================================================
# SCENARIO 11 — MEDIUM: population anomaly + high uncertainty, drift low
# ===========================================================================

def test_scenario_11_medium_anomaly_plus_uncertainty():
    """Population anomaly + high uncertainty (unc=16 > 30% of 50), drift_frac low → MEDIUM."""
    # delta = 3.0, drift = 12 - 10 = 2 uA, drift_frac = 2/50 = 4% → below MEDIUM threshold
    ev = _make_ev(value_0h=10.0, value_24h=13.0, predicted_168h=12.0,
                  lower_bound=4.0, upper_bound=20.0,  # width=16, 32% of 50
                  pop_score=4.0, is_pop_anomaly=True, is_ref_breach=False,
                  spec_max=50.0, classification_state="STATE_B_POPULATION_ANOMALY_ONLY")
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_MEDIUM
    assert ev.uncertainty_is_high


# ===========================================================================
# SCENARIO 12 — MEDIUM: strong population anomaly alone (no drift, no breach)
# ===========================================================================

def test_scenario_12_strong_anomaly_alone_at_least_medium():
    """Strong population anomaly score (>= 6.0) alone → at least MEDIUM."""
    ev = _make_ev(value_0h=10.0, value_24h=12.0, predicted_168h=12.0,
                  lower_bound=11.0, upper_bound=13.0,
                  pop_score=7.5, is_pop_anomaly=True, is_ref_breach=False,
                  spec_max=50.0, classification_state="STATE_B_POPULATION_ANOMALY_ONLY")
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level in (RISK_MEDIUM, RISK_HIGH)
    assert any("strong" in r.lower() or "population anomaly" in r.lower() for r in reasons)


# ===========================================================================
# SCENARIO 13 — Near-zero early delta: MUST NOT cause HIGH on its own
# ===========================================================================

def test_scenario_13_near_zero_early_delta_does_not_drive_high():
    """
    When delta_24_0 is very small (< min_delta_fraction_of_spec of spec_range),
    the supplementary trajectory ratio is suppressed.
    With drift_frac_spec also low, result must be LOW.

    Models the leakage_current case: delta=0.015 nA, spec_range=30.
    delta_frac_spec = 0.015/30 = 0.05% << 2% gate → supplementary ratio does not fire.
    drift = 2.5 - 5.0 = -2.5 ... wait, use a realistic leakage scenario:
    value_0h=5.0, predicted_168h=7.5, drift = 2.5 nA, spec_range=30
    drift_frac = 2.5/30 = 8.3% < 20% → LOW drift axis.
    """
    # leakage_current-like scenario
    ev = _make_ev(
        param="leakage_current", unit="nA",
        value_0h=5.0, value_24h=5.015,   # delta = 0.015 nA (tiny)
        predicted_168h=7.5,               # drift = 2.5 nA; 2.5/30 = 8.3% < 20%
        lower_bound=7.0, upper_bound=8.0,
        pop_score=0.5, is_pop_anomaly=False, is_ref_breach=False,
        spec_min=0.0, spec_max=30.0,
    )
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    # drift_frac_spec = 8.3% < 20% → LOW drift
    # supplementary: delta_frac_spec = 0.015/30 = 0.05% < 2% gate → suppressed
    # uncertainty: width = 1.0, 1/30 = 3.3% < 30% → LOW
    assert level == RISK_LOW, f"Expected LOW, got {level}. Reasons: {reasons}"
    # Confirm no drift reason fired
    assert not any("spec range" in r.lower() for r in reasons)


# ===========================================================================
# SCENARIO 14 — Ordinary leakage_current trajectory: LOW drift axis
# ===========================================================================

def test_scenario_14_ordinary_leakage_current_trajectory_low():
    """
    Ordinary leakage_current component with realistic drift.
    drift_frac = 0.33/30 = 1.1% of spec range → well below 20% MEDIUM.
    Even with tiny delta, result is LOW overall.
    """
    ev = _make_ev(
        param="leakage_current", unit="nA",
        value_0h=5.0, value_24h=5.1,       # delta = 0.1 nA; delta_frac = 0.1/30 = 0.33%
        predicted_168h=5.33,               # drift = 0.33 nA; 0.33/30 = 1.1%
        lower_bound=5.0, upper_bound=5.7,
        pop_score=0.8, is_pop_anomaly=False, is_ref_breach=False,
        spec_min=0.0, spec_max=30.0,
    )
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_LOW, f"Expected LOW, got {level}. Reasons: {reasons}"


# ===========================================================================
# SCENARIO 15 — Genuinely concerning future drift (leakage_current outlier)
# ===========================================================================

def test_scenario_15_genuinely_concerning_drift_leakage_current():
    """
    A leakage_current outlier with very large predicted 168h value.
    drift = 22 - 5 = 17 nA; drift_frac = 17/30 = 56.7% >= MEDIUM (20%) but < HIGH (60%).
    → MEDIUM drift axis.
    """
    ev = _make_ev(
        param="leakage_current", unit="nA",
        value_0h=5.0, value_24h=5.1,
        predicted_168h=22.0,               # drift = 17; 17/30 = 56.7%
        lower_bound=20.0, upper_bound=24.0,
        pop_score=0.8, is_pop_anomaly=False, is_ref_breach=False,
        spec_min=0.0, spec_max=30.0,
    )
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_MEDIUM, f"Expected MEDIUM, got {level}. Reasons: {reasons}"
    assert any("spec range" in r for r in reasons)


def test_scenario_15b_extreme_drift_leakage_current_high():
    """
    leakage_current with extreme predicted drift: drift/spec_range >= 60% → HIGH.
    drift = 20; 20/30 = 66.7% >= HIGH threshold.
    """
    ev = _make_ev(
        param="leakage_current", unit="nA",
        value_0h=5.0, value_24h=5.1,
        predicted_168h=25.0,               # drift = 20; 20/30 = 66.7%
        lower_bound=23.0, upper_bound=27.0,
        pop_score=0.8, is_pop_anomaly=False, is_ref_breach=False,
        spec_min=0.0, spec_max=30.0,
    )
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_HIGH, f"Expected HIGH, got {level}. Reasons: {reasons}"


# ===========================================================================
# SCENARIO 16 — Supplementary trajectory ratio fires only when delta meaningful
# ===========================================================================

def test_scenario_16_supplementary_ratio_fires_when_delta_large():
    """
    When |delta_24_0| >= 2% of spec_range AND drift/delta >= 5x AND drift_frac < 20%:
    supplementary ratio adds MEDIUM signal.
    propagation_delay: spec_range=100; delta=2.5 ps (delta_frac=2.5%>=2%);
    drift = 13-100 ... use: drift = 13 ps, ratio = 13/2.5 = 5.2 >= 5x
    drift_frac = 13/100 = 13% < 20% (primary LOW), but supplementary fires.
    """
    ev = _make_ev(
        param="propagation_delay", unit="ps",
        value_0h=100.0, value_24h=102.5,   # delta = 2.5; delta_frac = 2.5%
        predicted_168h=113.0,              # drift = 13; drift_frac = 13% < 20%; ratio = 5.2
        lower_bound=112.0, upper_bound=114.0,
        pop_score=0.5, is_pop_anomaly=False, is_ref_breach=False,
        spec_min=80.0, spec_max=180.0,
    )
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_MEDIUM, f"Expected MEDIUM, got {level}. Reasons: {reasons}"
    assert any("Supplementary" in r for r in reasons)


def test_scenario_16b_supplementary_ratio_suppressed_when_delta_small():
    """
    When |delta_24_0| < 2% of spec_range: supplementary ratio is suppressed.
    Same propagation_delay scenario but with tiny delta.
    """
    ev = _make_ev(
        param="propagation_delay", unit="ps",
        value_0h=100.0, value_24h=100.5,   # delta = 0.5; delta_frac = 0.5% < 2%
        predicted_168h=113.0,              # drift_frac = 13% < 20%; ratio = 26x but suppressed
        lower_bound=112.0, upper_bound=114.0,
        pop_score=0.5, is_pop_anomaly=False, is_ref_breach=False,
        spec_min=80.0, spec_max=180.0,
    )
    level, reasons = evaluate_parameter_risk(ev, DEFAULT_CFG)
    assert level == RISK_LOW, f"Expected LOW, got {level}. Reasons: {reasons}"
    assert not any("Supplementary" in r for r in reasons)


# ===========================================================================
# SCENARIO 17 — Multi-parameter: component risk = MAX across parameters
# ===========================================================================

def test_scenario_17_component_risk_is_max_of_params():
    """Component risk = max across parameters; one HIGH param drives overall HIGH."""
    param_risk_map = {
        "Iddq": (RISK_LOW, []),
        "leakage_current": (RISK_HIGH, ["[HIGH] spec breach"]),
        "propagation_delay": (RISK_MEDIUM, ["[MEDIUM] pop anomaly"]),
    }
    overall, reasons = compute_component_risk(param_risk_map)
    assert overall == RISK_HIGH


def test_scenario_17b_all_params_low():
    """All parameters LOW → component LOW."""
    param_risk_map = {
        "Iddq": (RISK_LOW, []),
        "leakage_current": (RISK_LOW, []),
        "propagation_delay": (RISK_LOW, []),
    }
    overall, _ = compute_component_risk(param_risk_map)
    assert overall == RISK_LOW


# ===========================================================================
# SCENARIO 18 — Deterministic execution
# ===========================================================================

def test_scenario_18_deterministic():
    """Same inputs always produce the same output (no randomness in rules)."""
    ev1 = _make_ev(value_0h=10.0, value_24h=10.5, predicted_168h=22.0,
                   lower_bound=21.0, upper_bound=23.0, pop_score=0.5,
                   is_pop_anomaly=False, spec_max=50.0)
    ev2 = _make_ev(value_0h=10.0, value_24h=10.5, predicted_168h=22.0,
                   lower_bound=21.0, upper_bound=23.0, pop_score=0.5,
                   is_pop_anomaly=False, spec_max=50.0)
    level1, reasons1 = evaluate_parameter_risk(ev1, DEFAULT_CFG)
    level2, reasons2 = evaluate_parameter_risk(ev2, DEFAULT_CFG)
    assert level1 == level2
    assert reasons1 == reasons2


# ===========================================================================
# SCENARIO 19 — Explainability utilities
# ===========================================================================

def test_scenario_19_format_assessment_non_empty():
    """format_component_assessment returns a non-empty string with expected fields."""
    ev = _make_ev()
    ev.parameter_risk_level = RISK_LOW
    assessment = ComponentRiskAssessment(
        component_id="COMP_001",
        lot_id="LOT_001",
        overall_risk_level=RISK_LOW,
        any_population_anomaly=False,
        any_reference_breach=False,
        any_predicted_spec_crossing=False,
        any_high_uncertainty=False,
        any_elevated_drift=False,
        parameter_risks={"Iddq": ev},
        recommendation_context="LOW RISK — all evidence signals nominal.",
        risk_reasons=[],
    )
    text = format_component_assessment(assessment)
    assert "COMP_001" in text
    assert "LOT_001" in text
    assert "LOW" in text
    assert "PROTOTYPE ADVISORY" in text


# ===========================================================================
# SCENARIO 20 — Production feature boundary enforcement
# ===========================================================================

def test_scenario_20_no_forbidden_columns_passed_to_module_b():
    """
    assess_component must only call predict_single(value_0h, value_24h).
    Columns value_96h and value_168h in row_df must be ignored by the engine.
    """
    param_ev = ParameterAnomalyEvidence(
        parameter_name="Iddq", unit="uA",
        observed_0h=10.0, observed_24h=10.5, observed_delta=0.5,
        lot_median_0h=10.0, lot_mad_0h=1.0,
        lot_median_24h=10.5, lot_mad_24h=1.0,
        lot_median_delta=0.5, lot_mad_delta=0.5,
        modified_zscore_0h=0.3, modified_zscore_24h=0.3, modified_zscore_delta=0.2,
        max_modified_zscore=0.3,
        percentile_0h=50.0, percentile_24h=50.0, percentile_delta=50.0,
        synthetic_spec_min=0.0, synthetic_spec_max=50.0,
        is_spec_breach=False,
    )
    comp_report = ComponentAnomalyReport(
        component_id="COMP_001", lot_id="LOT_001",
        is_population_anomaly=False, is_reference_limit_breach=False,
        population_anomaly_score=0.3, classification_state="STATE_A_NORMAL",
        parameter_evidence={"Iddq": param_ev},
    )

    row_df = pd.DataFrame([{
        "lot_id": "LOT_001", "component_id": "COMP_001",
        "parameter_name": "Iddq", "unit": "uA",
        "value_0h": 10.0, "value_24h": 10.5,
        "value_96h": 99.0,    # forbidden — must never reach Module B
        "value_168h": 11.5,   # forbidden — must never reach Module B
        "synthetic_spec_min": 0.0, "synthetic_spec_max": 50.0,
    }])

    captured_calls = []

    with patch("src.risk.engine.ProductionPredictor") as MockPredictor:
        instance = MagicMock()

        def fake_predict_single(value_0h, value_24h):
            captured_calls.append({"value_0h": value_0h, "value_24h": value_24h})
            return {
                "prediction": 11.0,
                "lower_bound": 10.5,
                "upper_bound": 11.5,
                "uncertainty_method": "test",
                "parameter": "Iddq",
                "model_id": "test",
            }

        instance.predict_single.side_effect = fake_predict_single
        MockPredictor.from_registry.return_value = instance

        from src.risk.engine import DynamicRiskEngine
        engine = DynamicRiskEngine.__new__(DynamicRiskEngine)
        engine.cfg = DEFAULT_CFG
        engine._predictors = {
            "Iddq": instance,
            "leakage_current": instance,
            "propagation_delay": instance,
        }
        assessment = engine.assess_component(comp_report, row_df)

    # Only value_0h and value_24h may be present in calls
    assert len(captured_calls) >= 1
    for call in captured_calls:
        assert "value_0h" in call
        assert "value_24h" in call
        assert "value_96h" not in call
        assert "value_168h" not in call
    assert assessment.component_id == "COMP_001"


# ===========================================================================
# Supplementary: assessment_to_dict and assessments_to_dataframe
# ===========================================================================

def test_assessment_to_dict_has_required_keys():
    ev = _make_ev()
    ev.parameter_risk_level = RISK_LOW
    assessment = ComponentRiskAssessment(
        component_id="C1", lot_id="L1",
        overall_risk_level=RISK_LOW,
        any_population_anomaly=False, any_reference_breach=False,
        any_predicted_spec_crossing=False, any_high_uncertainty=False,
        any_elevated_drift=False,
        parameter_risks={"Iddq": ev},
        recommendation_context="LOW RISK",
        risk_reasons=[],
    )
    d = assessment_to_dict(assessment)
    assert "lot_id" in d
    assert "component_id" in d
    assert "overall_risk_level" in d
    assert "Iddq_risk_level" in d
    assert "Iddq_predicted_168h" in d


def test_assessments_to_dataframe_shape():
    ev = _make_ev()
    ev.parameter_risk_level = RISK_LOW
    assessments = [
        ComponentRiskAssessment(
            component_id=f"C{i}", lot_id="L1",
            overall_risk_level=RISK_LOW,
            any_population_anomaly=False, any_reference_breach=False,
            any_predicted_spec_crossing=False, any_high_uncertainty=False,
            any_elevated_drift=False,
            parameter_risks={"Iddq": ev},
            recommendation_context="LOW",
            risk_reasons=[],
        )
        for i in range(3)
    ]
    df = assessments_to_dataframe(assessments)
    assert len(df) == 3
    assert "overall_risk_level" in df.columns
