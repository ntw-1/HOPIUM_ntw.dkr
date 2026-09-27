"""
src/risk/explainability.py

Human-readable explanation and reporting utilities for Phase 5 — Dynamic Risk Engine.

Provides:
    - format_component_assessment: Rich text summary of a ComponentRiskAssessment.
    - assessment_to_dict: Flat dict for JSON export / DataFrame construction.
    - assessments_to_dataframe: Batch export of ComponentRiskAssessments.
"""

from typing import Dict, List

import pandas as pd

from .schema import ComponentRiskAssessment, ParameterRiskEvidence, RISK_HIGH, RISK_MEDIUM, RISK_LOW

_DISCLAIMER = (
    "PROTOTYPE ADVISORY OUTPUT ONLY. Not official ISRO safety limits or "
    "certified acceptance criteria. Human engineering review required."
)


def format_component_assessment(assessment: ComponentRiskAssessment) -> str:
    """
    Return a human-readable multi-line text report for one ComponentRiskAssessment.
    """
    lines = [
        "=" * 72,
        f"RISK ASSESSMENT — Component: {assessment.component_id}  Lot: {assessment.lot_id}",
        "=" * 72,
        f"  Overall Risk Level : {assessment.overall_risk_level}",
        f"  Recommendation     : {assessment.recommendation_context}",
        "",
        "  Summary Flags:",
        f"    Population Anomaly     : {assessment.any_population_anomaly}",
        f"    Reference Limit Breach : {assessment.any_reference_breach}",
        f"    Predicted Spec Crossing: {assessment.any_predicted_spec_crossing}",
        f"    High Uncertainty       : {assessment.any_high_uncertainty}",
        f"    Elevated Drift         : {assessment.any_elevated_drift}",
        "",
    ]

    if assessment.risk_reasons:
        lines.append("  Evidence Reasons:")
        for reason in assessment.risk_reasons:
            lines.append(f"    • {reason}")
        lines.append("")

    for param_name, ev in assessment.parameter_risks.items():
        lines.append(f"  ── Parameter: {param_name} ──")
        lines.append(f"     Risk Level        : {ev.parameter_risk_level}")
        lines.append(f"     value_0h          : {ev.value_0h:.4g} [{ev.unit}]")
        lines.append(f"     value_24h         : {ev.value_24h:.4g} [{ev.unit}]")
        lines.append(f"     delta_24_0        : {ev.delta_24_0:.4g} [{ev.unit}]")
        lines.append(
            f"     predicted_168h    : {ev.predicted_168h:.4g} "
            f"[{ev.lower_bound_168h:.4g}, {ev.upper_bound_168h:.4g}] [{ev.unit}]"
        )
        lines.append(f"     uncertainty_method: {ev.uncertainty_method}")
        lines.append(f"     pop_anomaly_score : {ev.population_anomaly_score:.3f}")
        lines.append(f"     is_pop_anomaly    : {ev.is_population_anomaly}")
        lines.append(f"     is_ref_breach     : {ev.is_reference_limit_breach}")
        if ev.parameter_evidence_reasons:
            lines.append("     Reasons:")
            for r in ev.parameter_evidence_reasons:
                lines.append(f"       - {r}")
        lines.append("")

    lines.append(f"  [{_DISCLAIMER}]")
    lines.append("=" * 72)
    return "\n".join(lines)


def assessment_to_dict(assessment: ComponentRiskAssessment) -> dict:
    """
    Convert a ComponentRiskAssessment to a flat dict suitable for DataFrame export.
    One dict per component (parameter-level evidence is summarised).
    """
    row = {
        "lot_id": assessment.lot_id,
        "component_id": assessment.component_id,
        "overall_risk_level": assessment.overall_risk_level,
        "recommendation_context": assessment.recommendation_context,
        "any_population_anomaly": assessment.any_population_anomaly,
        "any_reference_breach": assessment.any_reference_breach,
        "any_predicted_spec_crossing": assessment.any_predicted_spec_crossing,
        "any_high_uncertainty": assessment.any_high_uncertainty,
        "any_elevated_drift": assessment.any_elevated_drift,
        "risk_reasons_count": len(assessment.risk_reasons),
        "risk_reasons_joined": " | ".join(assessment.risk_reasons),
    }
    # Per-parameter summary columns
    for param, ev in assessment.parameter_risks.items():
        safe = param.replace(" ", "_")
        row[f"{safe}_risk_level"] = ev.parameter_risk_level
        row[f"{safe}_pop_score"] = ev.population_anomaly_score
        row[f"{safe}_is_pop_anomaly"] = ev.is_population_anomaly
        row[f"{safe}_is_ref_breach"] = ev.is_reference_limit_breach
        row[f"{safe}_predicted_168h"] = ev.predicted_168h
        row[f"{safe}_lower_bound_168h"] = ev.lower_bound_168h
        row[f"{safe}_upper_bound_168h"] = ev.upper_bound_168h
        row[f"{safe}_uncertainty_width"] = ev.uncertainty_width
        row[f"{safe}_predicted_drift_from_0h"] = ev.predicted_drift_from_0h
        row[f"{safe}_predicted_crosses_spec"] = (
            ev.predicted_value_crosses_spec_max or ev.predicted_value_crosses_spec_min
        )
        row[f"{safe}_upper_bound_crosses_spec_max"] = ev.upper_bound_crosses_spec_max
        row[f"{safe}_uncertainty_is_high"] = ev.uncertainty_is_high
    return row


def assessments_to_dataframe(assessments: List[ComponentRiskAssessment]) -> pd.DataFrame:
    """
    Convert a list of ComponentRiskAssessments to a DataFrame with one row per component.
    """
    rows = [assessment_to_dict(a) for a in assessments]
    return pd.DataFrame(rows)
