"""
src/evaluation/evaluator.py

Evaluates the models on the blind lots.
"""

import json
import os
import pandas as pd
import numpy as np
from typing import Dict, Any

from ..model_lab.predictor import ProductionPredictor
from ..model_lab.features import PRODUCTION_FEATURE_ALLOWLIST
from .metrics import (
    calculate_scalar_metrics,
    calculate_error_distribution,
    calculate_uncertainty_metrics
)

def evaluate_module_b(
    csv_path: str,
    gt_path: str,
    split_info_path: str,
    registry_dir: str,
    parameters: list = ["Iddq", "leakage_current", "propagation_delay"]
) -> Dict[str, Any]:
    
    # 1. Integrity checks
    with open(split_info_path, "r") as f:
        split_info = json.load(f)
    
    train_lots = set(split_info["train_lots"])
    val_lots = set(split_info["val_lots"])
    blind_lots = set(split_info["blind_lots"])
    
    if train_lots.intersection(blind_lots):
        raise ValueError("Integrity Violation: Train and Blind lots overlap!")
    if val_lots.intersection(blind_lots):
        raise ValueError("Integrity Violation: Val and Blind lots overlap!")
        
    df = pd.read_csv(csv_path)
    with open(gt_path, "r") as f:
        gt_data = json.load(f)
    
    # Create component mapping for GT
    comp_gt = {c["component_id"]: c for c in gt_data["component_level"]}
    
    # Filter to blind lots
    blind_df = df[df["lot_id"].isin(blind_lots)].copy()
    
    results = {
        "metadata": {
            "dataset_id": split_info.get("dataset_id"),
            "dataset_sha256": split_info.get("dataset_sha256"),
            "split_seed": split_info.get("split_seed"),
            "blind_lots": list(blind_lots),
            "n_blind_lots": len(blind_lots)
        },
        "parameters": {}
    }
    
    for param in parameters:
        print(f"Evaluating {param}...")
        
        # Load predictor
        try:
            predictor = ProductionPredictor.from_registry(registry_dir, param)
        except Exception as e:
            raise RuntimeError(f"Integrity Violation: Failed to load model for {param}. Error: {e}")
        
        # Filter param rows
        param_df = blind_df[blind_df["parameter_name"] == param].copy()
        
        if param_df.empty:
            continue
            
        # Ensure target is present
        if "value_168h" not in param_df.columns:
            raise ValueError(f"Integrity Violation: Target value_168h missing for {param}")
            
        y_true = param_df["value_168h"].values
        
        # Build strict features
        param_df["delta_24_0"] = param_df["value_24h"] - param_df["value_0h"]
        X_prod = param_df[PRODUCTION_FEATURE_ALLOWLIST].copy()
        
        # Check forbidden features
        forbidden = ["value_96h", "value_168h"]
        for f in forbidden:
            if f in X_prod.columns:
                raise ValueError(f"Integrity Violation: Forbidden feature {f} in X")
                
        # Predict
        pred_res = predictor.predict(X_prod)
        y_pred = pred_res["predictions"]
        y_lower = pred_res["lower_bounds"]
        y_upper = pred_res["upper_bounds"]
        unc_method = pred_res["uncertainty_method"]
        
        # Aggregate metrics
        scalar = calculate_scalar_metrics(y_true, y_pred)
        dist = calculate_error_distribution(y_true, y_pred)
        unc = calculate_uncertainty_metrics(y_true, y_lower, y_upper)
        
        # Attach GT behavioral states
        param_df["behavioral_state"] = param_df["component_id"].apply(lambda cid: comp_gt[cid]["behavioral_state"])
        param_df["is_latent_degrader"] = param_df["component_id"].apply(lambda cid: comp_gt[cid]["is_latent_degrader"])
        param_df["is_population_anomaly"] = param_df["component_id"].apply(lambda cid: comp_gt[cid]["is_population_anomaly"])
        param_df["y_true"] = y_true
        param_df["y_pred"] = y_pred
        
        # Group metrics
        behavioral_groups = {}
        for state in param_df["behavioral_state"].unique():
            mask = param_df["behavioral_state"] == state
            if mask.sum() > 0:
                behavioral_groups[state] = {
                    "count": int(mask.sum()),
                    **calculate_scalar_metrics(y_true[mask], y_pred[mask])
                }
                
        # Latent degrader specific
        ld_mask = param_df["is_latent_degrader"] == True
        latent_metrics = None
        if ld_mask.sum() > 0:
            latent_metrics = {
                "count": int(ld_mask.sum()),
                **calculate_scalar_metrics(y_true[ld_mask], y_pred[ld_mask])
            }
            
        results["parameters"][param] = {
            "model_id": predictor.model_id,
            "selected_model_class": predictor.selected_model_class,
            "uncertainty_method": unc_method,
            "sample_count": len(y_true),
            "aggregate_metrics": scalar,
            "error_distribution": dist,
            "uncertainty_metrics": unc,
            "behavioral_groups": behavioral_groups,
            "latent_degrader_metrics": latent_metrics
        }
        
    return results
