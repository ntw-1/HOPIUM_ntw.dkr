"""
src/anomaly/__init__.py

Module A — Dynamic Population-Relative Anomaly Detector package for HOPIUM_sih26170.

Exposes PopulationAnomalyDetector, data schema dataclasses, and robust statistical utilities.
"""

from .detector import PopulationAnomalyDetector
from .metrics import compute_modified_zscores, compute_percentiles, compute_robust_statistics
from .schema import ComponentAnomalyReport, LotAnomalyReport, ParameterAnomalyEvidence

__all__ = [
    "PopulationAnomalyDetector",
    "LotAnomalyReport",
    "ComponentAnomalyReport",
    "ParameterAnomalyEvidence",
    "compute_modified_zscores",
    "compute_robust_statistics",
    "compute_percentiles",
]
