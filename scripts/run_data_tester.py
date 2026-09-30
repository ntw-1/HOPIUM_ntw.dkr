"""
scripts/run_data_tester.py

CLI runner for the Phase 2 Data Tester.

Validates a burn-in dataset CSV, companion .meta.json, and groundtruth.json.
Exports machine-readable JSON and human-readable Markdown reports to reports/.

Usage:
    python3 scripts/run_data_tester.py
    python3 scripts/run_data_tester.py --csv data/dev_burnin_data.csv
    python3 scripts/run_data_tester.py --csv data/demo_burnin_data.csv --output-prefix demo_validation
"""

import argparse
import json
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data.validation.tester import DataTester

DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "dev_burnin_data.csv")
DEFAULT_REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")


def main():
    parser = argparse.ArgumentParser(description="HOPIUM_sih26170 Phase 2 Data Tester CLI")
    parser.add_argument("--csv", type=str, default=DEFAULT_CSV, help="Path to input dataset CSV file")
    parser.add_argument("--meta", type=str, default=None, help="Path to companion .meta.json file")
    parser.add_argument("--groundtruth", type=str, default=None, help="Path to companion groundtruth.json file")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_REPORTS_DIR, help="Directory to save validation reports")
    parser.add_argument("--output-prefix", type=str, default="data_validation", help="Prefix for report filenames")
    args = parser.parse_args()

    csv_path = os.path.abspath(args.csv)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    meta_path = os.path.abspath(args.meta) if args.meta else csv_path.replace(".csv", ".meta.json")
    gt_path = os.path.abspath(args.groundtruth) if args.groundtruth else csv_path.replace(".csv", "_groundtruth.json")

    print("==================================================================")
    print("           HOPIUM_sih26170 Phase 2 Data Tester                     ")
    print("==================================================================")
    print(f"Target CSV:        {csv_path}")
    print(f"Metadata File:     {meta_path}")
    print(f"Ground Truth File: {gt_path}")
    print("------------------------------------------------------------------")

    tester = DataTester()
    result = tester.validate_paths(csv_path=csv_path, meta_path=meta_path, groundtruth_path=gt_path)

    # Prepare report file paths
    json_report_path = os.path.join(output_dir, f"{args.output_prefix}_report.json")
    md_report_path = os.path.join(output_dir, f"{args.output_prefix}_report.md")

    # Export reports (include_timestamp=False for canonical deterministic output in committed reports)
    json_dict = result.to_dict(include_timestamp=False)
    with open(json_report_path, "w", encoding="utf-8") as f:
        json.dump(json_dict, f, indent=2, ensure_ascii=False)
        f.write("\n")

    md_text = result.to_markdown(include_timestamp=False)
    with open(md_report_path, "w", encoding="utf-8") as f:
        f.write(md_text)

    print(f"Validation Status:  {result.overall_status}")
    print(f"Hard Failures:      {result.hard_failures_count}")
    print(f"Warnings:           {result.warnings_count}")
    print(f"Informational:      {result.info_count}")
    print(f"Total Checks:       {result.total_checks_evaluated}")
    print("------------------------------------------------------------------")
    print(f"JSON Report Saved:  {json_report_path}")
    print(f"Markdown Report:    {md_report_path}")
    print("==================================================================")

    if result.overall_status != "PASS":
        print("\nVALIDATION FAILED: Hard failures detected. Dataset BLOCKED from Phase 3.")
        sys.exit(1)
    else:
        print("\nVALIDATION PASSED: Dataset APPROVED for Phase 3 Model Lab.")
        sys.exit(0)


if __name__ == "__main__":
    main()
