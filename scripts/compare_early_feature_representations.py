#!/usr/bin/env python3
import json
import os
import sys
import numpy as np
import pandas as pd

from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

def get_models():
    return {
        "DummyRegressor": DummyRegressor(strategy="mean"),
        "Ridge": Ridge(alpha=1.0, random_state=42),
        "RandomForestRegressor": RandomForestRegressor(
            n_estimators=100, max_depth=5, min_samples_leaf=3, random_state=42
        ),
        "GradientBoostingRegressor": GradientBoostingRegressor(
            n_estimators=100, max_depth=3, learning_rate=0.1, subsample=0.8, random_state=42
        )
    }

def main():
    csv_path = "data/dev_burnin_data.csv"
    gt_path = "data/dev_burnin_groundtruth.json"
    registry_dir = "models/registered"
    split_info_path = os.path.join(registry_dir, "split_info.json")
    
    with open(split_info_path, "r") as f:
        split_info = json.load(f)
        
    train_lots = set(split_info["train_lots"])
    val_lots = set(split_info["val_lots"])
    blind_lots = set(split_info["blind_lots"])
    
    df = pd.read_csv(csv_path)
    with open(gt_path, "r") as f:
        gt_data = json.load(f)
        
    comp_gt = {c["component_id"]: c for c in gt_data["component_level"]}
    
    df["delta_24_0"] = df["value_24h"] - df["value_0h"]
    df["normalized_delta"] = df["delta_24_0"] / (df["synthetic_spec_max"] - df["synthetic_spec_min"])
    df["behavioral_state"] = df["component_id"].map(lambda c: comp_gt[c]["behavioral_state"])
    df["is_latent_degrader"] = df["component_id"].map(lambda c: comp_gt[c]["is_latent_degrader"])
    df["early_detectability"] = df["component_id"].map(lambda c: comp_gt[c].get("early_detectability"))
    
    def group_label(row):
        if row["behavioral_state"] == "nominal":
            return "nominal"
        if row["is_latent_degrader"]:
            return f"latent_{row['early_detectability']}"
        return row["behavioral_state"]
        
    df["group_label"] = df.apply(group_label, axis=1)
    
    features_F0 = ["value_0h", "value_24h", "delta_24_0"]
    features_F1 = features_F0 + ["normalized_delta"]
    features_F2 = features_F0 + ["delta_zscore"]
    features_F3 = features_F2 + ["abs_delta_zscore"]
    
    feature_sets = {
        "F0": features_F0,
        "F1": features_F1,
        "F2": features_F2,
        "F3": features_F3
    }
    
    parameters = ["Iddq", "leakage_current", "propagation_delay"]
    
    output_dir = "reports/evaluation"
    os.makedirs(output_dir, exist_ok=True)
    
    results = {}
    
    for param in parameters:
        print(f"Running experiment for {param}...")
        param_df = df[df["parameter_name"] == param].copy()
        
        train_mask = param_df["lot_id"].isin(train_lots)
        train_df = param_df[train_mask].copy()
        
        # Fit standard scaler on TRAIN ONLY
        train_mean = train_df["delta_24_0"].mean()
        train_std = train_df["delta_24_0"].std()
        
        param_df["delta_zscore"] = (param_df["delta_24_0"] - train_mean) / train_std
        param_df["abs_delta_zscore"] = param_df["delta_zscore"].abs()
        
        train_df = param_df[param_df["lot_id"].isin(train_lots)].copy()
        val_df = param_df[param_df["lot_id"].isin(val_lots)].copy()
        blind_df = param_df[param_df["lot_id"].isin(blind_lots)].copy()
        
        results[param] = {}
        
        for fs_name, fs_cols in feature_sets.items():
            X_train = train_df[fs_cols]
            X_val = val_df[fs_cols]
            y_train = train_df["value_168h"]
            y_val = val_df["value_168h"]
            
            best_val_mae = float("inf")
            best_model_name = None
            best_model = None
            
            models = get_models()
            for name, model in models.items():
                model.fit(X_train, y_train)
                preds = model.predict(X_val)
                mae = mean_absolute_error(y_val, preds)
                if mae < best_val_mae:
                    best_val_mae = mae
                    best_model_name = name
                    best_model = model
                    
            # Evaluate on Blind
            X_blind = blind_df[fs_cols]
            preds_blind = best_model.predict(X_blind)
            
            val_rmse = float(np.sqrt(mean_squared_error(y_val, best_model.predict(X_val))))
            blind_mae = float(mean_absolute_error(blind_df["value_168h"], preds_blind))
            blind_rmse = float(np.sqrt(mean_squared_error(blind_df["value_168h"], preds_blind)))
            mean_error = float(np.mean(preds_blind - blind_df["value_168h"]))
            
            # Subgroup MAEs and slopes
            subgroups = {}
            for grp in blind_df["group_label"].unique():
                grp_mask = blind_df["group_label"] == grp
                sub_true = blind_df[grp_mask]["value_168h"]
                sub_pred = preds_blind[grp_mask]
                sub_v0 = blind_df[grp_mask]["value_0h"]
                
                subgroups[grp] = {
                    "count": int(grp_mask.sum()),
                    "mae": float(mean_absolute_error(sub_true, sub_pred)),
                    "true_slope_mean": float(np.mean((sub_true - sub_v0)/168.0)),
                    "pred_slope_mean": float(np.mean((sub_pred - sub_v0)/168.0))
                }
                
            # Safety/Degradation Diagnostic: 
            # Existing risk engine concept: drift_frac = abs(predicted_168h - value_0h) / spec_range
            # Let's see how many exceed 20% (Medium risk) or 60% (High risk)
            spec_range = blind_df["synthetic_spec_max"] - blind_df["synthetic_spec_min"]
            true_drift_frac = (blind_df["value_168h"] - blind_df["value_0h"]).abs() / spec_range
            pred_drift_frac = (pd.Series(preds_blind, index=blind_df.index) - blind_df["value_0h"]).abs() / spec_range
            
            nom_mask = blind_df["behavioral_state"] == "nominal"
            latent_mask = blind_df["is_latent_degrader"] == True
            
            diag = {
                "nominal_high_risk_fpr": float(np.mean(pred_drift_frac[nom_mask] > 0.60)),
                "latent_high_risk_tpr": float(np.mean(pred_drift_frac[latent_mask] > 0.60)) if latent_mask.sum() > 0 else 0.0,
                "nominal_medium_risk_fpr": float(np.mean(pred_drift_frac[nom_mask] > 0.20)),
                "latent_medium_risk_tpr": float(np.mean(pred_drift_frac[latent_mask] > 0.20)) if latent_mask.sum() > 0 else 0.0,
            }
            
            results[param][fs_name] = {
                "selected_model": best_model_name,
                "val_mae": best_val_mae,
                "val_rmse": val_rmse,
                "blind_mae": blind_mae,
                "blind_rmse": blind_rmse,
                "mean_error": mean_error,
                "subgroups": subgroups,
                "diagnostic": diag
            }
            
    json_path = os.path.join(output_dir, "early_feature_representation_comparison.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
        
    md_path = os.path.join(output_dir, "early_feature_representation_comparison.md")
    with open(md_path, "w") as f:
        f.write("# Early Feature Representation Comparison\n\n")
        f.write("## OVERALL METRICS BY PARAMETER\n")
        
        for param, res in results.items():
            f.write(f"\n### {param}\n")
            f.write("| Feature Set | Selected Model | Val MAE | Blind MAE | Blind RMSE | Mean Error |\n")
            f.write("|-------------|----------------|---------|-----------|------------|------------|\n")
            for fs in ["F0", "F1", "F2", "F3"]:
                if fs in res:
                    f.write(f"| {fs} | {res[fs]['selected_model']} | {res[fs]['val_mae']:.4f} | {res[fs]['blind_mae']:.4f} | {res[fs]['blind_rmse']:.4f} | {res[fs]['mean_error']:.4f} |\n")
                    
            f.write("\n#### Subgroup Blind MAE\n")
            grps = set()
            for fs in ["F0", "F1", "F2", "F3"]:
                if fs in res:
                    grps.update(res[fs]["subgroups"].keys())
            grps = sorted(list(grps))
            
            f.write("| Feature Set | " + " | ".join(grps) + " |\n")
            f.write("|-------------|" + "|".join(["---"]*len(grps)) + "|\n")
            for fs in ["F0", "F1", "F2", "F3"]:
                if fs in res:
                    row = [f"{res[fs]['subgroups'].get(g, {}).get('mae', 0):.4f}" for g in grps]
                    f.write(f"| {fs} | " + " | ".join(row) + " |\n")
                    
            f.write("\n#### Predicted vs Actual Slope Means (Blind)\n")
            f.write("| Group | True Slope | Pred Slope (F0) | Pred Slope (F1) | Pred Slope (F2) | Pred Slope (F3) |\n")
            f.write("|-------|------------|-----------------|-----------------|-----------------|-----------------|\n")
            for g in grps:
                true_slope = res["F0"]["subgroups"].get(g, {}).get("true_slope_mean", 0)
                row = []
                for fs in ["F0", "F1", "F2", "F3"]:
                    if fs in res:
                        row.append(f"{res[fs]['subgroups'].get(g, {}).get('pred_slope_mean', 0):.4f}")
                f.write(f"| {g} | {true_slope:.4f} | " + " | ".join(row) + " |\n")
                
            f.write("\n#### High Risk (>60% Drift) Diagnostic\n")
            f.write("| Feature Set | Nominal FPR | Latent TPR |\n")
            f.write("|-------------|-------------|------------|\n")
            for fs in ["F0", "F1", "F2", "F3"]:
                if fs in res:
                    f.write(f"| {fs} | {res[fs]['diagnostic']['nominal_high_risk_fpr']*100:.2f}% | {res[fs]['diagnostic']['latent_high_risk_tpr']*100:.2f}% |\n")
                    
        f.write("\n## CONCLUSIONS\n")
        f.write("### A. Does feature representation improve overall Value168 regression?\n")
        f.write("- (To be filled)\n\n")
        f.write("### B. Does it improve latent-degrader prediction?\n")
        f.write("- (To be filled)\n\n")
        f.write("### C. Does it preserve nominal performance?\n")
        f.write("- (To be filled)\n\n")
        f.write("### D. Is there sufficient evidence to justify a production Phase 3 feature change?\n")
        f.write("- (To be filled)\n\n")

if __name__ == "__main__":
    main()
