import os
import yaml
import json
import pytest
import pandas as pd
from src.data.synthetic.generator import SyntheticDataEngine

def test_v2_deterministic_regeneration():
    config_path = "configs/synthetic_config_v2.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)["synthetic_generator_config"]
    
    engine1 = SyntheticDataEngine(config=config, seed=42)
    rows1, cgt1, pgt1 = engine1.generate(num_lots=2, components_per_lot=10)
    
    engine2 = SyntheticDataEngine(config=config, seed=42)
    rows2, cgt2, pgt2 = engine2.generate(num_lots=2, components_per_lot=10)
    
    # Check that outputs are perfectly identical
    assert len(rows1) == len(rows2)
    for r1, r2 in zip(rows1, rows2):
        assert r1.value_168h == r2.value_168h

def test_v2_schema_compatibility():
    config_path = "configs/synthetic_config_v2.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)["synthetic_generator_config"]
    
    engine = SyntheticDataEngine(config=config, seed=42)
    rows, _, _ = engine.generate(num_lots=1, components_per_lot=10)
    
    row = rows[0]
    assert hasattr(row, "value_0h")
    assert hasattr(row, "value_24h")
    assert hasattr(row, "value_96h")
    assert hasattr(row, "value_168h")
    assert not hasattr(row, "value_48h") # Check forbidden
    
def test_v2_propagation_delay_non_identical():
    df = pd.read_csv("data/v2/dev_burnin_data.csv")
    with open("data/v2/dev_burnin_groundtruth.json", "r") as f:
        gt = {c["component_id"]: c for c in json.load(f)["component_level"]}
        
    df["is_latent_degrader"] = df["component_id"].map(lambda c: gt[c]["is_latent_degrader"])
    df["early_detectability"] = df["component_id"].map(lambda c: gt[c].get("early_detectability"))
    
    prop = df[df["parameter_name"] == "propagation_delay"]
    nom = prop[prop["is_latent_degrader"] == False]
    lat = prop[prop["is_latent_degrader"] == True]
    
    # Must have non-identical distributions
    assert abs(nom["value_168h"].mean() - lat["value_168h"].mean()) > 1.0

def test_v2_nonzero_hidden_early_signal():
    df = pd.read_csv("data/v2/dev_burnin_data.csv")
    with open("data/v2/dev_burnin_groundtruth.json", "r") as f:
        gt = {c["component_id"]: c for c in json.load(f)["component_level"]}
        
    df["is_latent_degrader"] = df["component_id"].map(lambda c: gt[c]["is_latent_degrader"])
    df["early_detectability"] = df["component_id"].map(lambda c: gt[c].get("early_detectability"))
    
    iddq = df[df["parameter_name"] == "Iddq"]
    hidden = iddq[(iddq["is_latent_degrader"] == True) & (iddq["early_detectability"] == "hidden")]
    
    delta = hidden["value_24h"] - hidden["value_0h"]
    assert delta.mean() > 0.1 # Must be strictly positive and nonzero early signal
