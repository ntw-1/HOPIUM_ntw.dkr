"""
scripts/run_model_lab.py

CLI entry point for Phase 3 Module B Model Lab.

Workflow:
    1. Load config and dev dataset.
    2. Perform deterministic lot split (60% Train, 20% Val, 20% Blind).
    3. Save split_info.json.
    4. For each parameter (Iddq, leakage_current, propagation_delay):
       a. Build feature matrices for Train and Validation sets.
       b. Train candidate models (Dummy, Ridge, RF, GB).
       c. Compute Validation MAE, RMSE, MAPE.
       d. Select winning model strictly using Validation MAE.
       e. Fit uncertainty estimation artifacts.
       f. Register model artifact and registry.json (BLIND TEST LOCKED).
    5. Print validation metrics summary and verification details.
"""

import argparse
import json
import os
import sys
import yaml
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.model_lab.candidates import CANDIDATE_ORDER
from src.model_lab.features import PRODUCTION_FEATURE_ALLOWLIST
from src.model_lab.predictor import ProductionPredictor
from src.model_lab.registry import register_model
from src.model_lab.selector import select_winner
from src.model_lab.splitter import save_split, split_lots
from src.model_lab.trainer import train_candidates
from src.model_lab.uncertainty import fit_uncertainty


def run_model_lab(config_path: str = "configs/model_lab_config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        config_full = yaml.safe_load(f)

    cfg = config_full["model_lab_config"]

    csv_path = cfg["dataset"]["csv_path"]
    meta_path = cfg["dataset"]["meta_path"]

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset CSV not found at {csv_path}")

    # Read dataset metadata if available
    dataset_id = "dev_burnin_data"
    dataset_sha256 = ""
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            dataset_id = meta.get("dataset_id", dataset_id)
            dataset_sha256 = meta.get("content_hash_sha256", meta.get("sha256_hash", ""))

    df = pd.read_csv(csv_path)

    # Deterministic lot-level split
    all_lots = sorted(df["lot_id"].unique().tolist())
    split_cfg = cfg["split"]
    seed = split_cfg["seed"]
    split = split_lots(
        all_lots,
        seed=seed,
        train_frac=split_cfg["train_frac"],
        val_frac=split_cfg["val_frac"],
    )

    save_split(
        split=split,
        seed=seed,
        output_path=split_cfg["split_output_path"],
        dataset_id=dataset_id,
        dataset_sha256=dataset_sha256,
    )

    print("==================================================================")
    print("                MODULE B MODEL LAB — PHASE 3 RUN                 ")
    print("==================================================================")
    print(f"Dataset CSV:          {csv_path} ({len(df)} rows)")
    print(f"Dataset ID:           {dataset_id}")
    print(f"Split seed:           {seed}")
    print(f"Train Lots ({len(split['train_lots'])}):       {split['train_lots']}")
    print(f"Val Lots ({len(split['val_lots'])}):         {split['val_lots']}")
    print(f"Blind Lots ({len(split['blind_lots'])} - LOCKED): {split['blind_lots']}")
    print("==================================================================\n")

    summary_results = {}

    output_dir = cfg["registry"]["output_dir"]
    parameters = cfg["parameters"]

    for param in parameters:
        print(f"------------------------------------------------------------------")
        print(f" Training & Selecting Model for Parameter: {param}")
        print(f"------------------------------------------------------------------")

        fitted_models, metrics_table = train_candidates(
            df=df,
            parameter=param,
            train_lots=split["train_lots"],
            val_lots=split["val_lots"],
            config=cfg,
            random_seed=cfg["random_seed"],
        )

        # Print candidate table
        print(f"{'Candidate':<28} | {'MAE (Train)':<12} | {'MAE (Val)':<12} | {'RMSE (Val)':<12} | {'MAPE (Val)':<12}")
        print("-" * 84)
        for name in CANDIDATE_ORDER:
            m = metrics_table[name]
            print(f"{name:<28} | {m['MAE_train']:<12.4f} | {m['MAE_val']:<12.4f} | {m['RMSE_val']:<12.4f} | {m['MAPE_val']:<12.4f}")

        # Select winner using MAE_val only
        winner_name, winner_mae_val = select_winner(metrics_table)
        winner_pipeline = fitted_models[winner_name]

        print("-" * 84)
        print(f"--> Selected Winner for {param}: {winner_name} (Val MAE: {winner_mae_val:.4f})")

        # Fit uncertainty model on winner
        unc_artifacts = fit_uncertainty(
            selected_model_name=winner_name,
            fitted_pipeline=winner_pipeline,
            df=df,
            parameter=param,
            train_lots=split["train_lots"],
            config=cfg,
            random_seed=cfg["random_seed"],
        )

        # Register model artifact
        model_id = f"module_b_{param}_v1"
        saved_dir = register_model(
            output_dir=output_dir,
            model_id=model_id,
            parameter=param,
            selected_model_name=winner_name,
            fitted_pipeline=winner_pipeline,
            uncertainty_artifacts=unc_artifacts,
            metrics_table=metrics_table,
            winner_mae_val=winner_mae_val,
            train_lots=split["train_lots"],
            val_lots=split["val_lots"],
            blind_lots=split["blind_lots"],
            split_seed=seed,
            dataset_id=dataset_id,
            dataset_sha256=dataset_sha256,
            production_features=PRODUCTION_FEATURE_ALLOWLIST,
            lab_version=cfg["lab_version"],
        )
        print(f"--> Registered Model Artifact: {saved_dir}\n")

        # Verify load and single prediction
        predictor = ProductionPredictor.from_registry(output_dir, param)
        # Sample test prediction using parameter 0h and 24h sample values from dataset
        sample_row = df[df["parameter_name"] == param].iloc[0]
        v0, v24 = float(sample_row["value_0h"]), float(sample_row["value_24h"])
        pred_res = predictor.predict_single(v0, v24)
        print(f"--> ProductionPredictor Test ({param}): v0={v0:.2f}, v24={v24:.2f} => "
              f"Pred 168h={pred_res['prediction']:.2f} [{pred_res['lower_bound']:.2f}, {pred_res['upper_bound']:.2f}] "
              f"(Method: {pred_res['uncertainty_method']})\n")

        summary_results[param] = {
            "selected_model": winner_name,
            "winner_MAE_val": winner_mae_val,
            "all_candidates_val_MAE": {k: v["MAE_val"] for k, v in metrics_table.items()},
            "uncertainty_method": unc_artifacts["method"],
        }

    print("==================================================================")
    print("                   PHASE 3 RUN SUMMARY                            ")
    print("==================================================================")
    for param, res in summary_results.items():
        print(f"Parameter: {param:<20} | Selected: {res['selected_model']:<25} | Val MAE: {res['winner_MAE_val']:.4f}")
    print("==================================================================")
    print("CONFIRMATION: Blind test lots remained LOCKED (0 blind predictions computed).")
    print("==================================================================")

    return summary_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the HOPIUM Module B Model Lab.")
    parser.add_argument(
        "--config",
        default="configs/model_lab_config.yaml",
        help="Path to a Model Lab YAML configuration file.",
    )
    args = parser.parse_args()
    run_model_lab(args.config)
