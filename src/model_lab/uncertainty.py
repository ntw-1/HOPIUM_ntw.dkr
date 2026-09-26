"""
src/model_lab/uncertainty.py

Lightweight prediction uncertainty estimation for Module B (Phase 3).

Approach by model type:
    GradientBoostingRegressor: Quantile regression siblings (q_lo=0.10, q_hi=0.90)
                               with deterministic envelope adjustment.
                               Returns per-sample interval [lower, upper].
    RandomForestRegressor:     Std of individual tree predictions around point estimate.
                               Returns per-sample interval [y_pred - std, y_pred + std].
    Ridge:                     Residual std on training set (constant per model).
                               Returns per-sample interval [y_pred - std, y_pred + std].
    DummyRegressor:            Std of training targets (constant per model).
                               Returns per-sample interval [y_pred - std, y_pred + std].

Envelope Guarantee:
    For all methods, lower_bound <= prediction <= upper_bound is strictly enforced:
        lower_bound = min(raw_lower, prediction)
        upper_bound = max(raw_upper, prediction)
    This handles skewed target distributions where conditional mean predictions can
    exceed upper conditional quantile estimates.
"""

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from .candidates import build_quantile_siblings
from .features import build_feature_matrix


def fit_uncertainty(
    selected_model_name: str,
    fitted_pipeline: Pipeline,
    df: pd.DataFrame,
    parameter: str,
    train_lots: list,
    config: dict,
    random_seed: int = 42,
) -> dict:
    """
    Fit uncertainty estimation artifacts for the selected model.

    Args:
        selected_model_name: Name of the winning candidate.
        fitted_pipeline:     Already-fitted sklearn Pipeline of the winner.
        df:                  Full long-format source DataFrame.
        parameter:           Parameter name.
        train_lots:          Training lot list.
        config:              model_lab_config dict.
        random_seed:         Seed for quantile sibling reproducibility.

    Returns:
        uncertainty_artifacts dict containing whatever is needed for predict-time estimation.
    """
    X_train, y_train, _ = build_feature_matrix(df, parameter, train_lots)
    unc_cfg = config.get("uncertainty", {})

    if selected_model_name == "GradientBoostingRegressor":
        siblings = build_quantile_siblings(config.get("candidates", {}), random_seed=random_seed)
        q_lo_pipeline = siblings["quantile_lo"]
        q_hi_pipeline = siblings["quantile_hi"]
        q_lo_pipeline.fit(X_train, y_train)
        q_hi_pipeline.fit(X_train, y_train)
        return {
            "method": "quantile_interval_envelope",
            "quantile_lo": unc_cfg.get("quantile_lo", 0.10),
            "quantile_hi": unc_cfg.get("quantile_hi", 0.90),
            "q_lo_pipeline": q_lo_pipeline,
            "q_hi_pipeline": q_hi_pipeline,
        }

    elif selected_model_name == "RandomForestRegressor":
        return {
            "method": "rf_tree_std",
            "rf_pipeline": fitted_pipeline,
        }

    elif selected_model_name == "Ridge":
        y_train_pred = fitted_pipeline.predict(X_train)
        residual_std = float(np.std(y_train.values - y_train_pred))
        return {
            "method": "residual_std",
            "residual_std": residual_std,
        }

    else:  # DummyRegressor
        target_std = float(np.std(y_train.values))
        return {
            "method": "target_std",
            "target_std": target_std,
        }


def predict_with_uncertainty(
    X: pd.DataFrame,
    fitted_pipeline: Pipeline,
    uncertainty_artifacts: dict,
) -> dict:
    """
    Make predictions with associated uncertainty estimates.

    Enforces the invariant:
        lower_bound <= prediction <= upper_bound
    for 100% of samples deterministically via envelope adjustment.

    Args:
        X:                     Production feature matrix.
        fitted_pipeline:       Fitted sklearn Pipeline for point predictions.
        uncertainty_artifacts: Dict from fit_uncertainty().

    Returns:
        Dict with keys:
            predictions:        np.ndarray of point predictions.
            lower_bounds:       np.ndarray of lower uncertainty bound (per sample).
            upper_bounds:       np.ndarray of upper uncertainty bound (per sample).
            uncertainty_method: str describing the method used.
    """
    y_pred = fitted_pipeline.predict(X)
    method = uncertainty_artifacts.get("method", "target_std")

    if method == "quantile_interval_envelope":
        q_lo_pipeline = uncertainty_artifacts["q_lo_pipeline"]
        q_hi_pipeline = uncertainty_artifacts["q_hi_pipeline"]
        raw_lo = q_lo_pipeline.predict(X)
        raw_hi = q_hi_pipeline.predict(X)

        # Compute outer envelope including point prediction y_pred
        lower = np.minimum(np.minimum(raw_lo, raw_hi), y_pred)
        upper = np.maximum(np.maximum(raw_lo, raw_hi), y_pred)

    elif method == "rf_tree_std":
        rf_pipeline = uncertainty_artifacts["rf_pipeline"]
        rf_model = rf_pipeline.named_steps["model"]
        X_scaled = rf_pipeline.named_steps["scaler"].transform(X)
        tree_preds = np.array([tree.predict(X_scaled) for tree in rf_model.estimators_])
        std_preds = np.std(tree_preds, axis=0)
        raw_lo = y_pred - std_preds
        raw_hi = y_pred + std_preds
        lower = np.minimum(raw_lo, y_pred)
        upper = np.maximum(raw_hi, y_pred)

    elif method == "residual_std":
        std = uncertainty_artifacts["residual_std"]
        raw_lo = y_pred - std
        raw_hi = y_pred + std
        lower = np.minimum(raw_lo, y_pred)
        upper = np.maximum(raw_hi, y_pred)

    else:  # target_std
        std = uncertainty_artifacts.get("target_std", 0.0)
        raw_lo = y_pred - std
        raw_hi = y_pred + std
        lower = np.minimum(raw_lo, y_pred)
        upper = np.maximum(raw_hi, y_pred)

    # Invariant assertion
    assert np.all(lower <= y_pred + 1e-9), "Uncertainty lower bound exceeds point prediction!"
    assert np.all(y_pred <= upper + 1e-9), "Point prediction exceeds uncertainty upper bound!"

    return {
        "predictions": y_pred,
        "lower_bounds": lower,
        "upper_bounds": upper,
        "uncertainty_method": method,
    }
