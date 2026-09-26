# Architecture Specification

**Project:** `HOPIUM_sih26170`  
**Document:** `docs/ARCHITECTURE.md`

---

## 1. End-to-End System Dataflow

```text
                                  ┌────────────────────────┐
                                  │      CSV Data File     │
                                  └───────────┬────────────┘
                                              │
                                              ▼
                                  ┌────────────────────────┐
                                  │   IDataSource Loader   │
                                  └───────────┬────────────┘
                                              │
                                              ▼
                                  ┌────────────────────────┐
                                  │ Data Tester / Validator│
                                  └───────────┬────────────┘
                                              │
                                              ▼
                      ┌───────────────────────┴───────────────────────┐
                      │                                               │
                      ▼                                               ▼
          ┌───────────────────────┐                       ┌───────────────────────┐
          │       Module A        │                       │       Module B        │
          │  Population Outlier   │                       │  168h Prediction      │
          │    Score (S_pop)      │                       │   (Value_168h_pred)   │
          └───────────┬───────────┘                       └───────────┬───────────┘
                      │                                               │
                      └───────────────────────┬───────────────────────┘
                                              │
                                              ▼
                                  ┌────────────────────────┐
                                  │  Dynamic Risk Engine   │
                                  │   (Evidence Reasoning) │
                                  └───────────┬────────────┘
                                              │
                                              ▼
                                  ┌────────────────────────┐
                                  │   Screening Platform   │
                                  │   (Selected Model)     │
                                  └───────────┬────────────┘
                                              │
                                              ▼
                                  ┌────────────────────────┐
                                  │ Human Review & Audit   │
                                  │   (PASS/REJECT/EXTEND) │
                                  └────────────────────────┘
```

---

## 2. Ingestion & Data Source Decoupling

To ensure future extensibility without coupling the system to complex hardware drivers:
- **`IDataSource` Interface:** Defines abstract `load_lot_data(lot_id)` methods.
- **`CSVDataSource` Implementation:** Initial concrete implementation consuming standardized CSV files.
- **Future ATE Path:** Future ATE integration can be achieved by implementing an `ATEDataSource` adapter satisfying `IDataSource`, leaving core analytics completely unmodified.

---

## 3. Dynamic Risk & Safety Reasoning Engine Architecture

The Dynamic Risk Engine balances official specifications against dynamic statistical evidence:

### Separation of Boundaries
1. **Official Engineering Specifications:**
   - Static hard boundaries from component datasheets (e.g., $I_{ddq} \le \text{spec\_max}$).
2. **Derived AI Screening & Risk Boundaries:**
   - Multi-factor risk calculation combining:
     - Population anomaly score $S_{\text{pop}}$ (Module A)
     - Predicted 168h value $\hat{y}_{168h}$ and distance to spec limit (Module B)
     - Trajectory velocity $\Delta_{24-0}$
     - Model prediction uncertainty estimate $\sigma_{\text{pred}}$

*Note: Derived AI risk boundaries are explicitly advisory to assist engineering signoff. They must not replace official engineering acceptance criteria.*

---

## 4. Phase-Gating Strategy

- **Phase-Gating Policy:** *No production implementation for Phase N+1 will begin until Phase N has passed its defined quality gates, unless a dependency or interface prototype is explicitly required and documented.*
- **System Footprint:** The initial codebase relies strictly on standard Python libraries (`pandas`, `numpy`, `scikit-learn`, `pytest`), deferring databases, deep learning frameworks, and streaming protocols until empirically justified.
