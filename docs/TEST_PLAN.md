# Test Plan & Quality Gates

**Project:** `HOPIUM_sih26170`  
**Document:** `docs/TEST_PLAN.md`

---

## 1. Quality Gates per Phase

Each phase must satisfy specific quality gates before proceeding to subsequent production implementations:

| Phase | Core Objective | Quality Gate Requirements |
| :--- | :--- | :--- |
| **Phase 0** | Contracts & Setup | All specification documents verified for internal consistency. |
| **Phase 1** | Synthetic Data Engine | Generator produces valid `0h, 24h, 96h, 168h` trajectories; explicit `is_synthetic: true` metadata present; 100% reproducible with random seed. |
| **Phase 2** | Data Tester & Validator | Validator correctly flags invalid schemas, missing values, sequence breaks, and out-of-bounds readings. |
| **Phase 3** | Module B Model Lab | Validation-driven selection succeeds; data leakage test confirms `value_96h` and `value_168h` are excluded from production features. |
| **Phase 4** | Module A Anomaly Engine | Correctly identifies known synthetic multivariate outliers across lot populations. |
| **Phase 5** | Dynamic Risk Engine | Dynamic risk calculation produces consistent advisory risk scores across trajectory profiles. |
| **Phase 6** | Screening Platform | End-to-end lot processing succeeds using registered model artifact without retraining per lot. |
| **Phase 7** | Audit & Export System | Immutable log records human signoff; JSON/CSV export matches specification schema. |
| **Phase 8** | Integration & Demo | Unsealed Blind Test evaluation executes cleanly; end-to-end integration tests pass. |

---

## 2. Automated Test Suite Layout

```text
tests/
├── unit/
│   ├── test_synthetic_generator.py   # Phase 1: Test seed reproducibility & metadata
│   ├── test_data_tester.py          # Phase 2: Test schema validation & boundary rules
│   ├── test_module_b_features.py     # Phase 3: Data leakage checks (strictly 0h & 24h)
│   ├── test_module_a_anomaly.py      # Phase 4: Test population anomaly detection
│   ├── test_dynamic_risk.py          # Phase 5: Test dynamic risk reasoning
│   └── test_audit_logging.py         # Phase 7: Test audit trail immutability
└── integration/
    ├── test_screening_pipeline.py    # Phase 6 & 8: End-to-end screening execution
    └── test_locked_blind_eval.py     # Phase 8: Sealed vs unsealed blind test evaluation
```

---

## 3. Data Leakage Prevention Check

A mandatory unit test (`test_module_b_features.py`) will automatically verify:
1. Feature matrix $\mathbf{X}$ columns fed into candidate/registered models contain **only** `value_0h`, `value_24h`, and derived early deltas ($\Delta_{24-0}$).
2. Assertion failure is triggered if `value_96h` or `value_168h` are detected in $\mathbf{X}$.
