# HOPIUM — SIH26170 Project Status

## 1. Project Overview
- **Project Name:** `HOPIUM_sih26170`
- **Problem Statement:** Smart India Hackathon 2026 — Problem Statement SIH26170: *AI-Driven Anomaly Detection in Component Burn-In & Screening*
- **Core Mission:** Early identification of latent degradation, anomalous parametric drift, and infant mortality in semiconductor components during Environmental Stress Screening (ESS) burn-in testing. The system consumes early burn-in measurements ($0\text{h}$ and $24\text{h}$) to identify anomalous population behaviour, forecast $168\text{h}$ drift, and estimate reliability risk before components undergo the full, costly $168\text{h}$ chamber run.
- **Intended Users:** Reliability Engineers, Quality Assurance Evaluators, Semiconductor Test Engineers, and Mission Assurance Officers for aerospace and defense screening.
- **Product Concept:** An auditable, explainable decision-support workstation combining robust early population outlier detection (Module A) and strict non-leaking trajectory prediction (Module B) with human-in-the-loop oversight and compliance audit logging.

---

## 2. Current Product Architecture
The system operates as an end-to-end pipeline with strict feature separation and auditable human oversight:

```
CSV / Data Ingestion (IDataSource interface)
        ↓
Data Tester & Validator (29 schema, range, and leakage checks)
        ↓
Module A (Multivariate Population Anomaly Detector — Modified Z-Score)
        ↓
Module B (168h Drift Predictor — strictly consumes 0h & 24h)
        ↓
Dynamic Risk Engine (Evidence synthesis: Anomaly + Spec Breach + Drift + Uncertainty)
        ↓
Screening Workstation UI (Command Center, Component Analysis, Risk Analysis)
        ↓
Human-in-the-Loop Review (Engineer Final Disposition: PASS / MONITOR / REJECT)
        ↓
Immutable Compliance Audit Trail (CSV / JSON Export with Override Tracking)
```

- **Implemented Components:** Full offline synthetic generation, data validation, Module A, Module B, Model Registry, Dynamic Risk Engine, Screening Pipeline, Human-in-the-Loop audit logger, and the local single-page Screening Workstation UI.
- **Future Concepts:** Direct automated ATE hardware drivers (SECS/GEM, direct IEEE-488/GPIB instrument buses) are deferred; data ingestion currently operates on CSV datasets behind the abstract `IDataSource` contract.

---

## 3. Module A — Dynamic Population Anomaly Detection
- **Purpose:** Identifies components that behave abnormally relative to their manufacturing lot peer group during early burn-in ($0\text{h}$ and $24\text{h}$), distinguishing between within-spec population anomalies and catalog specification breaches.
- **Algorithm:** Modified Z-Score ($M_i$) using Median and Median Absolute Deviation (MAD), based on Iglewicz and Hoaglin:
  $$M_i = \frac{0.6745 \cdot |x_i - \tilde{x}|}{\text{MAD}}$$
- **Inputs:** Parametric readings across all components in a lot at $0\text{h}$ and $24\text{h}$ (`Iddq`, `leakage_current`, `propagation_delay`).
- **Anomaly Score & Threshold:** The component anomaly score is the maximum Modified Z-Score across the evaluated parameters and timepoints. A component is flagged as an anomalous population outlier when $M_i \ge 3.5$ (configurable in configuration constants).
- **Population-Relative Evaluation:** Because evaluation is performed relative to the lot median and MAD rather than absolute datasheet limits, Module A successfully catches "freak" components that remain inside datasheet maximums but are statistically atypical compared to their lot cohort.
- **Validation:** Verified in `tests/unit/test_module_a_anomaly.py` across nominal distributions, synthetic outliers, multi-modal cohorts, and edge cases.

---

