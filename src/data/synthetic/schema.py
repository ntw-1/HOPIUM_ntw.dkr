"""
src/data/synthetic/schema.py

Data structures for synthetic burn-in trajectory rows and metadata.

All field definitions follow docs/DATA_CONTRACT.md exactly.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Trajectory row — corresponds exactly to one CSV row
# ---------------------------------------------------------------------------

@dataclass
class TrajectoryRow:
    """
    One parameter trajectory row for a single component.
    Corresponds to one row in the output CSV dataset.

    Production inference fields:
        value_0h, value_24h — the ONLY permitted production inputs for Module B.

    Ground-truth / historical fields (must never enter production feature matrices):
        value_96h, value_168h
    """
    lot_id: str
    component_id: str
    parameter_name: str          # "Iddq" | "leakage_current" | "propagation_delay"
    unit: str                    # "uA"  | "nA"               | "ps"
    value_0h: float
    value_24h: float
    value_96h: float
    value_168h: float
    synthetic_spec_min: float    # Synthetic scenario reference limit (NOT a datasheet limit)
    synthetic_spec_max: float    # Synthetic scenario reference limit (NOT a datasheet limit)


# ---------------------------------------------------------------------------
# Ground truth — component level
# ---------------------------------------------------------------------------

@dataclass
class ComponentGroundTruth:
    """
    Component-level ground truth.
    Stored separately from CSV; never enters production inference.
    """
    component_id: str
    lot_id: str

    # Behavioral state: temporal trajectory classification
    behavioral_state: str        # "nominal" | "latent_degradation"
    is_latent_degrader: bool

    # Latent degradation early detectability (None if not a latent degrader)
    early_detectability: Optional[str]   # "hidden"|"subtle"|"moderate"|"strong"

    # Anomaly attributes — independent axes (not mutually exclusive with each other
    # or with behavioral_state)
    is_population_anomaly: bool       # True if statistically unusual within lot
    is_reference_limit_breach: bool   # True if any parameter exceeds synthetic limits

    # Aggregated list of active anomaly attributes
    anomaly_attributes: List[str]     # e.g. ["population_anomaly", "reference_limit_breach"]

    # Severity of the worst anomaly attribute (None if no anomaly attributes)
    severity_level: Optional[str]     # "mild"|"moderate"|"strong"|"severe"


# ---------------------------------------------------------------------------
# Ground truth — parameter level
# ---------------------------------------------------------------------------

@dataclass
class ParameterGroundTruth:
    """
    Parameter-level ground truth.
    Stored separately from CSV; never enters production inference.
    """
    component_id: str
    parameter_name: str
    true_value_168h: float
    true_drift_168h: float         # value_168h - value_0h
    is_parameter_anomalous: bool
    parameter_anomaly_severity: Optional[str]   # "mild"|"moderate"|"strong"|"severe"


# ---------------------------------------------------------------------------
# Dataset metadata — companion .meta.json content
# ---------------------------------------------------------------------------

@dataclass
class DatasetMetadata:
    """
    Canonical provenance metadata stored in the companion .meta.json file.
    The SHA-256 hash is computed over the canonical CSV byte stream AFTER
    CSV generation and is NOT embedded in the CSV itself.
    """
    is_synthetic: bool
    generator_version: str
    random_seed: int
    dataset_id: str
    content_hash_sha256: str         # hex digest of canonical CSV UTF-8 bytes (LF-normalized)
    num_lots: int
    components_per_lot: int
    total_rows: int
    generation_timestamp_utc: str
    disclaimer: str = (
        "SYNTHETIC DATASET GENERATED FOR SIH26170 EXPERIMENTATION. "
        "NOT REAL ISRO/INDUSTRY DATA."
    )
