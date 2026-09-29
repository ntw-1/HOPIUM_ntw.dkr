# HOPIUM — SIH26170 Project Status

## Current implementation

HOPIUM is a local prototype for AI-assisted anomaly detection and decision support during semiconductor component burn-in and screening. It consumes CSV datasets and serves a browser workstation through `scripts/run_screening_ui.py`. Repository datasets are synthetic; reference limits in those datasets and the Secondary Use application catalogue are illustrative, not official specifications.

The current screening path is:

```text
CSV measurements → validation → Module A anomaly evidence + Module B 168h prediction
→ advisory risk assessment → engineer PASS / MONITOR / REJECT
```

The system does not make the final screening disposition. Module B production features are explicitly allowlisted to `value_0h`, `value_24h`, and `delta_24_0`; `value_96h` and `value_168h` are excluded from its feature matrix. Screening executes registered artifacts; it does not train/select a model for each run.

## Secondary Use

Secondary Use is an integrated downstream UI and service workflow, entered only after an explicit engineer `REJECT` exists in the active screening `AuditRecorder`:

```text
Engineer REJECT → Reuse Pool → Evidence Profile → Illustrative Application Profiles
→ Deterministic Compatibility Assessment → Rule-Based Recommendation
→ Engineer APPROVE / REJECT → Separate Repurposed Register (APPROVE only)
```

Available measurements and derived evidence are carried into the assessment; missing evidence is reported as `UNKNOWN`/unavailable. Compatibility yields `CANDIDATE`, `INCOMPATIBLE`, or `INSUFFICIENT_EVIDENCE`; only a `CANDIDATE` can be approved. Recommendations are advisory and cannot certify suitability. Approval records a separate register entry and does not rewrite the original screening record. Its current transfer status is `PENDING`; transfer and test-result management are not implemented.

Application profiles are YAML files under `data/applications/`. The current catalogue is a prototype and marks its requirements as illustrative. It is not an authoritative engineering standards library.

## Implemented components

- **Data generation/validation:** `src/data/synthetic/` and `src/data/validation/`, configured under `configs/`; scripts under `scripts/` generate and validate local synthetic CSV data.
- **Module A:** `src/anomaly/` computes population-relative anomaly evidence.
- **Module B / Model Lab:** `src/model_lab/` builds an explicit production feature matrix, trains/evaluates candidates, registers artifacts, and supports explicit model lifecycle operations. The locked blind-test process belongs to evaluation tooling and is separate from screening inference.
- **Risk:** `src/risk/` combines anomaly, reference-boundary, drift, and uncertainty evidence into advisory risk outputs.
- **Screening/audit:** `src/screening/` and `src/audit/` provide pipeline, service, session-level engineer decisions, exports, and browser UI. Screening audit records are held in memory for the active process; they are not restored as a persistent audit log after restart.
- **Secondary Use:** `src/secondary_use/` contains evidence, deterministic compatibility, rule-based recommendation, and separate local persistence. Assessment/register state is in `data/secondary_use/records.json`; decision events are appended to `data/secondary_use/records.json.audit.jsonl`.
- **UI server:** `scripts/run_screening_ui.py` serves `src/screening/ui/index.html` and the screening, Model Lab, audit, and Secondary Use routes.

## HTTP routes

The server currently exposes:

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/` and `/index.html` | Browser workstation |
| GET | `/api/datasets` | Discover root-level CSV datasets |
| GET | `/api/current` | Current screening snapshot; lazily runs the default demo dataset if needed |
| POST | `/api/screen` | Run screening for `csv_path` |
| POST | `/api/decision` | Record screening engineer disposition and reason |
| GET | `/api/export_audit` | Return screening audit records as JSON |
| GET | `/api/download_audit` | Download screening audit CSV |
| GET | `/api/model_lab/status` | Deployed model metadata and versions |
| GET | `/api/model_lab/audit_log` | Current process model-switch history |
| POST | `/api/model_lab/reevaluate` | Re-evaluate deployed model; body accepts `csv_path`/`dataset_path`, `parameter` |
| POST | `/api/model_lab/compare` | Compare candidates; body accepts `csv_path`/`dataset_path`, `parameter` |
| POST | `/api/model_lab/switch` | Register and activate a candidate; body accepts `parameter`, `candidate_name`, optional dataset/reason/operator |
| GET | `/api/secondary-use/pool` | Active-session REJECT pool |
| GET | `/api/secondary-use/evidence/{lot_id}/{component_id}` | Evidence for an eligible component |
| GET | `/api/secondary-use/applications` | Application profile catalogue |
| POST | `/api/secondary-use/assess` | Persist an assessment for `component_id`, `lot_id`, optional `application_ids` |
| GET | `/api/secondary-use/assessments/{assessment_id}` | Retrieve a stored assessment |
| POST | `/api/secondary-use/decision` | Submit engineer `APPROVE`/`REJECT` with assessment, application, reason, and engineer ID |
| GET | `/api/secondary-use/register` | Approved Secondary Use records |
| GET | `/api/secondary-use/export_pool` | Download current eligible pool as CSV |
| GET | `/api/secondary-use/export_register` | Download register as CSV |

The Secondary Use evidence route also accepts `/api/secondary-use/evidence/{component_id}?lot_id={lot_id}`. Errors are returned with route-specific HTTP errors; the service rejects missing/ineligible components, unknown profiles/assessments, duplicate candidate decisions, and approval unless compatibility is `CANDIDATE`.

## Running and tests

From the repository root:

```bash
python3 -m pip install -r requirements.txt
python3 scripts/run_screening_ui.py --port 8501
```

Use `--no-browser` for headless operation. Open `http://127.0.0.1:8501`.

Run tests with:

```bash
pytest -q
```

Latest verified checkpoint result: **175 passed** (`pytest -q`, 2026-09-29). The suite includes screening, model feature boundaries/lifecycle, data generation/validation, risk, audit, and Secondary Use tests.

## Known limitations

- The screening `AuditRecorder` is session-memory-only. Secondary Use eligibility therefore depends on the active screening session and cannot be reconstructed from persisted audit decisions after a restart.
- The Secondary Use record store is local JSON/JSONL, not a database. It is separate from the original screening record.
- There is no authentication, role verification, multi-user coordination, or independently verified engineer identity. Engineer IDs are caller-supplied.
- Application profile requirements are illustrative prototype values. Approval is human decision support, not certification, qualification, or proof of suitability.
- No custody transfer execution, additional-test result entry, or test-station integration is implemented; approved register rows currently use `transfer_status: PENDING`.
- Source CSV data may not contain original application, test conditions, environment, or lifetime history. These remain unavailable rather than inferred.
- Direct ATE/Burn-In/ESS equipment control or streaming is not implemented; input is file-based CSV.
- Synthetic datasets are not real ISRO or industry data. See `data/README.md` for provenance.

## Verification note

This status describes the checked implementation, not a production-release claim. Test results reflect the command and date above; rerun the suite for later revisions.