## 4. Module B — Time-Series Drift Prediction
- **Feature Contract:**
  - **Strict Production Inputs:** Consumes **strictly and exclusively** `Value_0h`, `Value_24h`, and engineered features derived solely from those two timepoints (e.g., delta $\Delta_{24-0} = \text{Value}_{24h} - \text{Value}_{0h}$ and relative slope).
  - **Prediction Target:** Ground truth `Value_168h`.
  - **Strictly Forbidden Inputs:** `Value_96h` and `Value_168h` are strictly forbidden as input features during production predictions. Explicit data leakage tests (`tests/unit/test_module_b_features.py`) verify that these columns are rejected if present in inference feature sets.
- **Candidate Models:** Linear Regression, Ridge Regression, and ElasticNet models evaluated in the offline Model Lab.
- **Model Selection & Validation:**
  - Model selection is driven **exclusively by Validation MAE** on `Value_168h`.
  - Data splits occur strictly at the **Lot level** (60% Train / 20% Validation / 20% Locked Blind Test) to prevent intra-lot data leakage.
- **Metrics Recorded:** Validation MAE, RMSE, and $R^2$ score recorded in `models/registered/<module>/registry.json` and evaluation reports.
- **Uncertainty Bounds:** Residual-based 90% prediction intervals ($[\hat{y} - 1.645\sigma, \hat{y} + 1.645\sigma]$) computed from validation split residual variance.
- **Model Registry:** Registered model artifacts (`model.pkl`, `uncertainty.pkl`, `registry.json`) are stored per parameter under `models/registered/` for deterministic production execution without retraining during screening runs.

---

## 5. Data Generation
- **Dataset Structure:** Hierarchical lot-based data containing `component_id`, `lot_id`, `parameter_name`, `Value_0h`, `Value_24h`, `Value_96h`, `Value_168h`, and provenance metadata.
- **Parameters & Timepoints:** Standard SIH26170 parameters:
  - `Iddq` ($\mu\text{A}$)
  - `leakage_current` ($\text{nA}$)
  - `propagation_delay` ($\text{ns}$)
  - Measured across burn-in checkpoints: $0\text{h}$, $24\text{h}$, $96\text{h}$, $168\text{h}$.
- **Degradation Patterns Implemented:**
  1. *Nominal baseline:* Slight, predictable aging within datasheet boundaries.
  2. *Infant mortality / Sudden failure:* Rapid degradation between 0h and 24h.
  3. *Progressive wearout:* Accelerating drift exceeding limits by 168h.
  4. *Erratic / Fluctuating drift:* Non-monotonic shifts indicating structural gate oxide or metallization defects.
- **Provenance & Safety:** Every synthetic dataset includes explicit metadata tags (`is_synthetic: true`, generator version, random seed).
- **Empirical Calibration Status:** Current data generation is physics-informed and seed-reproducible. Direct empirical calibration against classified or restricted NASA/ISRO operational telemetry is **not** claimed as implemented and remains ongoing research work.

---

## 6. Data Tester / Validation
- **Engine:** Implemented in `src/data/validation.py` (`DataTester`).
- **Validation Checks:** Runs 29 structural, schema, range, monotonic timepoint, and statistical sanity checks:
  - Mandatory column schema and type verification.
  - Non-null and non-empty constraint enforcement.
  - Parameter range boundaries (e.g., non-negative current, valid propagation delay).
  - Timepoint progression ordering ($0\text{h} \le 24\text{h} \le 96\text{h} \le 168\text{h}$).
  - Strict leakage prevention (ensuring no test-time targets pollute inference sets).
- **Outcomes:** Returns deterministic statuses (`PASS`, `WARNING`, `HARD_FAIL`) with granular failure messages.

---

## 7. Model Lab
- **Offline R&D vs Production Screening:**
  - The Model Lab (`src/models/` and `scripts/run_module_b_evaluation.py`) is an offline research and evaluation framework.
  - It trains candidate models, validates performance strictly on lot-split validation sets, and records comparative benchmark metrics.
  - The winning model artifact is sealed into the Model Registry.
  - The production screening platform loads the pre-registered model artifact and never retrains or reselects models during active screening of incoming lots.

