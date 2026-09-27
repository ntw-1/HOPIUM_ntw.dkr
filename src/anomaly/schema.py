"""
src/anomaly/schema.py

Data contracts and schema definitions for Module A (Population-Relative Anomaly Detector).

Provides structured data objects for parameter-level evidence, component-level anomaly reports,
and lot-level summary reports.

Distinguishes between:
    - Population-relative anomalies (based on robust Modified Z-Score relative to lot distribution)
    - Reference-limit breaches (based on synthetic reference spec min/max when available)

Classification States:
    - STATE_A_NORMAL: Population normal & within reference limits
    - STATE_B_POPULATION_ANOMALY_ONLY: Population anomalous & within reference limits
    - STATE_C_SPEC_BREACH_ONLY: Population normal & outside reference limits
    - STATE_D_POPULATION_ANOMALY_AND_SPEC_BREACH: Population anomalous & outside reference limits
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ParameterAnomalyEvidence:
    """Statistical and reference-limit evidence for a single component parameter."""
    parameter_name: str
    unit: str

    # Observed measurements
    observed_0h: float
    observed_24h: float
    observed_delta: float

    # Lot population robust statistics
    lot_median_0h: float
    lot_mad_0h: float
    lot_median_24h: float
    lot_mad_24h: float
    lot_median_delta: float
    lot_mad_delta: float

    # Robust Modified Z-Scores
    modified_zscore_0h: float
    modified_zscore_24h: float
    modified_zscore_delta: float
    max_modified_zscore: float

    # Percentile ranks within lot [0, 100]
    percentile_0h: float
    percentile_24h: float
    percentile_delta: float

    # Reference limits (synthetic scenario limits)
    synthetic_spec_min: Optional[float] = None
    synthetic_spec_max: Optional[float] = None
    is_spec_breach: bool = False


@dataclass
class ComponentAnomalyReport:
    """Comprehensive anomaly report for a single component."""
    component_id: str
    lot_id: str
    is_population_anomaly: bool
    is_reference_limit_breach: bool
    population_anomaly_score: float  # Maximum modified Z-score across all parameters
    classification_state: str        # STATE_A, STATE_B, STATE_C, or STATE_D
    parameter_evidence: Dict[str, ParameterAnomalyEvidence] = field(default_factory=dict)
    human_readable_reasons: List[str] = field(default_factory=list)


@dataclass
class LotAnomalyReport:
    """Lot-level summary report containing all component anomaly records."""
    lot_id: str
    total_components: int
    anomalous_components_count: int
    reference_breach_count: int
    component_reports: List[ComponentAnomalyReport] = field(default_factory=list)
