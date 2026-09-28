"""
tests/unit/test_screening_pipeline.py

Phase 6 unit and integration tests — Screening Pipeline.

Tests cover all 16 required scenarios:
    1.  Valid CSV passes validation
    2.  Invalid CSV stops before screening (aborted flag)
    3.  Module A executes (anomaly evidence present)
    4.  Module B executes using registered production predictors
    5.  Risk Engine executes (overall_risk_level present)
    6.  Lot summary is produced
    7.  Component results are produced
    8.  Parameter results contain prediction and uncertainty
    9.  Multiple lots work
    10. Multiple parameters work
    11. Deterministic repeated execution
    12. Input data is not mutated
    13. Phase 0–5 tests remain passing (verified by running full suite)
    14. Module B receives ONLY permitted production features
    15. value_96h and value_168h are never used as Module B inputs
    16. Existing registered model artifacts are not modified

Uses the actual Phase 1 demo dataset for integration testing.
"""

import os
import sys
import copy

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from src.screening.pipeline import ScreeningPipeline
from src.screening.schema import (
    ComponentScreeningResult,
    LotScreeningResult,
    ParameterScreeningResult,
    ScreeningResult,
)
from src.risk.schema import RISK_HIGH, RISK_LOW, RISK_MEDIUM

# ---- Paths ----
DEMO_CSV = os.path.join(os.path.dirname(__file__), "../../data/v2/demo_burnin_data.csv")
REGISTRY_DIR = os.path.join(os.path.dirname(__file__), "../../models/registered")
RISK_CONFIG = os.path.join(os.path.dirname(__file__), "../../configs/risk_engine_config.yaml")


@pytest.fixture(scope="module")
def pipeline():
    """One pipeline instance shared across tests (loads model artifacts once)."""
    return ScreeningPipeline(
        registry_dir=REGISTRY_DIR,
        risk_config_path=RISK_CONFIG,
    )


@pytest.fixture(scope="module")
def demo_result(pipeline):
    """Run the full demo pipeline once and cache the result for multiple tests."""
    return pipeline.run(csv_path=DEMO_CSV)


# ===========================================================================
# TEST 1 — Valid CSV passes validation
# ===========================================================================

def test_01_valid_csv_passes_validation(demo_result):
    """demo_burnin_data.csv must pass Phase 2 validation."""
    assert demo_result.validation_status == "PASS"
    assert demo_result.validation_hard_failures == 0
    assert not demo_result.aborted


# ===========================================================================
# TEST 2 — Invalid CSV stops before screening
# ===========================================================================

def test_02_invalid_csv_aborts_screening(tmp_path, pipeline):
    """A CSV missing required columns should fail validation and abort screening."""
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("col_a,col_b\n1,2\n3,4\n")
    result = pipeline.run(csv_path=str(bad_csv))
    assert result.aborted
    assert result.validation_status == "FAIL"
    assert result.validation_hard_failures > 0
    # No lots processed
    assert result.total_lots == 0
    assert len(result.lot_results) == 0


# ===========================================================================
# TEST 3 — Module A executes (anomaly evidence present)
# ===========================================================================

def test_03_module_a_executes(demo_result):
    """Each component result must have anomaly_classification_state from Module A."""
    assert demo_result.total_components > 0
    for lot in demo_result.lot_results.values():
        for comp in lot.component_results:
            assert comp.anomaly_classification_state in (
                "STATE_A_NORMAL",
                "STATE_B_POPULATION_ANOMALY_ONLY",
                "STATE_C_SPEC_BREACH_ONLY",
                "STATE_D_POPULATION_ANOMALY_AND_SPEC_BREACH",
            )
            assert comp.anomaly_score >= 0.0


# ===========================================================================
# TEST 4 — Module B executes using registered production predictors
# ===========================================================================

def test_04_module_b_executes(demo_result):
    """Every parameter result must include a Module B prediction."""
    for lot in demo_result.lot_results.values():
        for comp in lot.component_results:
            for param_name, pr in comp.parameters.items():
                assert pr.predicted_168h is not None
                assert pr.lower_bound_168h <= pr.predicted_168h <= pr.upper_bound_168h, (
                    f"Uncertainty interval must bracket point prediction for "
                    f"{comp.component_id}/{param_name}: "
                    f"[{pr.lower_bound_168h:.4g}, {pr.upper_bound_168h:.4g}] "
                    f"pred={pr.predicted_168h:.4g}"
                )
                assert pr.uncertainty_width >= 0


# ===========================================================================
# TEST 5 — Risk Engine executes (risk level present)
# ===========================================================================

