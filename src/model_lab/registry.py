"""
src/model_lab/registry.py

Model artifact serialization and loading for Phase 3.

Each registered model artifact contains:
    model.pkl         — Fitted sklearn Pipeline (via joblib).
    uncertainty.pkl   — Fitted uncertainty artifact (via joblib).
    registry.json     — Full metadata without blind-test metrics.

Blind-test evaluation is DEFERRED to Phase 8.
The registry records the identity of blind lots, but not their metrics.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import joblib


def register_model(
    output_dir: str,
    model_id: str,
    parameter: str,
    selected_model_name: str,
    fitted_pipeline: Any,
    uncertainty_artifacts: Any,
    metrics_table: Dict[str, Dict[str, float]],
    winner_mae_val: float,
    train_lots: List[str],
    val_lots: List[str],
    blind_lots: List[str],
    split_seed: int,
    dataset_id: str,
    dataset_sha256: str,
    production_features: List[str],
    lab_version: str,
) -> str:
    """
    Persist the fitted model, uncertainty artifact, and metadata JSON.

    Args:
        output_dir:           Root directory for registered models.
        model_id:             Unique model identifier (e.g. 'module_b_Iddq_v1').
        parameter:            Parameter this model predicts.
        selected_model_name:  Name of the winning candidate.
        fitted_pipeline:      Fitted sklearn Pipeline.
        uncertainty_artifacts:Uncertainty artifacts from uncertainty.fit_uncertainty().
        metrics_table:        All candidates' metrics dict.
        winner_mae_val:       Winner's validation MAE.
        train_lots:           Training lot list.
        val_lots:             Validation lot list.
        blind_lots:           Blind lot list (identity only — no metrics).
        split_seed:           Split reproducibility seed.
        dataset_id:           Source dataset identifier.
        dataset_sha256:       SHA-256 of source CSV.
        production_features:  List of features in X.
        lab_version:          Version string for this Model Lab.

    Returns:
        model_dir: Absolute path to the saved model directory.
    """
    model_dir = os.path.join(output_dir, model_id)
    os.makedirs(model_dir, exist_ok=True)

    # Serialize fitted pipeline
    pipeline_path = os.path.join(model_dir, "model.pkl")
    joblib.dump(fitted_pipeline, pipeline_path)

    # Serialize uncertainty artifacts (strip non-serializable if needed — all are sklearn/numpy)
    unc_path = os.path.join(model_dir, "uncertainty.pkl")
    joblib.dump(uncertainty_artifacts, unc_path)

    # Build registry.json metadata
    all_candidates_val_mae = {
        name: round(m["MAE_val"], 6)
        for name, m in metrics_table.items()
    }
    all_candidates_metrics = {
        name: {k: round(v, 6) for k, v in m.items()}
        for name, m in metrics_table.items()
    }

    registry = {
        "schema_version": "1.0",
        "model_id": model_id,
        "parameter": parameter,
        "target": "value_168h",
        "production_features": production_features,
        "forbidden_features": ["value_96h", "value_168h"],
        "selected_model_class": selected_model_name,
        "selection_metric": "MAE_val",
        "winner_MAE_val": round(winner_mae_val, 6),
        "all_candidates_val_MAE": all_candidates_val_mae,
        "all_candidates_metrics": all_candidates_metrics,
        "dataset_id": dataset_id,
        "dataset_sha256": dataset_sha256,
        "split_seed": split_seed,
        "train_lots": train_lots,
        "val_lots": val_lots,
        "blind_lots_identity": blind_lots,
        "blind_test_metrics": "DEFERRED — Phase 8 final evaluation only.",
        "uncertainty_method": uncertainty_artifacts.get("method", "unknown"),
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
        "lab_version": lab_version,
        "notes": (
            "blind_lots_identity records which lots are locked for Phase 8. "
            "No predictions or metrics have been computed on blind lots in Phase 3."
        ),
    }

    registry_path = os.path.join(model_dir, "registry.json")
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return model_dir


def load_model(model_dir: str) -> dict:
    """
    Load a registered model artifact from disk.

    Args:
        model_dir: Path to the model directory containing model.pkl,
                   uncertainty.pkl, and registry.json.

    Returns:
        Dict with keys:
            pipeline:             Fitted sklearn Pipeline.
            uncertainty_artifacts:Fitted uncertainty artifact.
            registry:             Registry metadata dict.
    """
    pipeline_path = os.path.join(model_dir, "model.pkl")
    unc_path = os.path.join(model_dir, "uncertainty.pkl")
    registry_path = os.path.join(model_dir, "registry.json")

    for path in [pipeline_path, registry_path]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Artifact missing: {path}")

    pipeline = joblib.load(pipeline_path)
    uncertainty_artifacts = joblib.load(unc_path) if os.path.exists(unc_path) else {}

    with open(registry_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    return {
        "pipeline": pipeline,
        "uncertainty_artifacts": uncertainty_artifacts,
        "registry": registry,
    }
