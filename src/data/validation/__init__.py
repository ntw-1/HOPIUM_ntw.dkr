"""
src/data/validation/__init__.py

Phase 2 Data Tester package for HOPIUM_sih26170.
Provides automated, reproducible validation for burn-in trajectory datasets
before they enter Phase 3 Model Lab.
"""

from .tester import DataTester, ValidationResult

__all__ = ["DataTester", "ValidationResult"]
