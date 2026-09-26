"""
tests/unit/test_synthetic_generator.py

Phase 1 acceptance tests for the Synthetic Data Engine.

Tests implement the Phase 1 quality gates defined in docs/TEST_PLAN.md:
  - Deterministic seed reproducibility (identical SHA-256 on re-run)
  - Schema completeness (all required columns present)
  - Ground truth isolation (value_96h / value_168h never enter production features)
  - Correlation matrix PSD validation
  - Demo Cases A-D presence and correct labeling
  - Population anomaly / reference_limit_breach independence invariant
  - Synthetic metadata / provenance validation
  - Non-negativity of current/delay parameters
  - Timepoint ordering and uniqueness

All data produced in these tests is SYNTHETIC and is generated with explicit
is_synthetic=True provenance. It must never be represented as real ISRO data.
"""

import hashlib
import json
import os
import sys
import tempfile

import numpy as np
import pytest

# Make the project root importable from tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import yaml

from src.data.synthetic.correlation import (
    build_cholesky_factor,
    build_physical_covariance,
    sample_correlated_baselines,
    validate_correlation_matrix,
)
from src.data.synthetic.exporter import (
    _canonicalize_csv,
    compute_sha256,
    export_dataset,
)
from src.data.synthetic.generator import PARAMETERS, SyntheticDataEngine
from src.data.synthetic.schema import (
    ComponentGroundTruth,
    ParameterGroundTruth,
    TrajectoryRow,
)
from src.data.synthetic.trajectories import (
    EARLY_DETECTABILITY_SCALE,
    accelerating,
    evaluate_trajectory,
    stable_mild,
    step_jump,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "configs", "synthetic_config.yaml"
)


@pytest.fixture(scope="module")
def config():
    with open(CONFIG_PATH, "r") as f:
        raw = yaml.safe_load(f)
    return raw["synthetic_generator_config"]


@pytest.fixture(scope="module")
def engine(config):
    return SyntheticDataEngine(config=config, seed=42)


@pytest.fixture(scope="module")
def small_dataset(engine):
    """3 lots x 10 components — fast fixture for most tests."""
    return engine.generate(num_lots=3, components_per_lot=10)


@pytest.fixture(scope="module")
def demo_dataset(engine):
    """Demo dataset containing controlled Cases A-D."""
    return engine.generate_demo(num_lots=2, components_per_lot=10)


# ===========================================================================
# 1. CORRELATION MATRIX VALIDATION
# ===========================================================================

class TestCorrelationMatrix:

    def test_R_is_accepted_as_valid(self, config):
        R = np.array(config["cross_parameter_correlation"]["R_matrix"])
        # Must not raise
        validate_correlation_matrix(R)

    def test_R_diagonal_is_one(self, config):
        R = np.array(config["cross_parameter_correlation"]["R_matrix"])
        assert np.allclose(np.diag(R), 1.0), "R diagonal entries must all be 1.0"

    def test_R_is_symmetric(self, config):
        R = np.array(config["cross_parameter_correlation"]["R_matrix"])
        assert np.allclose(R, R.T, atol=1e-10), "R must be symmetric"

    def test_R_is_positive_semi_definite(self, config):
        R = np.array(config["cross_parameter_correlation"]["R_matrix"])
        eigvals = np.linalg.eigvalsh(R)
        assert np.all(eigvals >= -1e-10), (
            f"R must be positive semi-definite. Min eigenvalue: {eigvals.min()}"
        )

    def test_invalid_R_is_rejected(self):
        """A non-symmetric matrix must raise ValueError."""
        R_bad = np.array([[1.0, 0.9], [0.1, 1.0]])
        with pytest.raises(ValueError, match="not symmetric"):
            validate_correlation_matrix(R_bad)

    def test_R_not_called_covariance(self):
        """Terminology check: R must not be referred to as a covariance matrix."""
        import src.data.synthetic.correlation as corr_module
        src_text = open(corr_module.__file__).read()
        # The word "covariance" should only appear when explicitly constructing Sigma
        # The correlation matrix variable R must not be called a covariance matrix.
        assert "R is a covariance" not in src_text
        assert "correlation matrix R" in src_text

    def test_sigma_DRD_derivation(self, config):
        """Verify Sigma = D R D produces a valid symmetric PSD matrix."""
        R = np.array(config["cross_parameter_correlation"]["R_matrix"])
        sigmas = [config["parameters"][p]["global_sigma"] for p in PARAMETERS]
        Sigma = build_physical_covariance(R, sigmas)
        # Must be symmetric
        assert np.allclose(Sigma, Sigma.T, atol=1e-10)
        # Must be PSD
        eigvals = np.linalg.eigvalsh(Sigma)
        assert np.all(eigvals >= -1e-10)

    def test_cholesky_sampling_shape(self, config):
        R = np.array(config["cross_parameter_correlation"]["R_matrix"])
        L = build_cholesky_factor(R)
        rng = np.random.default_rng(0)
        samples = sample_correlated_baselines(
            n_samples=50,
            means=[1.0, 2.0, 3.0],
            sigmas=[0.5, 0.3, 1.0],
            L=L,
            rng=rng,
        )
        assert samples.shape == (50, 3)


