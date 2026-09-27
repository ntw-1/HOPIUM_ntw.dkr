#!/usr/bin/env python3
import json
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.model_lab.predictor import ProductionPredictor
from src.model_lab.features import PRODUCTION_FEATURE_ALLOWLIST

def analyze_safety_slopes():
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
        
        # True slopes
        param_df["true_slope_0_168"] = (param_df["value_168h"] - param_df["value_0h"]) / 168.0
        param_df["true_slope_24_168"] = (param_df["value_168h"] - param_df["value_24h"]) / 144.0
        
        # Predicted slopes
        param_df["pred_slope_0_168"] = (param_df["pred_168h"] - param_df["value_0h"]) / 168.0
        param_df["pred_slope_24_168"] = (param_df["pred_168h"] - param_df["value_24h"]) / 144.0
        
        # Headroom
        param_df["headroom_24_168_slope"] = (param_df["synthetic_spec_max"] - param_df["value_24h"]) / 144.0
        
        results[param] = {"distributions": {}, "boundaries": {}}
        
        groups = {
            "all": param_df,
            "nominal": param_df[param_df["behavioral_state"] == "nominal"],
            "latent_degrader": param_df[param_df["is_latent_degrader"] == True],
        }
        
        for ed in param_df["early_detectability"].dropna().unique():
            groups[f"latent_degrader_{ed}"] = param_df[param_df["early_detectability"] == ed]
            
        for grp_name, grp_df in groups.items():
            if grp_df.empty:
                continue
                
            dist_res = {}
            for col in ["true_slope_0_168", "true_slope_24_168", "pred_slope_0_168", "pred_slope_24_168"]:
                vals = grp_df[col].values
                dist_res[col] = {
                    "count": int(len(vals)),
                    "mean": float(np.mean(vals)),
                    "median": float(np.median(vals)),
                    "std": float(np.std(vals)),
                    "min": float(np.min(vals)),
                    "max": float(np.max(vals)),
                    "q05": float(np.percentile(vals, 5)),
                    "q25": float(np.percentile(vals, 25)),
                    "q50": float(np.percentile(vals, 50)),
                    "q75": float(np.percentile(vals, 75)),
                    "q90": float(np.percentile(vals, 90)),
                    "q95": float(np.percentile(vals, 95)),
                    "q99": float(np.percentile(vals, 99)),
                }
            results[param]["distributions"][grp_name] = dist_res
            
        # Boundaries analysis
        nom_df = groups["nominal"]
        ld_df = groups["latent_degrader"]
        
        if not nom_df.empty:
            results[param]["boundaries"] = {}
            for pct in [90, 95, 99]:
                b_res = {}
                for col in ["true_slope_0_168", "true_slope_24_168", "pred_slope_0_168", "pred_slope_24_168"]:
                    boundary = np.percentile(nom_df[col], pct)
                    nom_fpr = np.mean(nom_df[col] > boundary)
                    ld_tpr = np.mean(ld_df[col] > boundary) if not ld_df.empty else 0.0
                    
                    # Also calculate TPR for subcategories
                    ld_tpr_sub = {}
                    for ed in ld_df["early_detectability"].unique():
                        ed_df = groups[f"latent_degrader_{ed}"]
                        ld_tpr_sub[ed] = np.mean(ed_df[col] > boundary) if not ed_df.empty else 0.0
                    
                    b_res[col] = {
                        "boundary_value": float(boundary),
                        "nominal_fpr": float(nom_fpr),
                        "latent_tpr": float(ld_tpr),
                        "latent_tpr_by_detectability": {str(k): float(v) for k,v in ld_tpr_sub.items()}
                    }
                results[param]["boundaries"][f"p{pct}"] = b_res
                
        # Headroom correlation
        results[param]["headroom_analysis"] = {
            "mean_headroom_slope": float(np.mean(param_df["headroom_24_168_slope"])),
            "min_headroom_slope": float(np.min(param_df["headroom_24_168_slope"])),
            "true_slope_above_headroom_rate": float(np.mean(param_df["true_slope_24_168"] > param_df["headroom_24_168_slope"])),
            "pred_slope_above_headroom_rate": float(np.mean(param_df["pred_slope_24_168"] > param_df["headroom_24_168_slope"]))
        }
                
    json_path = os.path.join(output_dir, "safety_slope_analysis.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
        
    md_path = os.path.join(output_dir, "safety_slope_analysis.md")
    with open(md_path, "w") as f:
        f.write("# Safety Slope Analysis Report\n\n")
        
        f.write("## Data Used\n")
        f.write(f"- Train + Validation Lots: {sorted(list(train_val_lots))}\n")
        f.write("- Excluded: Blind Lots (completely untouched)\n\n")
        
        for param, p_res in results.items():
            f.write(f"## Parameter: {param}\n\n")
            
            f.write("### Distributions (True Slope 0->168h)\n")
            for grp, dists in p_res["distributions"].items():
                d = dists["true_slope_0_168"]
                f.write(f"- **{grp}** (n={d['count']}): Mean={d['mean']:.4f}, Median={d['median']:.4f}, p95={d['q95']:.4f}, Max={d['max']:.4f}\n")
            f.write("\n")
            
            f.write("### Predicted Distributions (Pred Slope 0->168h)\n")
            for grp, dists in p_res["distributions"].items():
                d = dists["pred_slope_0_168"]
                f.write(f"- **{grp}** (n={d['count']}): Mean={d['mean']:.4f}, Median={d['median']:.4f}, p95={d['q95']:.4f}, Max={d['max']:.4f}\n")
            f.write("\n")
            
            f.write("### Candidate Boundaries (True Slope 0->168h)\n")
            for pct, b_data in p_res.get("boundaries", {}).items():
                b = b_data["true_slope_0_168"]
                f.write(f"- **{pct}** Boundary={b['boundary_value']:.4f}\n")
                f.write(f"  - Nominal FPR: {b['nominal_fpr']*100:.2f}%\n")
                f.write(f"  - Latent TPR: {b['latent_tpr']*100:.2f}%\n")
                for k, v in b['latent_tpr_by_detectability'].items():
                    f.write(f"    - {k} TPR: {v*100:.2f}%\n")
            f.write("\n")
            
            f.write("### Candidate Boundaries (Pred Slope 0->168h)\n")
            for pct, b_data in p_res.get("boundaries", {}).items():
                b = b_data["pred_slope_0_168"]
                f.write(f"- **{pct}** Boundary={b['boundary_value']:.4f}\n")
                f.write(f"  - Nominal FPR: {b['nominal_fpr']*100:.2f}%\n")
                f.write(f"  - Latent TPR: {b['latent_tpr']*100:.2f}%\n")
                for k, v in b['latent_tpr_by_detectability'].items():
                    f.write(f"    - {k} TPR: {v*100:.2f}%\n")
            f.write("\n")
            
            f.write("### Headroom Analysis\n")
            h = p_res["headroom_analysis"]
            f.write(f"- Mean Headroom Slope (24->168h): {h['mean_headroom_slope']:.4f}\n")
            f.write(f"- True Slope > Headroom Rate: {h['true_slope_above_headroom_rate']*100:.2f}%\n")
            f.write(f"- Pred Slope > Headroom Rate: {h['pred_slope_above_headroom_rate']*100:.2f}%\n\n")

if __name__ == "__main__":
    analyze_safety_slopes()
