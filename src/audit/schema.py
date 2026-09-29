"""
src/audit/schema.py

Phase 7 — Human-in-the-Loop Audit Trail contracts.

Defines the data structures for recording human engineering decisions (PASS / MONITOR / REJECT),
retaining mandatory justification notes, and pairing human signoff with AI screening evidence.

DISCLAIMER:
    Human engineering signoff is the final decision authority. AI outputs are advisory only.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

DECISION_PASS = "PASS"
DECISION_MONITOR = "MONITOR"
DECISION_REJECT = "REJECT"

ALLOWED_DECISIONS = (DECISION_PASS, DECISION_MONITOR, DECISION_REJECT)


@dataclass
class AuditRecord:
    """
    Snapshot record for one engineering decision.
    Pairs AI screening evidence with the human engineer's decision and mandatory reasoning.
    """
    component_id: str
    lot_id: str

    # --- Human Decision & Reasoning ---
    engineer_decision: str              # PASS / MONITOR / REJECT
    engineer_reason: str                # Mandatory non-empty human justification

    # --- AI Screening Context (Preserved at time of decision) ---
    ai_overall_risk: str                # LOW / MEDIUM / HIGH
    ai_recommendation_context: str      # AI advisory recommendation text
    ai_reasons: List[str] = field(default_factory=list)  # AI evidence reasons

    # --- Metadata ---
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    session_id: str = "default_session"

    # --- Parameter Context Snapshot ---
    parameter_snapshots: Dict[str, dict] = field(default_factory=dict)


@dataclass
class AuditTrailSummary:
    """Summary statistics for an audit session."""
    total_decisions: int
    pass_count: int
    monitor_count: int
    reject_count: int
    decisions_by_lot: Dict[str, dict] = field(default_factory=dict)
