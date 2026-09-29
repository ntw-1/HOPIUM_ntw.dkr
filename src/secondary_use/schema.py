"""Typed contracts for the separate secondary-use lifecycle."""

from typing import Any, Dict, List, Optional, TypedDict


class SecondaryUseComponent(TypedDict):
    component_id: str
    lot_id: str
    original_application: Optional[str]
    original_engineer_decision: str
    original_rejection_reason: str
    screening_summary: Dict[str, Any]
    assessment_status: str
    candidate_count: int


class ComponentEvidenceProfile(TypedDict):
    component_id: str
    lot_id: str
    measurements: Dict[str, Dict[str, Any]]
    observed_behavior: Dict[str, Dict[str, Any]]
    module_a: Dict[str, Any]
    module_b: Dict[str, Any]
    original_disposition: Dict[str, Any]
    evidence_references: List[str]


class Requirement(TypedDict, total=False):
    id: str
    parameter: Optional[str]
    evidence_field: Optional[str]
    minimum: float
    maximum: float
    unit: str
    source: str
    confidence: str
    status: str


class ApplicationProfile(TypedDict):
    id: str
    name: str
    criticality: str
    provenance: str
    requirements: List[Requirement]
    additional_testing_required: bool


class EvidenceAssessment(TypedDict):
    requirement_id: str
    status: str
    observed_value: Optional[float]
    requirement: Requirement
    reason: str


class Recommendation(TypedDict):
    application_id: str
    application_name: str
    compatibility_status: str
    requirements: List[EvidenceAssessment]
    missing_evidence: List[str]
    rationale: str


class EngineerAssessment(TypedDict):
    assessment_id: str
    component_id: str
    lot_id: str
    application_id: str
    engineer_decision: str
    engineer_reason: str
    engineer_id: str
    timestamp_utc: str


class RepurposeAuditRecord(EngineerAssessment):
    secondary_use_audit_id: str
