#!/usr/bin/env python3
"""
scripts/run_module_b_evaluation.py

Runs the blind evaluation for Module B models.
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.evaluation.evaluator import evaluate_module_b
from src.evaluation.reports import generate_reports

def main():
    csv_path = "data/v2/dev_burnin_data.csv"
    gt_path = "data/v2/dev_burnin_groundtruth.json"
    registry_dir = "models/registered"
    split_info_path = os.path.join(registry_dir, "split_info.json")
    output_dir = "reports/evaluation"
    
    print("Starting Module B Blind Evaluation...")
    results = evaluate_module_b(
        csv_path=csv_path,
        gt_path=gt_path,
        split_info_path=split_info_path,
        registry_dir=registry_dir
    )
    
    print(f"Generating reports in {output_dir}...")
    generate_reports(results, output_dir)
    print("Evaluation complete.")

if __name__ == "__main__":
    main()