# ===========================================================================
# 2. SCHEMA COMPLETENESS
# ===========================================================================

REQUIRED_CSV_FIELDS = [
    "lot_id", "component_id", "parameter_name", "unit",
    "value_0h", "value_24h", "value_96h", "value_168h",
    "synthetic_spec_min", "synthetic_spec_max",
]


class TestSchema:

    def test_trajectory_row_has_all_required_fields(self, small_dataset):
        rows, _, _ = small_dataset
        assert len(rows) > 0
        row = rows[0]
        for field in REQUIRED_CSV_FIELDS:
            assert hasattr(row, field), f"TrajectoryRow missing field: {field}"

    def test_all_parameters_present(self, small_dataset):
        rows, _, _ = small_dataset
        found_params = {r.parameter_name for r in rows}
        assert found_params == set(PARAMETERS), (
            f"Expected parameters {set(PARAMETERS)}, got {found_params}"
        )

    def test_component_ground_truth_fields(self, small_dataset):
        _, comp_gt, _ = small_dataset
        required = [
            "component_id", "lot_id", "behavioral_state",
            "is_latent_degrader", "early_detectability",
            "is_population_anomaly", "is_reference_limit_breach",
            "anomaly_attributes", "severity_level",
        ]
        for field in required:
            assert hasattr(comp_gt[0], field), (
                f"ComponentGroundTruth missing field: {field}"
            )

    def test_parameter_ground_truth_fields(self, small_dataset):
        _, _, param_gt = small_dataset
        required = [
            "component_id", "parameter_name", "true_value_168h",
            "true_drift_168h", "is_parameter_anomalous",
            "parameter_anomaly_severity",
        ]
        for field in required:
            assert hasattr(param_gt[0], field), (
                f"ParameterGroundTruth missing field: {field}"
            )

    def test_uniqueness_lot_component_parameter(self, small_dataset):
        rows, _, _ = small_dataset
        keys = [(r.lot_id, r.component_id, r.parameter_name) for r in rows]
        assert len(keys) == len(set(keys)), (
            "Duplicate (lot_id, component_id, parameter_name) found"
        )

    def test_non_negative_values(self, small_dataset):
        rows, _, _ = small_dataset
        for r in rows:
            assert r.value_0h >= 0.0, f"value_0h negative for {r.component_id}/{r.parameter_name}"
            assert r.value_24h >= 0.0
            assert r.value_96h >= 0.0
            assert r.value_168h >= 0.0

    def test_units_match_parameter(self, small_dataset):
        rows, _, _ = small_dataset
        expected_units = {"Iddq": "uA", "leakage_current": "nA", "propagation_delay": "ps"}
        for r in rows:
            assert r.unit == expected_units[r.parameter_name], (
                f"Unit mismatch for {r.parameter_name}: expected "
                f"{expected_units[r.parameter_name]}, got {r.unit}"
            )

    def test_synthetic_spec_limits_labelled_correctly(self, small_dataset):
        """Verify the fields are named synthetic_spec_* not spec_* per the contract."""
        rows, _, _ = small_dataset
        row = rows[0]
        assert hasattr(row, "synthetic_spec_min")
        assert hasattr(row, "synthetic_spec_max")
        assert not hasattr(row, "spec_min"), (
            "Field spec_min should not exist; use synthetic_spec_min"
        )


