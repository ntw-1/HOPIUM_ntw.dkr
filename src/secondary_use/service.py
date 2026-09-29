"""Secondary-use assessment built around canonical screening and engineer records."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from ..audit.schema import DECISION_REJECT
from .compatibility import assess_compatibility
from .recommendation import RecommendationProvider, RuleBasedRecommendationProvider


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SecondaryUseService:
    """Build profiles, assess application profiles, and persist a separate lifecycle."""

    VERSION = "rule-based-v1"

    def __init__(self, storage_path: str = "data/secondary_use/records.json"):
        self.storage_path = storage_path
        self.recommendation_provider: RecommendationProvider = RuleBasedRecommendationProvider()

    @staticmethod
    def _components(screening_result: Any) -> Dict[tuple, Any]:
        if screening_result is None:
            return {}
        return {
            (c.lot_id, c.component_id): c
            for lot in screening_result.lot_results.values()
            for c in lot.component_results
        }

    def list_pool(self, screening_result: Any, recorder: Any) -> List[dict]:
        """Only explicit engineer REJECT records enter this pool."""
        items = []
        for rec in recorder.list_records():
            if rec.engineer_decision != DECISION_REJECT:
                continue
            component = self._components(screening_result).get((rec.lot_id, rec.component_id))
            assessments = [a for a in self._read()["assessments"]
                           if a["component_id"] == rec.component_id and a["lot_id"] == rec.lot_id]
            items.append({
                "component_id": rec.component_id, "lot_id": rec.lot_id,
                "original_application": "unavailable",
                "original_engineer_decision": rec.engineer_decision,
                "original_rejection_reason": rec.engineer_reason,
                "original_rejection_timestamp_utc": rec.timestamp_utc,
                "screening_summary": self._summary(component),
                "assessment_status": (
                    "DECISION_RECORDED" if assessments and assessments[-1]["engineer_decisions"]
                    else "ENGINEERING_REVIEW_REQUIRED" if assessments else "NOT_ASSESSED"
                ),
                "latest_engineer_decision": (
                    assessments[-1]["engineer_decisions"][-1]["engineer_decision"]
                    if assessments and assessments[-1]["engineer_decisions"] else None
                ),
                "candidate_count": sum(
                    item["compatibility_status"] == "CANDIDATE"
                    for item in assessments[-1]["recommendations"]
                ) if assessments else 0,
            })
        return items

    @staticmethod
    def _summary(component: Any) -> dict:
        if component is None:
            return {"available": False}
        return {"available": True, "ai_risk": component.overall_risk_level,
                "module_a_anomaly": component.is_population_anomaly,
                "reference_breach": component.is_reference_breach,
                "risk_reasons": list(component.risk_reasons)}

    def build_evidence(self, screening_result: Any, recorder: Any, component_id: str,
                       lot_id: str) -> dict:
        record = recorder.get_record(component_id, lot_id)
        if record is None or record.engineer_decision != DECISION_REJECT:
            raise ValueError("Component is not eligible: an engineer REJECT record is required.")
        component = self._components(screening_result).get((lot_id, component_id))
        if component is None:
            raise ValueError("Component is not present in the active screening result.")
        rows: Dict[str, dict] = {}
        csv_path = getattr(screening_result, "csv_path", None)
        if csv_path and os.path.isfile(csv_path):
            frame = pd.read_csv(csv_path)
            selected = frame[(frame["component_id"] == component_id) & (frame["lot_id"] == lot_id)]
            for _, row in selected.iterrows():
                name = str(row["parameter_name"])
                rows[name] = {key: (None if pd.isna(row.get(key)) else row.get(key)) for key in (
                    "unit", "value_0h", "value_24h", "value_96h", "value_168h",
                    "synthetic_spec_min", "synthetic_spec_max")}
        derived = {}
        for name, values in rows.items():
            v0, v24, v168 = values.get("value_0h"), values.get("value_24h"), values.get("value_168h")
            derived[name] = {
                "early_delta_24_0": v24 - v0 if v24 is not None and v0 is not None else None,
                "observed_drift_168_0": v168 - v0 if v168 is not None and v0 is not None else None,
                "reference_breach": bool((values.get("synthetic_spec_min") is not None and v168 is not None and v168 < values["synthetic_spec_min"]) or
                                          (values.get("synthetic_spec_max") is not None and v168 is not None and v168 > values["synthetic_spec_max"])) if v168 is not None else None,
            }
        predicted = {name: {
            "predicted_168h": p.predicted_168h, "lower_bound_168h": p.lower_bound_168h,
            "upper_bound_168h": p.upper_bound_168h, "uncertainty_width": p.uncertainty_width,
            "uncertainty_method": p.uncertainty_method, "risk": p.parameter_risk_level,
            "module_a_anomaly": p.is_population_anomaly,
            "population_anomaly_score": p.population_anomaly_score,
        } for name, p in component.parameters.items()}
        return {
            "component_id": component_id, "lot_id": lot_id,
            "parameter_class": sorted(rows), "original_application": None,
            "measurements": rows, "observed_behavior": derived,
            "module_a": {"anomaly": component.is_population_anomaly,
                         "classification": component.anomaly_classification_state,
                         "score": component.anomaly_score},
            "module_b": predicted, "ai_risk": self._summary(component),
            "screening_history": {"conditions": None, "duration_hours": None,
                                  "test_environment": None, "status": "unavailable in source record"},
            "original_disposition": {"ai_recommendation": component.recommendation_context,
                                     "engineer_decision": record.engineer_decision,
                                     "rejection_reason": record.engineer_reason,
                                     "timestamp_utc": record.timestamp_utc},
            "evidence_references": [f"screening:{lot_id}:{component_id}", f"audit:{record.session_id}:{record.timestamp_utc}"],
        }

    @staticmethod
    def list_applications(directory: str = "data/applications") -> List[dict]:
        profiles = []
        if not os.path.isdir(directory):
            return profiles
        for name in sorted(os.listdir(directory)):
            if name.endswith((".yaml", ".yml")):
                with open(os.path.join(directory, name), encoding="utf-8") as handle:
                    loaded = yaml.safe_load(handle)
                    profiles.extend(loaded if isinstance(loaded, list) else [loaded])
        return profiles

    @staticmethod
    def assess(evidence: dict, application: dict) -> dict:
        return assess_compatibility(evidence, application)

    def recommend(self, evidence: dict, applications: Optional[List[dict]] = None) -> dict:
        considered = applications if applications is not None else self.list_applications()
        return self.recommendation_provider.recommend(evidence, considered)

    def create_assessment(self, evidence: dict, applications: Optional[List[dict]] = None) -> dict:
        recommendation = self.recommend(evidence, applications)
        assessment = {"assessment_id": str(uuid.uuid4()), "component_id": evidence["component_id"],
                      "lot_id": evidence["lot_id"], "evidence_profile": evidence,
                      "recommendation": recommendation, "recommendations": recommendation["recommendations"],
                      "created_at": recommendation["generated_at"], "engineer_decisions": []}
        state = self._read(); state["assessments"].append(assessment); self._write(state)
        return assessment

    def submit_decision(self, assessment_id: str, application_id: str, decision: str,
                        reason: str, engineer_id: str) -> dict:
        norm = str(decision).upper().strip()
        if norm not in ("APPROVE", "REJECT"):
            raise ValueError("Decision must be APPROVE or REJECT.")
        if not reason or not reason.strip() or not engineer_id or not engineer_id.strip():
            raise ValueError("Engineer identity and decision reason are required.")
        state = self._read()
        assessment = next((a for a in state["assessments"] if a["assessment_id"] == assessment_id), None)
        if assessment is None:
            raise ValueError("Assessment not found.")
        recommendation = next((r for r in assessment["recommendations"] if r["application_id"] == application_id), None)
        if recommendation is None:
            raise ValueError("Application was not assessed for this assessment.")
        if norm == "APPROVE" and recommendation["compatibility_status"] != "CANDIDATE":
            raise ValueError("Only a CANDIDATE with no UNKNOWN or FAIL requirements can be approved.")
        if any(d["application_id"] == application_id for d in assessment["engineer_decisions"]):
            raise ValueError("A decision already exists for this candidate application.")
        decision_record = {"secondary_use_audit_id": str(uuid.uuid4()), "assessment_id": assessment_id,
                           "component_id": assessment["component_id"], "lot_id": assessment["lot_id"],
                           "application_id": application_id, "engineer_decision": norm,
                           "engineer_reason": reason.strip(), "engineer_id": engineer_id.strip(), "timestamp_utc": _now()}
        assessment["engineer_decisions"].append(decision_record)
        if norm == "APPROVE":
            state["register"].append({**decision_record,
                "original_application": assessment["evidence_profile"].get("original_application"),
                "original_rejection_reason": assessment["evidence_profile"]["original_disposition"]["rejection_reason"],
                "candidate_application": recommendation["application_name"],
                "ai_recommendation": recommendation["rationale"],
                "evidence_summary": assessment["evidence_profile"]["measurements"],
                "additional_testing_required": recommendation["additional_testing_required"],
                "additional_testing_result": None, "approved_destination": recommendation["application_name"],
                "transfer_status": "PENDING"})
        self._write(state)
        audit_path = self.storage_path + ".audit.jsonl"
        os.makedirs(os.path.dirname(os.path.abspath(audit_path)), exist_ok=True)
        with open(audit_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(decision_record, allow_nan=False) + "\n")
        return decision_record

    def get_assessment(self, assessment_id: str) -> dict:
        assessment = next((a for a in self._read()["assessments"] if a["assessment_id"] == assessment_id), None)
        if assessment is None:
            raise ValueError("Assessment not found.")
        return assessment

    def list_register(self) -> List[dict]:
        return self._read()["register"]

    def _read(self) -> dict:
        if not os.path.exists(self.storage_path):
            return {"assessments": [], "audit": [], "register": []}
        with open(self.storage_path, encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, state: dict) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.storage_path)), exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(self.storage_path)))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, allow_nan=False)
            os.replace(temp_path, self.storage_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
