"""
src/evaluation/metrics.py

Functions to compute evaluation metrics.
"""
import numpy as np

def calculate_scalar_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    if len(y_true) == 0:
        return {}
    errors = y_pred - y_true
    abs_errors = np.abs(errors)
    
    return {
        "MAE": float(np.mean(abs_errors)),
        "RMSE": float(np.sqrt(np.mean(errors**2))),
        "mean_error": float(np.mean(errors)),
        "median_absolute_error": float(np.median(abs_errors)),
        "max_absolute_error": float(np.max(abs_errors))
    }

def calculate_error_distribution(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    if len(y_true) == 0:
        return {}
    errors = y_pred - y_true
    abs_errors = np.abs(errors)
    
    return {
        "residual_mean": float(np.mean(errors)),
        "residual_median": float(np.median(errors)),
        "residual_std": float(np.std(errors)),
        "residual_quantiles": {
            "q05": float(np.percentile(errors, 5)),
            "q25": float(np.percentile(errors, 25)),
            "q75": float(np.percentile(errors, 75)),
            "q95": float(np.percentile(errors, 95))
        },
        "absolute_error_quantiles": {
            "q50": float(np.percentile(abs_errors, 50)),
            "q75": float(np.percentile(abs_errors, 75)),
            "q90": float(np.percentile(abs_errors, 90)),
            "q95": float(np.percentile(abs_errors, 95)),
            "q99": float(np.percentile(abs_errors, 99))
        }
    }

def calculate_uncertainty_metrics(y_true: np.ndarray, lower_bounds: np.ndarray, upper_bounds: np.ndarray) -> dict:
    if len(y_true) == 0:
        return {}
    
    covered = (y_true >= lower_bounds) & (y_true <= upper_bounds)
    widths = upper_bounds - lower_bounds
    
    return {
        "empirical_coverage": float(np.mean(covered)),
        "average_interval_width": float(np.mean(widths)),
        "median_interval_width": float(np.median(widths))
    }
