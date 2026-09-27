#!/usr/bin/env python3
import json
import os
import numpy as np
import pandas as pd

from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

def get_models():
    # Use config-specified hyperparameters exactly
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
    
    features = ["value_0h", "value_24h", "delta_24_0"]
    parameters = ["Iddq", "leakage_current", "propagation_delay"]
    
    output_dir = "reports/evaluation"
    os.makedirs(output_dir, exist_ok=True)
    
    results = {}
    
    for param in parameters:
        print(f"Running experiment for {param}...")
        param_df = df[df["parameter_name"] == param].copy()
        
        train_df = param_df[param_df["lot_id"].isin(train_lots)].copy()
        val_df = param_df[param_df["lot_id"].isin(val_lots)].copy()
        blind_df = param_df[param_df["lot_id"].isin(blind_lots)].copy()
        
        X_train = train_df[features]
        X_val = val_df[features]
        X_blind = blind_df[features]
        
        # Formulation A: target = value_168h
        y_train_A = train_df["value_168h"]
        # Formulation B: target = drift = value_168h - value_0h
        y_train_B = train_df["value_168h"] - train_df["value_0h"]
        
        best_A_model_name = None
        best_A_val_mae = float("inf")
        best_A_model = None
        
        best_B_model_name = None
        best_B_val_mae = float("inf")
        best_B_model = None
        
        models_A = get_models()
        models_B = get_models()
        
        # Select for Formulation A
        for name, model in models_A.items():
            model.fit(X_train, y_train_A)
            preds = model.predict(X_val)
            mae = mean_absolute_error(val_df["value_168h"], preds)
            if mae < best_A_val_mae:
                best_A_val_mae = mae
                best_A_model_name = name
                best_A_model = model
                
        # Select for Formulation B
        for name, model in models_B.items():
            model.fit(X_train, y_train_B)
            drift_preds = model.predict(X_val)
            preds = val_df["value_0h"] + drift_preds
            mae = mean_absolute_error(val_df["value_168h"], preds)
            if mae < best_B_val_mae:
                best_B_val_mae = mae
                best_B_model_name = name
                best_B_model = model
                
        # Helper to compute metrics
        def get_metrics(df_sub, preds_168h):
            true_168h = df_sub["value_168h"]
            true_drift = true_168h - df_sub["value_0h"]
            pred_drift = preds_168h - df_sub["value_0h"]
            
            return {
                "val_168h_mae": float(mean_absolute_error(true_168h, preds_168h)),
                "val_168h_rmse": float(np.sqrt(mean_squared_error(true_168h, preds_168h))),
                "drift_mae": float(mean_absolute_error(true_drift, pred_drift)),
                "drift_rmse": float(np.sqrt(mean_squared_error(true_drift, pred_drift))),
                "mean_error": float(np.mean(preds_168h - true_168h)),
                "count": len(df_sub)
            }
            
        def evaluate_formulation(model, form_type, eval_df):
            X_eval = eval_df[features]
            if form_type == "A":
                preds_168h = model.predict(X_eval)
            else:
                preds_168h = eval_df["value_0h"] + model.predict(X_eval)
                
            metrics_global = get_metrics(eval_df, preds_168h)
            metrics_group = {}
            for grp in eval_df["group_label"].unique():
                grp_mask = eval_df["group_label"] == grp
                if grp_mask.sum() > 0:
                    metrics_group[grp] = get_metrics(eval_df[grp_mask], preds_168h[grp_mask])
                    
            # Slope
            true_slope = (eval_df["value_168h"] - eval_df["value_0h"]) / 168.0
            pred_slope = (preds_168h - eval_df["value_0h"]) / 168.0
            
            slope_res = {}
            for grp in eval_df["group_label"].unique():
                grp_mask = eval_df["group_label"] == grp
                slope_res[grp] = {
                    "true_slope_mean": float(np.mean(true_slope[grp_mask])),
                    "pred_slope_mean": float(np.mean(pred_slope[grp_mask])),
                    "pred_slope_std": float(np.std(pred_slope[grp_mask]))
                }
                    
            return metrics_global, metrics_group, slope_res
            
        val_global_A, val_group_A, _ = evaluate_formulation(best_A_model, "A", val_df)
        val_global_B, val_group_B, _ = evaluate_formulation(best_B_model, "B", val_df)
        
        blind_global_A, blind_group_A, blind_slope_A = evaluate_formulation(best_A_model, "A", blind_df)
        blind_global_B, blind_group_B, blind_slope_B = evaluate_formulation(best_B_model, "B", blind_df)
        
        results[param] = {
            "Formulation_A": {
                "selected_model": best_A_model_name,
                "validation": {"global": val_global_A, "groups": val_group_A},
                "blind": {"global": blind_global_A, "groups": blind_group_A, "slopes": blind_slope_A}
            },
            "Formulation_B": {
                "selected_model": best_B_model_name,
                "validation": {"global": val_global_B, "groups": val_group_B},
                "blind": {"global": blind_global_B, "groups": blind_group_B, "slopes": blind_slope_B}
            }
        }
        
    json_path = os.path.join(output_dir, "module_b_target_comparison.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
        
    md_path = os.path.join(output_dir, "module_b_target_comparison.md")
    with open(md_path, "w") as f:
        f.write("# Module B Target Comparison (Formulation A vs B)\n\n")
        f.write("## A. EXPERIMENT DESIGN\n")
        f.write("- **Formulation A**: Predict `Value_168h` directly.\n")
        f.write("- **Formulation B**: Predict `drift` (`Value_168h - Value_0h`) directly, reconstruct `Value_168h = Value_0h + drift`.\n")
        f.write("- Validation model selection strictly by reconstructed `Value_168h` MAE.\n\n")
        
        f.write("## Summary Comparison Table\n")
        f.write("| Parameter | Form | Selected Model | Val 168h MAE | Blind 168h MAE | Blind Drift MAE |\n")
        f.write("|-----------|------|----------------|--------------|----------------|-----------------|\n")
        for param, res in results.items():
            for form in ["Formulation_A", "Formulation_B"]:
                f_res = res[form]
                f.write(f"| {param} | {form[-1]} | {f_res['selected_model']} | {f_res['validation']['global']['val_168h_mae']:.4f} | {f_res['blind']['global']['val_168h_mae']:.4f} | {f_res['blind']['global']['drift_mae']:.4f} |\n")
        f.write("\n")
        
        for param, res in results.items():
            f.write(f"## {param} Deep Dive\n")
            for form in ["Formulation_A", "Formulation_B"]:
                f.write(f"### {form} (Model: {res[form]['selected_model']})\n")
                
                f.write("#### Validation Results (Groups)\n")
                f.write("| Group | Count | 168h MAE | 168h RMSE | Drift MAE | Drift RMSE |\n")
                f.write("|-------|-------|----------|-----------|-----------|------------|\n")
                for grp, m in res[form]["validation"]["groups"].items():
                    f.write(f"| {grp} | {m['count']} | {m['val_168h_mae']:.4f} | {m['val_168h_rmse']:.4f} | {m['drift_mae']:.4f} | {m['drift_rmse']:.4f} |\n")
                
                f.write("\n#### Blind Results (Groups)\n")
                f.write("| Group | Count | 168h MAE | 168h RMSE | Drift MAE | Mean Error |\n")
                f.write("|-------|-------|----------|-----------|-----------|------------|\n")
                for grp, m in res[form]["blind"]["groups"].items():
                    f.write(f"| {grp} | {m['count']} | {m['val_168h_mae']:.4f} | {m['val_168h_rmse']:.4f} | {m['drift_mae']:.4f} | {m['mean_error']:.4f} |\n")
                
                f.write("\n#### Predicted Slopes vs Actual (Blind)\n")
                f.write("| Group | True Slope Mean | Pred Slope Mean | Pred Slope Std |\n")
                f.write("|-------|-----------------|-----------------|----------------|\n")
                for grp, m in res[form]["blind"]["slopes"].items():
                    f.write(f"| {grp} | {m['true_slope_mean']:.4f} | {m['pred_slope_mean']:.4f} | {m['pred_slope_std']:.4f} |\n")
                f.write("\n")
        
        f.write("## INTERPRETATION & RECOMMENDATION\n")
        f.write("1. **Does drift-target training improve latent-degrader prediction?**\n")
        f.write("   - (To be answered by observing the data above)\n")
        f.write("2. **Does it improve subtle/moderate cases?**\n")
        f.write("   - (To be answered by observing the data above)\n")
        f.write("3. **Does it preserve nominal performance?**\n")
        f.write("   - (To be answered by observing the data above)\n")
        f.write("4. **Does the effect generalize to blind lots?**\n")
        f.write("   - (To be answered by observing the data above)\n")
        f.write("5. **Is there sufficient evidence to justify a future production Phase 3 change?**\n")
        f.write("   - (To be answered by observing the data above)\n")

if __name__ == "__main__":
    main()
