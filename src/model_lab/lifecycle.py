"""
src/model_lab/lifecycle.py

Model Lab Re-Evaluation, Candidate Comparison, and Explicit Model Switch Workflow
for SIH26170 Module B Predictive Regression (Value_0h + Value_24h -> Value_168h).

Enforces:
    1. Re-evaluation of the active deployed model on completed historical observations
       without retraining.
    2. Strict feature boundary enforcement: input features strictly [Value_0h, Value_24h, delta_24_0].
       Value_96h and Value_168h are strictly forbidden as prediction inputs.
    3. Model comparison using the exact same evaluation dataset partition.
    4. Deterministic model selection rule: Primary = lowest MAE; Secondary = RMSE, R2.
    5. Explicit human model switch: Version history is preserved, previous model remains intact,
       new deployment is versioned (e.g. v1 -> v2), and the switch is auditable.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .candidates import CANDIDATE_ORDER, build_candidates
from .features import PRODUCTION_FEATURE_ALLOWLIST, _assert_feature_boundary, build_feature_matrix
from .predictor import ProductionPredictor
from .registry import (
    get_active_model_id,
    get_next_version_id,
    list_model_versions,
    load_model,
    register_model,
    set_active_model_id,
)
from .selector import select_winner
from .splitter import split_lots
from .trainer import train_candidates
from .uncertainty import fit_uncertainty


def validate_evaluation_dataset(df: pd.DataFrame, parameter: str) -> Dict[str, Any]:
    """
    Validate that an evaluation dataset satisfies the Module B contract:
    - Must contain required identifier and measurement columns: lot_id, component_id, parameter_name,
      value_0h, value_24h, value_168h.
    - Must have completed observations (non-null value_168h) for the specified parameter.
    - Must satisfy feature boundary: value_96h and value_168h are NEVER used in X.
    """
    errors: List[str] = []
    warnings: List[str] = []

    required_cols = ["lot_id", "component_id", "parameter_name", "value_0h", "value_24h", "value_168h"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {missing}")
        return {
            "valid": False,
            "parameter": parameter,
            "sample_count": 0,
            "lot_count": 0,
            "errors": errors,
            "warnings": warnings,
        }

    param_df = df[df["parameter_name"] == parameter].copy()
    if param_df.empty:
        errors.append(f"No observations found for parameter: {parameter}")
        return {
            "valid": False,
            "parameter": parameter,
            "sample_count": 0,
            "lot_count": 0,
            "errors": errors,
            "warnings": warnings,
        }

    # Check for NaN / infinite values in essential columns
    for col in ["value_0h", "value_24h", "value_168h"]:
        null_count = int(param_df[col].isna().sum())
        if null_count > 0:
            errors.append(f"Column '{col}' contains {null_count} null/NaN values.")
        inf_count = int(np.isinf(pd.to_numeric(param_df[col], errors="coerce")).sum())
        if inf_count > 0:
            errors.append(f"Column '{col}' contains {inf_count} infinite values.")

    # Check that lots are available
    lots = param_df["lot_id"].dropna().unique().tolist()
    if not lots:
        errors.append("No valid lot identifiers found in dataset.")

    is_valid = len(errors) == 0
    return {
        "valid": is_valid,
        "parameter": parameter,
        "sample_count": len(param_df),
        "lot_count": len(lots),
        "lots": sorted(lots),
        "errors": errors,
        "warnings": warnings,
    }


def reevaluate_deployed_model(
    csv_path: str,
    parameter: str,
    registry_dir: str = "models/registered",
) -> Dict[str, Any]:
    """
    Measure how the CURRENT DEPLOYED MODEL performs on newly completed screening data
    for which the actual Value_168h is available.

    This is NOT retraining.
    This is NOT automatic deployment.
    Uses ONLY Value_0h and Value_24h as inputs. Value_168h is the target only.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Evaluation dataset CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    val_report = validate_evaluation_dataset(df, parameter)
    if not val_report["valid"]:
        raise ValueError(f"Evaluation dataset validation failed for {parameter}: {val_report['errors']}")

    # Load currently active deployed model
    active_model_id = get_active_model_id(registry_dir, parameter)
    predictor = ProductionPredictor.from_registry(registry_dir, parameter, model_id=active_model_id)

    # Filter parameter rows
    param_df = df[df["parameter_name"] == parameter].copy()
    y_true = param_df["value_168h"].to_numpy(dtype=float)

    # Strictly construct production features
    param_df["delta_24_0"] = param_df["value_24h"].astype(float) - param_df["value_0h"].astype(float)
    X_prod = param_df[PRODUCTION_FEATURE_ALLOWLIST].copy()
    _assert_feature_boundary(X_prod)

    # Predict
    pred_res = predictor.predict(X_prod)
    y_pred = pred_res["predictions"].astype(float)
    y_lower = pred_res["lower_bounds"].astype(float)
    y_upper = pred_res["upper_bounds"].astype(float)

    # Calculate scalar metrics
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    try:
        r2 = float(r2_score(y_true, y_pred))
    except Exception:
        r2 = 0.0

    errors = y_pred - y_true
    abs_errors = np.abs(errors)
    mean_err = float(np.mean(errors))
    max_err = float(np.max(abs_errors))

    # Calculate residual distribution
    residual_dist = {
        "residual_mean": float(np.mean(errors)),
        "residual_std": float(np.std(errors)),
        "q05": float(np.percentile(errors, 5)),
        "q25": float(np.percentile(errors, 25)),
        "q50": float(np.percentile(errors, 50)),
        "q75": float(np.percentile(errors, 75)),
        "q95": float(np.percentile(errors, 95)),
    }

    # Lot-level performance breakdown
    lot_metrics = {}
    for lot_id in sorted(param_df["lot_id"].unique()):
        mask = (param_df["lot_id"] == lot_id).to_numpy()
        if mask.sum() > 0:
            lot_yt = y_true[mask]
            lot_yp = y_pred[mask]
            lot_metrics[lot_id] = {
                "sample_count": int(mask.sum()),
                "MAE": float(mean_absolute_error(lot_yt, lot_yp)),
                "RMSE": float(np.sqrt(mean_squared_error(lot_yt, lot_yp))),
            }

    # Original metadata from registry
    meta = predictor.registry_meta
    orig_winner_mae = meta.get("winner_MAE_val")
    delta_vs_orig_val = None
    if orig_winner_mae is not None:
        delta_vs_orig_val = float(mae - orig_winner_mae)

    return {
        "status": "success",
        "model_id": active_model_id,
        "parameter": parameter,
        "selected_model_class": predictor.selected_model_class,
        "evaluation_dataset": csv_path,
        "evaluation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(y_true),
        "lot_count": len(lot_metrics),
        "metrics": {
            "MAE": round(mae, 6),
            "RMSE": round(rmse, 6),
            "R2": round(r2, 6),
            "mean_error": round(mean_err, 6),
            "max_absolute_error": round(max_err, 6),
        },
        "residual_distribution": {k: round(v, 6) for k, v in residual_dist.items()},
        "lot_metrics": lot_metrics,
        "original_baseline": {
            "model_id": meta.get("model_id"),
            "original_val_MAE": orig_winner_mae,
            "original_dataset_id": meta.get("dataset_id"),
            "delta_MAE_vs_original": round(delta_vs_orig_val, 6) if delta_vs_orig_val is not None else None,
        },
    }


