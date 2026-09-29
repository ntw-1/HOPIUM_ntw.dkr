# Tests and Verification

## Run the suite

From the repository root:

```bash
pytest -q
```

Run focused areas with, for example:

```bash
pytest -q tests/unit/test_screening_pipeline.py tests/unit/test_audit_trail.py
pytest -q tests/unit/test_secondary_use.py tests/unit/test_model_lab_lifecycle.py
```

All automated tests currently live in `tests/unit/`; there is no `tests/integration/` directory in this repository. A recent repository checkpoint ran `pytest -q`; the current verified count is recorded in the root `README.md` and `PROJECT_STATUS.md` only after execution.

## Current test areas

- Synthetic dataset generation, provenance, and V2 trajectories.
- Schema/data validation and dataset integrity.
- Module A anomaly detection and Module B input feature boundaries.
- Model Lab lifecycle and model registration/switch behavior.
- Risk engine reasoning, uncertainty, and safety-slope behavior.
- Screening pipeline and session audit recording/export.
- Secondary Use eligibility after engineer `REJECT`, evidence/profile assessment, `UNKNOWN` handling, recommendation outcomes, decision validation, and separate register persistence.

## Important behavior to preserve

- Module B feature matrix is limited to `value_0h`, `value_24h`, and derived `delta_24_0`. `value_96h` and `value_168h` remain excluded from prediction features.
- Secondary Use pool membership requires the active session's explicit engineer `REJECT`; startup/demo loading must not create engineer decisions.
- Missing compatibility evidence remains `UNKNOWN`; approval is accepted only for `CANDIDATE`.
- Secondary-use approval creates a separate register entry and never rewrites the screening decision.
- Screening audit memory is session-scoped; tests and docs must not call it a persistent immutable log.

## Runtime smoke checks

The pytest suite primarily checks library/service behavior. For a local API/UI smoke check, start the app with `python3 scripts/run_screening_ui.py --port 8501 --no-browser`, request `/`, `/api/current`, `/api/secondary-use/pool`, and verify a real engineer `REJECT` is required before an evidence request or assessment succeeds. Use a temporary Secondary Use storage path when exercising approval/rejection so local saved records are not changed. Stop the server after the check.
