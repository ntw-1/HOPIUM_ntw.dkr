#!/usr/bin/env python3
import json
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.model_lab.predictor import ProductionPredictor
from src.model_lab.features import PRODUCTION_FEATURE_ALLOWLIST

def evaluate_threshold(df, flags_col, subgroup_col="early_detectability"):
    # DF must have: is_latent_degrader, flags_col, subgroup_col
    n_nominal = (df["is_latent_degrader"] == 0).sum()
    n_latent = (df["is_latent_degrader"] == 1).sum()
    
    fp = ((df["is_latent_degrader"] == 0) & df[flags_col]).sum()
    tp = ((df["is_latent_degrader"] == 1) & df[flags_col]).sum()
    
    fpr = fp / n_nominal if n_nominal > 0 else 0.0
    tpr = tp / n_latent if n_latent > 0 else 0.0
    
    subgroup_tpr = {}
    for sg in ["hidden", "subtle", "moderate", "strong"]:
        mask = (df["is_latent_degrader"] == 1) & (df[subgroup_col] == sg)
        sg_total = mask.sum()
        if sg_total > 0:
            sg_tp = (mask & df[flags_col]).sum()
            subgroup_tpr[sg] = float(sg_tp / sg_total)
        else:
            subgroup_tpr[sg] = None
            
    return {
        "nominal_fpr": float(fpr),
        "latent_tpr": float(tpr),
        "nominal_flagged": int(fp),
        "latent_flagged": int(tp),
        "subgroup_tpr": subgroup_tpr
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
    
    df["true_slope"] = (df["value_168h"] - df["value_0h"]) / 168.0
    
    parameters = ["Iddq", "leakage_current", "propagation_delay"]
    results = {}
    
    for param in parameters:
        print(f"Analyzing candidates for {param}...")
        try:
            predictor = ProductionPredictor.from_registry(registry_dir, param)
        except Exception as e:
            print(f"Skipping {param} due to error: {e}")
            continue
            
        param_df = df[df["parameter_name"] == param].copy()
        
        # We need predicted 168h for all subsets
        X_prod = param_df[PRODUCTION_FEATURE_ALLOWLIST].copy()
        pred_res = predictor.predict(X_prod)
        param_df["predicted_168h"] = pred_res["predictions"]
        param_df["predicted_slope"] = (param_df["predicted_168h"] - param_df["value_0h"]) / 168.0
        
        # Baseline Risk Logic (drift_frac_spec)
        # abs(predicted_168h - value_0h) / (spec_max - spec_min)
        # Note: we need to handle denominator carefully. 
        # But wait, propagation_delay has no spec_min sometimes. Let's use spec_max if spec_min is NaN.
        spec_max = param_df["synthetic_spec_max"].iloc[0] if not pd.isna(param_df["synthetic_spec_max"].iloc[0]) else 1e9
        spec_min = param_df["synthetic_spec_min"].iloc[0] if not pd.isna(param_df["synthetic_spec_min"].iloc[0]) else 0.0
        
        if pd.isna(param_df["synthetic_spec_max"].iloc[0]):
            # Fallback if no specs
            drift_frac = np.zeros(len(param_df))
        else:
            drift_frac = np.abs(param_df["predicted_168h"] - param_df["value_0h"]) / (spec_max - spec_min + 1e-9)
            
        param_df["drift_frac_spec"] = drift_frac
        
        # Split Data
        train_mask = param_df["lot_id"].isin(train_lots)
        val_mask = param_df["lot_id"].isin(val_lots)
        blind_mask = param_df["lot_id"].isin(blind_lots)
        
        df_train = param_df[train_mask].copy()
        df_val = param_df[val_mask].copy()
        df_blind = param_df[blind_mask].copy()
        
        # ---------------------------------------------------------
        # STEP 2: Calculate Candidate Boundaries (on TRAIN ONLY)
        # ---------------------------------------------------------
        
        # A. Population nominal trajectory slope
        # MUST calibrate on predicted_slopes of nominals in train, 
        # because regression models overpredict nominals to balance global MAE.
        nominal_train = df_train[df_train["is_latent_degrader"] == 0]
        pred_slopes_nominal = nominal_train["predicted_slope"].values
        
        p95 = np.percentile(pred_slopes_nominal, 95)
        p97_5 = np.percentile(pred_slopes_nominal, 97.5)
        p99 = np.percentile(pred_slopes_nominal, 99)
        p99_5 = np.percentile(pred_slopes_nominal, 99.5)
        
        # B. Early-state / headroom slope
        # Evaluated purely per-component, no global threshold to fit.
        # headroom_slope = (spec_max - value_24h) / (168 - 24)
        # If spec_max is not available, we can't use it.
        
        # C. Lot-relative dynamic slope
        # We will use predicted slopes of the REST of the lot to score the component.
        # But we evaluate on Validation. So we do it on the fly.
        
        # ---------------------------------------------------------
        # STEP 3: Evaluate Candidates on VALIDATION
        # ---------------------------------------------------------
        
        candidates_res = {}
        
        # Helper to eval a boolean mask on VAL
        def eval_val(mask_val, thresh_val=None):
            df_val_temp = df_val.copy()
            df_val_temp["flag"] = mask_val
            res = evaluate_threshold(df_val_temp, "flag")
            if thresh_val is not None:
                res["threshold_used"] = thresh_val
            return res
            
        # A.
        candidates_res["A_P95"] = eval_val(df_val["predicted_slope"] > p95, float(p95))
        candidates_res["A_P97.5"] = eval_val(df_val["predicted_slope"] > p97_5, float(p97_5))
        candidates_res["A_P99"] = eval_val(df_val["predicted_slope"] > p99, float(p99))
        candidates_res["A_P99.5"] = eval_val(df_val["predicted_slope"] > p99_5, float(p99_5))
        
        # B.
        if not pd.isna(spec_max):
            headroom_slope_val = (spec_max - df_val["value_24h"]) / 144.0
            candidates_res["B_Headroom"] = eval_val(df_val["predicted_slope"] > headroom_slope_val)
        else:
            candidates_res["B_Headroom"] = None
            
        # C.
        lot_flags_val = []
        for idx, row in df_val.iterrows():
            lot = row["lot_id"]
            comp = row["component_id"]
            lot_others = df_val[(df_val["lot_id"] == lot) & (df_val["component_id"] != comp)]
            if len(lot_others) < 5:
                # Fallback if lot too small
                lot_flags_val.append(False)
            else:
                l_mean = lot_others["predicted_slope"].mean()
                l_std = lot_others["predicted_slope"].std()
                if l_std == 0: l_std = 1e-9
                z = (row["predicted_slope"] - l_mean) / l_std
                lot_flags_val.append(z > 3.0)
                
        candidates_res["C_LotRelative_Z3"] = eval_val(pd.Series(lot_flags_val, index=df_val.index))
        
        # Baseline Risk Logic (drift_frac_spec)
        candidates_res["Current_DriftFrac_0.20"] = eval_val(df_val["drift_frac_spec"] >= 0.20)
        candidates_res["Current_DriftFrac_0.60"] = eval_val(df_val["drift_frac_spec"] >= 0.60)
        
        # ---------------------------------------------------------
        # STEP 5: Select Best and Evaluate on BLIND
        # ---------------------------------------------------------
        
        # Documented selection rule:
        # Choose the formulation that maximizes Latent TPR on Val, subject to Nominal FPR < 0.05.
        # If none, choose the one with lowest FPR.
        best_cand_name = None
        best_score = -1.0
        
        for name, res in candidates_res.items():
            if res is None or "Current" in name: 
                continue
            fpr = res["nominal_fpr"]
            tpr = res["latent_tpr"]
            if fpr <= 0.05:
                if tpr > best_score:
                    best_score = tpr
                    best_cand_name = name
                    
        if best_cand_name is None:
            # Fallback to lowest FPR
            best_cand_name = min(
                [(n, r["nominal_fpr"]) for n, r in candidates_res.items() if r is not None and "Current" not in n],
                key=lambda x: x[1]
            )[0]
            
        # Apply selected on BLIND
        blind_res = None
        if best_cand_name.startswith("A_"):
            if "95" in best_cand_name: thresh = p95
            elif "97" in best_cand_name: thresh = p97_5
            elif "99.5" in best_cand_name: thresh = p99_5
            else: thresh = p99
            
            df_blind_temp = df_blind.copy()
            df_blind_temp["flag"] = df_blind_temp["predicted_slope"] > thresh
            blind_res = evaluate_threshold(df_blind_temp, "flag")
            blind_res["threshold_used"] = float(thresh)
            
        elif best_cand_name == "B_Headroom":
            df_blind_temp = df_blind.copy()
            headroom_slope_blind = (spec_max - df_blind_temp["value_24h"]) / 144.0
            df_blind_temp["flag"] = df_blind_temp["predicted_slope"] > headroom_slope_blind
            blind_res = evaluate_threshold(df_blind_temp, "flag")
            
        elif best_cand_name == "C_LotRelative_Z3":
            lot_flags_blind = []
            for idx, row in df_blind.iterrows():
                lot = row["lot_id"]
                comp = row["component_id"]
                lot_others = df_blind[(df_blind["lot_id"] == lot) & (df_blind["component_id"] != comp)]
                if len(lot_others) < 5:
                    lot_flags_blind.append(False)
                else:
                    l_mean = lot_others["predicted_slope"].mean()
                    l_std = lot_others["predicted_slope"].std()
                    if l_std == 0: l_std = 1e-9
                    z = (row["predicted_slope"] - l_mean) / l_std
                    lot_flags_blind.append(z > 3.0)
            df_blind_temp = df_blind.copy()
            df_blind_temp["flag"] = lot_flags_blind
            blind_res = evaluate_threshold(df_blind_temp, "flag")
            
        results[param] = {
            "validation_candidates": candidates_res,
            "selected_formulation": best_cand_name,
            "blind_evaluation": blind_res,
            "predicted_slope_stats": {
                "train_mean": float(df_train["predicted_slope"].mean()),
                "train_std": float(df_train["predicted_slope"].std()),
                "val_mean": float(df_val["predicted_slope"].mean()),
                "val_std": float(df_val["predicted_slope"].std()),
            }
        }
        
    with open(os.path.join(output_dir, "safety_slope_candidate_analysis.json"), "w") as f:
        json.dump(results, f, indent=2)
        
    with open(os.path.join(output_dir, "safety_slope_candidate_analysis.md"), "w") as f:
        f.write("# Safety Slope Candidate Analysis\n\n")
        
        for param, res in results.items():
            f.write(f"## Parameter: {param}\n\n")
            
            f.write("### Validation Candidates\n")
            f.write("| Formulation | Nom FPR | Latent TPR | Hidden TPR | Subtle TPR | Moderate TPR | Strong TPR | Nom Flagged | Latent Flagged |\n")
            f.write("|-------------|---------|------------|------------|------------|--------------|------------|-------------|----------------|\n")
            
            for c_name, c_res in res["validation_candidates"].items():
                if c_res is None: continue
                sg = c_res["subgroup_tpr"]
                f.write(f"| {c_name} | {c_res['nominal_fpr']:.4f} | {c_res['latent_tpr']:.4f} | {sg.get('hidden',0):.4f} | {sg.get('subtle',0):.4f} | {sg.get('moderate',0):.4f} | {sg.get('strong',0):.4f} | {c_res['nominal_flagged']} | {c_res['latent_flagged']} |\n")
            
            f.write("\n")
            
            f.write(f"**Selected Formulation:** `{res['selected_formulation']}`\n\n")
            
            f.write("### Blind Evaluation (Frozen)\n")
            b_res = res["blind_evaluation"]
            if b_res:
                sg = b_res["subgroup_tpr"]
                f.write("| Formulation | Nom FPR | Latent TPR | Hidden TPR | Subtle TPR | Moderate TPR | Strong TPR | Nom Flagged | Latent Flagged |\n")
                f.write("|-------------|---------|------------|------------|------------|--------------|------------|-------------|----------------|\n")
                f.write(f"| {res['selected_formulation']} | {b_res['nominal_fpr']:.4f} | {b_res['latent_tpr']:.4f} | {sg.get('hidden',0):.4f} | {sg.get('subtle',0):.4f} | {sg.get('moderate',0):.4f} | {sg.get('strong',0):.4f} | {b_res['nominal_flagged']} | {b_res['latent_flagged']} |\n\n")
            else:
                f.write("No blind evaluation available.\n\n")
                
            f.write("---\n\n")

if __name__ == "__main__":
    main()