def compare_candidates_on_dataset(
    csv_path: str,
    parameter: str,
    registry_dir: str = "models/registered",
    config_path: str = "configs/model_lab_config.yaml",
) -> Dict[str, Any]:
    """
    Compare currently deployed model against available candidate models
    (Ridge, RandomForestRegressor, GradientBoostingRegressor, DummyRegressor)
    using the exact same evaluation dataset split.

    Deterministic selection rule:
        Primary: lowest MAE on the evaluation process
        Secondary: RMSE, R2
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Evaluation dataset CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    val_report = validate_evaluation_dataset(df, parameter)
    if not val_report["valid"]:
        raise ValueError(f"Dataset validation failed: {val_report['errors']}")

    # Load candidate configuration
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)["model_lab_config"]
    else:
        cfg = {"random_seed": 42, "candidates": {}}

    random_seed = cfg.get("random_seed", 42)
    all_lots = sorted(df[df["parameter_name"] == parameter]["lot_id"].unique().tolist())

    if len(all_lots) >= 2:
        # Standard lot-level split
        split = split_lots(
            all_lots,
            seed=random_seed,
            train_frac=0.60 if len(all_lots) >= 3 else 0.50,
            val_frac=0.40 if len(all_lots) >= 3 else 0.50,
        )
        train_lots = split["train_lots"]
        val_lots = split["val_lots"]
    else:
        # Fallback if only 1 lot exists: use all observations
        train_lots = all_lots
        val_lots = all_lots

    # 1. Train candidates on train partition & evaluate on validation partition
    fitted_candidates, candidate_metrics = train_candidates(
        df=df,
        parameter=parameter,
        train_lots=train_lots,
        val_lots=val_lots,
        config=cfg,
        random_seed=random_seed,
    )

    # 2. Evaluate current deployed model on the EXACT SAME validation partition
    active_model_id = get_active_model_id(registry_dir, parameter)
    deployed_predictor = ProductionPredictor.from_registry(registry_dir, parameter, model_id=active_model_id)

    X_val, y_val, _ = build_feature_matrix(df, parameter, val_lots)
    deployed_pred = deployed_predictor.predict(X_val)["predictions"].astype(float)
    y_val_np = y_val.to_numpy(dtype=float)

    deployed_mae = float(mean_absolute_error(y_val_np, deployed_pred))
    deployed_rmse = float(np.sqrt(mean_squared_error(y_val_np, deployed_pred)))
    try:
        deployed_r2 = float(r2_score(y_val_np, deployed_pred))
    except Exception:
        deployed_r2 = 0.0

    # 3. Assemble unified comparison table
    comparison_table: List[Dict[str, Any]] = []

    # Current deployed entry
    comparison_table.append({
        "model_name": f"Current Deployed ({active_model_id})",
        "candidate_key": "CURRENT_DEPLOYED",
        "model_type": deployed_predictor.selected_model_class,
        "is_deployed": True,
        "MAE": round(deployed_mae, 6),
        "RMSE": round(deployed_rmse, 6),
        "R2": round(deployed_r2, 6),
        "delta_MAE_vs_deployed": 0.0,
        "delta_RMSE_vs_deployed": 0.0,
        "status": "CURRENT_DEPLOYED",
    })

    # Add each candidate
    for name in CANDIDATE_ORDER:
        if name not in candidate_metrics:
            continue
        pipeline = fitted_candidates[name]
        pred_cand = pipeline.predict(X_val)
        c_mae = float(mean_absolute_error(y_val_np, pred_cand))
        c_rmse = float(np.sqrt(mean_squared_error(y_val_np, pred_cand)))
        try:
            c_r2 = float(r2_score(y_val_np, pred_cand))
        except Exception:
            c_r2 = 0.0

        delta_mae = c_mae - deployed_mae
        delta_rmse = c_rmse - deployed_rmse

        comparison_table.append({
            "model_name": name,
            "candidate_key": name,
            "model_type": name,
            "is_deployed": False,
            "MAE": round(c_mae, 6),
            "RMSE": round(c_rmse, 6),
            "R2": round(c_r2, 6),
            "delta_MAE_vs_deployed": round(delta_mae, 6),
            "delta_RMSE_vs_deployed": round(delta_rmse, 6),
            "status": "CANDIDATE",
        })

    # 4. Identify best-suited candidate using lowest MAE
    # Filter candidates (excluding CURRENT_DEPLOYED entry)
    candidate_entries = [row for row in comparison_table if not row["is_deployed"]]
    candidate_entries.sort(key=lambda r: (r["MAE"], r["RMSE"]))

    best_candidate = candidate_entries[0] if candidate_entries else None

    # Recommendation rule: candidate must strictly outperform deployed model
    # (i.e. lower MAE by meaningful epsilon 1e-4)
    switch_recommended = False
    best_suited_model_info = None

    if best_candidate and best_candidate["MAE"] < (deployed_mae - 0.0001):
        switch_recommended = True
        pct_improvement = ((deployed_mae - best_candidate["MAE"]) / deployed_mae) * 100.0 if deployed_mae > 0 else 0.0
        best_suited_model_info = {
            "model_name": best_candidate["model_name"],
            "candidate_key": best_candidate["candidate_key"],
            "model_type": best_candidate["model_type"],
            "MAE": best_candidate["MAE"],
            "RMSE": best_candidate["RMSE"],
            "R2": best_candidate["R2"],
            "deployed_MAE": round(deployed_mae, 6),
            "improvement_MAE": round(deployed_mae - best_candidate["MAE"], 6),
            "pct_improvement": round(pct_improvement, 2),
            "selection_basis": f"Lowest validation MAE ({best_candidate['MAE']:.4f} vs deployed {deployed_mae:.4f})",
        }
    else:
        switch_recommended = False
        best_suited_model_info = {
            "model_name": f"Current Deployed ({active_model_id})",
            "candidate_key": "CURRENT_DEPLOYED",
            "model_type": deployed_predictor.selected_model_class,
            "MAE": round(deployed_mae, 6),
            "RMSE": round(deployed_rmse, 6),
            "R2": round(deployed_r2, 6),
            "deployed_MAE": round(deployed_mae, 6),
            "improvement_MAE": 0.0,
            "pct_improvement": 0.0,
            "selection_basis": "Current deployed model already achieves lowest MAE; no candidate outperforms it.",
        }

    return {
        "status": "success",
        "parameter": parameter,
        "dataset_path": csv_path,
        "sample_count_val": len(y_val_np),
        "train_lots": train_lots,
        "val_lots": val_lots,
        "current_deployed_model": active_model_id,
        "current_deployed_mae": round(deployed_mae, 6),
        "comparison_table": comparison_table,
        "switch_recommended": switch_recommended,
        "best_suited_model": best_suited_model_info,
    }


def execute_model_switch(
    parameter: str,
    candidate_name: str,
    csv_path: str,
    reason: str,
    operator: str = "E. Mercer [L3-ENG]",
    registry_dir: str = "models/registered",
    config_path: str = "configs/model_lab_config.yaml",
) -> Dict[str, Any]:
    """
    Explicit Human Model Switch Workflow:
    1. Fits the selected candidate on the training partition of the evaluation dataset.
    2. Fits uncertainty estimation artifacts for the winner.
    3. Registers the new model as a sequential version (e.g. module_b_{param}_v2) preserving history.
    4. Updates active_models.json to make the new version the active deployed model.
    5. Returns deployment confirmation record.
    """
    if not reason or not str(reason).strip():
        raise ValueError("Model switch justification note is mandatory and cannot be empty.")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    val_report = validate_evaluation_dataset(df, parameter)
    if not val_report["valid"]:
        raise ValueError(f"Dataset validation failed: {val_report['errors']}")

    # Load config
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)["model_lab_config"]
    else:
        cfg = {"random_seed": 42, "lab_version": "v1.1.0-lifecycle", "candidates": {}}

    random_seed = cfg.get("random_seed", 42)
    all_lots = sorted(df[df["parameter_name"] == parameter]["lot_id"].unique().tolist())
    if len(all_lots) >= 2:
        split = split_lots(
            all_lots,
            seed=random_seed,
            train_frac=0.60 if len(all_lots) >= 3 else 0.50,
            val_frac=0.40 if len(all_lots) >= 3 else 0.50,
        )
        train_lots = split["train_lots"]
        val_lots = split["val_lots"]
        blind_lots = split.get("blind_lots", [])
    else:
        train_lots = all_lots
        val_lots = all_lots
        blind_lots = []

    # Train candidates
    fitted_candidates, metrics_table = train_candidates(
        df=df,
        parameter=parameter,
        train_lots=train_lots,
        val_lots=val_lots,
        config=cfg,
        random_seed=random_seed,
    )

    if candidate_name not in fitted_candidates:
        raise ValueError(f"Candidate '{candidate_name}' is not in available candidates: {list(fitted_candidates.keys())}")

    winner_pipeline = fitted_candidates[candidate_name]
    winner_mae_val = metrics_table[candidate_name]["MAE_val"]

    # Fit uncertainty estimation artifacts
    unc_artifacts = fit_uncertainty(
        selected_model_name=candidate_name,
        fitted_pipeline=winner_pipeline,
        df=df,
        parameter=parameter,
        train_lots=train_lots,
        config=cfg,
        random_seed=random_seed,
    )

    # Determine next version and previous version
    prev_model_id = get_active_model_id(registry_dir, parameter)
    new_model_id = get_next_version_id(registry_dir, parameter)

    # Load previous model metadata for audit
    old_val_mae = None
    try:
        _, prev_meta = load_model(registry_dir, prev_model_id)
        old_val_mae = prev_meta.get("winner_MAE_val")
    except Exception:
        pass

    # Register new model artifact (preserves previous model artifact untouched)
    saved_dir = register_model(
        output_dir=registry_dir,
        model_id=new_model_id,
        parameter=parameter,
        selected_model_name=candidate_name,
        fitted_pipeline=winner_pipeline,
        uncertainty_artifacts=unc_artifacts,
        metrics_table=metrics_table,
        winner_mae_val=winner_mae_val,
        train_lots=train_lots,
        val_lots=val_lots,
        blind_lots=blind_lots,
        split_seed=random_seed,
        dataset_id=os.path.basename(csv_path),
        dataset_sha256="",
        production_features=PRODUCTION_FEATURE_ALLOWLIST,
        lab_version=cfg.get("lab_version", "v1.1.0-lifecycle"),
    )

    # Update active deployed model pointer
    set_active_model_id(registry_dir, parameter, new_model_id)

    # Build confirmation record
    switch_record = {
        "status": "success",
        "event_type": "MODEL_DEPLOYMENT_CHANGE",
        "parameter": parameter,
        "previous_model": prev_model_id,
        "new_model": new_model_id,
        "selected_model_class": candidate_name,
        "evaluation_dataset": csv_path,
        "old_val_MAE": round(old_val_mae, 6) if old_val_mae is not None else None,
        "new_val_MAE": round(winner_mae_val, 6),
        "new_val_RMSE": round(metrics_table[candidate_name]["RMSE_val"], 6),
        "reason": str(reason).strip(),
        "operator": operator,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "DEPLOYED",
        "artifact_directory": saved_dir,
    }

    return switch_record
