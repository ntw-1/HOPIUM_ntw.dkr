"""
tests/unit/test_audit_trail.py

Phase 7 unit and integration tests — Human-in-the-Loop Audit Trail.

Tests cover all required scenarios:
    1. PASS decision with valid reason is accepted
    2. MONITOR decision with valid reason is accepted
    3. REJECT decision with valid reason is accepted
    4. Empty reason is rejected (raises ValueError)
    5. Whitespace-only reason is rejected (raises ValueError)
    6. AI assessment remains separate from engineer decision
    7. Audit record retains component and lot identity
    8. Audit record retains AI risk/evidence
    9. Audit record retains human decision/reason
    10. Multiple component decisions can coexist
    11. Export contains required audit fields
    12. Export does not lose distinction between AI assessment and human decision
    13. Regression: demo screening dataset still yields 78/118/54 distribution
"""

import os
import sys
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from src.audit.schema import (
    DECISION_PASS,
    DECISION_MONITOR,
    DECISION_REJECT,
    AuditRecord,
)
from src.audit.recorder import AuditRecorder
from src.audit.exporter import AuditExporter, audit_record_to_dict
from src.screening.pipeline import ScreeningPipeline

DEMO_CSV = os.path.join(os.path.dirname(__file__), "../../data/demo_burnin_data.csv")
REGISTRY_DIR = os.path.join(os.path.dirname(__file__), "../../models/registered")
RISK_CONFIG = os.path.join(os.path.dirname(__file__), "../../configs/risk_engine_config.yaml")


# ===========================================================================
# TEST 1 — PASS decision with valid reason is accepted
# ===========================================================================

def test_01_pass_decision_accepted():
    recorder = AuditRecorder(session_id="test_sess")
    rec = recorder.record_decision(
        component_id="COMP_001",
        lot_id="LOT_001",
        engineer_decision=DECISION_PASS,
        engineer_reason="Trajectory is stable despite minor population variance.",
        ai_overall_risk="LOW",
        ai_recommendation_context="LOW RISK",
    )
    assert rec.engineer_decision == "PASS"
    assert rec.engineer_reason == "Trajectory is stable despite minor population variance."
    assert rec.component_id == "COMP_001"


# ===========================================================================
# TEST 2 — MONITOR decision with valid reason is accepted
# ===========================================================================

def test_02_monitor_decision_accepted():
    recorder = AuditRecorder(session_id="test_sess")
    rec = recorder.record_decision(
        component_id="COMP_002",
        lot_id="LOT_001",
        engineer_decision=DECISION_MONITOR,
        engineer_reason="Retain for secondary 96h measurement cycle due to elevated Iddq drift.",
        ai_overall_risk="MEDIUM",
        ai_recommendation_context="MEDIUM RISK",
    )
    assert rec.engineer_decision == "MONITOR"
    assert "secondary 96h" in rec.engineer_reason


# ===========================================================================
# TEST 3 — REJECT decision with valid reason is accepted
# ===========================================================================

def test_03_reject_decision_accepted():
    recorder = AuditRecorder(session_id="test_sess")
    rec = recorder.record_decision(
        component_id="COMP_003",
        lot_id="LOT_001",
        engineer_decision=DECISION_REJECT,
        engineer_reason="Confirmed spec boundary breach on Iddq parameter.",
        ai_overall_risk="HIGH",
        ai_recommendation_context="HIGH RISK",
    )
    assert rec.engineer_decision == "REJECT"
    assert rec.engineer_reason == "Confirmed spec boundary breach on Iddq parameter."


# ===========================================================================
# TEST 4 — Empty reason is rejected
# ===========================================================================

def test_04_empty_reason_rejected():
    recorder = AuditRecorder()
    with pytest.raises(ValueError, match="mandatory"):
        recorder.record_decision(
            component_id="COMP_004",
            lot_id="LOT_001",
            engineer_decision=DECISION_PASS,
            engineer_reason="",
            ai_overall_risk="LOW",
            ai_recommendation_context="LOW",
        )


# ===========================================================================
# TEST 5 — Whitespace-only reason is rejected
# ===========================================================================

