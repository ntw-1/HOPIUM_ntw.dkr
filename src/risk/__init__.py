"""
src/risk/__init__.py

Phase 5 — Dynamic Risk Engine public API.
"""

from .schema import (
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    ComponentRiskAssessment,
    ParameterRiskEvidence,
)
from .rules import evaluate_parameter_risk, compute_component_risk
from .engine import DynamicRiskEngine
from .explainability import (
    format_component_assessment,
    assessment_to_dict,
    assessments_to_dataframe,
)

__all__ = [
    "RISK_LOW",
    "RISK_MEDIUM",
    "RISK_HIGH",
    "ParameterRiskEvidence",
    "ComponentRiskAssessment",
    "evaluate_parameter_risk",
    "compute_component_risk",
    "DynamicRiskEngine",
    "format_component_assessment",
    "assessment_to_dict",
    "assessments_to_dataframe",
]
