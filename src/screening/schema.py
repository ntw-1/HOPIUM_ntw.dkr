"""
src/screening/schema.py

Phase 6 — Screening Platform result contracts.

Defines the data structures that the screening pipeline produces and
the UI/downstream consumers read.

These are pure data containers — no ML or statistical logic here.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Parameter-level result
# ---------------------------------------------------------------------------

@dataclass
class ParameterScreeningResult:
    """
    All available evidence for a single parameter of a single component.
    Fields are sourced directly from Module A and Module B outputs.
    """
    parameter_name: str
    unit: str

    # --- Raw measurements (production input) ---
    value_0h: float
    value_24h: float
    delta_24_0: float          # value_24h - value_0h

    # --- Module B prediction ---
    predicted_168h: float
    lower_bound_168h: float
    upper_bound_168h: float
    uncertainty_width: float
    uncertainty_method: str

    # --- Drift evidence ---
    predicted_drift_from_0h: float     # predicted_168h - value_0h
    drift_frac_spec: Optional[float]   # abs(drift) / spec_range; None if no spec

    # --- Reference limits ---
    synthetic_spec_min: Optional[float]
    synthetic_spec_max: Optional[float]
    is_reference_breach: bool

    # --- Module A population evidence ---
    is_population_anomaly: bool
    population_anomaly_score: float    # max modified Z-score for this parameter

    # --- Boundary crossing flags ---
    predicted_value_crosses_spec_max: bool
    predicted_value_crosses_spec_min: bool
    upper_bound_crosses_spec_max: bool
    uncertainty_is_high: bool

    # --- Risk level for this parameter ---
    parameter_risk_level: str          # LOW / MEDIUM / HIGH

    # --- Explainable reasons ---
    reasons: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Component-level result
# ---------------------------------------------------------------------------

@dataclass
class ComponentScreeningResult:
    """
    Full screening result for a single component across all parameters.
    Assembles Module A, Module B, and Risk Engine outputs.
    """
    component_id: str
    lot_id: str

    # --- Overall risk (max across parameters) ---
    overall_risk_level: str           # LOW / MEDIUM / HIGH
    recommendation_context: str       # Advisory context string for human review

    # --- Summary flags ---
    is_population_anomaly: bool       # Any parameter flagged by Module A
    is_reference_breach: bool         # Any parameter currently outside spec
    any_predicted_spec_crossing: bool
    any_high_uncertainty: bool
    any_elevated_drift: bool

    # --- Per-parameter results ---
    parameters: Dict[str, ParameterScreeningResult] = field(default_factory=dict)

    # --- Aggregated reasons ---
    risk_reasons: List[str] = field(default_factory=list)

    # --- Module A classification ---
    anomaly_classification_state: str = "STATE_A_NORMAL"
    anomaly_score: float = 0.0        # Max modified Z-score across all parameters


# ---------------------------------------------------------------------------
# Lot-level summary
# ---------------------------------------------------------------------------

@dataclass
class LotScreeningResult:
    """
    Lot-level summary of screening results.
    """
    lot_id: str
    total_components: int

    # --- Validation ---
    validation_status: str             # PASS / FAIL / SKIPPED
    validation_hard_failures: int
    validation_warnings: int

    # --- Risk distribution ---
    risk_low_count: int
    risk_medium_count: int
    risk_high_count: int

    # --- Module A summary ---
    population_anomaly_count: int
    reference_breach_count: int

    # --- Component results ---
    component_results: List[ComponentScreeningResult] = field(default_factory=list)

    def components_requiring_attention(self) -> List[ComponentScreeningResult]:
        """Return MEDIUM and HIGH risk components, sorted by risk (HIGH first)."""
        rank = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
        flagged = [c for c in self.component_results
                   if c.overall_risk_level in ("MEDIUM", "HIGH")]
        return sorted(flagged, key=lambda c: -rank.get(c.overall_risk_level, 0))


# ---------------------------------------------------------------------------
# Full screening result (multi-lot or single-lot)
# ---------------------------------------------------------------------------

@dataclass
class ScreeningResult:
    """
    Top-level result produced by the ScreeningPipeline for one run.
    May contain one or many lots.
    """
    csv_path: Optional[str]
    total_lots: int
    total_components: int

    # --- Overall validation ---
    validation_status: str             # PASS / FAIL
    validation_hard_failures: int
    validation_warnings: int
    validation_messages: List[str] = field(default_factory=list)

    # --- Aggregate risk counts across all lots ---
    risk_low_count: int = 0
    risk_medium_count: int = 0
    risk_high_count: int = 0

    # --- Per-lot results ---
    lot_results: Dict[str, LotScreeningResult] = field(default_factory=dict)

    # --- Error / abort reason ---
    aborted: bool = False
    abort_reason: str = ""

    def get_component(self, component_id: str,
                      lot_id: Optional[str] = None) -> Optional[ComponentScreeningResult]:
        """Look up a component result by ID (optionally scoped to a lot)."""
        for lid, lot in self.lot_results.items():
            if lot_id is not None and lid != lot_id:
                continue
            for comp in lot.component_results:
                if comp.component_id == component_id:
                    return comp
        return None
