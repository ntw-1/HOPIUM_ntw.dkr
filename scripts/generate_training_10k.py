"""Generate the HOPIUM-native 10,000-component Model Lab training dataset."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.synthetic.exporter import export_dataset
from src.data.synthetic.generator import SyntheticDataEngine


def main() -> None:
    config_path = Path("configs/synthetic_config_v2.yaml")
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)["synthetic_generator_config"]

    dataset_cfg = config["dataset_sizes"]["training_10k"]
    seed = config["random_seed"]
    engine = SyntheticDataEngine(config=config, seed=seed)
    rows, component_gt, parameter_gt = engine.generate(
        num_lots=dataset_cfg["num_lots"],
        components_per_lot=dataset_cfg["components_per_lot"],
    )

    output_dir = Path("data/v2")
    output_dir.mkdir(parents=True, exist_ok=True)
    meta = export_dataset(
        rows=rows,
        component_gt=component_gt,
        parameter_gt=parameter_gt,
        csv_path=str(output_dir / "training_10k_burnin_data.csv"),
        meta_path=str(output_dir / "training_10k_burnin_data.meta.json"),
        groundtruth_path=str(output_dir / "training_10k_burnin_groundtruth.json"),
        dataset_id=f"training_10k_burnin_data_seed{seed}_v2",
        generator_version=config["generator_version"],
        random_seed=seed,
        config_snapshot={
            "num_lots": dataset_cfg["num_lots"],
            "components_per_lot": dataset_cfg["components_per_lot"],
        },
    )
    print(
        f"Generated {len(rows)} trajectory rows for "
        f"{dataset_cfg['num_lots']} lots × {dataset_cfg['components_per_lot']} components; "
        f"SHA-256: {meta.content_hash_sha256}"
    )


if __name__ == "__main__":
    main()
