# HOPIUM_sih26170: AI-Driven Anomaly Detection in Component Burn-In & Screening

## Overview
**Smart India Hackathon 2026 (Problem Statement SIH26170)**

This project provides an AI-driven screening and anomaly detection system for electronic component burn-in testing. It focuses on early anomaly detection and parameter trajectory prediction using 0h and 24h burn-in measurements to predict 168h parameter stability, aiding engineering decision-making while maintaining high reliability standards.

---

## Key Modules
1. **Synthetic Data Engine:** Physics-informed, reproducible synthetic burn-in trajectory generator (`0h`, `24h`, `96h`, `168h`).
2. **Data Tester & Validation:** Comprehensive data quality, schema integrity, and range check engine.
3. **Module A (Population Anomaly Detection):** Dynamic, multivariate population outlier screening at 0h and 24h.
4. **Module B (168h Trajectory Prediction):** Predicts `Value_168h` using strictly `[Value_0h, Value_24h]` input features.
5. **Model Lab & Registry:** Candidate model benchmarking with validation-driven selection and locked blind-test evaluation.
6. **Dynamic Risk Engine:** Evidence-based risk reasoning distinguishing dynamic AI risk scores from official datasheet limits.
7. **Screening & Audit Platform:** Human-in-the-loop engineering review interface with immutable audit trail and export.

---

## Permanent Specifications & Documentation
- [AGENTS.md](AGENTS.md): Strict rules and constraints for AI agents.
- [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md): Problem context, objectives, and human-in-the-loop workflow.
- [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md): Parameter definitions, timepoints, and synthetic data schemas.
- [docs/ML_CONTRACT.md](docs/ML_CONTRACT.md): Feature boundaries, splitting rules, and Model Lab criteria.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): System architecture, dynamic risk reasoning, and ATE abstraction.
- [docs/TEST_PLAN.md](docs/TEST_PLAN.md): Testing strategy, quality gates, and blind-test lock checks.
- [docs/DECISIONS.md](docs/DECISIONS.md): Architectural Decision Records (ADRs).

---

## Development Phases
- **Phase 0:** Contracts, Specifications, and Documentation (Current Phase)
- **Phase 1:** Synthetic Data Engine
- **Phase 2:** Data Tester & Validation Engine
- **Phase 3:** Module B Model Lab & Registry
- **Phase 4:** Module A Dynamic Population Anomaly Engine
- **Phase 5:** Evidence-Based Dynamic Risk & Safety Engine
- **Phase 6:** Core Screening Platform
- **Phase 7:** Human Review, Audit Trail & Export System
- **Phase 8:** Integration Testing & Demo

---

## Phase-Gating Policy
*No production implementation for Phase N+1 will begin until Phase N has passed its defined quality gates, unless a dependency or interface prototype is explicitly required and documented.*
