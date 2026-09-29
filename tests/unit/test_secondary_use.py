import json
from types import SimpleNamespace

import pandas as pd
import pytest

from src.audit.recorder import AuditRecorder
from src.secondary_use.service import SecondaryUseService
from src.screening.service import ScreeningService


@pytest.fixture
def case(tmp_path):
    csv_path = tmp_path / "source.csv"
    rows = []
    for name, unit, v0, v24, v96, v168, lo, hi in [
        ("Iddq", "uA", 10.0, 10.2, 10.4, 10.5, 0.0, 50.0),
        ("leakage_current", "nA", 4.0, 4.1, 4.2, 4.3, 0.0, 30.0),
        ("propagation_delay", "ps", 100.0, 101.0, 102.0, 103.0, 80.0, 180.0),
    ]:
        rows.append({"lot_id": "LOT1", "component_id": "C1", "parameter_name": name,
                     "unit": unit, "value_0h": v0, "value_24h": v24, "value_96h": v96,
                     "value_168h": v168, "synthetic_spec_min": lo, "synthetic_spec_max": hi})
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    params = {r["parameter_name"]: SimpleNamespace(
        unit=r["unit"], value_0h=r["value_0h"], value_24h=r["value_24h"],
        predicted_168h=r["value_168h"], lower_bound_168h=r["value_168h"] - 1,
        upper_bound_168h=r["value_168h"] + 1, uncertainty_width=2,
        uncertainty_method="test", parameter_risk_level="LOW", is_population_anomaly=False,
        population_anomaly_score=0.1) for r in rows}
    component = SimpleNamespace(component_id="C1", lot_id="LOT1", overall_risk_level="HIGH",
        is_population_anomaly=True, is_reference_breach=False, risk_reasons=["illustrative risk"],
        anomaly_classification_state="STATE_A_NORMAL", anomaly_score=0.1,
        recommendation_context="Review required", parameters=params)
    lot = SimpleNamespace(component_results=[component])
    screening = SimpleNamespace(csv_path=str(csv_path), lot_results={"LOT1": lot})
    recorder = AuditRecorder("test-session")
    storage = tmp_path / "secondary" / "records.json"
    service = SecondaryUseService(str(storage))
    return SimpleNamespace(service=service, screening=screening, recorder=recorder,
                           component=component, storage=storage)


def reject(case):
    case.recorder.record_from_screening_component(case.component, "REJECT", "Rejected at final engineering review")


def test_pool_gate_requires_explicit_engineer_reject(case):
    case.component.overall_risk_level = "HIGH"
    case.component.is_population_anomaly = True
    assert case.service.list_pool(case.screening, case.recorder) == []
    case.recorder.record_from_screening_component(case.component, "PASS", "Accepted")
    assert case.service.list_pool(case.screening, case.recorder) == []
    reject(case)
    pool = case.service.list_pool(case.screening, case.recorder)
    assert len(pool) == 1
    assert pool[0]["original_rejection_reason"] == "Rejected at final engineering review"


def test_evidence_profile_uses_available_source_measurements(case):
    reject(case)
    evidence = case.service.build_evidence(case.screening, case.recorder, "C1", "LOT1")
    assert evidence["measurements"]["Iddq"]["value_96h"] == 10.4
    assert evidence["measurements"]["Iddq"]["value_168h"] == 10.5
    assert evidence["observed_behavior"]["Iddq"]["early_delta_24_0"] == pytest.approx(0.2)
    assert evidence["screening_history"]["duration_hours"] is None
    assert evidence["original_disposition"]["engineer_decision"] == "REJECT"


def test_application_catalogue_has_provenance_and_illustrative_requirements():
    profiles = SecondaryUseService.list_applications()
    assert 5 <= len(profiles) <= 8
    assert all(p["provenance"] == "prototype-illustrative" for p in profiles)
    assert all(req["source"] and req["confidence"] for p in profiles for req in p["requirements"])


def test_requirement_engine_pass_fail_unknown_and_missing_requirement():
    evidence = {"measurements": {"Iddq": {"value_168h": 12.0}}}
    app = {"id": "test", "name": "Test", "requirements": [
        {"id": "pass", "parameter": "Iddq", "evidence_field": "value_168h", "maximum": 20},
        {"id": "fail", "parameter": "Iddq", "evidence_field": "value_168h", "maximum": 10},
        {"id": "unknown", "parameter": "leakage_current", "evidence_field": "value_168h", "maximum": 5},
    ]}
    result = SecondaryUseService.assess(evidence, app)
    assert [r["status"] for r in result["requirements"]] == ["PASS", "FAIL", "UNKNOWN"]
    assert result["compatibility_status"] == "INCOMPATIBLE"
    assert SecondaryUseService.assess(evidence, {"id": "empty", "name": "Empty", "requirements": []})["compatibility_status"] == "INSUFFICIENT_EVIDENCE"


