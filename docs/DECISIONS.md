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
