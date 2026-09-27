#!/usr/bin/env python3
import json
import os
import sys
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.model_lab.predictor import ProductionPredictor
from src.model_lab.features import PRODUCTION_FEATURE_ALLOWLIST
from src.evaluation.metrics import calculate_scalar_metrics

def cohen_d(x, y):
    if len(x) == 0 or len(y) == 0:
        return 0.0
    nx = len(x)
    ny = len(y)
    dof = nx + ny - 2
    if dof <= 0:
        return 0.0
    pool_sd = np.sqrt(((nx - 1) * np.var(x, ddof=1) + (ny - 1) * np.var(y, ddof=1)) / dof)
    if pool_sd == 0:
        return 0.0
    return (np.mean(x) - np.mean(y)) / pool_sd

def analyze_early_signal():
    csv_path = "data/dev_burnin_data.csv"
    gt_path = "data/dev_burnin_groundtruth.json"
    registry_dir = "models/registered"
    split_info_path = os.path.join(registry_dir, "split_info.json")
    output_dir = "reports/evaluation"
    os.makedirs(output_dir, exist_ok=True)
    
    with open(split_info_path, "r") as f:
        split_info = json.load(f)
        
    train_val_lots = set(split_info["train_lots"] + split_info["val_lots"])
    
    df = pd.read_csv(csv_path)
    with open(gt_path, "r") as f:
        gt_data = json.load(f)
        
    comp_gt = {c["component_id"]: c for c in gt_data["component_level"]}
    
    df = df[df["lot_id"].isin(train_val_lots)].copy()
    df["delta_24_0"] = df["value_24h"] - df["value_0h"]
    df["behavioral_state"] = df["component_id"].map(lambda c: comp_gt[c]["behavioral_state"])
    df["is_latent_degrader"] = df["component_id"].map(lambda c: comp_gt[c]["is_latent_degrader"])
    df["early_detectability"] = df["component_id"].map(lambda c: comp_gt[c].get("early_detectability"))
    
    parameters = ["Iddq", "leakage_current", "propagation_delay"]
    
    results = {}
    
    for param in parameters:
        param_df = df[df["parameter_name"] == param].copy()
        if param_df.empty:
            continue
            
        predictor = ProductionPredictor.from_registry(registry_dir, param)
        X_prod = param_df[PRODUCTION_FEATURE_ALLOWLIST].copy()
        
        pred_res = predictor.predict(X_prod)
        param_df["pred_168h"] = pred_res["predictions"]
        
        results[param] = {
            "early_signal_measurement": {},
            "correlation": {},
            "frozen_model_performance": {}
        }
        
        groups = {
            "nominal": param_df[param_df["behavioral_state"] == "nominal"],
        }
        
        for ed in param_df["early_detectability"].dropna().unique():
            groups[f"latent_degrader_{ed}"] = param_df[param_df["early_detectability"] == ed]
            
        nom_df = groups["nominal"]
        
        for grp_name, grp_df in groups.items():
            if grp_df.empty:
                continue
                
            # Early signal measurement
            esm = {"count": len(grp_df)}
            for col in ["value_0h", "value_24h", "delta_24_0"]:
                vals = grp_df[col].values
                esm[col] = {
                    "mean": float(np.mean(vals)),
                    "median": float(np.median(vals)),
                    "std": float(np.std(vals)),
                    "q25": float(np.percentile(vals, 25)),
                    "q75": float(np.percentile(vals, 75))
                }
                if grp_name != "nominal":
                    esm[col]["cohen_d_vs_nominal"] = float(cohen_d(vals, nom_df[col].values))
            
            results[param]["early_signal_measurement"][grp_name] = esm
            
            # Correlation with true_value_168h
            corr = {"count": len(grp_df)}
            for col in ["value_0h", "value_24h", "delta_24_0"]:
                if len(grp_df) > 1 and np.std(grp_df[col]) > 0 and np.std(grp_df["value_168h"]) > 0:
                    r, _ = pearsonr(grp_df[col], grp_df["value_168h"])
                else:
                    r = 0.0
                corr[col] = float(r)
            results[param]["correlation"][grp_name] = corr
            
            # Frozen model performance
            metrics = calculate_scalar_metrics(grp_df["value_168h"].values, grp_df["pred_168h"].values)
            results[param]["frozen_model_performance"][grp_name] = {
                "count": len(grp_df),
                **metrics
            }
                
    json_path = os.path.join(output_dir, "early_signal_analysis.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
        
    md_path = os.path.join(output_dir, "early_signal_analysis.md")
    with open(md_path, "w") as f:
        f.write("# Early Signal Analysis Report\n\n")
        
        f.write("## Data Used\n")
        f.write("- Train + Validation Lots only. Blind Lots excluded.\n\n")
        
        for param, p_res in results.items():
            f.write(f"## Parameter: {param}\n\n")
            
            f.write("### Early-Signal Measurement (delta_24_0)\n")
            f.write("| Group | Count | Mean | Median | Std | Cohen's d vs Nominal |\n")
            f.write("|-------|-------|------|--------|-----|-----------------------|\n")
            for grp, esm in p_res["early_signal_measurement"].items():
                d = esm["delta_24_0"]
                f.write(f"| {grp} | {esm['count']} | {d['mean']:.4f} | {d['median']:.4f} | {d['std']:.4f} | {d.get('cohen_d_vs_nominal', 0):.4f} |\n")
            f.write("\n")
            
            f.write("### Early Signal vs Future Outcome (Correlation with value_168h)\n")
            f.write("| Group | Count | r(value_0h) | r(value_24h) | r(delta_24_0) |\n")
            f.write("|-------|-------|-------------|--------------|---------------|\n")
            for grp, corr in p_res["correlation"].items():
                f.write(f"| {grp} | {corr['count']} | {corr['value_0h']:.4f} | {corr['value_24h']:.4f} | {corr['delta_24_0']:.4f} |\n")
            f.write("\n")
            
            f.write("### Frozen Model Performance\n")
            f.write("| Group | Count | MAE | RMSE | Mean Error | Median Absolute Error |\n")
            f.write("|-------|-------|-----|------|------------|------------------------|\n")
            for grp, m in p_res["frozen_model_performance"].items():
                f.write(f"| {grp} | {m['count']} | {m.get('MAE',0):.4f} | {m.get('RMSE',0):.4f} | {m.get('mean_error',0):.4f} | {m.get('median_absolute_error',0):.4f} |\n")
            f.write("\n")

if __name__ == "__main__":
    analyze_early_signal()