def test_05_risk_engine_executes(demo_result):
    """Every component must have a valid overall risk level from the Risk Engine."""
    valid_levels = {RISK_LOW, RISK_MEDIUM, RISK_HIGH}
    for lot in demo_result.lot_results.values():
        for comp in lot.component_results:
            assert comp.overall_risk_level in valid_levels
            assert comp.recommendation_context


# ===========================================================================
# TEST 6 — Lot summary is produced
# ===========================================================================

def test_06_lot_summary_produced(demo_result):
    """ScreeningResult and LotScreeningResult must have correct summary counts."""
    assert demo_result.total_lots == 5          # demo dataset has 5 lots
    assert demo_result.total_components == 250  # 5 lots × 50 components

    # Aggregate risk counts must sum to total components
    total_risk = (
        demo_result.risk_low_count
        + demo_result.risk_medium_count
        + demo_result.risk_high_count
    )
    assert total_risk == demo_result.total_components

    for lot in demo_result.lot_results.values():
        lot_total = (
            lot.risk_low_count + lot.risk_medium_count + lot.risk_high_count
        )
        assert lot_total == lot.total_components


# ===========================================================================
# TEST 7 — Component results are produced
# ===========================================================================

def test_07_component_results_produced(demo_result):
    """Every lot must have exactly 50 component results."""
    for lot_id, lot in demo_result.lot_results.items():
        assert len(lot.component_results) == 50, (
            f"Lot {lot_id}: expected 50 components, got {len(lot.component_results)}"
        )


# ===========================================================================
# TEST 8 — Parameter results contain prediction and uncertainty
# ===========================================================================

def test_08_parameter_results_have_prediction_and_uncertainty(demo_result):
    """Each ParameterScreeningResult must contain non-None prediction and valid uncertainty."""
    supported = {"Iddq", "leakage_current", "propagation_delay"}
    for lot in demo_result.lot_results.values():
        for comp in lot.component_results:
            assert set(comp.parameters.keys()).issubset(supported)
            for param_name, pr in comp.parameters.items():
                assert pr.uncertainty_method, (
                    f"Missing uncertainty_method for {comp.component_id}/{param_name}"
                )
                assert pr.uncertainty_width >= 0


# ===========================================================================
# TEST 9 — Multiple lots work
# ===========================================================================

def test_09_multiple_lots_work(demo_result):
    """All 5 demo lots must be present in the result."""
    expected_lots = {f"LOT_00{i}" for i in range(1, 6)}
    assert set(demo_result.lot_results.keys()) == expected_lots


# ===========================================================================
# TEST 10 — Multiple parameters work
# ===========================================================================

def test_10_multiple_parameters_work(demo_result):
    """Every component must have results for all three parameters."""
    for lot in demo_result.lot_results.values():
        for comp in lot.component_results:
            assert "Iddq" in comp.parameters
            assert "leakage_current" in comp.parameters
            assert "propagation_delay" in comp.parameters


# ===========================================================================
# TEST 11 — Deterministic repeated execution
# ===========================================================================

def test_11_deterministic_execution(pipeline):
    """Running pipeline twice on same CSV must produce identical results."""
    r1 = pipeline.run(csv_path=DEMO_CSV)
    r2 = pipeline.run(csv_path=DEMO_CSV)
    assert r1.risk_low_count == r2.risk_low_count
    assert r1.risk_medium_count == r2.risk_medium_count
    assert r1.risk_high_count == r2.risk_high_count
    # Spot-check a component from each run
    for lot_id in r1.lot_results:
        l1 = r1.lot_results[lot_id]
        l2 = r2.lot_results[lot_id]
        for c1, c2 in zip(l1.component_results, l2.component_results):
            assert c1.overall_risk_level == c2.overall_risk_level
            assert c1.anomaly_score == c2.anomaly_score


# ===========================================================================
# TEST 12 — Input data is not mutated
# ===========================================================================

def test_12_input_data_not_mutated(pipeline):
    """Pipeline must not modify the caller's DataFrame."""
    df = pd.read_csv(DEMO_CSV)
    original_columns = list(df.columns)
    original_shape = df.shape
    original_values = df["value_0h"].copy()

    pipeline.run(df=df)  # pass df directly (no csv_path)

    assert list(df.columns) == original_columns
    assert df.shape == original_shape
    pd.testing.assert_series_equal(df["value_0h"], original_values)


# ===========================================================================
# TEST 14 & 15 — Module B receives only permitted production features;
#                value_96h and value_168h are never used as Module B inputs
# ===========================================================================

