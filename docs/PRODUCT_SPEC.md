# Product Scope and Current Workflow

**Project:** `HOPIUM_sih26170`  
**Problem statement:** SIH26170 — *AI-Driven Anomaly Detection in Component Burn-In & Screening*

HOPIUM is a local prototype for analyzing component burn-in measurements and supporting engineer review. It processes CSV data; direct ATE, Burn-In, or ESS hardware control and live data streaming are not implemented. Repository datasets are synthetic and are not real ISRO or industry data.

## Primary screening workflow

```text
ATE / Burn-In / ESS measurements supplied as CSV
→ Module A population anomaly evidence
→ Module B 168-hour prediction from 0h/24h inputs
→ AI-assisted advisory risk assessment
→ Engineer final decision: PASS / MONITOR / REJECT
```

Module A provides population-relative anomaly evidence. Module B predicts `value_168h` using `value_0h`, `value_24h`, and the derived `delta_24_0`; `value_96h` and `value_168h` are not prediction inputs. AI risk and model outputs are decision support. HOPIUM does not automatically accept or reject components, certify performance, or replace engineering judgment.

## Secondary Use workflow

Secondary Use can be entered **only after an engineer records a final `REJECT` in the active screening session**. AI risk, an anomaly, predicted drift, or a projected boundary crossing does not independently create eligibility.

```text
Engineer REJECT
→ Secondary-Use Pool
→ Component Evidence Profile
→ Application Profiles
→ Deterministic Compatibility Assessment
→ Rule-Based Recommendation
→ Engineer review and APPROVE / REJECT
→ Separate Repurposed Component Register (APPROVE only)
→ Local audit/provenance records
```

The evidence profile draws from available CSV measurements and screening/audit results. Missing original application, operating conditions, environment, lifetime history, or other source fields remain unavailable. The current application catalogue is `data/applications/profiles.yaml`; the bounds and requirements are explicitly illustrative prototype values, not authoritative standards, datasheet limits, or qualification criteria.

Requirement results use `PASS`, `FAIL`, and `UNKNOWN`. A missing measurement is `UNKNOWN` and cannot be treated as a pass. Overall outcomes are:

- `CANDIDATE`: every configured requirement has evidence and passes; this permits engineer review only.
- `INCOMPATIBLE`: at least one configured requirement fails.
- `INSUFFICIENT_EVIDENCE`: no failure decides the outcome, but required evidence is unknown or no requirements are defined.

The current recommender is deterministic and rule-based. It ranks these compatibility outcomes and supplies a rationale. Engineer approval is required and accepted only for a `CANDIDATE`. Approval writes a separate repurposed record; it does not edit the original screening disposition. The register currently records transfer as `PENDING`; no custody transfer execution or test-result entry is implemented.

## Audit and persistence

Screening engineer decisions are held by an in-memory `AuditRecorder` for the active server process. Exporting a CSV does not make this recorder persistent or tamper-proof. Secondary-use assessments/register entries are stored in local JSON and decision events append to JSONL under `data/secondary_use/`. The two histories are separate. The application does not authenticate engineer IDs or provide a cryptographic immutable ledger.

## Non-goals / limitations

- Direct equipment drivers and real-time ATE/ESS data ingestion.
- Standards certification, real-world qualification, or automatic authorization of reuse.
- Authentication, role-based approval, multi-user concurrency, and controlled custody transfer.
- Persistent restoration of screening decisions across server restarts.
- Verified test conditions/lifetime context when those data are absent from the source.
