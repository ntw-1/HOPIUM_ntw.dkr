"""
src/anomaly/metrics.py

Robust statistical metric functions for Module A (Population-Relative Anomaly Detector).

Implements Iglewicz & Hoaglin (1993) Robust Modified Z-Score:
    M_i = 0.6745 * (x_i - median(x)) / (MAD(x) + epsilon)

Features:
    - Zero-MAD / constant population handling via epsilon (10^-9) to guarantee finite outputs.
    - Percentile rank computation within population.
    - Deterministic numerical execution without NaN/Inf outputs.
"""

from typing import Tuple
import numpy as np


def compute_robust_statistics(values: np.ndarray, epsilon: float = 1e-9) -> Tuple[float, float]:
    """
    Compute robust center (median) and scale (MAD) for a 1D numeric array.

    MAD = median(|x - median(x)|)

    Args:
        values: 1D numpy array of values.
        epsilon: Small numerical stabilizer (default 1e-9).

    Returns:
        (median_val, mad_val) as floats.
    """
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return 0.0, 0.0

    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    return med, mad


def compute_modified_zscores(
    values: np.ndarray,
    epsilon: float = 1e-9,
) -> Tuple[np.ndarray, float, float]:
    """
    Calculate robust Modified Z-Scores for a 1D numeric array.

    Formula (Iglewicz & Hoaglin, 1993):
        M_i = 0.6745 * (x_i - median) / (MAD + epsilon)

    Args:
        values: 1D numpy array of feature values.
        epsilon: Small numerical stabilizer to handle zero MAD (constant population).

    Returns:
        (modified_zscores, median_val, mad_val)
    """
    arr = np.asarray(values, dtype=float)
    med, mad = compute_robust_statistics(arr, epsilon=epsilon)

    # 0.6745 is the scaling factor so MAD equals std dev for normal distributions
    z_scores = 0.6745 * (arr - med) / (mad + epsilon)

    # Guard against non-finite values if any exist in raw array
    z_scores = np.nan_to_num(z_scores, nan=0.0, posinf=0.0, neginf=0.0)

    return z_scores, med, mad


def compute_percentiles(values: np.ndarray) -> np.ndarray:
    """
    Calculate the empirical percentile rank (0 to 100) of each value within a 1D array.

    Args:
        values: 1D numpy array.

    Returns:
        1D numpy array of percentile ranks (0.0 to 100.0).
    """
    arr = np.asarray(values, dtype=float)
    n = arr.size
    if n <= 1:
        return np.full(n, 50.0)

    # Compute percentage of array elements <= value
    percentiles = np.array([float(np.mean(arr <= val) * 100.0) for val in arr], dtype=float)
    return percentiles