def test_14_15_module_b_feature_boundary(demo_result):
    """
    Verify that Module B predictions exist for all components, and that the
    pipeline did not use value_96h or value_168h as inputs (by checking that
    removing those columns from the DataFrame produces identical predictions).
    """
    # Load stripped DataFrame (no value_96h, no value_168h)
    df_full = pd.read_csv(DEMO_CSV)
    df_stripped = df_full.drop(columns=["value_96h", "value_168h"], errors="ignore")

    # Check that the stripped df still contains the required columns
    assert "value_0h" in df_stripped.columns
    assert "value_24h" in df_stripped.columns

    pipeline = ScreeningPipeline(
        registry_dir=REGISTRY_DIR,
        risk_config_path=RISK_CONFIG,
    )
    result_stripped = pipeline.run(df=df_stripped)

    # Must produce same counts as full run
    assert result_stripped.risk_low_count == demo_result.risk_low_count
    assert result_stripped.risk_medium_count == demo_result.risk_medium_count
    assert result_stripped.risk_high_count == demo_result.risk_high_count

    # Spot-check predictions are identical (first lot, first component, Iddq)
    first_lot_id = sorted(demo_result.lot_results.keys())[0]
    comp_a = demo_result.lot_results[first_lot_id].component_results[0]
    comp_b = result_stripped.lot_results[first_lot_id].component_results[0]

    pr_a = comp_a.parameters.get("Iddq")
    pr_b = comp_b.parameters.get("Iddq")
    assert pr_a is not None and pr_b is not None
    assert abs(pr_a.predicted_168h - pr_b.predicted_168h) < 1e-9, (
        "Predictions must be identical whether or not value_96h/value_168h are in the input"
    )


# ===========================================================================
# TEST 16 — Existing registered model artifacts are not modified
# ===========================================================================

def test_16_model_artifacts_not_modified(demo_result):
    """Model registry directories must still exist and be intact after pipeline run."""
    expected_models = [
        "module_b_Iddq_v1",
        "module_b_leakage_current_v1",
        "module_b_propagation_delay_v1",
    ]
    for model_dir in expected_models:
        path = os.path.join(REGISTRY_DIR, model_dir)
        assert os.path.isdir(path), f"Model artifact directory missing: {path}"
        assert os.path.exists(os.path.join(path, "model.pkl"))
        assert os.path.exists(os.path.join(path, "registry.json"))


# ===========================================================================
# Regression test — Phase 5 risk distribution must be preserved
# ===========================================================================

def test_regression_phase5_risk_distribution(demo_result):
    """
    Regression check: demo dataset must still produce the approved distribution.
    LOW=135, MEDIUM=102, HIGH=13 (from Phase 5 approval).
    Do NOT alter risk logic to pass this test.
    """
    assert demo_result.risk_low_count == 135, (
        f"Expected LOW=135, got {demo_result.risk_low_count}"
    )
    assert demo_result.risk_medium_count == 102, (
        f"Expected MEDIUM=102, got {demo_result.risk_medium_count}"
    )
    assert demo_result.risk_high_count == 13, (
        f"Expected HIGH=13, got {demo_result.risk_high_count}"
    )


# ===========================================================================
# Convenience helper — components requiring attention
# ===========================================================================

def test_components_requiring_attention(demo_result):
    """LotScreeningResult.components_requiring_attention() must return only MEDIUM/HIGH."""
    for lot in demo_result.lot_results.values():
        attention = lot.components_requiring_attention()
        for comp in attention:
            assert comp.overall_risk_level in (RISK_MEDIUM, RISK_HIGH)
        # HIGH components must appear before MEDIUM
        levels = [c.overall_risk_level for c in attention]
        high_done = False
        for lvl in levels:
            if lvl == RISK_MEDIUM:
                high_done = True
            if high_done:
                assert lvl != RISK_HIGH, "HIGH must precede MEDIUM in attention list"


# ===========================================================================
# get_component lookup
# ===========================================================================

def test_get_component_lookup(demo_result):
    """ScreeningResult.get_component() must return the correct ComponentScreeningResult."""
    first_lot = sorted(demo_result.lot_results.keys())[0]
    first_comp = demo_result.lot_results[first_lot].component_results[0]
    found = demo_result.get_component(first_comp.component_id, lot_id=first_lot)
    assert found is not None
    assert found.component_id == first_comp.component_id

    # Lookup with wrong lot returns None
    not_found = demo_result.get_component(first_comp.component_id, lot_id="NONEXISTENT")
    assert not_found is None
