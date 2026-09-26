"""
src/model_lab/selector.py

Model selection based on validation MAE for Phase 3.

Selection rule (ML_CONTRACT.md §3):
    winner = argmin over candidates of MAE_val[parameter, candidate]

Explicitly enforced:
    - Selection uses MAE_val, not MAE_train, not RMSE_val, not MAPE_val.
    - Blind-test information is not available at selection time.
    - Tied MAE_val is broken by CANDIDATE_ORDER (first-listed wins).
"""

from typing import Dict, Tuple

from .candidates import CANDIDATE_ORDER


def select_winner(
    metrics_table: Dict[str, Dict[str, float]],
) -> Tuple[str, float]:
    """
    Select the best candidate based on lowest validation MAE.

    Args:
        metrics_table: Dict from trainer.train_candidates:
                       { candidate_name: { "MAE_val": float, ... }, ... }

    Returns:
        winner_name:    Name of the selected candidate.
        winner_mae_val: Its validation MAE.
    """
    best_name: str = None
    best_mae: float = float("inf")

    # Iterate in canonical order to ensure deterministic tie-breaking
    for name in CANDIDATE_ORDER:
        if name not in metrics_table:
            continue
        mae_val = metrics_table[name]["MAE_val"]
        if mae_val < best_mae:
            best_mae = mae_val
            best_name = name

    if best_name is None:
        raise RuntimeError("No candidates found in metrics_table during selection.")

    return best_name, best_mae