def test_05_whitespace_reason_rejected():
    recorder = AuditRecorder()
    with pytest.raises(ValueError, match="mandatory"):
        recorder.record_decision(
            component_id="COMP_005",
            lot_id="LOT_001",
            engineer_decision=DECISION_REJECT,
            engineer_reason="    \n\t  ",
            ai_overall_risk="HIGH",
            ai_recommendation_context="HIGH",
        )


# ===========================================================================
# TEST 6 — AI assessment remains separate from engineer decision
# ===========================================================================

def test_06_ai_assessment_separate_from_human_decision():
    recorder = AuditRecorder()

    # Engineer overrides AI HIGH risk to PASS with justification
    rec = recorder.record_decision(
        component_id="COMP_OVERRIDE",
        lot_id="LOT_001",
        engineer_decision=DECISION_PASS,
        engineer_reason="Lab re-measurement confirmed initial 0h spike was test setup artifact.",
        ai_overall_risk="HIGH",
        ai_recommendation_context="HIGH RISK — predicted spec crossing.",
        ai_reasons=["[HIGH] Module B predicts Iddq crossing spec_max=50."],
    )

    # AI assessment fields remain unchanged
    assert rec.ai_overall_risk == "HIGH"
    assert "predicted spec crossing" in rec.ai_recommendation_context
    assert len(rec.ai_reasons) == 1

    # Engineer decision is distinct
    assert rec.engineer_decision == "PASS"
    assert rec.engineer_decision != rec.ai_overall_risk


# ===========================================================================
# TEST 7 — Audit record retains component and lot identity
# ===========================================================================

def test_07_identity_retention():
    recorder = AuditRecorder()
    rec = recorder.record_decision(
        component_id="LOT_002_CMP_0042",
        lot_id="LOT_002",
        engineer_decision=DECISION_PASS,
        engineer_reason="Normal operating trajectory.",
        ai_overall_risk="LOW",
        ai_recommendation_context="LOW",
    )
    assert rec.component_id == "LOT_002_CMP_0042"
    assert rec.lot_id == "LOT_002"
    found = recorder.get_record("LOT_002_CMP_0042", "LOT_002")
    assert found is rec


# ===========================================================================
# TEST 8 — Audit record retains AI risk and evidence
# ===========================================================================

def test_08_ai_evidence_retention():
    recorder = AuditRecorder()
    ai_reasons = [
        "[MEDIUM] Iddq predicted drift exceeds 20% of spec range.",
        "[MEDIUM] High prediction uncertainty width.",
    ]
    rec = recorder.record_decision(
        component_id="C8", lot_id="L8",
        engineer_decision=DECISION_MONITOR,
        engineer_reason="Monitoring due to high uncertainty.",
        ai_overall_risk="MEDIUM",
        ai_recommendation_context="MEDIUM RISK — elevated drift.",
        ai_reasons=ai_reasons,
    )
    assert rec.ai_overall_risk == "MEDIUM"
    assert rec.ai_reasons == ai_reasons


# ===========================================================================
# TEST 9 — Audit record retains human decision and reason
# ===========================================================================

def test_09_human_decision_reason_retention():
    recorder = AuditRecorder()
    rec = recorder.record_decision(
        component_id="C9", lot_id="L9",
        engineer_decision=DECISION_REJECT,
        engineer_reason="Exceeds acceptable internal degradation rate.",
        ai_overall_risk="HIGH",
        ai_recommendation_context="HIGH",
    )
    assert rec.engineer_decision == "REJECT"
    assert rec.engineer_reason == "Exceeds acceptable internal degradation rate."
    assert rec.timestamp_utc


# ===========================================================================
# TEST 10 — Multiple component decisions can coexist
# ===========================================================================

