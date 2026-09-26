"""
tests/unit/test_data_tester.py

Phase 2 acceptance tests for the Data Tester engine.

Tests verify:
  1. Real generated datasets (dev & demo) pass validation with 0 hard failures.
  2. Deliberately corrupted temporary datasets trigger HARD FAILURE for:
     - missing required column
     - duplicate component/parameter key
     - null value in production inputs
     - non-finite timepoints (NaN / Inf)
     - invalid unit string
     - invalid parameter name
     - non-negative parameter violation
     - SHA-256 content hash mismatch
     - missing is_synthetic=true flag
     - ground-truth column embedded in CSV (feature leakage)
     - insufficient lot count (<3 lots)
  3. Large relative changes do NOT cause hard failure or warning failure, but are
     reported descriptively as INFORMATION without arbitrary threshold bounds.

IMPORTANT: Real generated datasets in data/ are NEVER modified by these tests.
All corruption tests operate on temporary files created via tempfile.
"""

import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.data.validation.tester import DataTester

DEV_CSV = os.path.join(os.path.dirname(__file__), "..", "..", "data", "dev_burnin_data.csv")
DEMO_CSV = os.path.join(os.path.dirname(__file__), "..", "..", "data", "demo_burnin_data.csv")


@pytest.fixture(scope="module")
def tester():
    return DataTester()


# ===========================================================================
# 1. REAL GENERATED DATASETS VALIDATION
# ===========================================================================

class TestRealDatasetsValidation:

    def test_dev_dataset_passes_validation(self, tester):
        """dev_burnin_data.csv must pass validation with 0 hard failures."""
        assert os.path.exists(DEV_CSV), f"Dev CSV missing at {DEV_CSV}"
        result = tester.validate_paths(csv_path=DEV_CSV)

        assert result.overall_status == "PASS", f"Dev dataset failed: {result.findings}"
        assert result.hard_failures_count == 0

    def test_demo_dataset_passes_validation(self, tester):
        """demo_burnin_data.csv must pass validation with 0 hard failures."""
        assert os.path.exists(DEMO_CSV), f"Demo CSV missing at {DEMO_CSV}"
        result = tester.validate_paths(csv_path=DEMO_CSV)

        assert result.overall_status == "PASS", f"Demo dataset failed: {result.findings}"
        assert result.hard_failures_count == 0


# ===========================================================================
# 2. DELIBERATELY CORRUPTED DATASET TESTS (TEMPORARY FILES ONLY)
# ===========================================================================

