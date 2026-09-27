#!/usr/bin/env python3
import json
import os
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.anomaly.metrics import compute_robust_statistics

def get_modified_zscore(values):
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return np.zeros_like(arr)
    med, mad = compute_robust_statistics(arr)
    z = 0.6745 * (arr - med) / (mad + 1e-9)
    return z

def get_metrics(df_sub, score_col, threshold=3.5):
    preds = (df_sub[score_col].abs() > threshold).astype(int)
    y_true = df_sub["is_latent_degrader"].astype(int)
    
    cm = confusion_matrix(y_true, preds, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    
    nominal_fpr = fp / (tn + fp) if (tn + fp) > 0 else 0.0
    overall_recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    recalls = {}
    for ed in ["hidden", "subtle", "moderate", "strong"]:
        mask = (df_sub["is_latent_degrader"] == 1) & (df_sub["early_detectability"] == ed)
        sub_y = y_true[mask]
        sub_p = preds[mask]
        if len(sub_y) > 0:
            recalls[ed] = float(np.mean(sub_p))
        else:
            recalls[ed] = 0.0
            
    return {
        "nominal_fpr": float(nominal_fpr),
        "overall_recall": float(overall_recall),
        "recalls": recalls,
        "cm": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}
    }

def main():
    csv_path = "data/dev_burnin_data.csv"
    gt_path = "data/dev_burnin_groundtruth.json"
    split_info_path = "models/registered/split_info.json"
    output_dir = "reports/evaluation"
    os.makedirs(output_dir, exist_ok=True)
    
    with open(split_info_path, "r") as f:
        split_info = json.load(f)
        
    blind_lots = set(split_info["blind_lots"])
    
    df = pd.read_csv(csv_path)
    with open(gt_path, "r") as f:
        gt_data = json.load(f)
        
    comp_gt = {c["component_id"]: c for c in gt_data["component_level"]}
    
    df["delta_24_0"] = df["value_24h"] - df["value_0h"]
    df["is_latent_degrader"] = df["component_id"].map(lambda c: comp_gt[c]["is_latent_degrader"]).astype(int)
    df["early_detectability"] = df["component_id"].map(lambda c: comp_gt[c].get("early_detectability"))
    df["behavioral_state"] = df["component_id"].map(lambda c: comp_gt[c]["behavioral_state"])
    
    parameters = ["Iddq", "leakage_current", "propagation_delay"]
    features = ["value_0h", "value_24h", "delta_24_0"]
    
    results = {}
    
    for param in parameters:
        print(f"Running Module A diagnostic for {param}...")
        param_df = df[df["parameter_name"] == param].copy()
        if param_df.empty:
            continue
            
        # Module A calculates Z-scores per lot independently
        z_scores = []
        for lot, lot_df in param_df.groupby("lot_id"):
            res_df = lot_df[["component_id", "is_latent_degrader", "early_detectability", "behavioral_state", "lot_id"]].copy()
            for feat in features:
                res_df[f"z_{feat}"] = get_modified_zscore(lot_df[feat].values)
            
            # Combined score is max of absolute individual z-scores
            z_cols = [f"z_{f}" for f in features]
            res_df["z_combined"] = res_df[z_cols].abs().max(axis=1)
            z_scores.append(res_df)
            
        z_df = pd.concat(z_scores)
        
        # Evaluate exclusively on BLIND lots (as per final diagnostic evaluation request)
        # "Evaluate the final diagnostic on the locked blind lots."
        blind_z_df = z_df[z_df["lot_id"].isin(blind_lots)].copy()
        
        param_res = {}
        for feat in features:
            param_res[feat] = get_metrics(blind_z_df, f"z_{feat}", threshold=3.5)
            
        param_res["Combined (Module A)"] = get_metrics(blind_z_df, "z_combined", threshold=3.5)
        
        results[param] = param_res
        
    json_path = os.path.join(output_dir, "module_a_early_signal_diagnostic.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
        
    md_path = os.path.join(output_dir, "module_a_early_signal_diagnostic.md")
    with open(md_path, "w") as f:
        f.write("# Module A Early Abnormality Diagnostic (Blind Lots)\n\n")
        f.write("Evaluation of existing per-lot Modified Z-Score (threshold=3.5).\n\n")
        
        for param, param_res in results.items():
            f.write(f"## Parameter: {param}\n")
            
            f.write("| Feature | Nominal FPR | Latent Recall | Hidden Recall | Subtle Recall | Moderate Recall | Strong Recall | CM (TN,FP,FN,TP) |\n")
            f.write("|---------|-------------|---------------|---------------|---------------|-----------------|---------------|------------------|\n")
            
            for feat_name, m in param_res.items():
                cm = m["cm"]
                cm_str = f"{cm['tn']}, {cm['fp']}, {cm['fn']}, {cm['tp']}"
                f.write(f"| {feat_name} | {m['nominal_fpr']*100:.2f}% | {m['overall_recall']*100:.2f}% | {m['recalls']['hidden']*100:.2f}% | {m['recalls']['subtle']*100:.2f}% | {m['recalls']['moderate']*100:.2f}% | {m['recalls']['strong']*100:.2f}% | {cm_str} |\n")
            f.write("\n")
            
        f.write("## CONCLUSIONS\n")
        f.write("### A. Can existing Module A detect the early abnormality found by the classifier?\n")
        f.write("- (To be filled)\n\n")
        f.write("### B. Which parameter(s) show useful early anomaly signal?\n")
        f.write("- (To be filled)\n\n")
        f.write("### C. Can Module A detect hidden degraders without knowing the latent-degrader label?\n")
        f.write("- (To be filled)\n\n")
        f.write("### D. How does its performance compare conceptually with the diagnostic classifier?\n")
        f.write("- (To be filled)\n\n")
        f.write("### E. Does this provide evidence for keeping Module A as the early-abnormality detector while Module B remains the future-value regression model?\n")
        f.write("- (To be filled)\n\n")

if __name__ == "__main__":
    main()