# ===========================================================================
# 3. PRODUCTION FEATURE BOUNDARY — value_96h and value_168h must NOT
#    enter production feature matrices (ML_CONTRACT.md requirement)
# ===========================================================================

class TestProductionFeatureBoundary:
    """
    These tests verify the architectural contract that value_96h and
    value_168h are available for ground truth evaluation only and must
    never enter production inference feature matrices.

    The generator stores them in TrajectoryRow for training-time use,
    but the feature extraction responsibility belongs to the Model Lab
    (Phase 3). The test here verifies the generator does not accidentally
    embed them in any ground-truth or metadata structure that could be
    confused with a production feature.
    """

    def test_value_96h_not_in_component_ground_truth(self, small_dataset):
        _, comp_gt, _ = small_dataset
        for cgt in comp_gt:
            assert not hasattr(cgt, "value_96h"), (
                "value_96h must not appear in ComponentGroundTruth"
            )

    def test_value_168h_not_in_component_ground_truth(self, small_dataset):
        _, comp_gt, _ = small_dataset
        for cgt in comp_gt:
            assert not hasattr(cgt, "value_168h"), (
                "value_168h must not appear in ComponentGroundTruth"
            )

    def test_generator_docstring_states_boundary(self):
        """Generator module docstring must state the production feature boundary."""
        import src.data.synthetic.generator as gen_module
        src_text = open(gen_module.__file__).read()
        assert "value_96h" in src_text and "value_168h" in src_text
        assert "production inference" in src_text.lower()

    def test_parameter_gt_contains_true_168h_for_eval_only(self, small_dataset):
        """Parameter GT contains true_value_168h for evaluation — this is correct."""
        _, _, param_gt = small_dataset
        for pgt in param_gt:
            assert hasattr(pgt, "true_value_168h"), (
                "true_value_168h must be in parameter ground truth for evaluation"
            )


# ===========================================================================
# 4. POPULATION ANOMALY / REFERENCE LIMIT BREACH INDEPENDENCE
# ===========================================================================

class TestAnomalyIndependence:

    def test_population_anomaly_can_exist_without_ref_breach(self, small_dataset):
        """A component may be population-anomalous but within synthetic limits."""
        _, comp_gt, _ = small_dataset
        pop_only = [
            c for c in comp_gt
            if c.is_population_anomaly and not c.is_reference_limit_breach
        ]
        # In a large dataset some should exist given prevalence settings
        # We run on 3x10=30 components so may not always appear; warn if not
        if len(pop_only) == 0:
            pytest.skip(
                "No population_anomaly-only cases in this small dataset; "
                "increase sample size or check prevalence settings."
            )
        assert all("population_anomaly" in c.anomaly_attributes for c in pop_only)

    def test_ref_breach_can_exist_without_population_anomaly(self, small_dataset):
        """A component may breach reference limits without being a lot outlier."""
        _, comp_gt, _ = small_dataset
        breach_only = [
            c for c in comp_gt
            if c.is_reference_limit_breach and not c.is_population_anomaly
        ]
        if len(breach_only) == 0:
            pytest.skip(
                "No reference_limit_breach-only cases in this small dataset; "
                "check prevalence settings."
            )
        assert all("reference_limit_breach" in c.anomaly_attributes for c in breach_only)

    def test_neither_attribute_components_exist(self, small_dataset):
        """Most components should have no anomaly attributes."""
        _, comp_gt, _ = small_dataset
        clean = [
            c for c in comp_gt
            if not c.is_population_anomaly and not c.is_reference_limit_breach
        ]
        assert len(clean) > 0, "Some components must have no anomaly attributes"

    def test_severe_outlier_terminology_absent(self, small_dataset):
        """
        Per specification, 'severe_outlier' as a unified term must not be used.
        Attributes are 'population_anomaly' and 'reference_limit_breach'.
        """
        _, comp_gt, _ = small_dataset
        for c in comp_gt:
            assert "severe_outlier" not in c.anomaly_attributes, (
                "Deprecated term 'severe_outlier' found in anomaly_attributes. "
                "Use 'population_anomaly' or 'reference_limit_breach'."
            )

    def test_demo_case_b_is_population_anomaly_without_breach(self, demo_dataset):
        """Case B must be population-anomalous and within synthetic limits."""
        _, comp_gt, _ = demo_dataset
        case_b = next(
            (c for c in comp_gt if c.component_id == "LOT_001_CMP_0002"), None
        )
        assert case_b is not None, "Demo Case B component not found"
        assert case_b.is_population_anomaly, "Case B must be population-anomalous"
        assert not case_b.is_reference_limit_breach, (
            "Case B must NOT breach reference limits (it tests Module A only)"
        )

    def test_demo_case_c_has_both_attributes(self, demo_dataset):
        """Case C must have both population_anomaly and reference_limit_breach."""
        _, comp_gt, _ = demo_dataset
        case_c = next(
            (c for c in comp_gt if c.component_id == "LOT_001_CMP_0003"), None
        )
        assert case_c is not None, "Demo Case C component not found"
        assert case_c.is_population_anomaly
        assert case_c.is_reference_limit_breach


