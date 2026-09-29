"""
tests/unit/test_model_lab_lifecycle.py

Unit tests for Model Lab Re-evaluation, Candidate Comparison, Best-Suited Model Selection,
and Explicit Human Model Switch Workflow.
"""

import os
import shutil
import tempfile
import numpy as np
import pandas as pd
import pytest

from src.model_lab.features import PRODUCTION_FEATURE_ALLOWLIST, _assert_feature_boundary
from src.model_lab.lifecycle import (
    compare_candidates_on_dataset,
    execute_model_switch,
    reevaluate_deployed_model,
    validate_evaluation_dataset,
)
from src.model_lab.predictor import ProductionPredictor
from src.model_lab.registry import (
    get_active_model_id,
    get_active_models,
    list_model_versions,
    set_active_model_id,
)
from src.screening.service import ScreeningService


@pytest.fixture
def temp_registry():
    """Create a temporary registry directory copied from models/registered with baseline v1 models."""
    import json
    tmpdir = tempfile.mkdtemp(prefix="test_reg_")
    src_reg = "models/registered"
    if os.path.exists(src_reg):
        for item in os.listdir(src_reg):
            # Only copy baseline v1 models and split_info.json to ensure test isolation
            if item.endswith("_v1") or item == "split_info.json":
                s = os.path.join(src_reg, item)
                d = os.path.join(tmpdir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
    # Ensure active_models.json starts cleanly at v1
    baseline_active = {
        "Iddq": "module_b_Iddq_v1",
        "leakage_current": "module_b_leakage_current_v1",
        "propagation_delay": "module_b_propagation_delay_v1",
    }
    with open(os.path.join(tmpdir, "active_models.json"), "w") as f:
        json.dump(baseline_active, f, indent=2)
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_reevaluation_feature_boundary_contract(temp_registry):
    """
    Test 1 & 2: Re-evaluation uses strictly Value_0h + Value_24h -> Value_168h.
    Value_168h and Value_96h are NOT permitted as input features.
    """
    csv_path = "data/v2/demo_burnin_data.csv"
    res = reevaluate_deployed_model(csv_path, "Iddq", registry_dir=temp_registry)

    assert res["status"] == "success"
    assert res["parameter"] == "Iddq"
    assert res["sample_count"] > 0
    assert "MAE" in res["metrics"]
    assert "RMSE" in res["metrics"]
    assert "R2" in res["metrics"]

    # Verify feature boundary assertion triggers if forbidden features enter X
    df = pd.read_csv(csv_path)
    df_forbidden = df[df["parameter_name"] == "Iddq"][["value_0h", "value_24h", "value_96h"]].copy()
    with pytest.raises(ValueError, match="PRODUCTION FEATURE LEAKAGE DETECTED"):
        _assert_feature_boundary(df_forbidden)

    df_forbidden_target = df[df["parameter_name"] == "Iddq"][["value_0h", "value_24h", "value_168h"]].copy()
    with pytest.raises(ValueError, match="PRODUCTION FEATURE LEAKAGE DETECTED"):
        _assert_feature_boundary(df_forbidden_target)



def test_reevaluation_calculates_mae_correctly(temp_registry):
    """
    Test 3: Re-evaluation calculates MAE, RMSE, and R2 accurately against ground-truth.
    """
    csv_path = "data/v2/demo_burnin_data.csv"
    res = reevaluate_deployed_model(csv_path, "leakage_current", registry_dir=temp_registry)

    # Manually compute ground truth using the predictor
    df = pd.read_csv(csv_path)
    df_param = df[df["parameter_name"] == "leakage_current"].copy()
    y_true = df_param["value_168h"].values

    df_param["delta_24_0"] = df_param["value_24h"] - df_param["value_0h"]
    X = df_param[PRODUCTION_FEATURE_ALLOWLIST]

    predictor = ProductionPredictor.from_registry(temp_registry, "leakage_current")
    y_pred = predictor.predict(X)["predictions"]

    expected_mae = float(np.mean(np.abs(y_pred - y_true)))
    expected_rmse = float(np.sqrt(np.mean((y_pred - y_true) ** 2)))

    assert res["metrics"]["MAE"] == pytest.approx(expected_mae, rel=1e-5)
    assert res["metrics"]["RMSE"] == pytest.approx(expected_rmse, rel=1e-5)
    assert res["sample_count"] == len(y_true)


def test_dataset_validation_rejects_malformed_data():
    """
    Test dataset validation rejects missing columns, nulls, or empty parameter data.
    """
    # Missing required target value_168h
    df_missing = pd.DataFrame({
        "lot_id": ["LOT_001"],
        "component_id": ["C1"],
        "parameter_name": ["Iddq"],
        "value_0h": [10.0],
        "value_24h": [11.0],
    })
    val = validate_evaluation_dataset(df_missing, "Iddq")
    assert not val["valid"]
    assert any("Missing required columns" in err for err in val["errors"])

    # NaN in value_168h
    df_nan = pd.DataFrame({
        "lot_id": ["LOT_001"],
        "component_id": ["C1"],
        "parameter_name": ["Iddq"],
        "value_0h": [10.0],
        "value_24h": [11.0],
        "value_168h": [np.nan],
    })
    val_nan = validate_evaluation_dataset(df_nan, "Iddq")
    assert not val_nan["valid"]
    assert any("contains 1 null/NaN" in err for err in val_nan["errors"])


def test_candidate_comparison_uses_same_dataset(temp_registry):
    """
    Test 4: Candidate comparison benchmarks deployed model and candidates on the exact same dataset partition.
    """
    csv_path = "data/v2/demo_burnin_data.csv"
    res = compare_candidates_on_dataset(csv_path, "Iddq", registry_dir=temp_registry)

    assert res["dataset_path"] == csv_path
    assert res["parameter"] == "Iddq"
    assert "comparison_table" in res
    assert len(res["comparison_table"]) >= 4

    # Verify CURRENT_DEPLOYED is in comparison table
    deployed_rows = [r for r in res["comparison_table"] if r["is_deployed"]]
    assert len(deployed_rows) == 1
    assert deployed_rows[0]["MAE"] == res["current_deployed_mae"]

    # Verify candidates are present
    cand_names = [r["model_name"] for r in res["comparison_table"] if not r["is_deployed"]]
    assert "GradientBoostingRegressor" in cand_names
    assert "Ridge" in cand_names
    assert "RandomForestRegressor" in cand_names
    assert "DummyRegressor" in cand_names


def test_best_suited_model_selection_follows_lowest_mae(temp_registry):
    """
    Test 5: Best-suited candidate identification strictly follows lowest MAE rule.
    """
    csv_path = "data/v2/demo_burnin_data.csv"
    res = compare_candidates_on_dataset(csv_path, "Iddq", registry_dir=temp_registry)

    table = res["comparison_table"]
    candidate_rows = [r for r in table if not r["is_deployed"]]
    candidate_rows.sort(key=lambda r: r["MAE"])

    lowest_mae_cand = candidate_rows[0]
    deployed_mae = res["current_deployed_mae"]

    if lowest_mae_cand["MAE"] < (deployed_mae - 0.0001):
        assert res["switch_recommended"] is True
        assert res["best_suited_model"]["model_name"] == lowest_mae_cand["model_name"]
        assert res["best_suited_model"]["MAE"] == lowest_mae_cand["MAE"]
    else:
        assert res["switch_recommended"] is False
        assert "NO MODEL SWITCH RECOMMENDED" in res["best_suited_model"]["selection_basis"] or "Current deployed model" in res["best_suited_model"]["selection_basis"]


def test_no_model_switch_without_explicit_confirmation(temp_registry):
    """
    Test 6: Comparing candidates NEVER mutates the active deployed model without explicit switch.
    """
    initial_active = get_active_model_id(temp_registry, "Iddq")
    csv_path = "data/v2/demo_burnin_data.csv"

    # Run comparison
    _ = compare_candidates_on_dataset(csv_path, "Iddq", registry_dir=temp_registry)

    # Active model must remain unchanged
    after_compare = get_active_model_id(temp_registry, "Iddq")
    assert after_compare == initial_active


def test_explicit_model_switch_preserves_version_history_and_updates_deployment(temp_registry):
    """
    Test 7, 8 & 9:
    - Model registry preserves previous version (v1 preserved untouched).
    - New model becomes deployed only after confirmed switch (v2 created).
    - Model switch audit event is generated.
    """
    csv_path = "data/v2/demo_burnin_data.csv"
    prev_model = get_active_model_id(temp_registry, "leakage_current")
    assert prev_model == "module_b_leakage_current_v1"

    # Mandatory reason validation
    with pytest.raises(ValueError, match="mandatory"):
        execute_model_switch(
            parameter="leakage_current",
            candidate_name="Ridge",
            csv_path=csv_path,
            reason="",
            registry_dir=temp_registry,
        )

    # Execute valid model switch
    reason_text = "Validation MAE reduced on newly completed benchmark dataset."
    switch_res = execute_model_switch(
        parameter="leakage_current",
        candidate_name="Ridge",
        csv_path=csv_path,
        reason=reason_text,
        operator="E. Mercer [L3-ENG]",
        registry_dir=temp_registry,
    )

    assert switch_res["event_type"] == "MODEL_DEPLOYMENT_CHANGE"
    assert switch_res["previous_model"] == "module_b_leakage_current_v1"
    assert switch_res["new_model"] == "module_b_leakage_current_v2"
    assert switch_res["status"] == "DEPLOYED"

    # Check active model changed
    active_now = get_active_model_id(temp_registry, "leakage_current")
    assert active_now == "module_b_leakage_current_v2"

    # Check previous version artifact is intact
    v1_dir = os.path.join(temp_registry, "module_b_leakage_current_v1")
    assert os.path.exists(os.path.join(v1_dir, "model.pkl"))
    assert os.path.exists(os.path.join(v1_dir, "registry.json"))

    # Check new version artifact exists
    v2_dir = os.path.join(temp_registry, "module_b_leakage_current_v2")
    assert os.path.exists(os.path.join(v2_dir, "model.pkl"))
    assert os.path.exists(os.path.join(v2_dir, "registry.json"))

    # Check version listing shows v2 as active and v1 as previous
    versions = list_model_versions(temp_registry, parameter="leakage_current")
    v1_meta = next(v for v in versions if v["model_id"] == "module_b_leakage_current_v1")
    v2_meta = next(v for v in versions if v["model_id"] == "module_b_leakage_current_v2")
    assert v1_meta["is_active"] is False
    assert v2_meta["is_active"] is True


def test_production_screening_service_uses_new_model_after_switch(temp_registry):
    """
    Test 10 & 11:
    - Subsequent screening runs use the newly deployed model.
    - Existing screening behavior remains intact.
    """
    service = ScreeningService(registry_dir=temp_registry)

    # Initial predictor uses v1
    pred_v1 = service.pipeline.risk_engine._predictors["leakage_current"]
    assert pred_v1.model_id == "module_b_leakage_current_v1"

    # Switch model to v2
    service.switch_deployed_model(
        parameter="leakage_current",
        candidate_name="Ridge",
        csv_path="data/v2/demo_burnin_data.csv",
        reason="Model refresh post burn-in qualification.",
        operator="E. Mercer [L3-ENG]",
    )

    # Predictor in risk engine should now use v2!
    pred_v2 = service.pipeline.risk_engine._predictors["leakage_current"]
    assert pred_v2.model_id == "module_b_leakage_current_v2"

    # Run screening on demo data
    screening_res = service.run_screening("data/v2/demo_burnin_data.csv")
    assert screening_res.validation_status == "PASS"
    assert screening_res.total_components == 250
    assert not screening_res.aborted

    # Check that model switch audit trail was recorded
    audit_history = service.audit_recorder.list_model_switches()
    assert len(audit_history) >= 1
    assert audit_history[-1]["event_type"] == "MODEL_DEPLOYMENT_CHANGE"
    assert audit_history[-1]["new_model"] == "module_b_leakage_current_v2"
