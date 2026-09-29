"""
src/model_lab/predictor.py

Production prediction interface for Module B (Phase 3).

Provides a clean production inference API:
    predictor = ProductionPredictor.from_registry(registry_dir, parameter)
    result = predictor.predict(X_production)

    Or predict on raw single-component values:
    result = predictor.predict_single(value_0h=10.0, value_24h=10.5)

Returns predictions and lightweight uncertainty estimates.
Assumes features X have been passed or constructed strictly as [value_0h, value_24h, delta_24_0].
"""

import os
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd

from .features import PRODUCTION_FEATURE_ALLOWLIST, _assert_feature_boundary
from .registry import load_model
from .uncertainty import predict_with_uncertainty


class ProductionPredictor:
    """Production predictor for a single parameter using a registered model artifact."""

    def __init__(
        self,
        parameter: str,
        pipeline: object,
        uncertainty_artifacts: dict,
        registry_meta: dict,
    ):
        self.parameter = parameter
        self.pipeline = pipeline
        self.uncertainty_artifacts = uncertainty_artifacts
        self.registry_meta = registry_meta
        self.model_id = registry_meta.get("model_id", f"module_b_{parameter}_v1")
        self.selected_model_class = registry_meta.get("selected_model_class", "unknown")

    @classmethod
    def from_registry(
        cls,
        registry_dir: str,
        parameter: str,
        model_id: Optional[str] = None,
    ) -> "ProductionPredictor":
        """
        Load a ProductionPredictor for the specified parameter from the registry directory.
        If model_id is not specified, dynamically loads the currently active model from active_models.json.

        Args:
            registry_dir: Path to directory containing registered models (e.g. 'models/registered').
            parameter:    Parameter name ('Iddq', 'leakage_current', 'propagation_delay').
            model_id:     Optional explicit model directory name.
        """
        if model_id is None:
            from .registry import get_active_model_id
            model_id = get_active_model_id(registry_dir, parameter)

        model_dir = os.path.join(registry_dir, model_id)
        artifacts = load_model(model_dir)
        return cls(
            parameter=parameter,
            pipeline=artifacts["pipeline"],
            uncertainty_artifacts=artifacts["uncertainty_artifacts"],
            registry_meta=artifacts["registry"],
        )


    def predict(self, X: pd.DataFrame) -> Dict[str, Union[np.ndarray, str]]:
        """
        Predict 168h drift value and uncertainty bounds for a production feature DataFrame.

        Args:
            X: DataFrame with columns strictly matching [value_0h, value_24h, delta_24_0].

        Returns:
            Dict containing:
                predictions:        np.ndarray of predicted value_168h.
                lower_bounds:       np.ndarray of lower uncertainty bound.
                upper_bounds:       np.ndarray of upper uncertainty bound.
                uncertainty_method: str describing uncertainty method.
                parameter:          str parameter name.
                model_id:           str model identifier.
        """
        _assert_feature_boundary(X)

        res = predict_with_uncertainty(X, self.pipeline, self.uncertainty_artifacts)
        return {
            "predictions": res["predictions"],
            "lower_bounds": res["lower_bounds"],
            "upper_bounds": res["upper_bounds"],
            "uncertainty_method": res["uncertainty_method"],
            "parameter": self.parameter,
            "model_id": self.model_id,
        }

    def predict_single(self, value_0h: float, value_24h: float) -> Dict[str, Union[float, str]]:
        """
        Predict 168h drift value for a single component measurement.

        Args:
            value_0h:  Measurement at 0h.
            value_24h: Measurement at 24h.

        Returns:
            Dict containing single float prediction, lower_bound, upper_bound, etc.
        """
        delta_24_0 = value_24h - value_0h
        X_single = pd.DataFrame([{
            "value_0h": value_0h,
            "value_24h": value_24h,
            "delta_24_0": delta_24_0,
        }])
        res = self.predict(X_single)
        return {
            "prediction": float(res["predictions"][0]),
            "lower_bound": float(res["lower_bounds"][0]),
            "upper_bound": float(res["upper_bounds"][0]),
            "uncertainty_method": str(res["uncertainty_method"]),
            "parameter": self.parameter,
            "model_id": self.model_id,
        }
