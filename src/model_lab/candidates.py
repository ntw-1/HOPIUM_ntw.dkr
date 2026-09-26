"""
src/model_lab/candidates.py

Candidate model definitions for Module B Model Lab (Phase 3).

Candidates are selected to be appropriate for tabular regression with a
very small feature set (3 production features: value_0h, value_24h, delta_24_0).
See ML_CONTRACT.md §3 for the contractual requirement.

Candidate rationale:
    DummyRegressor (mean):          Sanity floor. If any candidate underperforms
                                    the mean predictor, data pipeline is suspect.
    Ridge:                          Obligatory linear baseline. Interpretable and
                                    well-conditioned with 3 features.
    RandomForestRegressor:          Captures non-linear trajectory saturation without
                                    a closed-form assumption.
    GradientBoostingRegressor:      State-of-the-art tabular baseline; expected best
                                    performance on structured synthetic data.

Excluded from this version: TabPFN, XGBoost, LightGBM, SVR, neural approaches.
These require additional dependencies and are deferred unless evidence justifies them.
"""

from typing import Any, Dict

from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def build_candidates(config: dict, random_seed: int = 42) -> Dict[str, Pipeline]:
    """
    Build a dictionary of named scikit-learn pipelines from config.

    Each pipeline applies StandardScaler then the model, ensuring features
    are on comparable scales for Ridge and consistent preprocessing across all candidates.

    Args:
        config:      model_lab_config['candidates'] dict.
        random_seed: Global reproducibility seed.

    Returns:
        Dict mapping candidate name -> fitted Pipeline (unfitted).
    """
    ridge_cfg = config.get("Ridge", {})
    rf_cfg = config.get("RandomForestRegressor", {})
    gb_cfg = config.get("GradientBoostingRegressor", {})
    dummy_cfg = config.get("DummyRegressor", {})

    candidates: Dict[str, Pipeline] = {
        "DummyRegressor": Pipeline([
            ("scaler", StandardScaler()),
            ("model", DummyRegressor(
                strategy=dummy_cfg.get("strategy", "mean"),
            )),
        ]),
        "Ridge": Pipeline([
            ("scaler", StandardScaler()),
            ("model", Ridge(
                alpha=ridge_cfg.get("alpha", 1.0),
            )),
        ]),
        "RandomForestRegressor": Pipeline([
            ("scaler", StandardScaler()),
            ("model", RandomForestRegressor(
                n_estimators=rf_cfg.get("n_estimators", 100),
                max_depth=rf_cfg.get("max_depth", 5),
                min_samples_leaf=rf_cfg.get("min_samples_leaf", 3),
                random_state=random_seed,
            )),
        ]),
        "GradientBoostingRegressor": Pipeline([
            ("scaler", StandardScaler()),
            ("model", GradientBoostingRegressor(
                n_estimators=gb_cfg.get("n_estimators", 100),
                max_depth=gb_cfg.get("max_depth", 3),
                learning_rate=gb_cfg.get("learning_rate", 0.1),
                subsample=gb_cfg.get("subsample", 0.8),
                random_state=random_seed,
            )),
        ]),
    }
    return candidates


def build_quantile_siblings(
    config: dict, random_seed: int = 42
) -> Dict[str, Pipeline]:
    """
    Build quantile regression sibling pipelines for GradientBoostingRegressor uncertainty estimation.

    Trains at q_lo and q_hi quantile levels using StandardScaler matching candidate pipelines.
    Produces prediction intervals [y_pred_lo, y_pred_hi].
    """
    gb_cfg = config.get("GradientBoostingRegressor", {})
    unc_cfg = config.get("uncertainty", {})
    q_lo = unc_cfg.get("quantile_lo", 0.10)
    q_hi = unc_cfg.get("quantile_hi", 0.90)

    return {
        "quantile_lo": Pipeline([
            ("scaler", StandardScaler()),
            ("model", GradientBoostingRegressor(
                loss="quantile",
                alpha=q_lo,
                n_estimators=gb_cfg.get("n_estimators", 100),
                max_depth=gb_cfg.get("max_depth", 3),
                learning_rate=gb_cfg.get("learning_rate", 0.1),
                random_state=random_seed,
            )),
        ]),
        "quantile_hi": Pipeline([
            ("scaler", StandardScaler()),
            ("model", GradientBoostingRegressor(
                loss="quantile",
                alpha=q_hi,
                n_estimators=gb_cfg.get("n_estimators", 100),
                max_depth=gb_cfg.get("max_depth", 3),
                learning_rate=gb_cfg.get("learning_rate", 0.1),
                random_state=random_seed,
            )),
        ]),
    }


# Ordered evaluation sequence for deterministic reporting
CANDIDATE_ORDER = [
    "DummyRegressor",
    "Ridge",
    "RandomForestRegressor",
    "GradientBoostingRegressor",
]
