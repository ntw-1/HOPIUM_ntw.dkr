"""
tests/unit/test_evaluation.py
"""
import pytest
import numpy as np
from src.evaluation.metrics import calculate_scalar_metrics, calculate_uncertainty_metrics

def test_calculate_scalar_metrics():
    y_true = np.array([10.0, 20.0, 30.0])
    y_pred = np.array([12.0, 18.0, 30.0])
    
    res = calculate_scalar_metrics(y_true, y_pred)
    assert res["MAE"] == pytest.approx((2.0 + 2.0 + 0.0) / 3)
    assert res["RMSE"] == pytest.approx(np.sqrt((4.0 + 4.0 + 0.0) / 3))
    assert res["mean_error"] == pytest.approx((2.0 - 2.0 + 0.0) / 3)
    assert res["max_absolute_error"] == pytest.approx(2.0)

def test_calculate_uncertainty_metrics():
    y_true = np.array([10.0, 20.0, 30.0])
    y_lower = np.array([9.0, 19.0, 31.0])
    y_upper = np.array([11.0, 21.0, 33.0])
    
    res = calculate_uncertainty_metrics(y_true, y_lower, y_upper)
    # y_true[0] in [9, 11] -> True
    # y_true[1] in [19, 21] -> True
    # y_true[2] in [31, 33] -> False
    assert res["empirical_coverage"] == pytest.approx(2/3)
    assert res["average_interval_width"] == pytest.approx(2.0)
