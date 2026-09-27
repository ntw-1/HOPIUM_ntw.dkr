"""
src/evaluation/reports.py

Generate JSON and Markdown reports.
"""
import json
import os

def generate_reports(results: dict, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    
    # JSON
    json_path = os.path.join(output_dir, "module_b_blind_evaluation.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
        
    # MD
    md_path = os.path.join(output_dir, "module_b_blind_evaluation.md")
    with open(md_path, "w") as f:
        f.write("# Module B Blind Test Evaluation Report\n\n")
        f.write("## Metadata\n")
        meta = results["metadata"]
        f.write(f"- **Dataset ID**: {meta.get('dataset_id', 'N/A')}\n")
        f.write(f"- **Split Seed**: {meta.get('split_seed', 'N/A')}\n")
        f.write(f"- **Blind Lots**: {', '.join(meta.get('blind_lots', []))} ({meta.get('n_blind_lots')} total)\n\n")
        
        for param, p_res in results["parameters"].items():
            f.write(f"## Parameter: {param}\n")
            f.write(f"- Model ID: {p_res['model_id']}\n")
            f.write(f"- Model Class: {p_res['selected_model_class']}\n")
            f.write(f"- Sample Count: {p_res['sample_count']}\n\n")
            
            f.write("### Aggregate Metrics\n")
            for k, v in p_res["aggregate_metrics"].items():
                f.write(f"- {k}: {v:.4f}\n")
            f.write("\n")
            
            f.write("### Error Distribution\n")
            dist = p_res["error_distribution"]
            f.write(f"- Residual Mean: {dist['residual_mean']:.4f}\n")
            f.write(f"- Residual Median: {dist['residual_median']:.4f}\n")
            f.write(f"- Residual Std: {dist['residual_std']:.4f}\n")
            f.write("- Residual Quantiles:\n")
            for k, v in dist["residual_quantiles"].items():
                f.write(f"  - {k}: {v:.4f}\n")
            f.write("- Absolute Error Quantiles:\n")
            for k, v in dist["absolute_error_quantiles"].items():
                f.write(f"  - {k}: {v:.4f}\n")
            f.write("\n")
            
            f.write("### Uncertainty Metrics\n")
            f.write(f"*(Method: {p_res['uncertainty_method']})*\n")
            f.write("> **Note**: These are uncertainty proxies based on the method described, not necessarily formally calibrated prediction intervals.\n")
            for k, v in p_res["uncertainty_metrics"].items():
                if "coverage" in k:
                    f.write(f"- {k}: {v*100:.2f}%\n")
                else:
                    f.write(f"- {k}: {v:.4f}\n")
            f.write("\n")
            
            f.write("### Behavioral Groups\n")
            for grp, m in p_res["behavioral_groups"].items():
                f.write(f"#### {grp} (n={m['count']})\n")
                f.write(f"- MAE: {m.get('MAE', 0):.4f}\n")
                f.write(f"- RMSE: {m.get('RMSE', 0):.4f}\n")
                f.write(f"- Mean Error: {m.get('mean_error', 0):.4f}\n")
                f.write(f"- Median Absolute Error: {m.get('median_absolute_error', 0):.4f}\n\n")
            
            f.write("### Latent Degrader Evaluation\n")
            ld = p_res.get("latent_degrader_metrics")
            if ld:
                f.write(f"- Count: {ld['count']}\n")
                f.write(f"- MAE on Latent Degraders: {ld.get('MAE', 0):.4f}\n")
                f.write(f"- RMSE on Latent Degraders: {ld.get('RMSE', 0):.4f}\n")
                f.write("> **Limitation**: Module B provides point predictions and uncertainty. The actual decision logic (flagging a component) resides in the Phase 5 Risk Engine. Therefore, false-negative/false-positive screening rates cannot be calculated strictly from Module B outputs without duplicating the Phase 5 drift logic.\n\n")
            else:
                f.write("- No latent degraders in this set.\n\n")