def test_10_multiple_decisions_coexist():
    recorder = AuditRecorder(session_id="multi_sess")
    recorder.record_decision("C10_A", "L10", DECISION_PASS, "Reason A", "LOW", "LOW")
    recorder.record_decision("C10_B", "L10", DECISION_MONITOR, "Reason B", "MEDIUM", "MED")
    recorder.record_decision("C10_C", "L10", DECISION_REJECT, "Reason C", "HIGH", "HIGH")

    records = recorder.list_records("L10")
    assert len(records) == 3
    summary = recorder.get_summary()
    assert summary.total_decisions == 3
    assert summary.pass_count == 1
    assert summary.monitor_count == 1
    assert summary.reject_count == 1


# ===========================================================================
# TEST 11 — Export contains required audit fields
# ===========================================================================

def test_11_export_contains_required_fields(tmp_path):
    pipeline = ScreeningPipeline(
        registry_dir=REGISTRY_DIR,
        risk_config_path=RISK_CONFIG,
    )
    screening_res = pipeline.run(csv_path=DEMO_CSV)

    recorder = AuditRecorder(session_id="export_sess")
    first_lot = sorted(screening_res.lot_results.keys())[0]
    first_comp = screening_res.lot_results[first_lot].component_results[0]

    recorder.record_from_screening_component(
        component_result=first_comp,
        engineer_decision=DECISION_PASS,
        engineer_reason="Approved after manual waveform inspection.",
    )

    exporter = AuditExporter(recorder=recorder)
    df = exporter.export_to_dataframe(screening_res)

    assert "lot_id" in df.columns
    assert "component_id" in df.columns
    assert "ai_overall_risk" in df.columns
    assert "ai_recommendation_context" in df.columns
    assert "engineer_decision_status" in df.columns
    assert "engineer_decision" in df.columns
    assert "engineer_reason" in df.columns
    assert "decision_timestamp_utc" in df.columns

    # Verify reviewed row
    reviewed_row = df[df["component_id"] == first_comp.component_id].iloc[0]
    assert reviewed_row["engineer_decision_status"] == "REVIEWED"
    assert reviewed_row["engineer_decision"] == "PASS"
    assert reviewed_row["engineer_reason"] == "Approved after manual waveform inspection."

    # Export to CSV file
    out_csv = tmp_path / "audit_export.csv"
    exporter.export_to_csv(screening_res, str(out_csv))
    assert out_csv.exists()
    assert out_csv.stat().st_size > 0


# ===========================================================================
# TEST 12 — Export does not lose distinction between AI assessment and human decision
# ===========================================================================

def test_12_export_preserves_ai_vs_human_distinction():
    pipeline = ScreeningPipeline(
        registry_dir=REGISTRY_DIR,
        risk_config_path=RISK_CONFIG,
    )
    screening_res = pipeline.run(csv_path=DEMO_CSV)

    recorder = AuditRecorder()

    # Find a HIGH risk component and override to PASS
    high_comp = None
    for lot in screening_res.lot_results.values():
        for comp in lot.component_results:
            if comp.overall_risk_level == "HIGH":
                high_comp = comp
                break
        if high_comp:
            break

    assert high_comp is not None

    recorder.record_from_screening_component(
        component_result=high_comp,
        engineer_decision=DECISION_PASS,
        engineer_reason="Human engineer override: acceptable application context.",
    )

    exporter = AuditExporter(recorder=recorder)
    df = exporter.export_to_dataframe(screening_res)

    comp_row = df[df["component_id"] == high_comp.component_id].iloc[0]
    # AI overall risk remains HIGH
    assert comp_row["ai_overall_risk"] == "HIGH"
    # Engineer decision is PASS
    assert comp_row["engineer_decision"] == "PASS"
    # They are distinctly represented in separate columns
    assert comp_row["ai_overall_risk"] != comp_row["engineer_decision"]


# ===========================================================================
# TEST 13 & 14 — Regression check on Phase 5 risk distribution
# ===========================================================================

def test_13_14_phase5_regression_distribution_preserved():
    pipeline = ScreeningPipeline(
        registry_dir=REGISTRY_DIR,
        risk_config_path=RISK_CONFIG,
    )
    res = pipeline.run(csv_path=DEMO_CSV)
    assert res.risk_low_count == 78
    assert res.risk_medium_count == 118
    assert res.risk_high_count == 54
