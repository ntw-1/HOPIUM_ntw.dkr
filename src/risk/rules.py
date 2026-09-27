"""
src/risk/rules.py

Evidence-to-risk-level evaluation rules for Phase 5 — Dynamic Risk Engine.

Rules are loaded from configs/risk_engine_config.yaml so every threshold is
explicit, configurable, and auditable — not hardcoded.

Rule Application:
    Each evidence axis is evaluated independently.
    Per-parameter risk is the maximum risk triggered across all axes.
    Component risk is the maximum per-parameter risk.

PROTOTYPE ENGINEERING LOGIC ONLY.
All thresholds are synthetic prototype assumptions for SIH26170 demo.
They must NOT be interpreted as official ISRO or industry acceptance limits.

---
DRIFT AXIS DESIGN NOTE (v2 — scale-aware revision):

The original Axis 5 used: abs(predicted_drift) / abs(delta_24_0)

This was structurally unstable because delta_24_0 (the early 0–24h measurement
change) is typically < 1.5% of the spec range for all three parameters (burn-in
devices drift slowly in the first 24h relative to their full week trajectory).
When the denominator is near zero, the ratio becomes arbitrarily large and
nearly every component fires the HIGH threshold — regardless of whether the
predicted future value is actually concerning relative to its operating limits.

Corrected Axis 5 uses: abs(predicted_drift_from_0h) / spec_range
  — "the predicted 0h→168h drift consumes X% of the allowable spec window"

This is:
  - Dimensionless and scale-invariant across Iddq, leakage_current, propagation_delay
  - Anchored to the same spec range already used for boundary crossing checks
  - Directly interpretable: a component drifting 20% of its spec range in a week
    is meaningfully more concerning than one drifting 2%
  - Stable: the denominator (spec_range) is a fixed known value per parameter

The early trajectory ratio (predicted_drift / delta_24_0) is retained as a
SUPPLEMENTARY signal only when |delta_24_0| is >= min_delta_fraction_of_spec
of spec_range (e.g., 2%), ensuring the denominator is physically meaningful.
Even when it fires, the supplementary ratio can raise risk by at most one level
(i.e., it adds a MEDIUM signal but cannot by itself produce HIGH).
"""

from typing import Dict, Tuple

from .schema import (
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    ParameterRiskEvidence,
)

# Risk level ordering for comparison
_RISK_RANK = {RISK_LOW: 0, RISK_MEDIUM: 1, RISK_HIGH: 2}
_RANK_RISK = {0: RISK_LOW, 1: RISK_MEDIUM, 2: RISK_HIGH}


def _max_risk(a: str, b: str) -> str:
    """Return the higher of two risk levels."""
    return _RANK_RISK[max(_RISK_RANK[a], _RISK_RANK[b])]


def _parse_level(level_str: str) -> str:
    """Parse a risk level string from config. Defaults to LOW if unrecognised."""
    level_str = str(level_str).upper().strip()
    return level_str if level_str in _RISK_RANK else RISK_LOW


