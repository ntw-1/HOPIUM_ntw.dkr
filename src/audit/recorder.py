"""
src/audit/recorder.py

Phase 7 — Audit Trail Recorder.

Provides in-memory session audit trail management. Validates that human decisions
have mandatory non-empty justification notes, and records engineering signoffs
paired with AI screening context.
"""

from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..screening.schema import ComponentScreeningResult
from .schema import (
    ALLOWED_DECISIONS,
    DECISION_MONITOR,
    DECISION_PASS,
    DECISION_REJECT,
    AuditRecord,
    AuditTrailSummary,
)


class AuditRecorder:
    """
    Session-level audit trail manager.
    Enforces mandatory human reasoning and stores immutable decision records.
    """

    def __init__(self, session_id: str = "default_session"):
        self.session_id = session_id
        # Key: (lot_id, component_id) -> AuditRecord
        self._records: Dict[tuple, AuditRecord] = {}

    def record_decision(
        self,
        component_id: str,
        lot_id: str,
        engineer_decision: str,
        engineer_reason: str,
        ai_overall_risk: str,
        ai_recommendation_context: str,
        ai_reasons: Optional[List[str]] = None,
        parameter_snapshots: Optional[Dict[str, dict]] = None,
    ) -> AuditRecord:
        """
        Record a human engineering decision for a component.

        Validation rules:
            - engineer_decision must be one of ['PASS', 'MONITOR', 'REJECT'].
            - engineer_reason must be a non-empty, non-whitespace string.

        Raises:
            ValueError if decision is unrecognised or reason is empty/whitespace.
        """
        if not component_id or not str(component_id).strip():
            raise ValueError("component_id cannot be empty.")
        if not lot_id or not str(lot_id).strip():
            raise ValueError("lot_id cannot be empty.")

        norm_decision = str(engineer_decision).upper().strip()
        if norm_decision not in ALLOWED_DECISIONS:
            raise ValueError(
                f"Invalid engineer decision '{engineer_decision}'. "
                f"Allowed values are: {', '.join(ALLOWED_DECISIONS)}"
            )

        if engineer_reason is None or not str(engineer_reason).strip():
            raise ValueError(
                "Human decision reason is mandatory and cannot be empty or whitespace-only."
            )

        record = AuditRecord(
            component_id=component_id,
            lot_id=lot_id,
            engineer_decision=norm_decision,
            engineer_reason=str(engineer_reason).strip(),
            ai_overall_risk=ai_overall_risk,
            ai_recommendation_context=ai_recommendation_context,
            ai_reasons=list(ai_reasons or []),
            session_id=self.session_id,
            parameter_snapshots=parameter_snapshots or {},
        )

        key = (lot_id, component_id)
        self._records[key] = record
        return record

    def record_from_screening_component(
        self,
        component_result: ComponentScreeningResult,
        engineer_decision: str,
        engineer_reason: str,
    ) -> AuditRecord:
        """Convenience method to record a decision directly from a ComponentScreeningResult object."""
        param_snapshots = {}
        for p_name, pr in component_result.parameters.items():
            param_snapshots[p_name] = {
                "unit": pr.unit,
                "value_0h": pr.value_0h,
                "value_24h": pr.value_24h,
                "predicted_168h": pr.predicted_168h,
                "lower_bound_168h": pr.lower_bound_168h,
                "upper_bound_168h": pr.upper_bound_168h,
                "parameter_risk_level": pr.parameter_risk_level,
            }

        return self.record_decision(
            component_id=component_result.component_id,
            lot_id=component_result.lot_id,
            engineer_decision=engineer_decision,
            engineer_reason=engineer_reason,
            ai_overall_risk=component_result.overall_risk_level,
            ai_recommendation_context=component_result.recommendation_context,
            ai_reasons=component_result.risk_reasons,
            parameter_snapshots=param_snapshots,
        )

    def get_record(self, component_id: str, lot_id: str) -> Optional[AuditRecord]:
        """Retrieve an audit record by (lot_id, component_id)."""
        return self._records.get((lot_id, component_id))

    def list_records(self, lot_id: Optional[str] = None) -> List[AuditRecord]:
        """List all recorded audit decisions (optionally filtered by lot_id)."""
        if lot_id is None:
            return list(self._records.values())
        return [rec for (lid, _), rec in self._records.items() if lid == lot_id]

    def get_summary(self) -> AuditTrailSummary:
        """Return summary statistics for recorded human decisions."""
        records = list(self._records.values())
        total = len(records)
        n_pass = sum(1 for r in records if r.engineer_decision == DECISION_PASS)
        n_mon = sum(1 for r in records if r.engineer_decision == DECISION_MONITOR)
        n_rej = sum(1 for r in records if r.engineer_decision == DECISION_REJECT)

        by_lot: Dict[str, dict] = {}
        for r in records:
            if r.lot_id not in by_lot:
                by_lot[r.lot_id] = {"total": 0, "PASS": 0, "MONITOR": 0, "REJECT": 0}
            by_lot[r.lot_id]["total"] += 1
            by_lot[r.lot_id][r.engineer_decision] += 1

        return AuditTrailSummary(
            total_decisions=total,
            pass_count=n_pass,
            monitor_count=n_mon,
            reject_count=n_rej,
            decisions_by_lot=by_lot,
        )

    def clear(self):
        """Clear all session audit records."""
        self._records.clear()