---

## 8. Dynamic Risk Engine
- **Current Multi-Factor Risk Formulation:**
  The `DynamicRiskEngine` evaluates four distinct evidentiary dimensions:
  1. **Population Anomaly:** Module A Modified Z-Score $\ge 3.5$.
  2. **Specification Breach:** Current value at $24\text{h}$ exceeds official engineering datasheet limits.
  3. **Spec-Normalized Trajectory Drift:** Predicted drift relative to the allowed catalog specification span:
     $$\text{Drift Ratio} = \frac{|\hat{y}_{168h} - y_{0h}|}{\text{Spec}_{\max} - \text{Spec}_{\min}}$$
  4. **Uncertainty Margin:** $90\%$ prediction interval upper bound $[\hat{y} + 1.645\sigma]$ encroaching upon the critical specification threshold.
- **Advisory Risk Classification:** Categorizes each component into deterministic advisory levels: `LOW`, `MEDIUM`, or `HIGH`.
- **Safety Boundary Refinement Note:** The current implementation uses spec-normalized drift and residual uncertainty envelopes. Dynamic population-derived safety boundaries without reference catalog specs (e.g. $P_{95}/P_{99}$ percentile clustering) are documented as a planned enhancement.

---

## 9. Human-in-the-Loop Workflow
- **AI Advisory Risk:** `LOW`, `MEDIUM`, `HIGH`.
- **Engineer Final Disposition:** `PASS`, `MONITOR`, `REJECT`.
- **Human Authority Principle:** AI recommendations act purely as decision support. An AI `HIGH` risk does not automatically scrap a component, nor does a `LOW` risk automatically pass it.
- **Override Handling & Justification:**
  - If a quality engineer's final decision differs from the AI advisory risk (e.g., AI suggests `HIGH` risk, but the engineer assigns `PASS`), the system flags the disposition with `is_override = true`.
  - The engineer must enter a mandatory technical justification note before the decision can be recorded.
- **Audit Persistence:** Every disposition, override status, timestamp, session ID, and operator note is appended to an immutable audit log (`reports/phase7_audit_log.csv`).

---

## 10. Screening Platform UI
A local web application served via Python's HTTP server (`scripts/run_screening_ui.py`) incorporating Stitch workstation ergonomics:

### Navigable Workstation Views
1. **Command Center:** Operational screening overview displaying active run telemetry, KPI cards, lot population overview, selected lot risk distribution, and prioritized attention queue.
2. **Component Analysis:** In-depth individual component diagnostics, timepoint trajectory charts ($0\text{h}$, $24\text{h}$, predicted $168\text{h}$ with $90\%$ envelope), Module A Z-score breakdowns, and interactive HITL disposition actions (`PASS`, `MONITOR`, `REJECT`).
3. **Risk Analysis:** Cohort-level risk distribution, risk factor breakdown matrix, and parameter correlation views.
4. **Audit / Export:** Live audit log display with real-time override tracking and one-click CSV audit log export.
5. **Model Lab:** Inspection of registered model metadata, validation MAE/RMSE, feature constraints, and training history.
6. **Data Validation:** Interface for running the 29-check `DataTester` suite with real-time pass/warning/fail diagnostics.

