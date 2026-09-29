"""
src/risk/engine.py

Phase 5 — Dynamic Risk Engine.

Orchestrates the combination of:
    - Module A ComponentAnomalyReport (per-component population anomaly evidence)
    - Module B ProductionPredictor predictions (per-parameter 168h drift predictions)
    - Raw component measurements (value_0h, value_24h per parameter)
    - Reference spec limits from the data (synthetic_spec_min, synthetic_spec_max)

into a ComponentRiskAssessment with:
    - Overall component risk level (LOW / MEDIUM / HIGH)
    - Per-parameter evidence breakdown
    - Human-readable reason list
    - Deterministic recommendation context for Phase 6

IMPORTANT DISCLAIMER:
    All risk levels are ADVISORY outputs for human engineering review.
    This engine does NOT make a PASS/REJECT decision — that is Phase 7 HITL.
    Derived AI risk levels must NEVER replace official engineering specifications.

Usage:
    engine = DynamicRiskEngine(registry_dir="models/registered",
                               config_path="configs/risk_engine_config.yaml")
    assessment = engine.assess_component(
        component_anomaly_report=report,
        row_df=component_df_row,
    )
"""

import os
from typing import Dict, List, Optional, Union

import pandas as pd
import yaml

from ..anomaly.schema import ComponentAnomalyReport
from ..model_lab.predictor import ProductionPredictor
from .rules import compute_component_risk, evaluate_parameter_risk
from .schema import (
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    ComponentRiskAssessment,
    ParameterRiskEvidence,
)


def _load_config(config_path: str) -> dict:
    """Load risk engine YAML config."""
    with open(config_path, "r") as fh:
        root = yaml.safe_load(fh)
    return root.get("risk_engine_config", root)


def _build_recommendation_context(
    overall_risk: str,
    any_reference_breach: bool,
    any_predicted_spec_crossing: bool,
    any_high_uncertainty: bool,
    any_population_anomaly: bool,
    any_elevated_drift: bool,
) -> str:
    """
    Produce a deterministic recommendation context string for Phase 6 consumption.
    NOT a PASS/REJECT decision — advisory text only.
    """
    if overall_risk == RISK_HIGH:
        if any_reference_breach:
            return (
                "HIGH RISK — observed measurement currently breaches reference limits. "
                "Immediate engineering review required."
            )
        if any_predicted_spec_crossing:
            return (
                "HIGH RISK — Module B predicts parameter(s) will cross specification "
                "boundary by 168h. Elevated engineering attention required."
            )
        if any_population_anomaly and any_elevated_drift:
            return (
                "HIGH RISK — component is simultaneously a population outlier and on an "
                "elevated predicted drift trajectory. Engineering review recommended."
            )
        return (
            "HIGH RISK — one or more strong evidence signals present. "
            "Engineering review recommended."
        )
    elif overall_risk == RISK_MEDIUM:
        reasons = []
        if any_population_anomaly:
            reasons.append("population outlier")
        if any_high_uncertainty:
            reasons.append("high prediction uncertainty")
        if any_elevated_drift:
            reasons.append("elevated predicted drift")
        body = ", ".join(reasons) if reasons else "moderate evidence signals"
        return f"MEDIUM RISK — {body} present. Engineering review recommended."
    else:
        return "LOW RISK — all evidence signals nominal. No immediate engineering concern."


