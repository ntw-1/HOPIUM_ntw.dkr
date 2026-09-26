# Product Specification

**Project:** `HOPIUM_sih26170`  
**Problem Statement:** SIH26170 — *AI-Driven Anomaly Detection in Component Burn-In & Screening*

---

## 1. Background & Problem Statement
In high-reliability electronics applications (such as space, aerospace, and defense systems), electronic components undergo 168-hour screening and burn-in testing to eliminate early-life failures (infant mortality) and identify parametric drift. 

Standard screening relies on measuring components at fixed timepoints (`0h`, `24h`, `96h`, `168h`). Waiting the full 168 hours for all lots increases testing overhead and cycle time. The objective of SIH26170 is to develop an AI-driven screening capability that detects anomalous component trajectories early (at 24h) and predicts parameter behavior at 168h using only 0h and 24h production inputs.

---

## 2. Core Objectives
1. **Early Anomaly Detection (Module A):** Identify component-level multivariate outliers within manufacturing lot populations using 0h and 24h readings.
2. **Parametric Drift Prediction (Module B):** Predict component parameter values at 168h (`Value_168h`) using exclusively early production readings (`Value_0h`, `Value_24h`).
3. **Dynamic Risk Reasoning:** Provide dynamic safety score and risk boundaries based on population variance, predicted drift, and distance to datasheet specs, avoiding arbitrary static limits.
4. **Human-in-the-Loop Screening:** Empower screening engineers with clear recommendations, diagnostic plots, and an immutable audit trail for final acceptance/rejection signoff.

---

## 3. Scope & Non-Goals

### In-Scope
- Synthetic burn-in data generation simulating realistic population variance and latent degradation modes.
- CSV data ingestion via an abstract `IDataSource` interface.
- Model benchmarking lab with validation-driven model selection and locked blind-test evaluation.
- Engineering review audit log and decision export.

### Non-Goals (Initial Phases)
- Direct hardware interfacing with Automated Test Equipment (ATE) protocols (MQTT, OPC-UA).
- Real-time streaming database clusters.
- Deep learning architectures (PINNs, TabPFN, PyTorch) unless justified by future empirical data.

---

## 4. Human-in-the-Loop (HITL) Workflow
1. **Ingestion:** Engineer loads component burn-in dataset for a lot.
2. **Automated Screening:** System evaluates lot through Module A (population anomalies) and Module B (168h prediction).
3. **Dynamic Risk Assessment:** System calculates dynamic risk scores and dynamic margins to official datasheet limits.
4. **Engineering Review:** System presents component flags and dynamic risk profiles to the engineer.
5. **Engineering Signoff:** The engineer reviews advisory AI flags and logs a final decision (PASS / REJECT / EXTEND_TESTING) with required justification notes into an immutable audit trail.