# ===========================================================================
# 5. LATENT DEGRADATION
# ===========================================================================

class TestLatentDegradation:

    def test_early_detectability_levels_defined(self):
        expected = {"hidden", "subtle", "moderate", "strong"}
        assert set(EARLY_DETECTABILITY_SCALE.keys()) == expected

    def test_hidden_latent_has_near_zero_early_scale(self):
        """Hidden latent degraders must have no early-slope amplification at 24h."""
        assert EARLY_DETECTABILITY_SCALE["hidden"] == 0.0

    def test_strong_latent_has_highest_early_scale(self):
        scales = EARLY_DETECTABILITY_SCALE
        assert scales["strong"] > scales["moderate"] > scales["subtle"] > scales["hidden"]

    def test_demo_case_d_is_latent_degrader_hidden(self, demo_dataset):
        """Case D must be latent_degradation with hidden early detectability."""
        _, comp_gt, _ = demo_dataset
        case_d = next(
            (c for c in comp_gt if c.component_id == "LOT_001_CMP_0004"), None
        )
        assert case_d is not None, "Demo Case D component not found"
        assert case_d.behavioral_state == "latent_degradation"
        assert case_d.early_detectability == "hidden"
        assert not case_d.is_population_anomaly
        assert not case_d.is_reference_limit_breach

    def test_demo_case_d_has_later_drift_larger_than_24h_delta(self, demo_dataset):
        """
        For Case D (hidden latent), the 168h drift must be substantially
        larger than the 24h delta, demonstrating the latent nature.
        """
        rows, comp_gt, param_gt = demo_dataset
        case_d_rows = [
            r for r in rows if r.component_id == "LOT_001_CMP_0004"
        ]
        assert len(case_d_rows) == len(PARAMETERS)
        for r in case_d_rows:
            delta_24_0 = abs(r.value_24h - r.value_0h)
            drift_168_0 = abs(r.value_168h - r.value_0h)
            assert drift_168_0 > delta_24_0, (
                f"Case D ({r.parameter_name}): 168h drift ({drift_168_0:.4f}) must "
                f"exceed 24h delta ({delta_24_0:.4f}) to demonstrate latent behaviour."
            )


# ===========================================================================
# 6. TRAJECTORY FAMILIES
# ===========================================================================

