"""
src/screening/service.py

Phase 6 & 7 — Screening & Audit Service Layer.

Provides high-level application service methods for UI / API / CLI clients
to interact with the screening platform and session audit trail.

Decouples UI execution from lower-level pipeline orchestration and audit recording.
"""

import os
from typing import Dict, List, Optional

from ..audit.exporter import AuditExporter
from ..audit.recorder import AuditRecorder
from ..audit.schema import AuditRecord, AuditTrailSummary
from .pipeline import ScreeningPipeline
from .schema import ComponentScreeningResult, LotScreeningResult, ScreeningResult


class ScreeningService:
    """
    Application service for running screening, listing available datasets,
    recording human engineering decisions (Phase 7 HITL), and exporting audit logs.
    """

    def __init__(
        self,
        registry_dir: str = "models/registered",
        risk_config_path: str = "configs/risk_engine_config.yaml",
        data_dir: str = "data",
        session_id: str = "session_sih26170",
    ):
        self.data_dir = data_dir
        self.pipeline = ScreeningPipeline(
            registry_dir=registry_dir,
            risk_config_path=risk_config_path,
        )
        self.audit_recorder = AuditRecorder(session_id=session_id)
        self.audit_exporter = AuditExporter(recorder=self.audit_recorder)

    def list_available_csvs(self) -> List[Dict[str, str]]:
        """
        Scan data/ directory for available CSV datasets.
        Returns list of dicts with 'filename', 'path', and 'size_bytes'.
        """
        available = []
        if os.path.exists(self.data_dir):
            for fname in sorted(os.listdir(self.data_dir)):
                if fname.endswith(".csv"):
                    fpath = os.path.join(self.data_dir, fname)
                    size = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
                    available.append({
                        "filename": fname,
                        "path": fpath,
                        "size_bytes": size,
                    })
        return available

    def run_screening(self, csv_path: str) -> ScreeningResult:
        """
        Execute end-to-end screening for a CSV file.
        Returns complete ScreeningResult object.
        """
        if not os.path.exists(csv_path):
            return ScreeningResult(
                csv_path=csv_path,
                total_lots=0,
                total_components=0,
                validation_status="FAIL",
                validation_hard_failures=1,
                validation_warnings=0,
                validation_messages=[f"[HARD FAILURE] File not found: {csv_path}"],
                aborted=True,
                abort_reason=f"File not found: {csv_path}",
            )
        return self.pipeline.run(csv_path=csv_path)

    # ------------------------------------------------------------------
    # Phase 7 Human-in-the-Loop Audit Trail Methods
    # ------------------------------------------------------------------

    def record_human_decision(
        self,
        component_result: ComponentScreeningResult,
        engineer_decision: str,
        engineer_reason: str,
    ) -> AuditRecord:
        """
        Record a human engineering signoff decision (PASS / MONITOR / REJECT).
        Enforces mandatory non-empty human reason.
        """
        return self.audit_recorder.record_from_screening_component(
            component_result=component_result,
            engineer_decision=engineer_decision,
            engineer_reason=engineer_reason,
        )

    def get_audit_record(
        self, component_id: str, lot_id: str
    ) -> Optional[AuditRecord]:
        """Retrieve recorded human decision for a component if available."""
        return self.audit_recorder.get_record(component_id, lot_id)

    def get_audit_summary(self) -> AuditTrailSummary:
        """Get summary stats of human engineering signoffs in current session."""
        return self.audit_recorder.get_summary()

    def export_audit_log(
        self, screening_result: ScreeningResult, output_path: str = "reports/phase7_audit_log.csv"
    ) -> str:
        """Export full combined AI screening + human audit log to CSV."""
        return self.audit_exporter.export_to_csv(
            screening_result=screening_result,
            output_path=output_path,
            recorder=self.audit_recorder,
        )