def test_recommendations_have_provenance_and_preserve_unknown(case):
    reject(case)
    evidence = case.service.build_evidence(case.screening, case.recorder, "C1", "LOT1")
    rec = case.service.recommend(evidence)
    assert rec["provider"] == "rule-based"
    assert rec["version"]
    assert rec["evidence_references"]
    high = next(r for r in rec["recommendations"] if r["application_id"] == "high_criticality_electronics")
    assert high["compatibility_status"] == "INSUFFICIENT_EVIDENCE"


def test_end_to_end_approval_register_audit_and_source_immutability(case):
    reject(case)
    original = case.recorder.get_record("C1", "LOT1")
    original_values = (original.engineer_decision, original.engineer_reason, original.timestamp_utc)
    assessment = case.service.create_assessment(
        case.service.build_evidence(case.screening, case.recorder, "C1", "LOT1"),
        [p for p in case.service.list_applications() if p["id"] == "educational_development_hardware"],
    )
    recommendation = assessment["recommendations"][0]
    assert recommendation["compatibility_status"] == "CANDIDATE"
    decision = case.service.submit_decision(assessment["assessment_id"], recommendation["application_id"],
                                            "APPROVE", "Approved for controlled prototype review", "ENG-1")
    assert decision["engineer_decision"] == "APPROVE"
    assert len(case.service.list_register()) == 1
    assert case.service.list_register()[0]["approved_destination"] == "Educational / Development Hardware"
    assert case.recorder.get_record("C1", "LOT1") is original
    assert (original.engineer_decision, original.engineer_reason, original.timestamp_utc) == original_values
    assert len((case.storage.parent / "records.json.audit.jsonl").read_text().splitlines()) == 1
    assert json.loads(case.storage.read_text())["register"][0]["component_id"] == "C1"
    reloaded = SecondaryUseService(str(case.storage))
    assert reloaded.get_assessment(assessment["assessment_id"])["assessment_id"] == assessment["assessment_id"]
    assert reloaded.list_register()[0]["secondary_use_audit_id"] == decision["secondary_use_audit_id"]


def test_unknown_cannot_be_approved_and_secondary_rejection_not_registered(case):
    reject(case)
    evidence = case.service.build_evidence(case.screening, case.recorder, "C1", "LOT1")
    assessment = case.service.create_assessment(evidence, [p for p in case.service.list_applications()
                                                           if p["id"] == "high_criticality_electronics"])
    rec = assessment["recommendations"][0]
    with pytest.raises(ValueError, match="Only a CANDIDATE"):
        case.service.submit_decision(assessment["assessment_id"], rec["application_id"], "APPROVE", "No", "ENG")
    case.service.submit_decision(assessment["assessment_id"], rec["application_id"], "REJECT", "Insufficient data", "ENG")
    assert case.service.list_register() == []


def test_invalid_and_duplicate_decisions_are_rejected(case):
    reject(case)
    assessment = case.service.create_assessment(
        case.service.build_evidence(case.screening, case.recorder, "C1", "LOT1"),
        [p for p in case.service.list_applications() if p["id"] == "educational_development_hardware"],
    )
    app_id = assessment["recommendations"][0]["application_id"]
    with pytest.raises(ValueError, match="not found"):
        case.service.get_assessment("missing")
    with pytest.raises(ValueError, match="not eligible"):
        case.service.build_evidence(case.screening, case.recorder, "missing", "LOT1")
    case.service.submit_decision(assessment["assessment_id"], app_id, "APPROVE", "yes", "ENG")
    with pytest.raises(ValueError, match="already exists"):
        case.service.submit_decision(assessment["assessment_id"], app_id, "APPROVE", "again", "ENG")


def test_screening_service_exposes_secondary_workflow(case):
    service = ScreeningService()
    service.current_screening_result = case.screening
    service.audit_recorder = case.recorder
    service.secondary_use = case.service
    reject(case)
    assert service.list_secondary_use_pool()[0]["component_id"] == "C1"
    assessment = service.assess_secondary_use("C1", "LOT1", ["educational_development_hardware"])
    assert assessment["recommendations"][0]["compatibility_status"] == "CANDIDATE"
