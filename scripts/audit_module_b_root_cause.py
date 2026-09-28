import json
import os
import sys
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

# Insert path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def evaluate_model(model, X_train, y_train, X_eval, y_eval, mask_dict):
    model.fit(X_train, y_train)
    preds = model.predict(X_eval)
    
    mae = mean_absolute_error(y_eval, preds)
    bias = np.mean(preds - y_eval)
    
    subgroup_mae = {}
    for name, mask in mask_dict.items():
        if mask.sum() > 0:
            subgroup_mae[name] = float(mean_absolute_error(y_eval[mask], preds[mask]))
        else:
            subgroup_mae[name] = None
            
    return {
        "mae": float(mae),
        "bias": float(bias),
        "subgroup_mae": subgroup_mae
    }

def main():
    csv_path = "data/dev_burnin_data.csv"
    gt_path = "data/dev_burnin_groundtruth.json"
    registry_dir = "models/registered"
    split_info_path = os.path.join(registry_dir, "split_info.json")
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
        print(f"Auditing root cause for {param}...")
        param_df = df[df["parameter_name"] == param].copy()
        
        # Base splits
        train_mask = param_df["lot_id"].isin(train_lots)
        val_mask = param_df["lot_id"].isin(val_lots)
        blind_mask = param_df["lot_id"].isin(blind_lots)
        
        df_train = param_df[train_mask]
        df_val = param_df[val_mask]
        df_blind = param_df[blind_mask]
        
        X_train = df_train[features].values
        y_train = df_train[target].values
        X_val = df_val[features].values
        y_val = df_val[target].values
        X_blind = df_blind[features].values
        y_blind = df_blind[target].values
        
        # Create masks for evaluation (on blind set)
        def make_masks(dataset):
            masks = {"nominal": dataset["is_latent_degrader"] == 0}
            for sg in ["hidden", "subtle", "moderate", "strong"]:
                masks[sg] = (dataset["is_latent_degrader"] == 1) & (dataset["early_detectability"] == sg)
            return masks
            
        val_masks = make_masks(df_val)
        blind_masks = make_masks(df_blind)
        
        param_res = {}
        
        # 1. Audit Information Availability (Train + Val)
        pool_df = pd.concat([df_train, df_val])
        nom = pool_df[pool_df["is_latent_degrader"] == 0]
        
        info_audit = {}
        for sg in ["hidden", "subtle", "moderate", "strong"]:
            sg_df = pool_df[(pool_df["is_latent_degrader"] == 1) & (pool_df["early_detectability"] == sg)]
            if len(sg_df) == 0: continue
            
            # Effect size for delta_24_0 (Cohen's d)
            mean_nom = nom["delta_24_0"].mean()
            mean_sg = sg_df["delta_24_0"].mean()
            std_nom = nom["delta_24_0"].std()
            std_sg = sg_df["delta_24_0"].std()
            
            pooled_std = np.sqrt(((len(nom)-1)*std_nom**2 + (len(sg_df)-1)*std_sg**2) / (len(nom)+len(sg_df)-2))
            d = (mean_sg - mean_nom) / (pooled_std + 1e-9)
            
            # Also target separation
            mean_nom_y = nom["value_168h"].mean()
            mean_sg_y = sg_df["value_168h"].mean()
            
            info_audit[sg] = {
                "mean_delta_nom": float(mean_nom),
                "mean_delta_sg": float(mean_sg),
                "cohens_d_delta": float(d),
                "mean_target_nom": float(mean_nom_y),
                "mean_target_sg": float(mean_sg_y)
            }
        
        param_res["information_availability"] = info_audit
        
        # 2. Simple Regression Baselines
        candidates = {
            "Dummy": DummyRegressor(strategy="mean"),
            "Ridge": Ridge(random_state=42),
            "RF": RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42),
            "GBM": GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42)
        }
        
        baseline_res = {}
        for name, model in candidates.items():
            res_val = evaluate_model(model, X_train, y_train, X_val, y_val, val_masks)
            res_blind = evaluate_model(model, X_train, y_train, X_blind, y_blind, blind_masks)
            baseline_res[name] = {
                "val": res_val,
                "blind": res_blind
            }
            
        param_res["baselines"] = baseline_res
        
        # 3. Counterfactual Observability Test
        # Encode regime as a one-hot feature
        def encode_regime(dataset):
            # 0=nominal, 1=hidden, 2=subtle, 3=moderate, 4=strong
            mapping = {"hidden":1, "subtle":2, "moderate":3, "strong":4}
            regimes = []
            for i, row in dataset.iterrows():
                if row["is_latent_degrader"] == 0:
                    regimes.append(0)
                else:
                    regimes.append(mapping.get(row["early_detectability"], 0))
            
            one_hot = np.zeros((len(dataset), 5))
            for i, r in enumerate(regimes):
                one_hot[i, r] = 1.0
            return one_hot
            
        train_regime_features = encode_regime(df_train)
        val_regime_features = encode_regime(df_val)
        blind_regime_features = encode_regime(df_blind)
        
        X_train_cf = np.hstack([X_train, train_regime_features])
        X_val_cf = np.hstack([X_val, val_regime_features])
        X_blind_cf = np.hstack([X_blind, blind_regime_features])
        
        # Train GBM on counterfactual features
        cf_model = GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42)
        cf_val = evaluate_model(cf_model, X_train_cf, y_train, X_val_cf, y_val, val_masks)
        cf_blind = evaluate_model(cf_model, X_train_cf, y_train, X_blind_cf, y_blind, blind_masks)
        
        param_res["counterfactual"] = {
            "val": cf_val,
            "blind": cf_blind
        }
        
        results[param] = param_res
        
    with open(os.path.join(output_dir, "module_b_root_cause_audit.json"), "w") as f:
        json.dump(results, f, indent=2)
        
    with open(os.path.join(output_dir, "module_b_root_cause_audit.md"), "w") as f:
        f.write("# Module B Regression Root Cause Audit\n\n")
        
        for param, res in results.items():
            f.write(f"## Parameter: {param}\n\n")
            
            f.write("### 1. Information Availability (Train + Val)\n")
            info = res["information_availability"]
            f.write("| Regime | Mean Delta (Nom) | Mean Delta (Regime) | Effect Size (Cohen's d) | Target (Nom) | Target (Regime) |\n")
            f.write("|--------|------------------|---------------------|-------------------------|--------------|-----------------|\n")
            for sg, sg_info in info.items():
                f.write(f"| {sg} | {sg_info['mean_delta_nom']:.4f} | {sg_info['mean_delta_sg']:.4f} | {sg_info['cohens_d_delta']:.4f} | {sg_info['mean_target_nom']:.2f} | {sg_info['mean_target_sg']:.2f} |\n")
            f.write("\n")
            
            f.write("### 2. Regression Baselines (Blind)\n")
            f.write("| Model | Overall MAE | Nom MAE | Hidden MAE | Subtle MAE | Mod MAE | Strong MAE |\n")
            f.write("|-------|-------------|---------|------------|------------|---------|------------|\n")
            for m_name, m_res in res["baselines"].items():
                sg = m_res["blind"]["subgroup_mae"]
                f.write(f"| {m_name} | {m_res['blind']['mae']:.4f} | {sg.get('nominal',0):.4f} | {sg.get('hidden',0):.4f} | {sg.get('subtle',0):.4f} | {sg.get('moderate',0):.4f} | {sg.get('strong',0):.4f} |\n")
            f.write("\n")
            
            f.write("### 3. Counterfactual Observability Test (Blind)\n")
            f.write("GBM model trained with explicit latent regime label to test if target is intrinsically unpredictable or just unobservable from 0h/24h features.\n\n")
            
            base_sg = res["baselines"]["GBM"]["blind"]["subgroup_mae"]
            cf_sg = res["counterfactual"]["blind"]["subgroup_mae"]
            
            f.write("| Configuration | Overall MAE | Nom MAE | Hidden MAE | Subtle MAE | Mod MAE | Strong MAE |\n")
            f.write("|---------------|-------------|---------|------------|------------|---------|------------|\n")
            f.write(f"| Standard GBM  | {res['baselines']['GBM']['blind']['mae']:.4f} | {base_sg.get('nominal',0):.4f} | {base_sg.get('hidden',0):.4f} | {base_sg.get('subtle',0):.4f} | {base_sg.get('moderate',0):.4f} | {base_sg.get('strong',0):.4f} |\n")
            f.write(f"| Label-Oracle  | {res['counterfactual']['blind']['mae']:.4f} | {cf_sg.get('nominal',0):.4f} | {cf_sg.get('hidden',0):.4f} | {cf_sg.get('subtle',0):.4f} | {cf_sg.get('moderate',0):.4f} | {cf_sg.get('strong',0):.4f} |\n")
            f.write("\n---\n\n")

        f.write("## CONCLUSIONS\n\n")
        f.write("1. **Is the 0h/24h → 168h problem actually predictable in our synthetic data?**\n")
        f.write("   - (To be filled)\n\n")
        f.write("2. **How much early signal exists for each parameter/regime?**\n")
        f.write("   - (To be filled)\n\n")
        f.write("3. **How much does each regression model exploit that signal?**\n")
        f.write("   - (To be filled)\n\n")
        f.write("4. **Are hidden/subtle failures intrinsically ambiguous from 0h/24h?**\n")
        f.write("   - (To be filled)\n\n")
        f.write("5. **Why does propagation_delay fail?**\n")
        f.write("   - (To be filled)\n\n")
        f.write("6. **Is the synthetic generator faithfully testing the SIH requirement?**\n")
        f.write("   - (To be filled)\n\n")
        f.write("7. **Is the current regression architecture actually the bottleneck?**\n")
        f.write("   - (To be filled)\n\n")
        f.write("8. **What, if anything, should be changed next?**\n")
        f.write("   - (To be filled)\n\n")

if __name__ == "__main__":
    main()
