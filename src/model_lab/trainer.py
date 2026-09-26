"""
src/model_lab/trainer.py

Candidate model training and validation-set metric evaluation for Phase 3.

Responsibilities:
    - Train each candidate on train partition
    - Evaluate on validation partition only (blind partition never touched here)
    - Compute: MAE_val, RMSE_val, MAPE_val
    - Return results table for model selection

Model selection uses validation MAE only (ML_CONTRACT.md §3).
Training MAE is computed for information but never used for selection.
"""

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from .candidates import CANDIDATE_ORDER, build_candidates
from .features import build_feature_matrix


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Percentage Error, guarded against zero denominators."""
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    nonzero = y_true != 0.0
    if nonzero.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero])))


def train_candidates(
    df: pd.DataFrame,
    parameter: str,
    train_lots: List[str],
    val_lots: List[str],
    config: dict,
    random_seed: int = 42,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, float]]]:
    """
    Train all candidate pipelines on train_lots; evaluate on val_lots.

    Args:
        df:           Full long-format source DataFrame.
        parameter:    Parameter name ('Iddq', 'leakage_current', 'propagation_delay').
        train_lots:   List of lot IDs for training.
        val_lots:     List of lot IDs for validation (NEVER blind lots).
        config:       model_lab_config dict.
        random_seed:  Global reproducibility seed.

    Returns:
        fitted_models:  Dict mapping candidate name -> fitted sklearn Pipeline.
        metrics_table:  Dict mapping candidate name -> metric dict:
                        {MAE_train, MAE_val, RMSE_val, MAPE_val}
    """
    candidates_cfg = config.get("candidates", {})
    pipelines = build_candidates(candidates_cfg, random_seed=random_seed)

    X_train, y_train, _ = build_feature_matrix(df, parameter, train_lots)
    X_val, y_val, _ = build_feature_matrix(df, parameter, val_lots)

    fitted_models: Dict[str, Any] = {}
    metrics_table: Dict[str, Dict[str, float]] = {}

    for name in CANDIDATE_ORDER:
        pipeline = pipelines[name]
        pipeline.fit(X_train, y_train)

        y_pred_train = pipeline.predict(X_train)
        y_pred_val = pipeline.predict(X_val)

        mae_train = float(mean_absolute_error(y_train, y_pred_train))
        mae_val = float(mean_absolute_error(y_val, y_pred_val))
        rmse_val = float(np.sqrt(mean_squared_error(y_val, y_pred_val)))
        mape_val = _mape(y_val.values, y_pred_val)

        fitted_models[name] = pipeline
        metrics_table[name] = {
            "MAE_train": mae_train,
            "MAE_val": mae_val,
            "RMSE_val": rmse_val,
            "MAPE_val": mape_val,
        }

    return fitted_models, metrics_table
