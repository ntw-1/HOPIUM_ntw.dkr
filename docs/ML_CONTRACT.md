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

*Data leakage check tests in `tests/` will automatically fail any pipeline where `value_96h` or `value_168h` are present in feature matrix $\mathbf{X}$.*

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
The Model Lab will evaluate multiple candidate models under identical lot-level splits:
- Linear / Ridge Regression baselines
- Decision Trees / Random Forests
- Gradient Boosting variants

*Model selection is strictly automated based on lowest $\text{MAE}_{\text{val}}$. The winning model is registered into the Model Registry artifact store.*

---

## 4. Module A Contract (Population Anomaly Detection)

- **Input:** Multivariate matrix of component parameters for all components in a given lot. Confirmed from the original SIH26170 problem statement supplied/reviewed by the team, Module A may use later telemetry including `value_96h`.
- **Output:** Population Anomaly Score $S_{\text{pop}} \in [0, 1]$ indicating component deviation relative to its lot population distribution.
- **Algorithms under evaluation:** Robust Mahalanobis distance, Isolation Forest, PCA reconstruction error.
