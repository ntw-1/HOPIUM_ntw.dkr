"""
src/screening/pipeline.py

Phase 6 — Screening Pipeline Orchestrator.

This module is a PURE ORCHESTRATOR. It:
    1. Validates the input CSV via the Phase 2 DataTester.
    2. Runs Module A (PopulationAnomalyDetector) per lot.
    3. Runs Module B (ProductionPredictor) per component-parameter.
    4. Runs the Phase 5 DynamicRiskEngine per component.
    5. Assembles a ScreeningResult from those outputs.

It does NOT:
    - Duplicate anomaly calculations.
    - Duplicate model predictions.
    - Duplicate risk calculations.
    - Modify the input DataFrame.

Usage:
    pipeline = ScreeningPipeline()
    result = pipeline.run(csv_path="data/demo_burnin_data.csv")
"""

import os
from typing import Dict, List, Optional, Union

import pandas as pd

from ..anomaly.detector import PopulationAnomalyDetector
from ..anomaly.schema import ComponentAnomalyReport, LotAnomalyReport
from ..data.validation.tester import DataTester
from ..risk.engine import DynamicRiskEngine
from ..risk.schema import ComponentRiskAssessment, RISK_LOW, RISK_MEDIUM, RISK_HIGH
from .schema import (
    ComponentScreeningResult,
    LotScreeningResult,
    ParameterScreeningResult,
    ScreeningResult,
)

_SUPPORTED_PARAMETERS = ("Iddq", "leakage_current", "propagation_delay")


def _build_parameter_result(
    param: str,
    component_row_df: pd.DataFrame,
    component_anomaly_report: ComponentAnomalyReport,
    risk_assessment: ComponentRiskAssessment,
) -> Optional[ParameterScreeningResult]:
    """
    Build a ParameterScreeningResult by reading directly from Module A and Phase 5 outputs.
    Does not recalculate anything.
    """
    param_rows = component_row_df[component_row_df["parameter_name"] == param]
    if param_rows.empty:
        return None

    r = param_rows.iloc[0]

    # Module A evidence for this parameter
    anomaly_ev = component_anomaly_report.parameter_evidence.get(param)
    is_pop_anomaly = (
        anomaly_ev.max_modified_zscore >= 3.5 if anomaly_ev else False
    )
    pop_score = anomaly_ev.max_modified_zscore if anomaly_ev else 0.0
    is_ref_breach = anomaly_ev.is_spec_breach if anomaly_ev else False

    # Phase 5 risk evidence for this parameter
    risk_ev = risk_assessment.parameter_risks.get(param)
    if risk_ev is None:
        return None

    # Spec range for drift fraction
    spec_min = risk_ev.synthetic_spec_min
    spec_max = risk_ev.synthetic_spec_max
    spec_range = (spec_max - spec_min) if (spec_min is not None and spec_max is not None) else None
    drift_frac = (
        abs(risk_ev.predicted_drift_from_0h) / spec_range
        if spec_range and spec_range > 0
        else None
    )

    return ParameterScreeningResult(
        parameter_name=param,
        unit=risk_ev.unit,
        value_0h=risk_ev.value_0h,
        value_24h=risk_ev.value_24h,
        delta_24_0=risk_ev.delta_24_0,
        predicted_168h=risk_ev.predicted_168h,
        lower_bound_168h=risk_ev.lower_bound_168h,
        upper_bound_168h=risk_ev.upper_bound_168h,
        uncertainty_width=risk_ev.uncertainty_width,
        uncertainty_method=risk_ev.uncertainty_method,
        predicted_drift_from_0h=risk_ev.predicted_drift_from_0h,
        drift_frac_spec=drift_frac,
        synthetic_spec_min=spec_min,
        synthetic_spec_max=spec_max,
        is_reference_breach=is_ref_breach,
        is_population_anomaly=is_pop_anomaly,
        population_anomaly_score=pop_score,
        predicted_value_crosses_spec_max=risk_ev.predicted_value_crosses_spec_max,
        predicted_value_crosses_spec_min=risk_ev.predicted_value_crosses_spec_min,
        upper_bound_crosses_spec_max=risk_ev.upper_bound_crosses_spec_max,
        uncertainty_is_high=risk_ev.uncertainty_is_high,
        parameter_risk_level=risk_ev.parameter_risk_level,
        reasons=list(risk_ev.parameter_evidence_reasons),
    )