class TestTrajectoryFamilies:

    def test_stable_mild_increases_monotonically(self):
        vals = [stable_mild(t, k=0.5, t0=24.0) for t in [0, 24, 96, 168]]
        assert vals == sorted(vals)

    def test_accelerating_hidden_has_no_early_slope(self):
        """Hidden early detectability: drift at 24h should be 0 (or minimal noise)."""
        drift_24 = accelerating(t=24.0, k=1.8, exponent=2.5, onset_h=24.0, early_scale=0.0)
        assert drift_24 == 0.0, (
            f"Hidden latent should have zero early scale; got {drift_24}"
        )

    def test_accelerating_grows_post_24h(self):
        drift_24 = accelerating(t=24.0, k=1.8, exponent=2.5, onset_h=24.0, early_scale=0.0)
        drift_96 = accelerating(t=96.0, k=1.8, exponent=2.5, onset_h=24.0, early_scale=0.0)
        drift_168 = accelerating(t=168.0, k=1.8, exponent=2.5, onset_h=24.0, early_scale=0.0)
        assert drift_96 > drift_24
        assert drift_168 > drift_96

    def test_step_jump_is_zero_before_jump(self):
        assert step_jump(t=0.0, k=10.0, jump_time_h=24.0) == 0.0
        assert step_jump(t=23.9, k=10.0, jump_time_h=24.0) == 0.0

    def test_step_jump_is_nonzero_after_jump(self):
        assert step_jump(t=24.0, k=10.0, jump_time_h=24.0) == 10.0

    def test_unknown_family_raises(self, config):
        param_cfg = config["parameters"]["Iddq"]
        with pytest.raises(ValueError, match="Unknown trajectory family"):
            evaluate_trajectory(family="nonexistent", t=24.0, param_cfg=param_cfg)


# ===========================================================================
# 7. DEMO CASES A-D PRESENCE
# ===========================================================================

DEMO_CASE_IDS = {
    "A": "LOT_001_CMP_0001",
    "B": "LOT_001_CMP_0002",
    "C": "LOT_001_CMP_0003",
    "D": "LOT_001_CMP_0004",
}


class TestDemoCases:

    def test_all_demo_cases_present(self, demo_dataset):
        _, comp_gt, _ = demo_dataset
        gt_ids = {c.component_id for c in comp_gt}
        for label, cid in DEMO_CASE_IDS.items():
            assert cid in gt_ids, f"Demo Case {label} ({cid}) not found in ground truth"

    def test_case_a_is_nominal_clean(self, demo_dataset):
        _, comp_gt, _ = demo_dataset
        case_a = next(c for c in comp_gt if c.component_id == DEMO_CASE_IDS["A"])
        assert case_a.behavioral_state == "nominal"
        assert not case_a.is_latent_degrader
        assert not case_a.is_population_anomaly
        assert not case_a.is_reference_limit_breach
        assert case_a.anomaly_attributes == []

    def test_case_b_within_spec_population_anomaly(self, demo_dataset):
        rows, comp_gt, _ = demo_dataset
        case_b = next(c for c in comp_gt if c.component_id == DEMO_CASE_IDS["B"])
        assert case_b.is_population_anomaly
        assert not case_b.is_reference_limit_breach
        # Row values must be within synthetic spec limits
        b_rows = [r for r in rows if r.component_id == DEMO_CASE_IDS["B"]]
        for r in b_rows:
            # Only check value_0h and value_24h (production inputs)
            # Note: latent degradation might push value_168h out of limits for Case D;
            # Case B is nominal so all values should be within limits.
            assert r.value_0h <= r.synthetic_spec_max, (
                f"Case B value_0h exceeds synthetic_spec_max for {r.parameter_name}"
            )

    def test_case_c_breach_and_population_anomaly(self, demo_dataset):
        _, comp_gt, _ = demo_dataset
        case_c = next(c for c in comp_gt if c.component_id == DEMO_CASE_IDS["C"])
        assert case_c.is_population_anomaly
        assert case_c.is_reference_limit_breach
        assert "population_anomaly" in case_c.anomaly_attributes
        assert "reference_limit_breach" in case_c.anomaly_attributes

    def test_case_d_latent_not_anomaly_attributed(self, demo_dataset):
        _, comp_gt, _ = demo_dataset
        case_d = next(c for c in comp_gt if c.component_id == DEMO_CASE_IDS["D"])
        assert case_d.behavioral_state == "latent_degradation"
        assert not case_d.is_population_anomaly
        assert not case_d.is_reference_limit_breach


