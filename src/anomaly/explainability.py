"""
src/anomaly/explainability.py

Human-readable diagnostic reason generator for Module A anomaly outputs.

Generates clear, interpretable audit logs and engineering summaries explaining why
a component was flagged as a population-relative anomaly or a reference limit breach.

Preserves key distinctions:
    - State A: Normal & within reference limits
    - State B: Population anomaly & within reference limits (out-of-family)
    - State C: Reference limit breach & population normal
    - State D: Population anomaly & reference limit breach
"""

from typing import List
from .schema import ParameterAnomalyEvidence


def generate_human_readable_reasons(
    component_id: str,
    lot_id: str,
    is_population_anomaly: bool,
    is_reference_limit_breach: bool,
    classification_state: str,
    parameter_evidence: dict,
    anomaly_threshold: float = 3.5,
) -> List[str]:
    """
    Generate natural language audit reasons for a component anomaly report.

    Args:
        component_id:               Component identifier.
        lot_id:                     Lot identifier.
        is_population_anomaly:      Boolean flag.
        is_reference_limit_breach:  Boolean flag.
        classification_state:       State string (STATE_A, STATE_B, STATE_C, STATE_D).
        parameter_evidence:         Dict mapping param_name -> ParameterAnomalyEvidence.
        anomaly_threshold:          Modified Z-Score threshold (default 3.5).

    Returns:
        List of human-readable explanation strings.
    """
    reasons: List[str] = []

    if classification_state == "STATE_A_NORMAL":
        reasons.append(
            f"Component {component_id} is nominal within lot {lot_id}. "
            f"All parameters are within normal population variation and reference limits."
        )
        return reasons

    # Parameter-level breakdown
    for param_name, ev in parameter_evidence.items():
        if isinstance(ev, dict):
            # Convert dict to attributes if needed
            p_name = ev.get("parameter_name", param_name)
            unit = ev.get("unit", "")
            obs_24h = ev.get("observed_24h", 0.0)
            obs_0h = ev.get("observed_0h", 0.0)
            delta = ev.get("observed_delta", 0.0)
            med_24h = ev.get("lot_median_24h", 0.0)
            mad_24h = ev.get("lot_mad_24h", 0.0)
            z_24h = ev.get("modified_zscore_24h", 0.0)
            z_delta = ev.get("modified_zscore_delta", 0.0)
            z_max = ev.get("max_modified_zscore", 0.0)
            spec_min = ev.get("synthetic_spec_min")
            spec_max = ev.get("synthetic_spec_max")
            is_breach = ev.get("is_spec_breach", False)
            perc_24h = ev.get("percentile_24h", 50.0)
        else:
            p_name = ev.parameter_name
            unit = ev.unit
            obs_24h = ev.observed_24h
            obs_0h = ev.observed_0h
            delta = ev.observed_delta
            med_24h = ev.lot_median_24h
            mad_24h = ev.lot_mad_24h
            z_24h = ev.modified_zscore_24h
            z_delta = ev.modified_zscore_delta
            z_max = ev.max_modified_zscore
            spec_min = ev.synthetic_spec_min
            spec_max = ev.synthetic_spec_max
            is_breach = ev.is_spec_breach
            perc_24h = ev.percentile_24h

        # Population anomaly evidence for this parameter
        if z_max >= anomaly_threshold:
            if abs(z_24h) >= anomaly_threshold:
                reasons.append(
                    f"[{p_name}] Population Anomaly: 24h reading ({obs_24h:.2f} {unit}) is "
                    f"{abs(z_24h):.2f} robust std dev from lot median ({med_24h:.2f} {unit}, "
                    f"percentile: {perc_24h:.1f}%). Modified Z-Score exceeds threshold ({anomaly_threshold})."
                )
            elif abs(z_delta) >= anomaly_threshold:
                reasons.append(
                    f"[{p_name}] Early Trajectory Anomaly: 0h->24h drift velocity Delta ({delta:+.2f} {unit}) "
                    f"exhibits an abnormal Modified Z-Score of {abs(z_delta):.2f} relative to lot population."
                )
            else:
                reasons.append(
                    f"[{p_name}] Population Anomaly: 0h measurement ({obs_0h:.2f} {unit}) exhibits "
                    f"an abnormal Modified Z-Score of {z_max:.2f} relative to lot baseline."
                )

        # Reference limit breach evidence for this parameter
        if is_breach:
            spec_str = []
            if spec_min is not None and obs_24h < spec_min:
                spec_str.append(f"below synthetic_spec_min ({spec_min} {unit})")
            if spec_max is not None and obs_24h > spec_max:
                spec_str.append(f"above synthetic_spec_max ({spec_max} {unit})")
            if spec_min is not None and obs_0h < spec_min:
                spec_str.append(f"0h below synthetic_spec_min ({spec_min} {unit})")
            if spec_max is not None and obs_0h > spec_max:
                spec_str.append(f"0h above synthetic_spec_max ({spec_max} {unit})")

            reasons.append(
                f"[{p_name}] Synthetic Reference Limit Breach: Component measurement is "
                f"{', '.join(spec_str)}."
            )

    # State summary phrase
    if classification_state == "STATE_B_POPULATION_ANOMALY_ONLY":
        reasons.insert(
            0,
            f"Component {component_id} is a POPULATION ANOMALY (Out-of-Family) while remaining "
            f"within synthetic reference limits."
        )
    elif classification_state == "STATE_C_SPEC_BREACH_ONLY":
        reasons.insert(
            0,
            f"Component {component_id} breaches synthetic reference limits but is population-normal."
        )
    elif classification_state == "STATE_D_POPULATION_ANOMALY_AND_SPEC_BREACH":
        reasons.insert(
            0,
            f"Component {component_id} is BOTH a population anomaly AND a synthetic reference limit breach."
        )

    return reasons