def _build_component_result(
    component_anomaly_report: ComponentAnomalyReport,
    risk_assessment: ComponentRiskAssessment,
    lot_df: pd.DataFrame,
) -> ComponentScreeningResult:
    """
    Assemble a ComponentScreeningResult from Module A + Phase 5 outputs.
    Reads data; does not recalculate.
    """
    comp_id = component_anomaly_report.component_id
    lot_id = component_anomaly_report.lot_id
    comp_df = lot_df[lot_df["component_id"] == comp_id]

    param_results: Dict[str, ParameterScreeningResult] = {}
    for param in _SUPPORTED_PARAMETERS:
        pr = _build_parameter_result(
            param, comp_df, component_anomaly_report, risk_assessment
        )
        if pr is not None:
            param_results[param] = pr

    return ComponentScreeningResult(
        component_id=comp_id,
        lot_id=lot_id,
        overall_risk_level=risk_assessment.overall_risk_level,
        recommendation_context=risk_assessment.recommendation_context,
        is_population_anomaly=risk_assessment.any_population_anomaly,
        is_reference_breach=risk_assessment.any_reference_breach,
        any_predicted_spec_crossing=risk_assessment.any_predicted_spec_crossing,
        any_high_uncertainty=risk_assessment.any_high_uncertainty,
        any_elevated_drift=risk_assessment.any_elevated_drift,
        parameters=param_results,
        risk_reasons=list(risk_assessment.risk_reasons),
        anomaly_classification_state=component_anomaly_report.classification_state,
        anomaly_score=component_anomaly_report.population_anomaly_score,
    )


