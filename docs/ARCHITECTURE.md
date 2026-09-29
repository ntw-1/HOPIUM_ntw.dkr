# Architecture Overview

**Project:** `HOPIUM_sih26170`

This document describes the current local prototype. It does not describe an ATE-connected or production deployment.

## Screening dataflow

```text
CSV file → schema/provenance/data validation → Module A + Module B
→ advisory Dynamic Risk Engine → local screening UI → engineer decision
```

`scripts/run_screening_ui.py` constructs `ScreeningService`, which coordinates the `ScreeningPipeline`, `AuditRecorder`, and `SecondaryUseService`. The pipeline reads CSV data through the current file-based workflow; there is no `IDataSource`/`CSVDataSource` abstraction implemented in the present source tree. Direct ATE, Burn-In, or ESS hardware integration is out of scope.

Module A derives lot-relative anomaly evidence. Module B predicts the 168-hour target using only `value_0h`, `value_24h`, and `delta_24_0`, enforced by `src/model_lab/features.py`. Risk combines engineering-reference context, anomaly evidence, predicted drift, and uncertainty. It is advisory; only an engineer records the screening disposition (`PASS`, `MONITOR`, or `REJECT`).

## Secondary Use dataflow

```text
Active-session engineer REJECT
  → Secondary-Use Pool
  → Component Evidence Profile
  → YAML Application Profiles
  → deterministic compatibility checks (PASS / FAIL / UNKNOWN)
  → rule-based recommendation (CANDIDATE / INCOMPATIBLE / INSUFFICIENT_EVIDENCE)
  → engineer decision
  → separate Repurposed Component Register on APPROVE
```

`src/secondary_use/service.py` reads the screening result and `AuditRecorder`; it will not build evidence or pool membership without the explicit engineer `REJECT`. Application requirements are prototype-illustrative and stored in `data/applications/`. Missing evidence yields `UNKNOWN`, never a positive compatibility result. Approval is accepted only for a `CANDIDATE`, with a non-empty reason and caller-provided engineer ID.

Secondary-use assessments, engineer decision records, and the approved register are persisted separately under `data/secondary_use/`. Decision events are appended to a JSONL file. The existing screening audit recorder is in-memory for the process session; its decision state is not restored after restart. Secondary Use does not rewrite the screening record. Register approval currently has `transfer_status: PENDING`; transfer and additional-test result workflows do not exist.

## Model Lab and deployment

`src/model_lab/` provides the production feature allowlist, candidate evaluation, model registry, and explicit model lifecycle operations. Candidate model selection uses validation MAE on lot-level splits. Screening loads registered models and does not train/select a new model for each lot. The model registry stores artifacts under `models/registered/`; active model pointers are represented in `active_models.json`.

## Audit and trust boundaries

- Screening decisions are session-memory-only. CSV export is available but is not a persistent append-only canonical store.
- Secondary-use JSON persistence uses a temporary file and replace for state writes; event records append to JSONL. This is local persistence, not a tamper-proof or cryptographically anchored audit ledger.
- The local app has no login, authentication, authorization roles, or independently verified engineer identity. Engineer IDs in requests are caller-supplied.
- Application profiles and synthetic dataset reference limits are not official product or standards requirements. HOPIUM does not certify component suitability or standards compliance.

## Local runtime

Run from the repository root using `python3 scripts/run_screening_ui.py --port 8501`; the server uses Python's built-in HTTP server bound to `127.0.0.1`. The browser UI is `src/screening/ui/index.html`. See the root README for routes, dependencies, and test commands.
