#!/usr/bin/env python3
import json
import os
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

def evaluate_predictions(df, y_true_col, y_pred_col):
    y_true = df[y_true_col]
    y_pred = df[y_pred_col]
    
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mean_err = np.mean(y_pred - y_true)
    
    # Subgroups
    subgroups = ["nominal", "hidden", "subtle", "moderate", "strong"]
    subgroup_mae = {}
    for sg in subgroups:
        if sg == "nominal":
            mask = df["is_latent_degrader"] == 0
        else:
            mask = (df["is_latent_degrader"] == 1) & (df["early_detectability"] == sg)
            
        if mask.sum() > 0:
            subgroup_mae[sg] = float(mean_absolute_error(y_true[mask], y_pred[mask]))
        else:
            subgroup_mae[sg] = None
            
    # Trajectory slopes
    df["true_slope"] = (df["value_168h"] - df["value_0h"]) / 168.0
    df["pred_slope"] = (y_pred - df["value_0h"]) / 168.0
    
    slope_means = {}
    for sg in subgroups:
        if sg == "nominal":
            mask = df["is_latent_degrader"] == 0
        else:
            mask = (df["is_latent_degrader"] == 1) & (df["early_detectability"] == sg)
            
        if mask.sum() > 0:
            slope_means[sg] = {
                "true": float(df.loc[mask, "true_slope"].mean()),
                "pred": float(df.loc[mask, "pred_slope"].mean())
            }
            
    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "mean_error": float(mean_err),
        "subgroup_mae": subgroup_mae,
        "slope_means": slope_means
    }

def fit_evaluate_baseline(X_train, y_train, X_val, y_val, df_val):
    candidates = {
        "Dummy": DummyRegressor(strategy="mean"),
        "Ridge": Ridge(random_state=42),
        "RF": RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42),
        "GBM": GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42)
    }
    
    best_mae = float('inf')
    best_name = None
    best_model = None
    
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_val)
        mae = mean_absolute_error(y_val, preds)
        if mae < best_mae:
            best_mae = mae
            best_name = name
            best_model = model
            
    return best_model, best_name

