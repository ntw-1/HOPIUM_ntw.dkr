"""
tests/unit/test_module_b_features.py

Unit tests for Phase 3 Module B Model Lab:
    - Production feature boundary & leakage guards (strictly value_0h, value_24h, delta_24_0 in X)
    - Source CSV compatibility (source dataframe contains value_96h/value_168h without error)
    - Deterministic, disjoint, total-coverage lot-level split
    - Blind test lock verification (no blind metrics in registry, blind lots untouched)
    - Validation MAE driven model selection (ignoring training MAE, RMSE, MAPE)
    - Artifact saving, loading, and production prediction schema
    - Prediction uncertainty envelope invariant (lower_bound <= prediction <= upper_bound)
"""

import os
import shutil
import tempfile
import pytest
import numpy as np
import pandas as pd
import yaml

from src.model_lab.candidates import CANDIDATE_ORDER, build_candidates
from src.model_lab.features import (
    PRODUCTION_FEATURE_ALLOWLIST,
    _assert_feature_boundary,
    build_feature_matrix,
)
from src.model_lab.predictor import ProductionPredictor
from src.model_lab.registry import load_model, register_model
from src.model_lab.selector import select_winner
from src.model_lab.splitter import load_split, save_split, split_lots
from src.model_lab.trainer import train_candidates
from src.model_lab.uncertainty import fit_uncertainty


@pytest.fixture
def sample_long_df():
    """Create a synthetic long-format DataFrame matching dev dataset schema."""
    rows = []
    lots = [f"LOT_{i:03d}" for i in range(1, 21)]
    params = ["Iddq", "leakage_current", "propagation_delay"]

    for lot in lots:
        for c in range(1, 11):
            comp_id = f"{lot}_CMP_{c:04d}"
            for p in params:
                v0 = 10.0 if p == "Iddq" else (5.0 if p == "leakage_current" else 120.0)
                v24 = v0 + 0.5
                v96 = v24 + 1.0
                v168 = v96 + 1.5
                rows.append({
                    "lot_id": lot,
                    "component_id": comp_id,
                    "parameter_name": p,
                    "unit": "uA" if p == "Iddq" else ("nA" if p == "leakage_current" else "ps"),
                    "value_0h": v0 + np.random.normal(0, 0.1),
                    "value_24h": v24 + np.random.normal(0, 0.1),
                    "value_96h": v96 + np.random.normal(0, 0.1),
                    "value_168h": v168 + np.random.normal(0, 0.1),
                    "synthetic_spec_min": 0.0,
                    "synthetic_spec_max": 50.0,
                })
    return pd.DataFrame(rows)


@pytest.fixture
def config_dict():
    with open("configs/model_lab_config.yaml", "r", encoding="utf-8") as f:
        full = yaml.safe_load(f)
    return full["model_lab_config"]


# -----------------------------------------------------------------------------
# 1. PRODUCTION FEATURE BOUNDARY TESTS
# -----------------------------------------------------------------------------

def test_allowed_production_feature_columns(sample_long_df):
    """1. X must contain strictly value_0h, value_24h, delta_24_0."""
    lots = sample_long_df["lot_id"].unique().tolist()
    X, y, comp_ids = build_feature_matrix(sample_long_df, "Iddq", lots[:5])
    assert list(X.columns) == ["value_0h", "value_24h", "delta_24_0"]


def test_value_96h_excluded_from_X(sample_long_df):
    """2. value_96h must be absent from feature matrix X."""
    lots = sample_long_df["lot_id"].unique().tolist()[:5]
    X, _, _ = build_feature_matrix(sample_long_df, "Iddq", lots)
    assert "value_96h" not in X.columns


def test_value_168h_excluded_from_X(sample_long_df):
    """3. value_168h must be absent from feature matrix X."""
    lots = sample_long_df["lot_id"].unique().tolist()[:5]
    X, _, _ = build_feature_matrix(sample_long_df, "leakage_current", lots)
    assert "value_168h" not in X.columns