class TestCorruptedDatasetsDetection:

    def test_missing_required_column_fails(self, tester):
        """Removing required column 'lot_id' must trigger HARD FAILURE."""
        df = pd.read_csv(DEV_CSV).drop(columns=["lot_id"])
        result = tester.validate(df=df)

        assert result.overall_status == "FAIL"
        assert result.hard_failures_count >= 1
        assert any(f["check_name"] == "required_columns" for f in result.findings)

    def test_null_production_input_fails(self, tester):
        """Injecting NaN into value_0h must trigger HARD FAILURE."""
        df = pd.read_csv(DEV_CSV)
        df.loc[0, "value_0h"] = None
        result = tester.validate(df=df)

        assert result.overall_status == "FAIL"
        assert any(f["check_name"] == "null_production_inputs" for f in result.findings)

    def test_non_finite_timepoint_fails(self, tester):
        """Injecting Inf into value_168h must trigger HARD FAILURE."""
        df = pd.read_csv(DEV_CSV)
        df.loc[0, "value_168h"] = np.inf
        result = tester.validate(df=df)

        assert result.overall_status == "FAIL"
        assert any(f["check_name"] == "non_finite_timepoints" for f in result.findings)

    def test_duplicate_key_fails(self, tester):
        """Duplicating a row must trigger HARD FAILURE."""
        df = pd.read_csv(DEV_CSV)
        dup_row = df.iloc[0:1]
        df_dup = pd.concat([df, dup_row], ignore_index=True)
        result = tester.validate(df=df_dup)

        assert result.overall_status == "FAIL"
        assert any(f["check_name"] == "duplicate_component_parameter_keys" for f in result.findings)

    def test_invalid_unit_fails(self, tester):
        """Replacing unit 'uA' with 'Volts' must trigger HARD FAILURE."""
        df = pd.read_csv(DEV_CSV)
        df.loc[0, "unit"] = "Volts"
        result = tester.validate(df=df)

        assert result.overall_status == "FAIL"
        assert any(f["check_name"] == "allowed_units" for f in result.findings)

    def test_invalid_parameter_name_fails(self, tester):
        """Replacing parameter_name with 'temperature' must trigger HARD FAILURE."""
        df = pd.read_csv(DEV_CSV)
        df.loc[0, "parameter_name"] = "temperature"
        result = tester.validate(df=df)

        assert result.overall_status == "FAIL"
        assert any(f["check_name"] == "allowed_parameters" for f in result.findings)

    def test_negative_iddq_fails(self, tester):
        """Setting Iddq value_0h = -15.0 must trigger HARD FAILURE."""
        df = pd.read_csv(DEV_CSV)
        df.loc[df["parameter_name"] == "Iddq", "value_0h"] = -15.0
        result = tester.validate(df=df)

        assert result.overall_status == "FAIL"
        assert any(f["check_name"] == "non_negative_parameters" for f in result.findings)

    def test_sha256_hash_mismatch_fails(self, tester):
        """Mutating CSV content without updating .meta.json must trigger HARD FAILURE."""
        with open(DEV_CSV, "rb") as f:
            csv_bytes = f.read()

        # Mutate first byte
        corrupted_bytes = b"CORRUPTED" + csv_bytes[9:]
        with open(DEV_CSV.replace(".csv", ".meta.json"), "r", encoding="utf-8") as f:
            meta = json.load(f)

        result = tester.validate(df=pd.read_csv(DEV_CSV), csv_bytes=corrupted_bytes, meta_dict=meta)

        assert result.overall_status == "FAIL"
        assert any(f["check_name"] == "sha256_content_hash_match" for f in result.findings)

    def test_missing_is_synthetic_flag_fails(self, tester):
        """Setting is_synthetic=False in metadata must trigger HARD FAILURE."""
        df = pd.read_csv(DEV_CSV)
        with open(DEV_CSV.replace(".csv", ".meta.json"), "r", encoding="utf-8") as f:
            meta = json.load(f)

        meta["is_synthetic"] = False
        result = tester.validate(df=df, meta_dict=meta)

        assert result.overall_status == "FAIL"
        assert any(f["check_name"] == "is_synthetic_flag" for f in result.findings)

    def test_ground_truth_embedded_in_csv_fails(self, tester):
        """Adding 'behavioral_state' column to CSV must trigger HARD FAILURE (feature leakage)."""
        df = pd.read_csv(DEV_CSV)
        df["behavioral_state"] = "nominal"
        result = tester.validate(df=df)

        assert result.overall_status == "FAIL"
        assert any(f["check_name"] == "ground_truth_embedded_in_csv" for f in result.findings)

    def test_too_few_lots_fails(self, tester):
        """Reducing lot count to 2 must trigger HARD FAILURE for split-readiness."""
        df = pd.read_csv(DEV_CSV)
        df_2lots = df[df["lot_id"].isin(["LOT_001", "LOT_002"])]
        result = tester.validate(df=df_2lots)

        assert result.overall_status == "FAIL"
        assert any(f["check_name"] == "minimum_lot_count_for_split" for f in result.findings)

    def test_large_relative_change_does_not_cause_failure(self, tester):
        """
        Per specification rules: Large relative changes must NOT cause HARD FAILURE
        or WARNING failure. They are reported descriptively as INFORMATION.
        """
        df = pd.read_csv(DEV_CSV)
        # Inject large relative change (e.g. 100x baseline) into first row
        df.loc[0, "value_168h"] = df.loc[0, "value_0h"] * 100.0 + 50.0

        # Pass dummy meta_dict without csv_bytes so provenance check passes without SHA-256 hash check
        meta_dummy = {
            "is_synthetic": True,
            "generator_version": "v1.0.0-phase1",
            "random_seed": 42,
            "content_hash_sha256": "dummy",
            "disclaimer": "SYNTHETIC DATASET",
        }

        result = tester.validate(df=df, meta_dict=meta_dummy)

        assert result.overall_status == "PASS", f"Large relative change must NOT cause FAIL; findings: {result.findings}"
        assert result.hard_failures_count == 0
        assert any(f["check_name"] == "trajectory_relative_change_statistics" for f in result.findings)