def evaluate_parameter_risk(evidence: ParameterRiskEvidence, cfg: dict) -> Tuple[str, list]:
    """
    Evaluate the risk level for a single ParameterRiskEvidence using loaded config rules.

    Returns (risk_level, list_of_reason_strings).

    Evidence axes evaluated:
        1. Reference limit breach (observed measurement outside synthetic spec)
        2. Predicted future value crosses spec boundary
        3. Upper uncertainty bound crosses spec max
        4. Population anomaly (severity: moderate vs. strong)
        5. Predicted future drift as a fraction of spec range (PRIMARY drift criterion)
           + Supplementary: early trajectory ratio (only when delta is physically meaningful)
        6. High prediction uncertainty (as fraction of spec range)
        7. Combined: anomaly + drift, anomaly + high uncertainty

    All axis-level risk signals are combined by taking the maximum.
    The final risk level for the parameter is returned.
    """
    reasons = []
    pa_cfg = cfg.get("population_anomaly", {})
    dr_cfg = cfg.get("drift", {})
    un_cfg = cfg.get("uncertainty", {})
    esc_cfg = cfg.get("risk_escalation_rules", {})

    current_risk = RISK_LOW

    # ------------------------------------------------------------------
    # AXIS 1: Reference limit breach (Module A observation, current meas.)
    # ------------------------------------------------------------------
    if evidence.is_reference_limit_breach:
        level = _parse_level(esc_cfg.get("reference_limit_breach_level", RISK_HIGH))
        current_risk = _max_risk(current_risk, level)
        reasons.append(
            f"[{level}] Observed measurement of {evidence.parameter_name} breaches "
            f"reference limit (spec_min={evidence.synthetic_spec_min}, "
            f"spec_max={evidence.synthetic_spec_max}). "
            f"value_0h={evidence.value_0h:.4g}, value_24h={evidence.value_24h:.4g} [{evidence.unit}]."
        )

    # ------------------------------------------------------------------
    # AXIS 2: Predicted future value crosses spec boundary
    # ------------------------------------------------------------------
    if evidence.predicted_value_crosses_spec_max or evidence.predicted_value_crosses_spec_min:
        level = _parse_level(esc_cfg.get("predicted_spec_crossing_level", RISK_HIGH))
        current_risk = _max_risk(current_risk, level)
        which = "spec_max" if evidence.predicted_value_crosses_spec_max else "spec_min"
        limit = (
            evidence.synthetic_spec_max
            if evidence.predicted_value_crosses_spec_max
            else evidence.synthetic_spec_min
        )
        reasons.append(
            f"[{level}] Module B predicts {evidence.parameter_name} at "
            f"{evidence.predicted_168h:.4g} [{evidence.unit}] by 168h, "
            f"crossing {which}={limit:.4g}."
        )

    # ------------------------------------------------------------------
    # AXIS 3: Upper uncertainty bound crosses spec max
    # ------------------------------------------------------------------
    if evidence.upper_bound_crosses_spec_max:
        level = _parse_level(esc_cfg.get("upper_bound_crosses_spec_max_level", RISK_MEDIUM))
        # Escalate to HIGH if also population anomalous
        if evidence.is_population_anomaly:
            level = RISK_HIGH
        current_risk = _max_risk(current_risk, level)
        reasons.append(
            f"[{level}] Module B 168h prediction upper bound "
            f"({evidence.upper_bound_168h:.4g} [{evidence.unit}]) "
            f"crosses spec_max={evidence.synthetic_spec_max:.4g}. "
            f"{'Also population anomalous.' if evidence.is_population_anomaly else ''}"
        )

    # ------------------------------------------------------------------
    # AXIS 4: Population anomaly (from Module A)
    # ------------------------------------------------------------------
    low_thr = float(pa_cfg.get("low_threshold", 3.5))
    high_thr = float(pa_cfg.get("high_threshold", 6.0))

    if evidence.is_population_anomaly:
        pop_score = evidence.population_anomaly_score
        if pop_score >= high_thr:
            level = _parse_level(esc_cfg.get("strong_population_anomaly_level", RISK_MEDIUM))
            current_risk = _max_risk(current_risk, level)
            reasons.append(
                f"[{level}] {evidence.parameter_name} population anomaly score "
                f"{pop_score:.3f} >= strong threshold {high_thr:.1f}."
            )
        else:
            level = _parse_level(esc_cfg.get("moderate_population_anomaly_level", RISK_MEDIUM))
            current_risk = _max_risk(current_risk, level)
            reasons.append(
                f"[{level}] {evidence.parameter_name} population anomaly score "
                f"{pop_score:.3f} >= anomaly threshold {low_thr:.1f} (moderate)."
            )

    # ------------------------------------------------------------------
    # AXIS 5: Predicted future drift — PRIMARY: fraction of spec range
    #
    # Formula:  drift_frac = abs(predicted_168h - value_0h) / spec_range
    #
    # This is scale-invariant across all parameters.  It expresses how much
    # of the allowable spec window the predicted drift consumes.
    # Thresholds are derived from the observed distribution across all three
    # parameters on the synthetic dataset (see calibration note in YAML).
    #
    # SUPPLEMENTARY: early trajectory ratio (predicted_drift / delta_24_0)
    # is only applied when |delta_24_0| >= min_delta_fraction_of_spec * spec_range
    # (ensuring the denominator is physically meaningful, not numerical noise).
    # The supplementary ratio can raise risk by at most one level (MEDIUM).
    # ------------------------------------------------------------------
    predicted_drift = evidence.predicted_drift_from_0h
    abs_early_delta = abs(evidence.observed_early_delta)
    drift_signal = RISK_LOW
    drift_reason = ""

    spec_range = None
    if (
        evidence.synthetic_spec_max is not None
        and evidence.synthetic_spec_min is not None
    ):
        spec_range = evidence.synthetic_spec_max - evidence.synthetic_spec_min

    if spec_range is not None and spec_range > 0:
        drift_frac = abs(predicted_drift) / spec_range

        frac_high = float(dr_cfg.get("drift_frac_spec_high", 0.60))
        frac_med  = float(dr_cfg.get("drift_frac_spec_medium", 0.20))

        if drift_frac >= frac_high:
            drift_signal = _parse_level(esc_cfg.get("high_drift_level", RISK_HIGH))
            drift_reason = (
                f"[{drift_signal}] {evidence.parameter_name} predicted drift "
                f"from 0h to 168h is {predicted_drift:.4g} [{evidence.unit}] "
                f"({drift_frac*100:.1f}% of spec range), "
                f"exceeding high-drift threshold of {frac_high*100:.0f}% of spec range."
            )
        elif drift_frac >= frac_med:
            drift_signal = _parse_level(esc_cfg.get("moderate_drift_level", RISK_MEDIUM))
            drift_reason = (
                f"[{drift_signal}] {evidence.parameter_name} predicted drift "
                f"from 0h to 168h is {predicted_drift:.4g} [{evidence.unit}] "
                f"({drift_frac*100:.1f}% of spec range), "
                f"exceeding moderate-drift threshold of {frac_med*100:.0f}% of spec range."
            )

        # Supplementary early trajectory check (only when delta is physically meaningful)
        min_delta_frac = float(dr_cfg.get("min_delta_fraction_of_spec", 0.02))
        delta_frac_of_spec = abs_early_delta / spec_range
        if delta_frac_of_spec >= min_delta_frac and drift_signal == RISK_LOW:
            drift_ratio = abs(predicted_drift) / abs_early_delta
            ratio_supp = float(dr_cfg.get("supplementary_trajectory_ratio", 5.0))
            if drift_ratio >= ratio_supp:
                # Supplementary signal: raise at most to MEDIUM
                drift_signal = RISK_MEDIUM
                drift_reason = (
                    f"[MEDIUM] {evidence.parameter_name} early trajectory ratio: "
                    f"predicted 168h drift ({predicted_drift:.4g} [{evidence.unit}]) "
                    f"is {drift_ratio:.1f}x the observed early delta "
                    f"({abs_early_delta:.4g} [{evidence.unit}], "
                    f"{delta_frac_of_spec*100:.1f}% of spec range). "
                    f"(Supplementary signal — primary drift fraction {drift_frac*100:.1f}% of spec range is below MEDIUM threshold.)"
                )

    else:
        # No spec range available: fall back to fraction of predicted value
        if evidence.predicted_168h != 0:
            drift_frac_pred = abs(predicted_drift) / abs(evidence.predicted_168h)
            frac_high_pred = float(dr_cfg.get("drift_frac_predicted_high", 0.50))
            frac_med_pred  = float(dr_cfg.get("drift_frac_predicted_medium", 0.20))
            if drift_frac_pred >= frac_high_pred:
                drift_signal = RISK_HIGH
                drift_reason = (
                    f"[HIGH] {evidence.parameter_name} predicted drift "
                    f"is {drift_frac_pred*100:.1f}% of predicted value (no spec range available)."
                )
            elif drift_frac_pred >= frac_med_pred:
                drift_signal = RISK_MEDIUM
                drift_reason = (
                    f"[MEDIUM] {evidence.parameter_name} predicted drift "
                    f"is {drift_frac_pred*100:.1f}% of predicted value (no spec range available)."
                )

    if drift_signal != RISK_LOW and drift_reason:
        current_risk = _max_risk(current_risk, drift_signal)
        reasons.append(drift_reason)

    # ------------------------------------------------------------------
    # AXIS 6: High prediction uncertainty (fraction of spec range)
    # ------------------------------------------------------------------
    un_width = evidence.uncertainty_width
    uncertainty_is_high = False

    if spec_range is not None and spec_range > 0:
        un_frac = un_width / spec_range
        un_thr = float(un_cfg.get("interval_fraction_of_spec_range_high", 0.30))
        if un_frac >= un_thr:
            uncertainty_is_high = True
    elif evidence.predicted_168h != 0:
        un_frac_pred = un_width / abs(evidence.predicted_168h)
        un_thr_pred = float(un_cfg.get("interval_fraction_of_predicted_high", 0.50))
        if un_frac_pred >= un_thr_pred:
            uncertainty_is_high = True

    if uncertainty_is_high:
        level = _parse_level(esc_cfg.get("high_uncertainty_alone_level", RISK_MEDIUM))
        current_risk = _max_risk(current_risk, level)
        reasons.append(
            f"[{level}] Module B 168h prediction interval width "
            f"({un_width:.4g} [{evidence.unit}]) is high relative to spec range, "
            f"indicating insufficient prediction confidence."
        )

    # ------------------------------------------------------------------
    # AXIS 7: Combined conditions (escalations for co-occurring signals)
    # ------------------------------------------------------------------
    if evidence.is_population_anomaly and drift_signal in (RISK_MEDIUM, RISK_HIGH):
        level = _parse_level(esc_cfg.get("anomaly_plus_drift_level", RISK_HIGH))
        if _RISK_RANK[level] > _RISK_RANK[current_risk]:
            current_risk = level
            reasons.append(
                f"[{level}] Combined: population anomaly (score={evidence.population_anomaly_score:.3f}) "
                f"co-occurring with elevated predicted drift — escalated to {level}."
            )

    if evidence.is_population_anomaly and uncertainty_is_high:
        level = _parse_level(esc_cfg.get("anomaly_plus_high_uncertainty_level", RISK_MEDIUM))
        current_risk = _max_risk(current_risk, level)
        # Avoid duplicate reason lines
        if level not in [r.split("]")[0].strip("[") for r in reasons]:
            reasons.append(
                f"[{level}] Combined: population anomaly co-occurring with high prediction "
                f"uncertainty — reduced confidence in normal trajectory."
            )

    # Annotate the evidence object
    evidence.uncertainty_is_high = uncertainty_is_high
    evidence.parameter_risk_level = current_risk
    evidence.parameter_evidence_reasons = reasons

    return current_risk, reasons


def compute_component_risk(
    parameter_risks: Dict[str, Tuple[str, list]],
) -> Tuple[str, list]:
    """
    Compute the overall component risk as the maximum across all parameter risk levels.

    Returns (overall_risk_level, combined_reasons).
    """
    overall = RISK_LOW
    all_reasons = []
    for param_name, (param_level, param_reasons) in parameter_risks.items():
        overall = _max_risk(overall, param_level)
        all_reasons.extend(param_reasons)
    return overall, all_reasons
