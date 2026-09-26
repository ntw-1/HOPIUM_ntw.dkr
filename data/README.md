# Synthetic Datasets Directory (`data/`)

**Project:** `HOPIUM_sih26170`  
**Phase:** Phase 1 — Synthetic Data Engine

---

## Important Notice & Provenance Disclaimer

> **CAUTION & DISCLAIMER:**  
> All datasets in this directory are **SYNTHETIC**. They have been synthetically generated specifically for Smart India Hackathon 2026 experimentation (Problem Statement SIH26170).  
> **They are NOT real ISRO data, nor are they real industry semiconductor data.**

- `synthetic_spec_min` and `synthetic_spec_max` in the datasets are **configurable synthetic reference scenario assumptions** designed for testing and visual demonstration. They are **not** official ISRO or component datasheet specification limits. SIH26170 does not specify numerical component limits.

---

## Dataset Inventory

| Dataset File | Metadata File | Ground Truth File | Description & Size |
| :--- | :--- | :--- | :--- |
| `dev_burnin_data.csv` | `dev_burnin_data.meta.json` | `dev_burnin_groundtruth.json` | **Development Dataset:** 20 lots × 100 components/lot (6,000 parameter trajectory rows). Used for model training, validation, and locked blind-test benchmarks. |
| `demo_burnin_data.csv` | `demo_burnin_data.meta.json` | `demo_burnin_groundtruth.json` | **Demonstration Dataset:** 5 lots × 50 components/lot (750 parameter trajectory rows). Contains seeded instances of Cases A, B, C, and D for visual verification. |

---

## File Roles & Isolation Rules

1. **Trajectory Data (`.csv`):**
   - Standard machine-readable CSV containing trajectory readings at `0h`, `24h`, `96h`, and `168h`.
   - **Production Feature Boundary:** Only `value_0h` and `value_24h` are permitted as production inference inputs for Module B. `value_96h` and `value_168h` are stored for ground truth prediction evaluation and **must never** enter production feature matrices.

2. **Provenance Metadata (`.meta.json`):**
   - Stores immutable generation metadata including `is_synthetic: true`, `random_seed`, `generator_version`, configuration snapshot, and the canonical UTF-8 SHA-256 content hash of the CSV file.

3. **Ground Truth (`groundtruth.json`):**
   - Stores component-level and parameter-level behavioral states, latent degradation labels, and true 168h drift values.
   - **Evaluation Only:** Ground truth files are strictly separate and **must never** be loaded into production inference feature extraction pipelines.

---

## Dataset Regeneration

All datasets can be deterministically regenerated using the Phase 1 dataset generator script:

```bash
python3 scripts/generate_datasets.py
```

Deterministic regeneration is guaranteed when using the same random seed (`42`), configuration file (`configs/synthetic_config.yaml`), and generator version.

---

## Next Steps

Phase 2 will provide the dedicated **Data Tester / Validation Pipeline** to automatically verify schema compliance, temporal ordering, and data quality gates.
