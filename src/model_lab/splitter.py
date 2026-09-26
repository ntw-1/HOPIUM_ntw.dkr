"""
src/model_lab/splitter.py

Deterministic lot-level Train/Validation/Blind-Test split for Phase 3 Model Lab.

Split rules (from ML_CONTRACT.md):
    - Partitioned at lot_id level — no lot crosses partition boundaries
    - Ratios: ~60% Train / ~20% Validation / ~20% Blind Test
    - Reproducible from a fixed seed + sorted lot list
    - Blind lots are recorded but LOCKED until Phase 8

The split JSON is saved alongside model artifacts for auditability.
"""

import json
import os
from typing import Dict, List, Tuple

import numpy as np


def split_lots(
    lot_ids: List[str],
    seed: int,
    train_frac: float = 0.60,
    val_frac: float = 0.20,
) -> Dict[str, List[str]]:
    """
    Deterministically split a list of lot IDs into train, val, and blind partitions.

    Args:
        lot_ids:    Full list of lot identifiers.
        seed:       RNG seed for reproducible shuffle.
        train_frac: Fraction of lots assigned to training (default 0.60).
        val_frac:   Fraction of lots assigned to validation (default 0.20).

    Returns:
        Dict with keys "train_lots", "val_lots", "blind_lots".
    """
    sorted_lots = sorted(lot_ids)  # deterministic base ordering
    n = len(sorted_lots)

    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(sorted_lots).tolist()

    n_train = round(n * train_frac)
    n_val = round(n * val_frac)
    n_blind = n - n_train - n_val

    train_lots = shuffled[:n_train]
    val_lots = shuffled[n_train: n_train + n_val]
    blind_lots = shuffled[n_train + n_val:]

    assert len(blind_lots) == n_blind
    assert len(set(train_lots) & set(val_lots)) == 0, "Lot overlap: train ∩ val"
    assert len(set(train_lots) & set(blind_lots)) == 0, "Lot overlap: train ∩ blind"
    assert len(set(val_lots) & set(blind_lots)) == 0, "Lot overlap: val ∩ blind"
    assert set(train_lots) | set(val_lots) | set(blind_lots) == set(sorted_lots), \
        "Union of splits does not equal full lot set"

    return {
        "train_lots": train_lots,
        "val_lots": val_lots,
        "blind_lots": blind_lots,
    }


def save_split(
    split: Dict[str, List[str]],
    seed: int,
    output_path: str,
    dataset_id: str = "",
    dataset_sha256: str = "",
) -> None:
    """Persist split metadata to JSON for auditability."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    record = {
        "schema_version": "1.0",
        "split_seed": seed,
        "dataset_id": dataset_id,
        "dataset_sha256": dataset_sha256,
        "train_lots": split["train_lots"],
        "val_lots": split["val_lots"],
        "blind_lots": split["blind_lots"],
        "n_train": len(split["train_lots"]),
        "n_val": len(split["val_lots"]),
        "n_blind": len(split["blind_lots"]),
        "note": (
            "Blind lots are LOCKED until Phase 8 final evaluation. "
            "Blind-test metrics are NOT recorded in Phase 3."
        ),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_split(path: str) -> Dict[str, List[str]]:
    """Load a previously saved split JSON."""
    with open(path, "r", encoding="utf-8") as f:
        record = json.load(f)
    return {
        "train_lots": record["train_lots"],
        "val_lots": record["val_lots"],
        "blind_lots": record["blind_lots"],
    }
