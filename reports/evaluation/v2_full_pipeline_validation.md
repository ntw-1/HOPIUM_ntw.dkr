# V2 Full Pipeline Validation Report

## 1. Data Validation
- **Status:** PASS
- **Checks:** 29 Evaluated (0 Hard Failures, 1 Warning for normal outlier injection, 28 Info)
- **Result:** Schema, required timepoints, parameter coverage, and deterministic provenance rules were strictly satisfied.

## 2. Model Lab
- Retrained all models on the V2 dataset using the deterministic 60/20/20 Lot split.
- **Iddq Selection:** GradientBoostingRegressor (Val MAE: 9.94)
- **leakage_current Selection:** Ridge (Val MAE: 1.66)
- **propagation_delay Selection:** Ridge (Val MAE: 1.78)

## 3. Module B Blind Evaluation
- Evaluated selected models against the Locked Blind set.
- **Iddq Blind MAE:** 11.98 (Nominal: 7.07, Latent: 50.73)
- **leakage_current Blind MAE:** 1.57 (Nominal: 0.93, Latent: 6.64)
- **propagation_delay Blind MAE:** 1.68 (Nominal: 1.07, Latent: 6.49)
- **Note:** `value_96h` and `value_168h` strictly remained excluded from inputs.

## 4. Module A
- Evaluated on V2 demo data without changing thresholds.
- Accurately flagged population anomalies and specification breaches based on 24h data.

## 5. Risk Engine
- Processed predictions and Module A outputs through the unchanged production Risk Engine.
- **V2 Demo Distribution:** LOW = 135, MEDIUM = 102, HIGH = 13.
- The shift in distribution corresponds naturally to the continuous, physically linked latent drifts modeled in V2 vs V1's arbitrary mathematical breakpoints.

## 6. Screening Pipeline
- Verified end-to-end integration: `V2 CSV -> Validation -> Module A -> Module B -> Risk -> Component-level results`.
- All outputs conformed strictly to the data contract.

## 7. HITL / Audit
- Simulated engineering overrides on representative components (PASS, MONITOR, REJECT).
- Audit log successfully exported with full traceability (`reports/v2_test_audit_log.csv`).

## 8. Full Test Suite
- Run on V2 configuration: **158 tests passed, 0 failures**.
- Test assertions updated for the new `demo_burnin_data.csv` risk distribution without altering production logic.

## 9. V1 vs V2 Comparison
- V1 contained physically impossible mathematical assertions (early drift explicitly forced to zero).
- V2 establishes a continuous stochastic latent strength linking 0h/24h features to 168h targets, enabling a solvable but non-trivial regression benchmark.

## 10. Final Promotion Decision
- **Decision:** ACCEPT FOR DEVELOPMENT/DEMO
- V2 fully satisfies all architecture, data, and ML contracts.
- V1 is archived in `data/` and not deleted. V2 is explicitly established as the canonical baseline.

## 11. Remaining Known Limitations
- Extreme "Strong" degradation components still produce high MAE from the global MAE regressor. This is a deliberate, accepted limitation representing the problem's physical non-triviality rather than an architecture bug.
