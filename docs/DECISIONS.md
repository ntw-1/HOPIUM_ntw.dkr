# Architectural Decision Records (ADR)

**Project:** `HOPIUM_sih26170`  
**Document:** `docs/DECISIONS.md`

---

## ADR-001: Minimal Dependencies and Lean CSV-Based Ingestion Architecture

- **Status:** Approved
- **Context:** Early-stage project requirements emphasize feasibility, rapid verification, and strict reproducibility.
- **Decision:** Use minimal core dependencies (`pandas`, `numpy`, `scikit-learn`, `pytest`) and standardized CSV file formats.
- **Consequences:** Avoids heavy infrastructure overhead while keeping the codebase easy to audit and test.

---

## ADR-002: Lot-Level Data Splitting & Locked Blind Test Evaluation

- **Status:** Approved
- **Context:** Components in burn-in testing belong to manufacturing lots. Random component-level splitting risks intra-lot data leakage.
- **Decision:** Split datasets strictly by `lot_id` into Train, Validation, and Locked Blind Test partitions.
- **Consequences:** Ensures models are evaluated on unseen manufacturing lots, reflecting true production conditions.

---

## ADR-003: Formal Separation of Official Specification Limits and Derived AI Risk Boundaries

- **Status:** Approved
- **Context:** Mixing official engineering spec limits with AI risk outputs creates confusion and regulatory risk.
- **Decision:** Explicitly separate static Datasheet Specification Limits from Dynamic AI Risk Scores. Dynamic AI risk scores serve strictly as advisory evidence for engineering review.
- **Consequences:** Preserves regulatory compliance while providing dynamic decision support.

---

## ADR-004: Abstract `IDataSource` Interface for Future ATE Integration

- **Status:** Approved
- **Context:** Initial inputs are CSV files, but future production environments may require direct ATE integration.
- **Decision:** Enforce an abstract `IDataSource` contract for data loading.
- **Consequences:** Allows adding an `ATEDataSource` in future phases without altering downstream ML or risk modules.

---

## ADR-005: Deferred Technologies (PINNs, TabPFN, Deep Learning, Databases, Hardware Protocols)

- **Status:** Approved (Deferred)
- **Context:** Advanced neural architectures, live database clusters, and hardware streaming protocols introduce significant complexity.
- **Decision:** Defer PINNs, TabPFN, PyTorch/TensorFlow, PostgreSQL/TimescaleDB, MQTT, and OPC-UA until empirical research and experimental data justify them.
- **Consequences:** Keeps initial phases focused on core SIH26170 screening objectives.

## ADR-006: External Enforcement of Module B Input Constraint

- **Status:** Approved
- **Context:** Previous ambiguity existed regarding whether predicting `Value_168h` strictly using only `Value_0h` and `Value_24h` was an internal architectural choice or an external requirement. 
- **Decision:** Confirmed from the original SIH26170 problem statement supplied/reviewed by the team, the requirement that Module B must forecast `Value_168h` using *only* `Value_0h` and `Value_24h` is an external rule. `Value_96h` is explicitly forbidden as a Module B prediction input. However, Module A may use `Value_96h` for anomaly detection, and deterministic derived features (e.g. `delta_24_0`) remain permitted.
- **Consequences:** This documents that the 0h/24h prediction bottleneck in Module B is a strict SIH requirement, and cannot be bypassed simply by feeding 96h telemetry to the regression model.

## ADR-007: Safety Slope Formulation vs Current Risk Logic

