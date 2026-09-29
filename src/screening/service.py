"""
src/screening/service.py

Phase 6 & 7 — Screening & Audit Service Layer.

Provides high-level application service methods for UI / API / CLI clients
to interact with the screening platform and session audit trail.

Decouples UI execution from lower-level pipeline orchestration and audit recording.
"""

import os
from typing import Any, Dict, List, Optional

from ..audit.exporter import AuditExporter
from ..audit.recorder import AuditRecorder
from ..audit.schema import AuditRecord, AuditTrailSummary
from .pipeline import ScreeningPipeline
from .schema import ComponentScreeningResult, LotScreeningResult, ScreeningResult
from ..secondary_use import SecondaryUseService


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
        self.secondary_use = SecondaryUseService()

    def list_secondary_use_pool(self) -> List[Dict[str, Any]]:
        return self.secondary_use.list_pool(
            getattr(self, "current_screening_result", None), self.audit_recorder
        )

    def get_secondary_use_evidence(self, component_id: str, lot_id: str) -> Dict[str, Any]:
        return self.secondary_use.build_evidence(
            getattr(self, "current_screening_result", None), self.audit_recorder,
            component_id, lot_id,
        )

    def assess_secondary_use(self, component_id: str, lot_id: str,
                             application_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        evidence = self.get_secondary_use_evidence(component_id, lot_id)
        profiles = self.secondary_use.list_applications()
        if application_ids is not None:
            profiles = [p for p in profiles if p["id"] in application_ids]
            if len(profiles) != len(set(application_ids)):
                raise ValueError("One or more application profiles were not found.")
        return self.secondary_use.create_assessment(evidence, profiles)

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
        result = self.pipeline.run(csv_path=csv_path)
        self.current_screening_result = result
        return result

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

    # ------------------------------------------------------------------
    # Model Lab Lifecycle & Model Switch Methods
    # ------------------------------------------------------------------

    def reload_predictors(self) -> None:
        """Reload predictors in pipeline so subsequent screening uses newly deployed models."""
        self.pipeline.reload_predictors()

    def get_model_lab_status(self) -> Dict[str, Any]:
        """
        Return the deployed model metadata, active versions, and history for all parameters.
        """
        from ..model_lab.registry import get_active_models, list_model_versions

        registry_dir = self.pipeline._registry_dir
        active_map = get_active_models(registry_dir)
        parameters = ["Iddq", "leakage_current", "propagation_delay"]

        status = {}
        for param in parameters:
            active_id = active_map.get(param, f"module_b_{param}_v1")
            versions = list_model_versions(registry_dir, parameter=param)
            active_version_meta = next((v for v in versions if v["model_id"] == active_id), None)

            status[param] = {
                "parameter": param,
                "active_model_id": active_id,
                "active_version_meta": active_version_meta,
                "version_count": len(versions),
                "versions": versions,
            }

        return {
            "parameters": status,
            "audit_history": self.audit_recorder.list_model_switches(),
        }

    def reevaluate_deployed_model(self, csv_path: str, parameter: str) -> Dict[str, Any]:
        """
        Re-evaluate the current deployed model against a completed dataset.
        """
        from ..model_lab.lifecycle import reevaluate_deployed_model

        return reevaluate_deployed_model(
            csv_path=csv_path,
            parameter=parameter,
            registry_dir=self.pipeline._registry_dir,
        )

    def compare_candidates(self, csv_path: str, parameter: str) -> Dict[str, Any]:
        """
        Benchmark deployed model against candidates on the same dataset.
        """
        from ..model_lab.lifecycle import compare_candidates_on_dataset

        return compare_candidates_on_dataset(
            csv_path=csv_path,
            parameter=parameter,
            registry_dir=self.pipeline._registry_dir,
            config_path=self.pipeline._risk_config_path.replace("risk_engine_config.yaml", "model_lab_config.yaml"),
        )

    def switch_deployed_model(
        self,
        parameter: str,
        candidate_name: str,
        csv_path: str,
        reason: str,
        operator: str = "E. Mercer [L3-ENG]",
    ) -> Dict[str, Any]:
        """
        Execute explicit human model switch:
        1. Registers new versioned model artifact.
        2. Preserves previous version.
        3. Updates active model pointer.
        4. Logs MODEL_DEPLOYMENT_CHANGE audit event.
        5. Reloads pipeline predictors so future screening runs immediately use the new model.
        """
        from ..model_lab.lifecycle import execute_model_switch

        res = execute_model_switch(
            parameter=parameter,
            candidate_name=candidate_name,
            csv_path=csv_path,
            reason=reason,
            operator=operator,
            registry_dir=self.pipeline._registry_dir,
            config_path=self.pipeline._risk_config_path.replace("risk_engine_config.yaml", "model_lab_config.yaml"),
        )

        # Record in audit recorder
        self.audit_recorder.record_model_switch(
            previous_model=res["previous_model"],
            new_model=res["new_model"],
            parameter=parameter,
            evaluation_dataset=csv_path,
            old_mae=res.get("old_mae") or res.get("old_val_MAE"),
            new_mae=res["new_val_MAE"],
            reason=reason,
            operator=operator,
            selection_basis=f"Selected candidate {candidate_name} via lowest validation MAE",
            timestamp_utc=res["timestamp_utc"],
            extra_info={"artifact_directory": res["artifact_directory"]},
        )

        # Append to persistent deployment audit CSV if reports/ exists
        audit_csv_path = "reports/model_switch_audit_log.csv"
        try:
            import os
            import csv
            os.makedirs("reports", exist_ok=True)
            file_exists = os.path.exists(audit_csv_path)
            with open(audit_csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow([
                        "timestamp_utc", "event_type", "parameter", "previous_model",
                        "new_model", "candidate_name", "new_val_MAE", "new_val_RMSE",
                        "evaluation_dataset", "operator", "reason"
                    ])
                writer.writerow([
                    res["timestamp_utc"], res["event_type"], parameter, res["previous_model"],
                    res["new_model"], candidate_name, res["new_val_MAE"], res.get("new_val_RMSE", ""),
                    csv_path, operator, reason
                ])
        except Exception:
            pass

        # Reload predictors for future screening
        self.reload_predictors()

        return res