class DynamicRiskEngine:
    """
    Combines Module A anomaly evidence and Module B drift predictions into a
    ComponentRiskAssessment for each component.

    Loads a ProductionPredictor per parameter from the model registry.
    Applies configurable evidence rules from risk_engine_config.yaml.

    PROTOTYPE NOTE: This engine provides AI-generated risk evidence to support
    engineering review. It is not a decision maker and must not replace human judgment.
    """

    SUPPORTED_PARAMETERS = ("Iddq", "leakage_current", "propagation_delay")

    def __init__(
        self,
        registry_dir: str = "models/registered",
        config_path: str = "configs/risk_engine_config.yaml",
    ):
        """
        Args:
            registry_dir: Path to models/registered directory.
            config_path:  Path to risk_engine_config.yaml.
        """
        self.config_path = config_path
        self.registry_dir = registry_dir
        self.cfg = _load_config(config_path)

        # Load one predictor per supported parameter
        self._predictors: Dict[str, ProductionPredictor] = {}
        self.reload_predictors()

    def reload_predictors(self) -> None:
        """Reload production predictors from registry to reflect active model updates."""
        for param in self.SUPPORTED_PARAMETERS:
            self._predictors[param] = ProductionPredictor.from_registry(self.registry_dir, param)

    def assess_component(
        self,
        component_anomaly_report: ComponentAnomalyReport,
        row_df: pd.DataFrame,
    ) -> ComponentRiskAssessment:
        """
        Produce a full ComponentRiskAssessment for one component.

        Args:
            component_anomaly_report:
                ComponentAnomalyReport from Module A for this component.
            row_df:
                DataFrame slice containing ALL measurement rows for this component
                (one row per parameter). Must include columns:
                    lot_id, component_id, parameter_name, unit,
                    value_0h, value_24h,
                    synthetic_spec_min, synthetic_spec_max.
                value_96h and value_168h may be present but will NOT be used.

        Returns:
            ComponentRiskAssessment
        """
        component_id = component_anomaly_report.component_id
        lot_id = component_anomaly_report.lot_id

        param_evidence_map: Dict[str, ParameterRiskEvidence] = {}
        param_risk_map: Dict[str, tuple] = {}

        any_population_anomaly = False
        any_reference_breach = False
        any_predicted_spec_crossing = False
        any_high_uncertainty = False
        any_elevated_drift = False

        for param in self.SUPPORTED_PARAMETERS:
            param_rows = row_df[row_df["parameter_name"] == param]
            if param_rows.empty:
                continue

            r = param_rows.iloc[0]
            value_0h = float(r["value_0h"])
            value_24h = float(r["value_24h"])
            delta_24_0 = value_24h - value_0h
            unit = str(r.get("unit", ""))
            spec_min = float(r["synthetic_spec_min"]) if pd.notna(r.get("synthetic_spec_min")) else None
            spec_max = float(r["synthetic_spec_max"]) if pd.notna(r.get("synthetic_spec_max")) else None

            # Retrieve Module A per-parameter evidence (if available)
            param_anomaly_ev = component_anomaly_report.parameter_evidence.get(param)
            # ParameterAnomalyEvidence has no "is_population_anomaly" field directly.
            # Use the component-level is_population_anomaly and per-parameter max_modified_zscore.
            is_population_anomaly = (
                component_anomaly_report.is_population_anomaly
                if param_anomaly_ev is None
                else (param_anomaly_ev.max_modified_zscore >= 3.5)
            )
            is_ref_breach = (
                param_anomaly_ev.is_spec_breach if param_anomaly_ev else False
            )
            pop_score = (
                param_anomaly_ev.max_modified_zscore if param_anomaly_ev else 0.0
            )
            classification_state = component_anomaly_report.classification_state

            # Module B prediction — strictly uses value_0h, value_24h only
            predictor = self._predictors[param]
            pred_result = predictor.predict_single(value_0h=value_0h, value_24h=value_24h)
            predicted_168h = pred_result["prediction"]
            lower_bound = pred_result["lower_bound"]
            upper_bound = pred_result["upper_bound"]
            uncertainty_method = pred_result["uncertainty_method"]
            uncertainty_width = upper_bound - lower_bound

            # Derived drift
            predicted_drift_from_0h = predicted_168h - value_0h
            predicted_drift_from_24h = predicted_168h - value_24h

            # Boundary crossing analysis
            predicted_crosses_max = (spec_max is not None) and (predicted_168h > spec_max)
            predicted_crosses_min = (spec_min is not None) and (predicted_168h < spec_min)
            upper_crosses_max = (spec_max is not None) and (upper_bound > spec_max)

            evidence = ParameterRiskEvidence(
                parameter_name=param,
                unit=unit,
                population_anomaly_score=pop_score,
                is_population_anomaly=is_population_anomaly,
                population_anomaly_classification=classification_state,
                is_reference_limit_breach=is_ref_breach,
                value_0h=value_0h,
                value_24h=value_24h,
                delta_24_0=delta_24_0,
                predicted_168h=predicted_168h,
                lower_bound_168h=lower_bound,
                upper_bound_168h=upper_bound,
                uncertainty_width=uncertainty_width,
                uncertainty_method=uncertainty_method,
                predicted_drift_from_0h=predicted_drift_from_0h,
                predicted_drift_from_24h=predicted_drift_from_24h,
                observed_early_delta=delta_24_0,
                synthetic_spec_min=spec_min,
                synthetic_spec_max=spec_max,
                predicted_value_crosses_spec_max=predicted_crosses_max,
                predicted_value_crosses_spec_min=predicted_crosses_min,
                upper_bound_crosses_spec_max=upper_crosses_max,
            )

            param_risk_level, param_reasons = evaluate_parameter_risk(evidence, self.cfg)

            param_evidence_map[param] = evidence
            param_risk_map[param] = (param_risk_level, param_reasons)

            # Update component-level summary flags
            any_population_anomaly = any_population_anomaly or is_population_anomaly
            any_reference_breach = any_reference_breach or is_ref_breach
            any_predicted_spec_crossing = (
                any_predicted_spec_crossing or predicted_crosses_max or predicted_crosses_min
            )
            any_high_uncertainty = any_high_uncertainty or evidence.uncertainty_is_high
            any_elevated_drift = any_elevated_drift or (
                evidence.parameter_risk_level in (RISK_MEDIUM, RISK_HIGH)
                and not is_population_anomaly
                and not is_ref_breach
                and not predicted_crosses_max
                and not predicted_crosses_min
                and not upper_crosses_max
                and not evidence.uncertainty_is_high
            )

        # Compute overall component risk
        overall_risk, all_reasons = compute_component_risk(param_risk_map)

        recommendation_context = _build_recommendation_context(
            overall_risk=overall_risk,
            any_reference_breach=any_reference_breach,
            any_predicted_spec_crossing=any_predicted_spec_crossing,
            any_high_uncertainty=any_high_uncertainty,
            any_population_anomaly=any_population_anomaly,
            any_elevated_drift=any_elevated_drift,
        )

        return ComponentRiskAssessment(
            component_id=component_id,
            lot_id=lot_id,
            overall_risk_level=overall_risk,
            any_population_anomaly=any_population_anomaly,
            any_reference_breach=any_reference_breach,
            any_predicted_spec_crossing=any_predicted_spec_crossing,
            any_high_uncertainty=any_high_uncertainty,
            any_elevated_drift=any_elevated_drift,
            parameter_risks=param_evidence_map,
            recommendation_context=recommendation_context,
            risk_reasons=all_reasons,
        )

    def assess_lot(
        self,
        lot_anomaly_report,
        lot_df: pd.DataFrame,
    ) -> List[ComponentRiskAssessment]:
        """
        Produce ComponentRiskAssessment for every component in a lot.

        Args:
            lot_anomaly_report: LotAnomalyReport from Module A.
            lot_df:             Full DataFrame of measurement rows for this lot.

        Returns:
            List of ComponentRiskAssessment, one per component.
        """
        assessments = []
        for comp_report in lot_anomaly_report.component_reports:
            comp_id = comp_report.component_id
            comp_df = lot_df[lot_df["component_id"] == comp_id]
            if comp_df.empty:
                continue
            assessment = self.assess_component(comp_report, comp_df)
            assessments.append(assessment)
        return assessments