class ScreeningPipeline:
    """
    Phase 6 end-to-end screening orchestrator.

    Chains:
        DataTester → PopulationAnomalyDetector → DynamicRiskEngine
        → ScreeningResult

    Parameters
    ----------
    registry_dir : str
        Path to models/registered directory containing Module B artifacts.
    risk_config_path : str
        Path to configs/risk_engine_config.yaml.
    anomaly_threshold : float
        Modified Z-score threshold for Module A (default 3.5).
    """

    def __init__(
        self,
        registry_dir: str = "models/registered",
        risk_config_path: str = "configs/risk_engine_config.yaml",
        anomaly_threshold: float = 3.5,
    ):
        self._registry_dir = registry_dir
        self._risk_config_path = risk_config_path
        self._anomaly_threshold = anomaly_threshold

        # Lazy-loaded heavy objects
        self._anomaly_detector: Optional[PopulationAnomalyDetector] = None
        self._risk_engine: Optional[DynamicRiskEngine] = None
        self._validator = DataTester()

    def _get_anomaly_detector(self) -> PopulationAnomalyDetector:
        if self._anomaly_detector is None:
            self._anomaly_detector = PopulationAnomalyDetector(
                anomaly_threshold=self._anomaly_threshold
            )
        return self._anomaly_detector

    def _get_risk_engine(self) -> DynamicRiskEngine:
        if self._risk_engine is None:
            self._risk_engine = DynamicRiskEngine(
                registry_dir=self._registry_dir,
                config_path=self._risk_config_path,
            )
        return self._risk_engine

    @property
    def risk_engine(self) -> DynamicRiskEngine:
        """Accessor for the underlying DynamicRiskEngine."""
        return self._get_risk_engine()

    def reload_predictors(self) -> None:
        """Reload predictors in underlying risk engine to reflect newly deployed models."""
        self._get_risk_engine().reload_predictors()

    # ------------------------------------------------------------------

    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        csv_path: Optional[str] = None,
        df: Optional[pd.DataFrame] = None,
    ) -> ScreeningResult:
        """
        Run the full screening pipeline on a CSV file or pre-loaded DataFrame.

        If csv_path is given, also runs Phase 2 validation.
        If only df is given, skips file-based validation.
        Input DataFrame is never mutated.

        Returns ScreeningResult regardless of success or failure.
        """
        # --- Validate ---
        validation_status = "SKIPPED"
        hard_fails = 0
        warnings = 0
        val_messages: List[str] = []

        if csv_path is not None:
            try:
                val_result = self._validator.validate_paths(csv_path)
                validation_status = val_result.overall_status
                hard_fails = val_result.hard_failures_count
                warnings = val_result.warnings_count
                val_messages = [
                    f"[{f['level']}] {f['message']}" for f in val_result.findings
                    if f["level"] in ("HARD FAILURE", "WARNING")
                ]
            except Exception as exc:
                # Validator crashed (e.g. missing expected columns) — treat as hard failure
                validation_status = "FAIL"
                hard_fails = 1
                warnings = 0
                val_messages = [f"[HARD FAILURE] Validator raised exception: {exc}"]

            if validation_status == "FAIL":
                return ScreeningResult(
                    csv_path=csv_path,
                    total_lots=0,
                    total_components=0,
                    validation_status=validation_status,
                    validation_hard_failures=hard_fails,
                    validation_warnings=warnings,
                    validation_messages=val_messages,
                    aborted=True,
                    abort_reason=(
                        f"Validation produced {hard_fails} hard failure(s). "
                        "Screening aborted to protect result integrity."
                    ),
                )

            if df is None:
                df = pd.read_csv(csv_path)
        else:
            if df is None:
                raise ValueError("Either csv_path or df must be provided.")

        # Work on a copy — never mutate the caller's DataFrame
        data = df.copy()

        # --- Run screening ---
        return self._run_screening(
            data=data,
            csv_path=csv_path,
            validation_status=validation_status,
            hard_fails=hard_fails,
            warnings=warnings,
            val_messages=val_messages,
        )

    def _run_screening(
        self,
        data: pd.DataFrame,
        csv_path: Optional[str],
        validation_status: str,
        hard_fails: int,
        warnings: int,
        val_messages: List[str],
    ) -> ScreeningResult:
        """Inner method that executes Module A → Module B → Risk Engine per lot."""
        anomaly_detector = self._get_anomaly_detector()
        risk_engine = self._get_risk_engine()

        lots = sorted(data["lot_id"].unique().tolist())
        lot_results: Dict[str, LotScreeningResult] = {}

        total_low = total_med = total_high = 0

        for lot_id in lots:
            lot_df = data[data["lot_id"] == lot_id]

            # --- Module A ---
            lot_anomaly_report: LotAnomalyReport = anomaly_detector.detect_anomalies(
                lot_df, lot_id=lot_id
            )

            # --- Phase 5 Risk Engine (also runs Module B internally) ---
            risk_assessments: List[ComponentRiskAssessment] = risk_engine.assess_lot(
                lot_anomaly_report, lot_df
            )

            # Build a lookup from component_id → ComponentRiskAssessment
            risk_by_comp: Dict[str, ComponentRiskAssessment] = {
                a.component_id: a for a in risk_assessments
            }

            # --- Assemble component results ---
            component_results: List[ComponentScreeningResult] = []
            low_n = med_n = high_n = 0

            for comp_report in lot_anomaly_report.component_reports:
                comp_id = comp_report.component_id
                risk_assessment = risk_by_comp.get(comp_id)
                if risk_assessment is None:
                    continue

                comp_result = _build_component_result(
                    comp_report, risk_assessment, lot_df
                )
                component_results.append(comp_result)

                lvl = comp_result.overall_risk_level
                if lvl == RISK_LOW:
                    low_n += 1
                elif lvl == RISK_MEDIUM:
                    med_n += 1
                elif lvl == RISK_HIGH:
                    high_n += 1

            total_low += low_n
            total_med += med_n
            total_high += high_n

            lot_results[lot_id] = LotScreeningResult(
                lot_id=lot_id,
                total_components=lot_anomaly_report.total_components,
                validation_status=validation_status,
                validation_hard_failures=hard_fails,
                validation_warnings=warnings,
                risk_low_count=low_n,
                risk_medium_count=med_n,
                risk_high_count=high_n,
                population_anomaly_count=lot_anomaly_report.anomalous_components_count,
                reference_breach_count=lot_anomaly_report.reference_breach_count,
                component_results=component_results,
            )

        total_components = sum(lr.total_components for lr in lot_results.values())

        return ScreeningResult(
            csv_path=csv_path,
            total_lots=len(lots),
            total_components=total_components,
            validation_status=validation_status,
            validation_hard_failures=hard_fails,
            validation_warnings=warnings,
            validation_messages=val_messages,
            risk_low_count=total_low,
            risk_medium_count=total_med,
            risk_high_count=total_high,
            lot_results=lot_results,
        )
