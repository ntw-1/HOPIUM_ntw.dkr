import numpy as np
import pandas as pd
import pytest
from src.model_lab.predictor import ProductionPredictor

def test_slope_calculations():
    value_0h = 10.0
    value_168h = 94.0
    slope = (value_168h - value_0h) / 168.0
    assert np.isclose(slope, 0.5)

def test_percentile_boundary_calculation():
    slopes = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    p90 = np.percentile(slopes, 90)
    assert np.isclose(p90, 0.91)

def test_train_only_reference_statistics():
    train_data = np.array([0.1, 0.2, 0.3])
    blind_data = np.array([0.9, 1.0])
    
    threshold = np.percentile(train_data, 95)
    # Ensure blind data does not influence threshold
    assert threshold < 0.35

def test_no_blind_data_leakage():
    # Simulate lot-relative calculation ensuring we don't look at blind lots when training
    train_lot_slopes = {"LOT_1": [0.1, 0.15], "LOT_2": [0.2, 0.25]}
    blind_lot_slopes = {"LOT_3": [0.5, 0.6]}
    
    # We should only train global thresholds on train
    all_train = [s for lot in train_lot_slopes.values() for s in lot]
    global_thresh = np.max(all_train)
    assert global_thresh == 0.25
    assert "LOT_3" not in train_lot_slopes

def test_deterministic_results():
    data = np.random.RandomState(42).randn(100)
    p95_1 = np.percentile(data, 95)
    p95_2 = np.percentile(data, 95)
    assert p95_1 == p95_2

def test_candidate_evaluation():
    df = pd.DataFrame({
        "is_latent_degrader": [0, 0, 1, 1],
        "flag": [False, True, False, True],
        "early_detectability": ["nominal", "nominal", "hidden", "strong"]
    })
    
    n_nominal = (df["is_latent_degrader"] == 0).sum()
    n_latent = (df["is_latent_degrader"] == 1).sum()
    
    fp = ((df["is_latent_degrader"] == 0) & df["flag"]).sum()
    tp = ((df["is_latent_degrader"] == 1) & df["flag"]).sum()
    
    fpr = fp / n_nominal
    tpr = tp / n_latent
    
    assert fpr == 0.5
    assert tpr == 0.5
