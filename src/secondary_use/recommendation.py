"""Recommendation-provider boundary, separate from compatibility decisions."""

from datetime import datetime, timezone
from typing import Protocol

from .compatibility import assess_compatibility


class RecommendationProvider(Protocol):
    def recommend(self, evidence: dict, applications: list[dict]) -> dict: ...


class RuleBasedRecommendationProvider:
    version = "rule-based-v1"

    def recommend(self, evidence: dict, applications: list[dict]) -> dict:
        assessments = [assess_compatibility(evidence, app) for app in applications]
        rank = {"CANDIDATE": 0, "INSUFFICIENT_EVIDENCE": 1, "INCOMPATIBLE": 2}
        assessments.sort(key=lambda item: (rank[item["compatibility_status"]], item["application_id"]))
        for item in assessments:
            item["rationale"] = ("Deterministic evidence checks support further engineering review." if item["compatibility_status"] == "CANDIDATE" else
                                 "At least one available measurement conflicts with the profile." if item["compatibility_status"] == "INCOMPATIBLE" else
                                 "Potential application cannot be assessed because required evidence is missing.")
        return {"provider": "rule-based", "version": self.version,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "evidence_references": evidence["evidence_references"], "recommendations": assessments}