### Command Center Layout Refinements (Current Release)
- **Lot / Population Screening Status:** Height capped at $\approx 340\text{px}$ with sticky headers and internal scrolling; all lots remain fully accessible.
- **Selected Lot Profile:** Height aligned to $\approx 340\text{px}$, maintaining horizontal alignment with the lot table.
- **Components Requiring Attention:** Brought into view substantially earlier in the operator viewport without excessive vertical scrolling.
- **Side Navigation Width:** Narrowed from $260\text{px}$ to $230\text{px}$ while preserving all navigation items, hierarchy, icons, and status information.
- **Run Status Relocation:** Moved `Active BRN-Run`, `Checkpoint`, and `Status` out of the main top bar into the left side rail, immediately above Station/Operator/Clock.
- **Dataset Selector & Execute:** Positioned on the left side of the top bar immediately following the side rail (`DATASET: [demo_burnin_data.csv ▼] [EXECUTE]`), visible and unclipped.
- **Enlarged Controls:** Modestly enlarged KPI cards and top-right controls (terminal, notifications, operator avatar).
- **Color Palette:** Preserved the original dark technical HOPIUM palette (`#0f131c` background, cyan accent, green nominal, amber medium risk, red critical risk).

---

## 11. API / Backend Endpoints
Implemented in `scripts/run_screening_ui.py`:

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Serves the single-page workstation application (`src/screening/ui/index.html`). |
| `/api/datasets` | `GET` | Returns list of available burn-in CSV files in `data/`. |
| `/api/screen` | `POST` | Executes `ScreeningPipeline` on a specified dataset (`{"csv_path": "data/..."}`). |
| `/api/current` | `GET` | Returns active screening state (lots, components, validation results, KPIs). |
| `/api/decision` | `POST` | Records engineer disposition (`component_id`, `lot_id`, `decision`, `notes`) to audit log. |
| `/api/export_audit`| `GET` | Returns all recorded audit records as a JSON array. |
| `/api/download_audit` | `GET` | Serves `reports/phase7_audit_log.csv` as a downloadable attachment. |

---

## 12. Testing & Quality Assurance
- **Automated Test Suite:** `pytest -q`
- **Result:** **158 passed** in 8.5 seconds.
- **Coverage Areas:**
  - Synthetic data generation contracts and trajectory physics (`tests/unit/test_synthetic_generator.py`, `tests/unit/test_generator_v2.py`).
  - Schema, range, monotonicity, and leakage validation (`tests/unit/test_data_validation.py`).
  - Module A Modified Z-Score outlier detection (`tests/unit/test_module_a_anomaly.py`).
  - Module B feature contract, zero 96h/168h leakage (`tests/unit/test_module_b_features.py`, `tests/unit/test_module_b_models.py`, `tests/unit/test_module_b_evaluation.py`).
  - Dynamic risk engine scoring, uncertainty intervals, and safety slopes (`tests/unit/test_risk_engine.py`, `tests/unit/test_safety_slope.py`).
  - End-to-end screening pipeline orchestration (`tests/unit/test_screening_pipeline.py`).
  - Immutable audit trail logging, schema compliance, and override detection (`tests/unit/test_audit_trail.py`).

---

## 13. Current Git & Release State
- **Branch:** `main`
- **Commit:** `861d9fc`
- **Release Date:** September 28, 2026
- **Implementation Status:** Phases 0 through 8 complete, validated, and verified against all engineering constraints.

---

## 14. Known Limitations & Technical Debt
1. **Proprietary Telemetry Calibration:** Synthetic burn-in trajectories follow mathematical degradation functions (Arrhenius acceleration, power-law drift) rather than proprietary aerospace flight telemetry.
2. **Ingestion Modality:** Ingestion is currently file-based (CSV) behind the `IDataSource` interface; direct socket streaming for automated test equipment (ATE) is intentionally deferred.
3. **Safety Boundary Refinement:** AI risk scoring normalizes drift against catalog specifications; population-derived percentile thresholds ($P_{95}/P_{99}$) for un-specified parameters remain an area for future refinement.

---

## 15. Future Work
- Empirical trajectory parameter calibration using open NASA/ISRO reliability databases.
- Real-time streaming adapter implementing `IDataSource` for SECS/GEM or MQTT automated test handlers.
- Dynamic clustering for multi-regime burn-in thermal profiles (e.g. combined thermal cycling and power burn-in).
