"""
src/anomaly/detector.py

Module A — Dynamic Population-Relative Anomaly Detector for HOPIUM_sih26170.

Implements Iglewicz & Hoaglin (1993) Robust Modified Z-Score screening per lot and parameter:
    M_i = 0.6745 * (x_i - median(x)) / (MAD(x) + epsilon)

Key Architecture Rules:
    - Operates strictly per-lot and per-parameter.
    - Features used: value_0h, value_24h, delta_24_0 = value_24h - value_0h.
    - Parameter score = max(|M_0h|, |M_24h|, |M_delta|).
    - Component population anomaly score = max(Parameter scores).
    - Anomaly threshold default = 3.5 (conventional robust outlier threshold).
    - Decouples population-relative anomaly from static reference-limit breaches.
    - Input DataFrame is never mutated.
"""

from typing import Dict, List, Optional, Union
import numpy as np
import pandas as pd

from .explainability import generate_human_readable_reasons
from .metrics import compute_modified_zscores, compute_percentiles
from .schema import (
    ComponentAnomalyReport,
    LotAnomalyReport,
    ParameterAnomalyEvidence,
)


class PopulationAnomalyDetector:
    """
    Dynamic Population-Relative Anomaly Detector (Module A).

    Evaluates component burn-in measurements relative to lot population distributions
    to identify out-of-family components independently of static datasheet spec limits.
    """

    def __init__(self, anomaly_threshold: float = 3.5, epsilon: float = 1e-9):
        """
        Args:
            anomaly_threshold: Modified Z-Score threshold for flagging anomalies (default 3.5).
            epsilon: Numerical stabilizer for zero-MAD populations (default 1e-9).
        """
        self.anomaly_threshold = float(anomaly_threshold)
        self.epsilon = float(epsilon)

    def detect_anomalies(
        self,
        df: pd.DataFrame,
        lot_id: Optional[str] = None,
    ) -> Union[LotAnomalyReport, Dict[str, LotAnomalyReport]]:
        """
        Run Module A anomaly detection on a long-format DataFrame.

        Args:
            df: Input long-format DataFrame (must contain lot_id, component_id,
                parameter_name, value_0h, value_24h).
            lot_id: Optional specific lot_id to filter. If None, processes all lots.

        Returns:
            LotAnomalyReport if a single lot is processed, or
            Dict[str, LotAnomalyReport] mapping lot_id -> LotAnomalyReport if multiple lots.
        """
        # Ensure input DataFrame is NOT mutated
        data = df.copy()

        required_cols = {"lot_id", "component_id", "parameter_name", "value_0h", "value_24h"}
        missing = required_cols - set(data.columns)
        if missing:
            raise ValueError(f"Input DataFrame missing required columns: {sorted(missing)}")

        if lot_id is not None:
            data = data[data["lot_id"] == lot_id].copy()
            if data.empty:
                raise ValueError(f"No rows found in DataFrame for lot_id='{lot_id}'")

        # Compute derived early trajectory delta
        data["delta_24_0"] = data["value_24h"] - data["value_0h"]

        # Group processing per lot
        lot_reports: Dict[str, LotAnomalyReport] = {}
        unique_lots = sorted(data["lot_id"].unique().tolist())

        for current_lot in unique_lots:
            lot_df = data[data["lot_id"] == current_lot].copy()
            report = self._process_single_lot(lot_df, current_lot)
            lot_reports[current_lot] = report

        if lot_id is not None or len(unique_lots) == 1:
            return lot_reports[unique_lots[0]]
        return lot_reports

    def _process_single_lot(self, lot_df: pd.DataFrame, lot_id: str) -> LotAnomalyReport:
        """Process all components and parameters within a single lot."""
        parameters = sorted(lot_df["parameter_name"].unique().tolist())
        components = sorted(lot_df["component_id"].unique().tolist())

        # Step 1: Precompute per-parameter robust population statistics and Z-scores
        param_evidence_map: Dict[str, Dict[str, ParameterAnomalyEvidence]] = {
            c: {} for c in components
        }

        for param in parameters:
            p_df = lot_df[lot_df["parameter_name"] == param].copy()
            if p_df.empty:
                continue

            unit = str(p_df["unit"].iloc[0]) if "unit" in p_df.columns else ""

            # Extract raw vectors for this parameter in this lot
            comp_ids = p_df["component_id"].values
            vals_0h = p_df["value_0h"].values
            vals_24h = p_df["value_24h"].values
            vals_delta = p_df["delta_24_0"].values

            # Compute robust modified Z-scores, median, and MAD for 0h, 24h, and delta
            z_0h, med_0h, mad_0h = compute_modified_zscores(vals_0h, epsilon=self.epsilon)
            z_24h, med_24h, mad_24h = compute_modified_zscores(vals_24h, epsilon=self.epsilon)
            z_delta, med_delta, mad_delta = compute_modified_zscores(vals_delta, epsilon=self.epsilon)

            perc_0h = compute_percentiles(vals_0h)
            perc_24h = compute_percentiles(vals_24h)
            perc_delta = compute_percentiles(vals_delta)

            # Optional reference limits
            spec_min_col = p_df["synthetic_spec_min"].values if "synthetic_spec_min" in p_df.columns else None
            spec_max_col = p_df["synthetic_spec_max"].values if "synthetic_spec_max" in p_df.columns else None

            for i, c_id in enumerate(comp_ids):
                v0 = float(vals_0h[i])
                v24 = float(vals_24h[i])
                v_delta = float(vals_delta[i])

                m0 = float(z_0h[i])
                m24 = float(z_24h[i])
                mdelta = float(z_delta[i])
                m_max = float(max(abs(m0), abs(m24), abs(mdelta)))

                s_min = float(spec_min_col[i]) if spec_min_col is not None and not np.isnan(spec_min_col[i]) else None
                s_max = float(spec_max_col[i]) if spec_max_col is not None and not np.isnan(spec_max_col[i]) else None

                is_breach = False
                if s_min is not None and (v0 < s_min or v24 < s_min):
                    is_breach = True
                if s_max is not None and (v0 > s_max or v24 > s_max):
                    is_breach = True

                ev = ParameterAnomalyEvidence(
                    parameter_name=param,
                    unit=unit,
                    observed_0h=v0,
                    observed_24h=v24,
                    observed_delta=v_delta,
                    lot_median_0h=med_0h,
                    lot_mad_0h=mad_0h,
                    lot_median_24h=med_24h,
                    lot_mad_24h=mad_24h,
                    lot_median_delta=med_delta,
                    lot_mad_delta=mad_delta,
                    modified_zscore_0h=m0,
                    modified_zscore_24h=m24,
                    modified_zscore_delta=mdelta,
                    max_modified_zscore=m_max,
                    percentile_0h=float(perc_0h[i]),
                    percentile_24h=float(perc_24h[i]),
                    percentile_delta=float(perc_delta[i]),
                    synthetic_spec_min=s_min,
                    synthetic_spec_max=s_max,
                    is_spec_breach=is_breach,
                )
                param_evidence_map[c_id][param] = ev

        # Step 2: Assemble component-level reports
        component_reports: List[ComponentAnomalyReport] = []
        anomalous_count = 0
        breach_count = 0

        for c_id in components:
            ev_dict = param_evidence_map[c_id]
            if not ev_dict:
                continue

            max_z = max(ev.max_modified_zscore for ev in ev_dict.values())
            is_pop_anomaly = bool(max_z >= self.anomaly_threshold)
            is_ref_breach = any(ev.is_spec_breach for ev in ev_dict.values())

            # Classification state assignment
            if not is_pop_anomaly and not is_ref_breach:
                state = "STATE_A_NORMAL"
            elif is_pop_anomaly and not is_ref_breach:
                state = "STATE_B_POPULATION_ANOMALY_ONLY"
            elif not is_pop_anomaly and is_ref_breach:
                state = "STATE_C_SPEC_BREACH_ONLY"
            else:
                state = "STATE_D_POPULATION_ANOMALY_AND_SPEC_BREACH"

            if is_pop_anomaly:
                anomalous_count += 1
            if is_ref_breach:
                breach_count += 1

            reasons = generate_human_readable_reasons(
                component_id=c_id,
                lot_id=lot_id,
                is_population_anomaly=is_pop_anomaly,
                is_reference_limit_breach=is_ref_breach,
                classification_state=state,
                parameter_evidence=ev_dict,
                anomaly_threshold=self.anomaly_threshold,
            )

            comp_report = ComponentAnomalyReport(
                component_id=c_id,
                lot_id=lot_id,
                is_population_anomaly=is_pop_anomaly,
                is_reference_limit_breach=is_ref_breach,
                population_anomaly_score=max_z,
                classification_state=state,
                parameter_evidence=ev_dict,
                human_readable_reasons=reasons,
            )
            component_reports.append(comp_report)

        return LotAnomalyReport(
            lot_id=lot_id,
            total_components=len(components),
            anomalous_components_count=anomalous_count,
            reference_breach_count=breach_count,
            component_reports=component_reports,
        )

    def to_dataframe(
        self,
        report: Union[LotAnomalyReport, Dict[str, LotAnomalyReport]],
    ) -> pd.DataFrame:
        """
        Convert LotAnomalyReport(s) into a flattened pandas DataFrame for downstream analysis.
        """
        if isinstance(report, LotAnomalyReport):
            reports_list = [report]
        else:
            reports_list = list(report.values())

        rows = []
        for lot_rep in reports_list:
            for comp in lot_rep.component_reports:
                row = {
                    "lot_id": comp.lot_id,
                    "component_id": comp.component_id,
                    "is_population_anomaly": comp.is_population_anomaly,
                    "is_reference_limit_breach": comp.is_reference_limit_breach,
                    "population_anomaly_score": comp.population_anomaly_score,
                    "classification_state": comp.classification_state,
                    "reasons_summary": " | ".join(comp.human_readable_reasons),
                }
                # Add parameter max z-scores
                for p_name, ev in comp.parameter_evidence.items():
                    row[f"{p_name}_max_zscore"] = ev.max_modified_zscore
                    row[f"{p_name}_spec_breach"] = ev.is_spec_breach
                rows.append(row)

        return pd.DataFrame(rows)
