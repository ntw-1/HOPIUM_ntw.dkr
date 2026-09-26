"""
src/data/synthetic/correlation.py

Mathematically correct cross-parameter correlation and covariance machinery.

Terminology (enforced throughout):
    R      — dimensionless correlation matrix (entries are pure numbers in [-1, 1])
    D      — diagonal matrix of per-parameter standard deviations (in parameter units)
    Sigma  — physical covariance matrix: Sigma = D R D  (units = sigma_i * sigma_j)

The correlation matrix R is a SYNTHETIC MODELLING ASSUMPTION.
It does not represent empirically validated semiconductor physics.

References:
    - Approved Phase 1 Specification (Revision 3), §2
    - docs/ML_CONTRACT.md — production feature boundary
"""

import numpy as np
from typing import List


def validate_correlation_matrix(R: np.ndarray) -> None:
    """
    Assert that R is a valid correlation matrix:
      1. Square and symmetric (within floating-point tolerance).
      2. Diagonal entries are all 1.0.
      3. All off-diagonal entries are in (-1, 1).
      4. Positive semi-definite (all eigenvalues >= 0).

    Raises ValueError with a descriptive message on any violation.

    Parameters
    ----------
    R : np.ndarray, shape (n, n)
        Candidate correlation matrix.
    """
    n = R.shape[0]

    if R.ndim != 2 or R.shape[0] != R.shape[1]:
        raise ValueError(f"R must be a square 2-D matrix; got shape {R.shape}.")

    if not np.allclose(R, R.T, atol=1e-10):
        raise ValueError("Correlation matrix R is not symmetric.")

    if not np.allclose(np.diag(R), 1.0, atol=1e-10):
        raise ValueError("Correlation matrix R must have all diagonal entries equal to 1.0.")

    off_diag_mask = ~np.eye(n, dtype=bool)
    off_vals = R[off_diag_mask]
    if np.any(np.abs(off_vals) >= 1.0):
        raise ValueError(
            "All off-diagonal entries of R must satisfy |rho| < 1.0. "
            f"Found: {off_vals[np.abs(off_vals) >= 1.0]}"
        )

    eigenvalues = np.linalg.eigvalsh(R)
    if np.any(eigenvalues < -1e-10):
        raise ValueError(
            f"Correlation matrix R is not positive semi-definite. "
            f"Minimum eigenvalue: {eigenvalues.min():.6e}"
        )


def build_cholesky_factor(R: np.ndarray) -> np.ndarray:
    """
    Compute the lower-triangular Cholesky factor L of correlation matrix R
    such that L @ L.T == R.

    A small regularisation term (1e-10 * I) is added prior to factorisation
    to handle numerical boundary cases near semi-definiteness without altering
    correlation structure at double precision.

    Parameters
    ----------
    R : np.ndarray, shape (n, n)
        A validated positive semi-definite correlation matrix.

    Returns
    -------
    L : np.ndarray, shape (n, n)
        Lower-triangular Cholesky factor.
    """
    R_reg = R + 1e-10 * np.eye(R.shape[0])
    try:
        L = np.linalg.cholesky(R_reg)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            f"Cholesky factorisation of R failed. "
            f"Ensure R is positive definite. Error: {exc}"
        ) from exc
    return L


def build_physical_covariance(
    R: np.ndarray,
    sigmas: List[float],
) -> np.ndarray:
    """
    Derive the physical covariance matrix Sigma from correlation matrix R and
    per-parameter standard deviations:

        Sigma = D R D

    where D = diag(sigmas).

    The resulting Sigma has units of (sigma_i * sigma_j) for the (i, j) entry,
    preserving physically meaningful cross-parameter covariances.

    Parameters
    ----------
    R : np.ndarray, shape (n, n)
        Validated dimensionless correlation matrix.
    sigmas : list of float
        Per-parameter standard deviations, length n.
        Order must match the axis ordering of R.

    Returns
    -------
    Sigma : np.ndarray, shape (n, n)
        Physical covariance matrix.
    """
    D = np.diag(sigmas)
    Sigma = D @ R @ D
    return Sigma


def sample_correlated_baselines(
    n_samples: int,
    means: List[float],
    sigmas: List[float],
    L: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Sample n_samples joint parameter baselines using the standardized
    correlated latent variable approach:

        z_i = D @ L @ u_i,    u_i ~ N(0, I)
        V_i(0h) = mu + z_i

    where:
        L  = Cholesky factor of R  (lower-triangular)
        D  = diag(sigmas)
        mu = vector of parameter means

    This preserves the cross-parameter correlation structure encoded in R
    while scaling each parameter to its own standard deviation.

    Parameters
    ----------
    n_samples : int
        Number of component baselines to generate.
    means : list of float
        Per-parameter global means, length n_params.
    sigmas : list of float
        Per-parameter standard deviations, length n_params.
    L : np.ndarray, shape (n_params, n_params)
        Cholesky factor of the correlation matrix R.
    rng : np.random.Generator
        NumPy random generator (seeded externally for reproducibility).

    Returns
    -------
    baselines : np.ndarray, shape (n_samples, n_params)
        Sampled parameter baselines. Column order matches the order of
        means, sigmas, and L axes.
    """
    n_params = len(means)
    mu = np.array(means, dtype=float)
    D = np.diag(sigmas)

    # u ~ N(0, I): shape (n_params, n_samples)
    u = rng.standard_normal(size=(n_params, n_samples))

    # z = D L u: shape (n_params, n_samples)
    z = D @ L @ u

    # baselines: shape (n_samples, n_params)
    baselines = (mu[:, None] + z).T
    return baselines
