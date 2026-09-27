"""
src/risk/schema.py

Data contracts and schema definitions for Phase 5 — Dynamic Risk Engine.

IMPORTANT DISCLAIMER:
    All risk levels, thresholds, and evidence rules in this module are
    engineering prototype decision logic for SIH26170 demonstration purposes.
    They are NOT official ISRO safety limits, datasheet specifications, or
    certified component acceptance criteria. They are advisory outputs to
    support human engineering review only.

Risk States:
    LOW     — All evidence is nominal or mildly elevated. No strong concern signals.
    MEDIUM  — One or more moderate concern signals present. Engineering review recommended.
    HIGH    — One or more strong concern signals present. Elevated engineering attention required.

Evidence Axes (computed independently, combined by rules.py):
    - Population anomaly evidence (from Module A)
    - Reference limit breach evidence (from Module A)
    - Drift evidence: observed early trajectory and predicted future drift (from Module B)
    - Uncertainty evidence: prediction interval width and boundary crossing (from Module B)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Risk level constants
RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"


@dataclass
class ParameterRiskEvidence:
    """Per-parameter risk evidence combining Module A anomaly + Module B prediction evidence."""

    parameter_name: str
    unit: str

    # --- Module A population evidence ---
    population_anomaly_score: float           # Max modified Z-Score from Module A
    is_population_anomaly: bool
    population_anomaly_classification: str    # STATE_A, STATE_B, STATE_C, STATE_D
    is_reference_limit_breach: bool

    # --- Raw measurements ---
    value_0h: float
    value_24h: float
    delta_24_0: float                         # value_24h - value_0h

    # --- Module B prediction evidence ---
    predicted_168h: float
    lower_bound_168h: float
    upper_bound_168h: float
    uncertainty_width: float                  # upper_bound - lower_bound
    uncertainty_method: str

    # --- Drift evidence ---
    predicted_drift_from_0h: float            # predicted_168h - value_0h
    predicted_drift_from_24h: float           # predicted_168h - value_24h
    observed_early_delta: float               # delta_24_0 (same as above, for clarity)

    # --- Reference limit context ---
    synthetic_spec_min: Optional[float] = None
    synthetic_spec_max: Optional[float] = None

    # --- Boundary crossing analysis ---
    # Does the POINT prediction exceed the synthetic spec?
    predicted_value_crosses_spec_max: bool = False
    predicted_value_crosses_spec_min: bool = False
    # Does the UPPER uncertainty bound cross the synthetic spec max?
    upper_bound_crosses_spec_max: bool = False
    # Is the prediction sufficiently uncertain to warrant escalation?
    uncertainty_is_high: bool = False

    # --- Per-parameter risk level ---
    parameter_risk_level: str = RISK_LOW

    # --- Human-readable evidence for this parameter ---
    parameter_evidence_reasons: List[str] = field(default_factory=list)


@dataclass
class ComponentRiskAssessment:
    """Full risk assessment for a single component, combining all Module A/B evidence."""

    component_id: str
    lot_id: str

    # --- Overall risk level ---
    overall_risk_level: str                  # LOW, MEDIUM, HIGH

    # --- Evidence summary flags ---
    any_population_anomaly: bool
    any_reference_breach: bool
    any_predicted_spec_crossing: bool
    any_high_uncertainty: bool
    any_elevated_drift: bool

    # --- Per-parameter evidence ---
    parameter_risks: Dict[str, ParameterRiskEvidence] = field(default_factory=dict)

    # --- Deterministic recommendation context for Phase 6 ---
    # This is NOT a PASS/REJECT decision — that belongs to Phase 7 HITL.
    # This is an evidence-based context string for engineering review.
    recommendation_context: str = ""

    # --- Human-readable explanation ---
    risk_reasons: List[str] = field(default_factory=list)