def test_ground_truth_labels_excluded_from_X():
    """4. Ground-truth classification columns must raise ValueError if passed into X."""
    bad_df_gt = pd.DataFrame({
        "value_0h": [10.0],
        "value_24h": [10.5],
        "delta_24_0": [0.5],
        "behavioral_state": ["nominal"],
    })
    with pytest.raises(ValueError, match="LEAKAGE DETECTED"):
        _assert_feature_boundary(bad_df_gt)


def test_delta_24_0_correctness(sample_long_df):
    """5. delta_24_0 must strictly equal value_24h - value_0h."""
    lots = sample_long_df["lot_id"].unique().tolist()[:5]
    X, _, _ = build_feature_matrix(sample_long_df, "propagation_delay", lots)
    expected_delta = X["value_24h"] - X["value_0h"]
    np.testing.assert_allclose(X["delta_24_0"].values, expected_delta.values, rtol=1e-6)


# -----------------------------------------------------------------------------
# 2. DETERMINISTIC LOT SPLIT TESTS
# -----------------------------------------------------------------------------

def test_deterministic_lot_split(sample_long_df):
    """6. Two calls to split_lots with same seed must produce identical partitions."""
    lots = sample_long_df["lot_id"].unique().tolist()
    split1 = split_lots(lots, seed=42)
    split2 = split_lots(lots, seed=42)
    assert split1["train_lots"] == split2["train_lots"]
    assert split1["val_lots"] == split2["val_lots"]
    assert split1["blind_lots"] == split2["blind_lots"]


def test_disjoint_lot_split(sample_long_df):
    """7. Train, Val, and Blind lot sets must have zero intersection."""
    lots = sample_long_df["lot_id"].unique().tolist()
    split = split_lots(lots, seed=42)
    assert len(set(split["train_lots"]) & set(split["val_lots"])) == 0
    assert len(set(split["train_lots"]) & set(split["blind_lots"])) == 0
    assert len(set(split["val_lots"]) & set(split["blind_lots"])) == 0


def test_all_lots_covered(sample_long_df):
    """8. Union of train, val, and blind lots must equal full lot list."""
    lots = sample_long_df["lot_id"].unique().tolist()
    split = split_lots(lots, seed=42)
    union_lots = set(split["train_lots"]) | set(split["val_lots"]) | set(split["blind_lots"])
    assert union_lots == set(lots)