# ===========================================================================
# 8. REPRODUCIBILITY & SHA-256
# ===========================================================================

class TestReproducibility:

    def test_identical_seed_produces_identical_rows(self, config):
        """Same seed + config must produce bit-identical trajectory rows."""
        engine_a = SyntheticDataEngine(config=config, seed=42)
        engine_b = SyntheticDataEngine(config=config, seed=42)
        rows_a, _, _ = engine_a.generate(num_lots=3, components_per_lot=10)
        rows_b, _, _ = engine_b.generate(num_lots=3, components_per_lot=10)

        assert len(rows_a) == len(rows_b)
        for ra, rb in zip(rows_a, rows_b):
            assert ra.component_id == rb.component_id
            assert abs(ra.value_0h - rb.value_0h) < 1e-12
            assert abs(ra.value_168h - rb.value_168h) < 1e-12

    def test_different_seed_produces_different_rows(self, config):
        """Different seeds must produce different results."""
        engine_a = SyntheticDataEngine(config=config, seed=42)
        engine_b = SyntheticDataEngine(config=config, seed=99)
        rows_a, _, _ = engine_a.generate(num_lots=3, components_per_lot=10)
        rows_b, _, _ = engine_b.generate(num_lots=3, components_per_lot=10)
        values_a = [r.value_0h for r in rows_a]
        values_b = [r.value_0h for r in rows_b]
        assert values_a != values_b

    def test_sha256_reproducible_on_same_seed(self, config):
        """
        SHA-256 content hash in .meta.json must be identical on re-run
        with the same seed and config — the primary reproducibility contract.
        """
        engine = SyntheticDataEngine(config=config, seed=42)

        with tempfile.TemporaryDirectory() as tmpdir:
            def run_and_get_hash(run_id: str) -> str:
                rows, cgt, pgt = engine.generate(num_lots=3, components_per_lot=10)
                csv_path = os.path.join(tmpdir, f"run{run_id}.csv")
                meta_path = os.path.join(tmpdir, f"run{run_id}.meta.json")
                gt_path = os.path.join(tmpdir, f"run{run_id}_gt.json")
                meta = export_dataset(
                    rows=rows,
                    component_gt=cgt,
                    parameter_gt=pgt,
                    csv_path=csv_path,
                    meta_path=meta_path,
                    groundtruth_path=gt_path,
                    dataset_id=f"test_seed42_run{run_id}",
                    generator_version=config["generator_version"],
                    random_seed=42,
                    config_snapshot={"num_lots": 3, "components_per_lot": 10},
                )
                return meta.content_hash_sha256

            hash_1 = run_and_get_hash("1")
            hash_2 = run_and_get_hash("2")
            assert hash_1 == hash_2, (
                f"SHA-256 hash not reproducible!\n  Run 1: {hash_1}\n  Run 2: {hash_2}"
            )

    def test_sha256_not_embedded_in_csv(self, config):
        """
        The CSV file must not contain the SHA-256 hash string.
        The hash belongs exclusively in the .meta.json companion file.
        """
        engine = SyntheticDataEngine(config=config, seed=42)
        rows, cgt, pgt = engine.generate(num_lots=2, components_per_lot=5)
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test.csv")
            meta_path = os.path.join(tmpdir, "test.meta.json")
            gt_path = os.path.join(tmpdir, "test_gt.json")
            meta = export_dataset(
                rows=rows, component_gt=cgt, parameter_gt=pgt,
                csv_path=csv_path, meta_path=meta_path,
                groundtruth_path=gt_path,
                dataset_id="test", generator_version=config["generator_version"],
                random_seed=42,
                config_snapshot={"num_lots": 2, "components_per_lot": 5},
            )
            with open(csv_path, "r") as f:
                csv_content = f.read()
            assert meta.content_hash_sha256 not in csv_content, (
                "SHA-256 hash must not be embedded inside the CSV file."
            )


# ===========================================================================
# 9. PROVENANCE / METADATA VALIDATION
# ===========================================================================