- **Status:** Evaluated (No Production Change)
- **Context:** The SIH problem statement dictates flagging if the "predicted 168h drift rate exceeds a calculated safety slope." The current Phase 5 risk engine uses a normalized drift fraction (`drift_frac_spec = abs(predicted - 0h) / (max - min)`), which lacks temporal division and isn't mathematically a "slope". We performed a controlled offline experiment (`analyze_safety_slope_candidates.py`) to evaluate strict slope candidates (e.g., P95-P99.5 of nominal predicted slope, available headroom slope, and lot-relative dynamic slope) against the current logic.
- **Decision:** Do NOT modify the production Module B risk logic at this time. The mathematical safety slope candidates correctly adhere to the SIH wording, but they cannot compensate for the underlying regression failure. Because the regression models fail to predict high `168h` values for `hidden` and `subtle` degraders, their predicted slopes are indistinguishable from nominal components. Any strict slope threshold that catches them results in an unacceptable nominal false-positive rate. Furthermore, `propagation_delay` exhibits effectively zero predictive signal for latent degraders.
- **Consequences:** The system will continue using `drift_frac_spec` in the short term. The core problem remains the regression objective (global MAE), which fundamentally misaligns with detecting minority anomalies. We cannot solve this by tuning the safety threshold.

## ADR-008: Module B Root Cause Audit

- **Status:** Approved (Diagnostic)
- **Context:** Module B regression consistently failed to predict 168h drift for "hidden" and "subtle" latent degraders using only 0h/24h features. After safety-slope thresholding failed to compensate for this, a root-cause audit was conducted on information availability and the synthetic data generator (`src/data/synthetic/`).
- **Findings:**
    1. **Generator Construction Flaw (`propagation_delay`):** `configs/synthetic_config.yaml` assigns the exact same trajectory math (`stable_mild`) to both nominal and latent components for `propagation_delay`. They are mathematically identical.
    2. **Unnatural Ambiguity (`Iddq` & `leakage_current`):** The generator simulates "hidden" cases by assigning an early drift scale of exactly 0.0. Therefore, a hidden degrader physically drifts *less* than a nominal component initially, perfectly overlapping with nominal components that have slight negative noise.
    3. **Mathematical Regression Trap:** Because the generator forces "hidden" degraders (Delta ~0) to perfectly overlap with noisy nominal components (Delta ~0), the regression model cannot predict a 168h spike for Delta=0 without destroying its global MAE performance on the nominal majority. A "Label-Oracle" counterfactual test proved that if the regression knows the true regime, its MAE drops to near-zero, proving the signal exists but is artificially obscured at 0h/24h.
- **Decision:** The bottleneck is primarily a **generator construction issue** and **data ambiguity/distribution imbalance**, not a flawed ML architecture. The synthetic generator is failing to faithfully represent the physical reality of the SIH requirement.
- **Consequences:** The synthetic generator mechanics (early scale formulas and `propagation_delay` trajectories) must be redesigned to produce physically plausible monotonic degradation signatures before any further Module B model architecture changes are considered.

## ADR-009: Controlled Synthetic Generator V2

- **Status:** Recommended (Under Review)
- **Context:** An audit of the V1 synthetic generator revealed fatal data construction flaws: `propagation_delay` latent cases were mathematically identical to nominal cases, and `hidden` degraders for Iddq/leakage were assigned exactly zero early drift, causing an unnatural 0h/24h overlap with negative nominal noise that could only be separated by an oracle. This led to a mathematically impossible regression benchmark.
- **Decision:** A principled V2 generator (`v2.0.0-phase1`) was implemented. It preserves the V1 files, parameters, and timepoints, but introduces the `accelerating_v2` trajectory family. In V2, latent degradation is governed by a continuous stochastic `latent_strength`. This mechanism ensures that a component's ultimate 168h drift acceleration is causally linked to a proportional (and strictly non-zero) early drift at 24h. 
- **Consequences:** 
  1. `propagation_delay` is now a valid regression task with genuine degradation trajectories.
  2. Hidden and subtle cases are now partially observable at 24h, producing realistic overlaps (e.g., Cohen's d of 0.2 to 0.3 for hidden cases) rather than mathematically forced invisibility. 
  3. The regression task is now solvable but remains non-trivial (due to nominal noise bounds).
- **Recommendation:** Adopt V2 for future Module B evaluation. It corrects arbitrary unnatural simulation assumptions while faithfully adhering to the SIH prediction bottleneck, resulting in a significantly more defensible benchmark.
