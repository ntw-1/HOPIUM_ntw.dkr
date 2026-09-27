#!/usr/bin/env python3
import json
import os
import sys
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

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

def analyze_predictive_signal():
    csv_path = "data/dev_burnin_data.csv"
    gt_path = "data/dev_burnin_groundtruth.json"
    split_info_path = "models/registered/split_info.json"
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
    df["normalized_delta"] = df["delta_24_0"] / (df["synthetic_spec_max"] - df["synthetic_spec_min"])
    df["future_drift"] = df["value_168h"] - df["value_0h"]
    df["future_slope"] = df["future_drift"] / 168.0
    
    df["behavioral_state"] = df["component_id"].map(lambda c: comp_gt[c]["behavioral_state"])
    df["is_latent_degrader"] = df["component_id"].map(lambda c: comp_gt[c]["is_latent_degrader"])
    df["early_detectability"] = df["component_id"].map(lambda c: comp_gt[c].get("early_detectability"))
    
    parameters = ["Iddq", "leakage_current", "propagation_delay"]
    features = ["value_0h", "value_24h", "delta_24_0", "normalized_delta"]
    
    results = {}
    
    for param in parameters:
        param_df = df[df["parameter_name"] == param].copy()
        if param_df.empty:
            continue
            
        results[param] = {}
        
        groups = {
            "nominal": param_df[param_df["behavioral_state"] == "nominal"],
        }
        
        detectabilities = param_df["early_detectability"].dropna().unique()
        for ed in detectabilities:
            groups[f"latent_{ed}"] = param_df[param_df["early_detectability"] == ed]
            
        groups["latent_any"] = param_df[param_df["is_latent_degrader"] == True]
            
        nom_df = groups["nominal"]
        
        # Distributions and Correlations
        for feat in features:
            results[param][feat] = {"distributions": {}, "separability": {}}
            for grp_name, grp_df in groups.items():
                if grp_df.empty:
                    continue
                vals = grp_df[feat].values
                fut_drift = grp_df["future_drift"].values
                fut_slope = grp_df["future_slope"].values
                
                d = {
                    "count": len(vals),
                    "mean": float(np.mean(vals)),
                    "median": float(np.median(vals)),
                    "std": float(np.std(vals)),
                    "q05": float(np.percentile(vals, 5)),
                    "q25": float(np.percentile(vals, 25)),
                    "q75": float(np.percentile(vals, 75)),
                    "q95": float(np.percentile(vals, 95)),
                }
                
                if grp_name != "nominal":
                    d["cohen_d"] = float(cohen_d(vals, nom_df[feat].values))
                else:
                    d["cohen_d"] = 0.0
                    
                # Corrs
                if len(vals) > 1 and np.std(vals) > 0 and np.std(fut_drift) > 0:
                    r_drift, _ = pearsonr(vals, fut_drift)
                    r_slope, _ = pearsonr(vals, fut_slope)
                else:
                    r_drift, r_slope = 0.0, 0.0
                    
                d["corr_future_drift"] = float(r_drift)
                d["corr_future_slope"] = float(r_slope)
                
                results[param][feat]["distributions"][grp_name] = d
                
            # Simple threshold-separability diagnostic (using 5% FPR threshold bounds)
            nom_vals = nom_df[feat].values
            latent_vals = groups["latent_any"][feat].values
            
            upper_thresh = np.percentile(nom_vals, 95)
            lower_thresh = np.percentile(nom_vals, 5)
            
            # evaluate both directions
            upper_fpr = np.mean(nom_vals > upper_thresh)
            upper_tpr = np.mean(latent_vals > upper_thresh) if len(latent_vals) > 0 else 0
            
            lower_fpr = np.mean(nom_vals < lower_thresh)
            lower_tpr = np.mean(latent_vals < lower_thresh) if len(latent_vals) > 0 else 0
            
            sep = {
                "upper_threshold": float(upper_thresh),
                "upper_fpr": float(upper_fpr),
                "upper_tpr_any": float(upper_tpr),
                "lower_threshold": float(lower_thresh),
                "lower_fpr": float(lower_fpr),
                "lower_tpr_any": float(lower_tpr),
                "category_tpr": {}
            }
            
            for ed in detectabilities:
                ed_vals = groups[f"latent_{ed}"][feat].values
                sep["category_tpr"][ed] = {
                    "upper_tpr": float(np.mean(ed_vals > upper_thresh)) if len(ed_vals) > 0 else 0,
                    "lower_tpr": float(np.mean(ed_vals < lower_thresh)) if len(ed_vals) > 0 else 0
                }
                
            results[param][feat]["separability"] = sep

    json_path = os.path.join(output_dir, "early_predictive_signal.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
        
    md_path = os.path.join(output_dir, "early_predictive_signal.md")
    with open(md_path, "w") as f:
        f.write("# Early Predictive Signal Diagnostic\n\n")
        f.write("Using TRAIN + VALIDATION lots only.\n\n")
        
        for param, f_res in results.items():
            f.write(f"## Parameter: {param}\n")
            for feat, data in f_res.items():
                f.write(f"### Feature: {feat}\n")
                f.write("#### Distributions\n")
                f.write("| Group | Count | Mean | Median | Std | q05 | q95 | Cohen's d | r(drift) |\n")
                f.write("|-------|-------|------|--------|-----|-----|-----|-----------|----------|\n")
                for grp, dist in data["distributions"].items():
                    f.write(f"| {grp} | {dist['count']} | {dist['mean']:.4f} | {dist['median']:.4f} | {dist['std']:.4f} | {dist['q05']:.4f} | {dist['q95']:.4f} | {dist['cohen_d']:.4f} | {dist['corr_future_drift']:.4f} |\n")
                f.write("\n")
                
                sep = data["separability"]
                f.write("#### Threshold Separability (Diagnostic)\n")
                f.write(f"- Upper Threshold (p95): {sep['upper_threshold']:.4f} (FPR={sep['upper_fpr']*100:.1f}%)\n")
                f.write(f"  - Any Latent TPR: {sep['upper_tpr_any']*100:.1f}%\n")
                for c, tprs in sep["category_tpr"].items():
                    f.write(f"    - latent_{c} TPR: {tprs['upper_tpr']*100:.1f}%\n")
                
                f.write(f"- Lower Threshold (p05): {sep['lower_threshold']:.4f} (FPR={sep['lower_fpr']*100:.1f}%)\n")
                f.write(f"  - Any Latent TPR: {sep['lower_tpr_any']*100:.1f}%\n")
                for c, tprs in sep["category_tpr"].items():
                    f.write(f"    - latent_{c} TPR: {tprs['lower_tpr']*100:.1f}%\n")
                f.write("\n")
                
        f.write("## CONCLUSIONS\n")
        f.write("### A. Signal clearly present\n")
        f.write("- (Filled after reading results)\n\n")
        f.write("### B. Signal weak/overlapping\n")
        f.write("- (Filled after reading results)\n\n")
        f.write("### C. Signal effectively absent\n")
        f.write("- (Filled after reading results)\n\n")
        f.write("### D. Implications for Module B\n")
        f.write("- (Filled after reading results)\n\n")

if __name__ == "__main__":
    analyze_predictive_signal()
