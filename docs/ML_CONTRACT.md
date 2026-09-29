# Machine Learning Contract Specification

**Project:** `HOPIUM_sih26170`  
**Document:** `docs/ML_CONTRACT.md`

---

## 1. Feature Boundary Specifications (Module B)

### Production Feature Set ($\mathbf{X}$)
During production screening inference, Module B **only** receives early production inputs:
$$\mathbf{X} = [\text{value\_0h}, \text{value\_24h}, \Delta_{24-0}]$$
where $\Delta_{24-0} = \text{value\_24h} - \text{value\_0h}$.

### Ground Truth Target ($y$)
$$y = \text{value\_168h}$$

### Strictly Forbidden Production Inputs
- `value_96h` (Confirmed from the original SIH26170 problem statement supplied/reviewed by the team, `value_96h` is explicitly forbidden as a Module B prediction input).
- `value_168h` (This is the target).

`src/model_lab/features.py` constructs `X` using an explicit allowlist and checks its columns at runtime. The unit tests in `tests/unit/test_module_b_features.py` exercise this boundary.

---

## 2. Dataset Partitioning Rules

To evaluate models reliably and mimic production deployment across unseen component batches:
- **Partitioning Level:** Data must be split at the **Lot Level** (`lot_id`), ensuring components from a single lot do not leak across splits.
- **Split Ratios:** 
  - Train Set: $\approx 60\%$ of lots
  - Validation Set: $\approx 20\%$ of lots
  - Locked Blind Test Set: $\approx 20\%$ of lots
- **Blind Test Seal:** The Blind Test set must remain sealed during hyperparameter tuning and model selection. It is accessed only during final Phase 8 evaluation.

---

## 3. Model Lab Evaluation Protocol

### Primary Selection Metric
- **Mean Absolute Error ($\text{MAE}_{\text{val}}$)** on target `value_168h`:
$$\text{MAE}_{\text{val}} = \frac{1}{N} \sum_{i=1}^{N} |\hat{y}_i - y_i|$$

### Secondary Metrics
- Root Mean Squared Error ($\text{RMSE}_{\text{val}}$)
- Mean Absolute Percentage Error ($\text{MAPE}_{\text{val}}$)

### Candidate Baselines
The current Model Lab evaluates these configured candidates on the same lot-level split:
- `DummyRegressor`
- `Ridge`
- `RandomForestRegressor`
- `GradientBoostingRegressor`

`src/model_lab/selector.py` selects the lowest validation MAE, with candidate-list ordering as deterministic tie-break. The chosen artifact is registered. This is an offline Model Lab operation; screening runs load registered artifacts and do not select or train models per lot.

---

## 4. Module A Contract (Population Anomaly Detection)

- **Input:** Per-lot, per-parameter `value_0h`, `value_24h`, and derived `delta_24_0`.
- **Output:** Modified Z-score evidence and a component anomaly score relative to its lot population. This score is not normalized to $[0, 1]$.
- **Current algorithm:** Robust Modified Z-score using median and median absolute deviation, with a default flag threshold of 3.5.
