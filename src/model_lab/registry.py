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


ACTIVE_MODELS_FILENAME = "active_models.json"
DEFAULT_ACTIVE_MODELS = {
    "Iddq": "module_b_Iddq_v1",
    "leakage_current": "module_b_leakage_current_v1",
    "propagation_delay": "module_b_propagation_delay_v1",
}


def get_active_models(registry_dir: str) -> Dict[str, str]:
    """
    Get the mapping of active deployed models for each parameter.
    If active_models.json is not present, initializes and returns defaults.
    """
    manifest_path = os.path.join(registry_dir, ACTIVE_MODELS_FILENAME)
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Fill any missing defaults
                    res = DEFAULT_ACTIVE_MODELS.copy()
                    res.update(data)
                    return res
        except Exception:
            pass

    # Initialize file if directory exists
    if os.path.exists(registry_dir):
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_ACTIVE_MODELS, f, indent=2)
                f.write("\n")
        except Exception:
            pass

    return DEFAULT_ACTIVE_MODELS.copy()


def get_active_model_id(registry_dir: str, parameter: str) -> str:
    """Get the active model identifier for the given parameter."""
    active = get_active_models(registry_dir)
    return active.get(parameter, f"module_b_{parameter}_v1")


def set_active_model_id(registry_dir: str, parameter: str, model_id: str) -> None:
    """
    Update the active deployed model identifier for a parameter.
    Preserves other parameter mappings in active_models.json.
    """
    active = get_active_models(registry_dir)
    active[parameter] = model_id
    manifest_path = os.path.join(registry_dir, ACTIVE_MODELS_FILENAME)
    os.makedirs(registry_dir, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(active, f, indent=2)
        f.write("\n")


def list_model_versions(registry_dir: str, parameter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List registered model versions and their metadata.
    If parameter is specified, only returns versions for that parameter.
    """
    if not os.path.exists(registry_dir):
        return []

    active_map = get_active_models(registry_dir)
    results = []

    for item in sorted(os.listdir(registry_dir)):
        item_path = os.path.join(registry_dir, item)
        if not os.path.isdir(item_path):
            continue
        if not item.startswith("module_b_"):
            continue

        reg_path = os.path.join(item_path, "registry.json")
        if not os.path.exists(reg_path):
            continue

        try:
            with open(reg_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            p = meta.get("parameter", "")
            if parameter and p != parameter:
                continue

            model_id = meta.get("model_id", item)
            is_active = (active_map.get(p) == model_id)

            results.append({
                "model_id": model_id,
                "parameter": p,
                "selected_model_class": meta.get("selected_model_class", "unknown"),
                "winner_MAE_val": meta.get("winner_MAE_val"),
                "selection_metric": meta.get("selection_metric", "MAE_val"),
                "registered_at_utc": meta.get("registered_at_utc", ""),
                "lab_version": meta.get("lab_version", ""),
                "dataset_id": meta.get("dataset_id", ""),
                "is_active": is_active,
                "all_candidates_metrics": meta.get("all_candidates_metrics", {}),
            })
        except Exception:
            continue

    return results


def get_next_version_id(registry_dir: str, parameter: str) -> str:
    """
    Determine the next sequential version string for a parameter (e.g. 'module_b_Iddq_v2').
    """
    versions = list_model_versions(registry_dir, parameter=parameter)
    max_v = 1
    prefix = f"module_b_{parameter}_v"
    for v in versions:
        m_id = v["model_id"]
        if m_id.startswith(prefix):
            try:
                num = int(m_id[len(prefix):])
                if num > max_v:
                    max_v = num
            except ValueError:
                pass
    return f"module_b_{parameter}_v{max_v + 1}"
