"""
src/audit/exporter.py

Phase 7 — Audit Trail Exporter.

Combines AI screening results with recorded human engineering decisions into
exportable formats (pandas DataFrame, CSV file, dicts).

Preserves strict distinction between AI Assessment and Engineer Final Decision.
"""

import os
from typing import List, Optional, Any, TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ..screening.schema import ScreeningResult

from .recorder import AuditRecorder
from .schema import AuditRecord


def audit_record_to_dict(
    lot_id: str,
    component_id: str,
    ai_risk: str,
    ai_recommendation: str,
    ai_reasons: List[str],
    audit_record: Optional[AuditRecord] = None,
    parameter_summaries: Optional[dict] = None,
) -> dict:
    """
    Convert a single component's screening + audit data into a flat dict.
    Clearly distinguishes AI Screening Assessment from Engineer Final Decision.
    """
    has_decision = audit_record is not None

    row = {
        # --- Identifiers ---
        "lot_id": lot_id,
        "component_id": component_id,

        # --- AI Screening Assessment ---
        "ai_overall_risk": ai_risk,
        "ai_recommendation_context": ai_recommendation,
        "ai_reasons_summary": " | ".join(ai_reasons) if ai_reasons else "",

        # --- Engineer Final Decision (Human Review) ---
        "engineer_decision_status": "REVIEWED" if has_decision else "UNREVIEWED",
        "engineer_decision": audit_record.engineer_decision if has_decision else "PENDING",
        "engineer_reason": audit_record.engineer_reason if has_decision else "",
        "decision_timestamp_utc": audit_record.timestamp_utc if has_decision else "",
        "session_id": audit_record.session_id if has_decision else "",
    }

    # Parameter summaries if provided
    if parameter_summaries:
        for p_name, p_data in parameter_summaries.items():
            safe_p = p_name.replace(" ", "_")
            if isinstance(p_data, dict):
                row[f"{safe_p}_0h"] = p_data.get("value_0h")
                row[f"{safe_p}_24h"] = p_data.get("value_24h")
                row[f"{safe_p}_pred_168h"] = p_data.get("predicted_168h")
                row[f"{safe_p}_risk"] = p_data.get("parameter_risk_level")
            else:
                row[f"{safe_p}_pred_168h"] = getattr(p_data, "predicted_168h", None)
                row[f"{safe_p}_risk"] = getattr(p_data, "parameter_risk_level", None)

    return row


class AuditExporter:
    """Exporter for combining ScreeningResult and AuditRecorder data."""

    def __init__(self, recorder: Optional[AuditRecorder] = None):
        self.recorder = recorder

    def export_to_dataframe(
        self,
        screening_result: ScreeningResult,
        recorder: Optional[AuditRecorder] = None,
    ) -> pd.DataFrame:
        """
        Combine screening results and audit records into a flattened pandas DataFrame.

        Parameters
        ----------
        screening_result : ScreeningResult
            Output from ScreeningPipeline.
        recorder : Optional[AuditRecorder]
            Session audit recorder. If None, uses self.recorder.

        Returns
        -------
        pd.DataFrame
            One row per component containing AI assessment + human decision.
        """
        rec = recorder or self.recorder
        rows = []

        for lot_id, lot_res in screening_result.lot_results.items():
            for comp in lot_res.component_results:
                audit_rec = rec.get_record(comp.component_id, lot_id) if rec else None
                param_dict = {
                    p_name: {
                        "value_0h": pr.value_0h,
                        "value_24h": pr.value_24h,
                        "predicted_168h": pr.predicted_168h,
                        "parameter_risk_level": pr.parameter_risk_level,
                    }
                    for p_name, pr in comp.parameters.items()
                }

                row = audit_record_to_dict(
                    lot_id=comp.lot_id,
                    component_id=comp.component_id,
                    ai_risk=comp.overall_risk_level,
                    ai_recommendation=comp.recommendation_context,
                    ai_reasons=comp.risk_reasons,
                    audit_record=audit_rec,
                    parameter_summaries=param_dict,
                )
                rows.append(row)

        return pd.DataFrame(rows)

    def export_to_csv(
        self,
        screening_result: ScreeningResult,
        output_path: str,
        recorder: Optional[AuditRecorder] = None,
    ) -> str:
        """
        Export screening + audit records to a CSV file.

        Returns output_path.
        """
        df = self.export_to_dataframe(screening_result, recorder=recorder)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        df.to_csv(output_path, index=False)
        return output_path
