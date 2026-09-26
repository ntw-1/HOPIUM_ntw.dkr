"""
src/data/validation/tester.py

Core DataTester orchestrator for HOPIUM_sih26170 Phase 2.

Runs all 13 validation categories against a burn-in dataset CSV, companion .meta.json,
and companion groundtruth.json.

Exports deterministic machine-readable JSON and human-readable Markdown reports.

References:
    - Approved Phase 2 Specification & Architecture
    - docs/DATA_CONTRACT.md, docs/ML_CONTRACT.md, docs/TEST_PLAN.md
"""

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .domain_check import check_domain
from .integrity_check import check_integrity
from .leakage_check import check_leakage
from .prevalence_check import check_prevalence
from .provenance_check import check_provenance
from .schema_check import check_schema
from .sih_check import check_sih_compliance
from .split_check import check_split
from .statistical_check import check_statistical
from .structure_check import check_structure
from .temporal_check import check_temporal

TESTER_VERSION = "v1.0.0-phase2"


@dataclass
class ValidationResult:
    """Encapsulates the complete result of a dataset validation run."""
    overall_status: str               # "PASS" or "FAIL"
    hard_failures_count: int
    warnings_count: int
    info_count: int
    total_checks_evaluated: int
    findings: List[Dict[str, Any]]
    dataset_id: str
    content_hash_sha256: str
    generator_version: str
    tester_version: str = TESTER_VERSION
    descriptive_statistics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_timestamp: bool = False) -> Dict[str, Any]:
        """Convert result to a structured dictionary for JSON export."""
        report_meta = {
            "tester_version": self.tester_version,
            "generator_version": self.generator_version,
            "dataset_id": self.dataset_id,
            "content_hash_sha256": self.content_hash_sha256,
        }
        if include_timestamp:
            from datetime import datetime, timezone
            report_meta["validation_timestamp_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Group findings by category
        categories_dict = {}
        for f in self.findings:
            cat = f["category"]
            if cat not in categories_dict:
                categories_dict[cat] = {"status": "PASS", "hard_failures": [], "warnings": [], "info": []}
            
            lvl = f["level"]
            if lvl == "HARD FAILURE":
                categories_dict[cat]["status"] = "FAIL"
                categories_dict[cat]["hard_failures"].append(f["message"])
            elif lvl == "WARNING":
                categories_dict[cat]["warnings"].append(f["message"])
            else:
                categories_dict[cat]["info"].append(f["message"])

        return {
            "report_metadata": report_meta,
            "summary": {
                "overall_status": self.overall_status,
                "hard_failures_count": self.hard_failures_count,
                "warnings_count": self.warnings_count,
                "info_count": self.info_count,
                "total_checks_evaluated": self.total_checks_evaluated,
            },
            "category_summary": categories_dict,
            "descriptive_statistics": self.descriptive_statistics,
            "detailed_findings": self.findings,
        }

    def to_markdown(self, include_timestamp: bool = False) -> str:
        """
        Generate deterministic human-readable Markdown report for GitHub.
        Omits execution timestamp by default to ensure report determinism.
        """
        lines = []
        lines.append("# Phase 2 Data Validation Report")
        lines.append("")
        lines.append(f"**Dataset ID:** `{self.dataset_id}`  ")
        lines.append(f"**Validation Status:** **`{self.overall_status}`** {'✅' if self.overall_status == 'PASS' else '❌'}  ")
        lines.append(f"**SHA-256 Hash:** `{self.content_hash_sha256}`  ")
        lines.append(f"**Generator Version:** `{self.generator_version}` | **Tester Version:** `{self.tester_version}`  ")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 1. Executive Summary")
        lines.append("")
        lines.append("| Metric | Result |")
        lines.append("| :--- | :--- |")
        lines.append(f"| **Overall Status** | **`{self.overall_status}`** ({'Approved for Phase 3 Model Lab' if self.overall_status == 'PASS' else 'BLOCKED — Requires Correction'}) |")
        lines.append(f"| **Hard Failures** | `{self.hard_failures_count}` |")
        lines.append(f"| **Warnings** | `{self.warnings_count}` |")
        lines.append(f"| **Informational Checks** | `{self.info_count}` |")
        lines.append(f"| **Total Checks Evaluated** | `{self.total_checks_evaluated}` |")
        lines.append("")

        # Descriptive stats if present
        if self.descriptive_statistics:
            ds = self.descriptive_statistics
            lines.append(f"| **Dataset Dimensions** | {ds.get('num_lots', '?')} Lots / {ds.get('num_components', '?')} Components ({ds.get('total_rows', '?')} Trajectory Rows) |")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## 2. Category Audit Results")
        lines.append("")

        # Group findings by category
        cat_findings: Dict[str, List[Dict[str, Any]]] = {}
        for f in self.findings:
            cat = f["category"]
            cat_findings.setdefault(cat, []).append(f)

        for cat, flist in cat_findings.items():
            has_fail = any(f["level"] == "HARD FAILURE" for f in flist)
            has_warn = any(f["level"] == "WARNING" for f in flist)
            status_icon = "❌ FAIL" if has_fail else ("⚠️ WARN" if has_warn else "✅ PASS")
            
            lines.append(f"### Category: `{cat}` — {status_icon}")
            lines.append("")
            for f in flist:
                icon = "❌" if f["level"] == "HARD FAILURE" else ("⚠️" if f["level"] == "WARNING" else "ℹ️")
                lines.append(f"- {icon} **[{f['level']}]** {f['message']}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("*Report generated by Phase 2 Data Tester engine (`src/data/validation/tester.py`).*")
        lines.append("")
        return "\n".join(lines)


class DataTester:
    """
    Main Phase 2 Data Tester engine.

    Usage:
        tester = DataTester()
        result = tester.validate_paths(
            csv_path="data/dev_burnin_data.csv",
            meta_path="data/dev_burnin_data.meta.json",
            groundtruth_path="data/dev_burnin_groundtruth.json",
        )
    """

    def __init__(self):
        pass

    def validate_paths(
        self,
        csv_path: str,
        meta_path: Optional[str] = None,
        groundtruth_path: Optional[str] = None,
    ) -> ValidationResult:
        """Validate a dataset from file paths."""
        if meta_path is None:
            meta_path = csv_path.replace(".csv", ".meta.json")
        if groundtruth_path is None:
            groundtruth_path = csv_path.replace(".csv", "_groundtruth.json")

        # Load CSV raw bytes for SHA-256 canonical hashing
        csv_bytes = None
        df = None
        if os.path.exists(csv_path):
            with open(csv_path, "rb") as f:
                csv_bytes = f.read()
            try:
                df = pd.read_csv(csv_path)
            except Exception:
                df = None

        # Load metadata JSON if present
        meta_dict = None
        if meta_path and os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_dict = json.load(f)
            except Exception:
                meta_dict = None

        # Load groundtruth JSON if present
        gt_dict = None
        if groundtruth_path and os.path.exists(groundtruth_path):
            try:
                with open(groundtruth_path, "r", encoding="utf-8") as f:
                    gt_dict = json.load(f)
            except Exception:
                gt_dict = None

        return self.validate(df=df, csv_bytes=csv_bytes, meta_dict=meta_dict, groundtruth=gt_dict, meta_path=meta_path)

    def validate(
        self,
        df: Optional[pd.DataFrame],
        csv_bytes: Optional[bytes] = None,
        meta_dict: Optional[dict] = None,
        groundtruth: Optional[dict] = None,
        meta_path: Optional[str] = None,
    ) -> ValidationResult:
        """Run all 13 validation categories and aggregate findings."""
        findings: List[Dict[str, Any]] = []

        # 1. Provenance check (Category 10)
        prov_findings = check_provenance(csv_bytes=csv_bytes, meta_dict=meta_dict, meta_path=meta_path)
        findings.extend(prov_findings)

        # Extract metadata info
        dataset_id = meta_dict.get("dataset_id", "unknown_dataset") if meta_dict else "unknown_dataset"
        content_hash = meta_dict.get("content_hash_sha256", "unknown_hash") if meta_dict else "unknown_hash"
        gen_version = meta_dict.get("generator_version", "unknown_version") if meta_dict else "unknown_version"

        # If CSV DataFrame is unreadable or None, stop after provenance
        if df is None:
            findings.append({
                "category": "schema",
                "level": "HARD FAILURE",
                "check_name": "csv_readable",
                "message": "Dataset CSV file could not be read or parsed as a DataFrame.",
                "details": {},
            })
            return self._build_result(findings, dataset_id, content_hash, gen_version, {})

        # Run remaining check categories
        # Category 1: Schema
        findings.extend(check_schema(df))

        # Category 2: Integrity & Completeness
        findings.extend(check_integrity(df))

        # Category 3: Temporal
        findings.extend(check_temporal(df))

        # Category 4: Domain & Ranges
        findings.extend(check_domain(df))

        # Category 5: Statistical Sanity
        findings.extend(check_statistical(df))

        # Category 6: Correlation Structure
        findings.extend(check_structure(df, config=meta_dict.get("config_snapshot") if meta_dict else None))

        # Category 7 & 8: Anomaly Prevalence & Latent Detectability
        findings.extend(check_prevalence(df, groundtruth=groundtruth))

        # Category 11: Feature Boundary & Target Isolation
        findings.extend(check_leakage(df))

        # Category 12: Split Readiness
        findings.extend(check_split(df))

        # Category 13: SIH26170 Compliance
        findings.extend(check_sih_compliance(df))

        # Compile descriptive statistics
        desc_stats = {
            "num_lots": int(df["lot_id"].nunique()) if "lot_id" in df.columns else 0,
            "num_components": int(df["component_id"].nunique()) if "component_id" in df.columns else 0,
            "total_rows": len(df),
        }

        return self._build_result(findings, dataset_id, content_hash, gen_version, desc_stats)

    def _build_result(
        self,
        findings: List[Dict[str, Any]],
        dataset_id: str,
        content_hash: str,
        gen_version: str,
        desc_stats: Dict[str, Any],
    ) -> ValidationResult:
        hard_fails = sum(1 for f in findings if f["level"] == "HARD FAILURE")
        warns = sum(1 for f in findings if f["level"] == "WARNING")
        infos = sum(1 for f in findings if f["level"] == "INFORMATION")
        status = "FAIL" if hard_fails > 0 else "PASS"

        return ValidationResult(
            overall_status=status,
            hard_failures_count=hard_fails,
            warnings_count=warns,
            info_count=infos,
            total_checks_evaluated=len(findings),
            findings=findings,
            dataset_id=dataset_id,
            content_hash_sha256=content_hash,
            generator_version=gen_version,
            descriptive_statistics=desc_stats,
        )
