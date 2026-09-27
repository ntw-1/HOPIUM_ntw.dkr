# Agent Guidelines & Engineering Rules

## Project Context
**Project:** `HOPIUM_sih26170`  
**Problem Statement:** SIH26170 — *AI-Driven Anomaly Detection in Component Burn-In & Screening*

This document defines strict operational rules, architectural constraints, and engineering standards for AI agents working on this codebase.

---

## 1. Feature Boundary Constraints (Module B)
- **Production Input Features:** Production inference for Module B **must strictly consume only** `Value_0h` and `Value_24h` (and engineered features derived solely from `Value_0h` and `Value_24h`, e.g., $\Delta_{24-0}$).
- **Target Variable:** `Value_168h` is the ground truth prediction target.
- **Strictly Forbidden Inputs:** `Value_96h` and `Value_168h` **must never** be included as input features for production predictions. Confirmed from the original SIH26170 problem statement supplied/reviewed by the team, `Value_96h` is explicitly forbidden as a Module B prediction input. Data leakage tests must verify this constraint.

---

## 2. Model Evaluation & Split Rules
- **Split Strategy:** Data splits must occur strictly at the **Lot level** (Train / Validation / Locked Blind Test) to prevent intra-lot leakage.
- **Model Selection:** Model selection in the Model Lab must be driven **exclusively by Validation performance** (primary metric: Validation MAE on `Value_168h`).
- **Locked Blind Test:** The Blind Test dataset must remain locked during training and model selection. It is unsealed only during final evaluation.
- **Screening Execution:** The screening platform executes the selected registered model artifact; it does not retrain or reselect models per incoming lot.

---

## 3. Dynamic Safety & Risk Boundaries vs Official Specifications
- **Official Specification Limits:** Defined by component engineering datasheets or official screening standards (e.g., maximum allowed $I_{ddq}$).
- **Derived AI Risk Boundaries:** Dynamic, evidence-based risk scores derived from population distribution, temporal trajectory, prediction magnitude, and uncertainty.
- **Strict Prohibition:** Derived AI risk scores must **never** be presented as official engineering acceptance criteria. They act purely as decision support for engineering review.
- **No Arbitrary Static Thresholds:** AI dynamic risk boundaries must be grounded in explicit empirical reasoning, not arbitrary static cutoff values.

---

## 4. Synthetic Data Provenance & Safety
- **Provenance Requirement:** All synthetic datasets must include explicit metadata tags (`is_synthetic: true`, random seed, generator version).
- **No Misrepresentation:** Synthetic data must **never** be represented as real ISRO or industry data.
- **Parameters Covered:** Synthetic data must follow SIH26170 timepoints (`0h`, `24h`, `96h`, `168h`) across required parameters (`Iddq`, `leakage_current`, `propagation_delay`) with component and lot identity.

---

## 5. Phase-Gating Rule
- **Strict Phased Progression:** No production implementation for Phase $N+1$ will begin until Phase $N$ has passed its defined quality gates, unless a dependency or interface prototype is explicitly required and documented.

---

## 6. Deferred Technologies & Lean Architecture
- **Core Dependencies:** Maintain a minimal technology stack (`pandas`, `numpy`, `scikit-learn`, `pytest`).
- **Deferred Technologies:** Do not add PINNs (Physics-Informed Neural Networks), TabPFN, deep learning frameworks (PyTorch/TensorFlow), direct ATE hardware drivers, MQTT, OPC-UA, or database servers unless explicit research and experimental evidence in later phases justifies them.
- **Input Strategy:** Ingestion must begin with CSV compatibility behind an abstract `IDataSource` interface.

---

## 7. Human-in-the-Loop & Auditability
- **Human Authority:** AI recommendations support but never replace human engineering judgment.
- **Immutable Audit Trail:** Screening decisions, AI risk recommendations, and human override notes must be recorded in an immutable audit log.