def test_blind_lots_not_used_before_final_evaluation(sample_long_df, config_dict):
    """9. Blind lots must not be passed to trainer or evaluated in registry metadata."""
    lots = sample_long_df["lot_id"].unique().tolist()
    split = split_lots(lots, seed=42)

    fitted_models, metrics = train_candidates(
        df=sample_long_df,
        parameter="Iddq",
        train_lots=split["train_lots"],
        val_lots=split["val_lots"],
        config=config_dict,
        random_seed=42,
    )
    winner_name, winner_mae = select_winner(metrics)
    winner_pipeline = fitted_models[winner_name]

    unc_artifacts = fit_uncertainty(
        selected_model_name=winner_name,
        fitted_pipeline=winner_pipeline,
        df=sample_long_df,
        parameter="Iddq",
        train_lots=split["train_lots"],
        config=config_dict,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        save_dir = register_model(
            output_dir=tmpdir,
            model_id="module_b_Iddq_v1",
            parameter="Iddq",
            selected_model_name=winner_name,
            fitted_pipeline=winner_pipeline,
            uncertainty_artifacts=unc_artifacts,
            metrics_table=metrics,
            winner_mae_val=winner_mae,
            train_lots=split["train_lots"],
            val_lots=split["val_lots"],
            blind_lots=split["blind_lots"],
            split_seed=42,
            dataset_id="test_dataset",
            dataset_sha256="dummy_hash",
            production_features=PRODUCTION_FEATURE_ALLOWLIST,
            lab_version="v1.0.0-phase3",
        )
        loaded = load_model(save_dir)
        registry = loaded["registry"]
        assert "DEFERRED" in registry["blind_test_metrics"]
        assert "MAE_blind" not in registry


# -----------------------------------------------------------------------------
# 3. TRAINING & SELECTION TESTS
# -----------------------------------------------------------------------------

def test_candidate_training_succeeds(sample_long_df, config_dict):
    """10. Candidate training must fit all four candidates and yield non-negative MAE."""
    lots = sample_long_df["lot_id"].unique().tolist()
    split = split_lots(lots, seed=42)
    fitted_models, metrics = train_candidates(
        df=sample_long_df,
        parameter="Iddq",
        train_lots=split["train_lots"],
        val_lots=split["val_lots"],
        config=config_dict,
        random_seed=42,
    )
    assert set(fitted_models.keys()) == set(CANDIDATE_ORDER)
    for name, m in metrics.items():
        assert m["MAE_val"] >= 0.0


def test_selection_uses_validation_mae_only():
    """11. Selection function must choose candidate with lowest MAE_val, ignoring training MAE or RMSE."""
    mock_metrics = {
        "Ridge": {"MAE_train": 1.0, "MAE_val": 5.0, "RMSE_val": 6.0},
        "RandomForestRegressor": {"MAE_train": 3.0, "MAE_val": 2.0, "RMSE_val": 10.0},
        "GradientBoostingRegressor": {"MAE_train": 0.1, "MAE_val": 3.0, "RMSE_val": 4.0},
        "DummyRegressor": {"MAE_train": 10.0, "MAE_val": 10.0, "RMSE_val": 12.0},
    }
    winner_name, winner_mae = select_winner(mock_metrics)
    assert winner_name == "RandomForestRegressor"
    assert winner_mae == 2.0


def test_mape_is_not_selection_criterion():
    """12. Selection function must select based on MAE_val even if another candidate has lower MAPE_val."""
    mock_metrics = {
        "Ridge": {"MAE_val": 2.0, "MAPE_val": 0.50},
        "RandomForestRegressor": {"MAE_val": 3.0, "MAPE_val": 0.10},
    }
    winner_name, winner_mae = select_winner(mock_metrics)
    assert winner_name == "Ridge"
    assert winner_mae == 2.0


# -----------------------------------------------------------------------------
# 4. ARTIFACT & PREDICTOR TESTS
# -----------------------------------------------------------------------------

def test_artifact_loads_correctly(sample_long_df, config_dict):
    """13. register_model and load_model must round-trip fitted pipelines and registry dict."""
    lots = sample_long_df["lot_id"].unique().tolist()
    split = split_lots(lots, seed=42)
    fitted_models, metrics = train_candidates(
        df=sample_long_df,
        parameter="leakage_current",
        train_lots=split["train_lots"],
        val_lots=split["val_lots"],
        config=config_dict,
    )
    winner_name, winner_mae = select_winner(metrics)
    fitted_pipeline = fitted_models[winner_name]
    unc_art = fit_uncertainty(winner_name, fitted_pipeline, sample_long_df, "leakage_current", split["train_lots"], config_dict)

    with tempfile.TemporaryDirectory() as tmpdir:
        save_dir = register_model(
            output_dir=tmpdir,
            model_id="module_b_leakage_current_v1",
            parameter="leakage_current",
            selected_model_name=winner_name,
            fitted_pipeline=fitted_pipeline,
            uncertainty_artifacts=unc_art,
            metrics_table=metrics,
            winner_mae_val=winner_mae,
            train_lots=split["train_lots"],
            val_lots=split["val_lots"],
            blind_lots=split["blind_lots"],
            split_seed=42,
            dataset_id="test",
            dataset_sha256="",
            production_features=PRODUCTION_FEATURE_ALLOWLIST,
            lab_version="v1.0.0-phase3",
        )
        loaded = load_model(save_dir)
        assert "pipeline" in loaded
        assert "uncertainty_artifacts" in loaded
        assert loaded["registry"]["model_id"] == "module_b_leakage_current_v1"


def test_predictor_output_schema(sample_long_df, config_dict):
    """14. ProductionPredictor must return dictionary matching expected output schema."""
    lots = sample_long_df["lot_id"].unique().tolist()
    split = split_lots(lots, seed=42)
    fitted_models, metrics = train_candidates(
        df=sample_long_df,
        parameter="propagation_delay",
        train_lots=split["train_lots"],
        val_lots=split["val_lots"],
        config=config_dict,
    )
    winner_name, winner_mae = select_winner(metrics)
    fitted_pipeline = fitted_models[winner_name]
    unc_art = fit_uncertainty(winner_name, fitted_pipeline, sample_long_df, "propagation_delay", split["train_lots"], config_dict)

    with tempfile.TemporaryDirectory() as tmpdir:
        register_model(
            output_dir=tmpdir,
            model_id="module_b_propagation_delay_v1",
            parameter="propagation_delay",
            selected_model_name=winner_name,
            fitted_pipeline=fitted_pipeline,
            uncertainty_artifacts=unc_art,
            metrics_table=metrics,
            winner_mae_val=winner_mae,
            train_lots=split["train_lots"],
            val_lots=split["val_lots"],
            blind_lots=split["blind_lots"],
            split_seed=42,
            dataset_id="test",
            dataset_sha256="",
            production_features=PRODUCTION_FEATURE_ALLOWLIST,
            lab_version="v1.0.0-phase3",
        )
        predictor = ProductionPredictor.from_registry(tmpdir, "propagation_delay")
        res = predictor.predict_single(120.0, 120.5)
        assert set(res.keys()) == {"prediction", "lower_bound", "upper_bound", "uncertainty_method", "parameter", "model_id"}


# -----------------------------------------------------------------------------
# 5. UNCERTAINTY INVARIANT TEST
# -----------------------------------------------------------------------------

def test_uncertainty_interval_brackets_prediction(sample_long_df, config_dict):
    """15. REGRESSION TEST: ProductionPredictor MUST ALWAYS satisfy lower_bound <= prediction <= upper_bound."""
    lots = sample_long_df["lot_id"].unique().tolist()
    split = split_lots(lots, seed=42)

    for param in ["Iddq", "leakage_current", "propagation_delay"]:
        fitted_models, metrics = train_candidates(
            df=sample_long_df,
            parameter=param,
            train_lots=split["train_lots"],
            val_lots=split["val_lots"],
            config=config_dict,
            random_seed=42,
        )
        winner_name, winner_mae = select_winner(metrics)
        winner_pipeline = fitted_models[winner_name]
        unc_art = fit_uncertainty(winner_name, winner_pipeline, sample_long_df, param, split["train_lots"], config_dict, random_seed=42)

        with tempfile.TemporaryDirectory() as tmpdir:
            register_model(
                output_dir=tmpdir,
                model_id=f"module_b_{param}_v1",
                parameter=param,
                selected_model_name=winner_name,
                fitted_pipeline=winner_pipeline,
                uncertainty_artifacts=unc_art,
                metrics_table=metrics,
                winner_mae_val=winner_mae,
                train_lots=split["train_lots"],
                val_lots=split["val_lots"],
                blind_lots=split["blind_lots"],
                split_seed=42,
                dataset_id="test",
                dataset_sha256="",
                production_features=PRODUCTION_FEATURE_ALLOWLIST,
                lab_version="v1.0.0-phase3",
            )
            predictor = ProductionPredictor.from_registry(tmpdir, param)
            X_val, _, _ = build_feature_matrix(sample_long_df, param, split["val_lots"])
            res = predictor.predict(X_val)

            preds = res["predictions"]
            lowers = res["lower_bounds"]
            uppers = res["upper_bounds"]

            assert np.all(lowers <= preds + 1e-9), f"Parameter {param}: lower_bound exceeds prediction!"
            assert np.all(preds <= uppers + 1e-9), f"Parameter {param}: prediction exceeds upper_bound!"