def main():
    csv_path = "data/dev_burnin_data.csv"
    gt_path = "data/dev_burnin_groundtruth.json"
    split_info_path = "models/registered/split_info.json"
    output_dir = "reports/evaluation"
    os.makedirs(output_dir, exist_ok=True)
    
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
    df["is_latent_degrader"] = df["component_id"].map(lambda c: comp_gt[c]["is_latent_degrader"]).astype(int)
    df["early_detectability"] = df["component_id"].map(lambda c: comp_gt[c].get("early_detectability"))
    
    features = ["value_0h", "value_24h", "delta_24_0"]
    target = "value_168h"
    parameters = ["Iddq", "leakage_current", "propagation_delay"]
    
    results = {}
    
    for param in parameters:
        print(f"Running regime-conditioned regression for {param}...")
        param_df = df[df["parameter_name"] == param].copy()
        
        train_mask = param_df["lot_id"].isin(train_lots)
        val_mask = param_df["lot_id"].isin(val_lots)
        blind_mask = param_df["lot_id"].isin(blind_lots)
        
        df_train = param_df[train_mask].copy()
        df_val = param_df[val_mask].copy()
        df_blind = param_df[blind_mask].copy()
        
        X_train = df_train[features].values
        y_train = df_train[target].values
        X_val = df_val[features].values
        y_val = df_val[target].values
        X_blind = df_blind[features].values
        y_blind = df_blind[target].values
        
        # 1. BASELINE
        base_model, base_name = fit_evaluate_baseline(X_train, y_train, X_val, y_val, df_val)
        df_val_base = df_val.copy()
        df_val_base["y_pred"] = base_model.predict(X_val)
        val_base_metrics = evaluate_predictions(df_val_base, target, "y_pred")
        
        df_blind_base = df_blind.copy()
        df_blind_base["y_pred"] = base_model.predict(X_blind)
        blind_base_metrics = evaluate_predictions(df_blind_base, target, "y_pred")
        
        param_res = {
            "baseline": {
                "selected_model": base_name,
                "val_metrics": val_base_metrics,
                "blind_metrics": blind_base_metrics
            }
        }
        
        # 2. REGIMES (K=2, K=3)
        for K in [2, 3]:
            # Fit scaler and clustering on TRAIN ONLY
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            kmeans = KMeans(n_clusters=K, random_state=42, n_init=10)
            train_regimes = kmeans.fit_predict(X_train_scaled)
            
            # Assign val and blind
            val_regimes = kmeans.predict(scaler.transform(X_val))
            blind_regimes = kmeans.predict(scaler.transform(X_blind))
            
            df_train_reg = df_train.copy()
            df_train_reg["regime"] = train_regimes
            df_val_reg = df_val.copy()
            df_val_reg["regime"] = val_regimes
            df_blind_reg = df_blind.copy()
            df_blind_reg["regime"] = blind_regimes
            
            # Train regressor per regime
            regime_models = {}
            for k in range(K):
                k_mask_tr = (train_regimes == k)
                k_X_tr = X_train[k_mask_tr]
                k_y_tr = y_train[k_mask_tr]
                
                k_mask_val = (val_regimes == k)
                k_X_val = X_val[k_mask_val]
                k_y_val = y_val[k_mask_val]
                
                if len(k_X_tr) < 10:
                    # Fallback to global baseline if insufficient data
                    regime_models[k] = (base_model, f"Fallback({base_name})")
                    continue
                    
                best_model, best_name = fit_evaluate_baseline(k_X_tr, k_y_tr, k_X_val, k_y_val, df_val_reg[k_mask_val])
                regime_models[k] = (best_model, best_name)
                
            # Aggregate predictions on Val
            df_val_reg["y_pred"] = 0.0
            for k in range(K):
                mask = (df_val_reg["regime"] == k)
                if mask.sum() > 0:
                    df_val_reg.loc[mask, "y_pred"] = regime_models[k][0].predict(X_val[mask])
                    
            val_reg_metrics = evaluate_predictions(df_val_reg, target, "y_pred")
            
            # Aggregate predictions on Blind
            df_blind_reg["y_pred"] = 0.0
            for k in range(K):
                mask = (df_blind_reg["regime"] == k)
                if mask.sum() > 0:
                    df_blind_reg.loc[mask, "y_pred"] = regime_models[k][0].predict(X_blind[mask])
                    
            blind_reg_metrics = evaluate_predictions(df_blind_reg, target, "y_pred")
            
            # Subgroup concentration in regimes
            def get_proportions(df_r):
                res = {}
                for k in range(K):
                    res[str(k)] = int((df_r["regime"] == k).sum())
                return res
            
            concentration = {}
            for sg in ["hidden", "subtle"]:
                mask = (df_blind_reg["is_latent_degrader"] == 1) & (df_blind_reg["early_detectability"] == sg)
                if mask.sum() > 0:
                    sg_df = df_blind_reg[mask]
                    concentration[sg] = {str(k): int((sg_df["regime"] == k).sum()) for k in range(K)}
            
            param_res[f"K={K}"] = {
                "models": {str(k): name for k, (mod, name) in regime_models.items()},
                "val_metrics": val_reg_metrics,
                "blind_metrics": blind_reg_metrics,
                "train_counts": get_proportions(df_train_reg),
                "val_counts": get_proportions(df_val_reg),
                "blind_counts": get_proportions(df_blind_reg),
                "subgroup_concentration_blind": concentration
            }
            
        results[param] = param_res
        
    with open(os.path.join(output_dir, "regime_conditioned_regression.json"), "w") as f:
        json.dump(results, f, indent=2)
        
    with open(os.path.join(output_dir, "regime_conditioned_regression.md"), "w") as f:
        f.write("# Regime-Conditioned Regression Diagnostic\n\n")
        f.write("## METRICS BY PARAMETER\n\n")
        
        for param, res in results.items():
            f.write(f"### Parameter: {param}\n\n")
            f.write("| Configuration | Val MAE | Blind MAE | Blind RMSE | Nominal MAE | Hidden MAE | Subtle MAE | Moderate MAE | Strong MAE |\n")
            f.write("|---------------|---------|-----------|------------|-------------|------------|------------|--------------|------------|\n")
            
            for config in ["baseline", "K=2", "K=3"]:
                if config not in res: continue
                c_res = res[config]
                bm = c_res["blind_metrics"]
                vm = c_res["val_metrics"]
                sg = bm["subgroup_mae"]
                f.write(f"| {config} | {vm['mae']:.4f} | {bm['mae']:.4f} | {bm['rmse']:.4f} | {sg.get('nominal',0):.4f} | {sg.get('hidden',0):.4f} | {sg.get('subtle',0):.4f} | {sg.get('moderate',0):.4f} | {sg.get('strong',0):.4f} |\n")
            f.write("\n")
            
        f.write("## CONCLUSIONS\n")
        f.write("### A. Does regime conditioning improve overall Value168 regression?\n")
        f.write("- (To be filled)\n\n")
        f.write("### B. Does it improve hidden/subtle latent-degrader prediction?\n")
        f.write("- (To be filled)\n\n")
        f.write("### C. Does it preserve nominal performance?\n")
        f.write("- (To be filled)\n\n")
        f.write("### D. Does it improve predicted future slope for dangerous trajectories?\n")
        f.write("- (To be filled)\n\n")
        f.write("### E. Does it generalize to the locked blind lots?\n")
        f.write("- (To be filled)\n\n")
        f.write("### F. Are the learned regimes interpretable as meaningful early-trajectory regimes, or are they merely arbitrary clusters?\n")
        f.write("- (To be filled)\n\n")
        f.write("### G. Is there sufficient evidence to justify considering regime-conditioned regression for production?\n")
        f.write("- (To be filled)\n\n")

if __name__ == "__main__":
    main()