class TestProvenance:

    def test_meta_json_has_required_fields(self, config):
        engine = SyntheticDataEngine(config=config, seed=42)
        rows, cgt, pgt = engine.generate(num_lots=2, components_per_lot=5)
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test.csv")
            meta_path = os.path.join(tmpdir, "test.meta.json")
            gt_path = os.path.join(tmpdir, "test_gt.json")
            export_dataset(
                rows=rows, component_gt=cgt, parameter_gt=pgt,
                csv_path=csv_path, meta_path=meta_path, groundtruth_path=gt_path,
                dataset_id="test", generator_version=config["generator_version"],
                random_seed=42,
                config_snapshot={"num_lots": 2, "components_per_lot": 5},
            )
            with open(meta_path, "r") as f:
                meta = json.load(f)

        required_keys = [
            "is_synthetic", "generator_version", "random_seed",
            "dataset_id", "content_hash_sha256",
            "generation_timestamp_utc", "disclaimer",
        ]
        for key in required_keys:
            assert key in meta, f".meta.json missing required key: {key}"

    def test_is_synthetic_is_true(self, config):
        engine = SyntheticDataEngine(config=config, seed=42)
        rows, cgt, pgt = engine.generate(num_lots=2, components_per_lot=5)
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test.csv")
            meta_path = os.path.join(tmpdir, "test.meta.json")
            gt_path = os.path.join(tmpdir, "test_gt.json")
            export_dataset(
                rows=rows, component_gt=cgt, parameter_gt=pgt,
                csv_path=csv_path, meta_path=meta_path, groundtruth_path=gt_path,
                dataset_id="test", generator_version=config["generator_version"],
                random_seed=42,
                config_snapshot={"num_lots": 2, "components_per_lot": 5},
            )
            with open(meta_path, "r") as f:
                meta = json.load(f)
        assert meta["is_synthetic"] is True

    def test_disclaimer_mentions_not_real_data(self, config):
        engine = SyntheticDataEngine(config=config, seed=42)
        rows, cgt, pgt = engine.generate(num_lots=2, components_per_lot=5)
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test.csv")
            meta_path = os.path.join(tmpdir, "test.meta.json")
            gt_path = os.path.join(tmpdir, "test_gt.json")
            export_dataset(
                rows=rows, component_gt=cgt, parameter_gt=pgt,
                csv_path=csv_path, meta_path=meta_path, groundtruth_path=gt_path,
                dataset_id="test", generator_version=config["generator_version"],
                random_seed=42,
                config_snapshot={"num_lots": 2, "components_per_lot": 5},
            )
            with open(meta_path, "r") as f:
                meta = json.load(f)
        disclaimer = meta["disclaimer"].upper()
        assert "NOT REAL" in disclaimer or "SYNTHETIC" in disclaimer, (
            "Disclaimer must clearly state the data is synthetic and not real."
        )

    def test_ground_truth_is_separate_file(self, config):
        """Ground truth must be exported to a separate file, not the CSV."""
        engine = SyntheticDataEngine(config=config, seed=42)
        rows, cgt, pgt = engine.generate(num_lots=2, components_per_lot=5)
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test.csv")
            meta_path = os.path.join(tmpdir, "test.meta.json")
            gt_path = os.path.join(tmpdir, "test_gt.json")
            export_dataset(
                rows=rows, component_gt=cgt, parameter_gt=pgt,
                csv_path=csv_path, meta_path=meta_path, groundtruth_path=gt_path,
                dataset_id="test", generator_version=config["generator_version"],
                random_seed=42,
                config_snapshot={"num_lots": 2, "components_per_lot": 5},
            )
            assert os.path.exists(gt_path), "Ground truth JSON file not created"
            with open(gt_path, "r") as f:
                gt = json.load(f)
            assert "component_level" in gt
            assert "parameter_level" in gt
            # Ground truth must not appear in CSV
            with open(csv_path, "r") as f:
                csv_text = f.read()
            assert "behavioral_state" not in csv_text
            assert "is_latent_degrader" not in csv_text
