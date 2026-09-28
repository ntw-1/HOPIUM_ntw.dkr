import os
import sys
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.data.synthetic.exporter import export_dataset
from src.data.synthetic.generator import SyntheticDataEngine

def main():
    config_path = "configs/synthetic_config_v2.yaml"
    output_dir = "data/v2"
    os.makedirs(output_dir, exist_ok=True)
    
    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)
    config = raw["synthetic_generator_config"]

    seed = config["random_seed"]
    version = config["generator_version"]
    engine = SyntheticDataEngine(config=config, seed=seed)

    # -------------------------------------------------------------------------
    # Development dataset
    # -------------------------------------------------------------------------
    dev_cfg = config["dataset_sizes"]["dev"]
    num_lots_dev = dev_cfg["num_lots"]
    cpl_dev = dev_cfg["components_per_lot"]

    print(f"Generating V2 development dataset: {num_lots_dev} lots × {cpl_dev} components/lot ...")
    rows_dev, cgt_dev, pgt_dev = engine.generate(
        num_lots=num_lots_dev, components_per_lot=cpl_dev
    )
    meta_dev = export_dataset(
        rows=rows_dev,
        component_gt=cgt_dev,
        parameter_gt=pgt_dev,
        csv_path=os.path.join(output_dir, "dev_burnin_data.csv"),
        meta_path=os.path.join(output_dir, "dev_burnin_data.meta.json"),
        groundtruth_path=os.path.join(output_dir, "dev_burnin_groundtruth.json"),
        dataset_id=f"dev_burnin_data_seed{seed}_v2",
        generator_version=version,
        random_seed=seed,
        config_snapshot={"num_lots": num_lots_dev, "components_per_lot": cpl_dev},
    )
    print(f"  -> {len(rows_dev)} rows written.")
    print(f"  -> SHA-256: {meta_dev.content_hash_sha256}")

    # -------------------------------------------------------------------------
    # Demonstration dataset
    # -------------------------------------------------------------------------
    demo_cfg = config["dataset_sizes"]["demo"]
    num_lots_demo = demo_cfg["num_lots"]
    cpl_demo = demo_cfg["components_per_lot"]

    print(f"\nGenerating V2 demonstration dataset: {num_lots_demo} lots × {cpl_demo} components/lot ...")
    rows_demo, cgt_demo, pgt_demo = engine.generate_demo(
        num_lots=num_lots_demo, components_per_lot=cpl_demo
    )
    meta_demo = export_dataset(
        rows=rows_demo,
        component_gt=cgt_demo,
        parameter_gt=pgt_demo,
        csv_path=os.path.join(output_dir, "demo_burnin_data.csv"),
        meta_path=os.path.join(output_dir, "demo_burnin_data.meta.json"),
        groundtruth_path=os.path.join(output_dir, "demo_burnin_groundtruth.json"),
        dataset_id=f"demo_burnin_data_seed{seed}_v2",
        generator_version=version,
        random_seed=seed,
        config_snapshot={"num_lots": num_lots_demo, "components_per_lot": cpl_demo},
    )
    print(f"  -> {len(rows_demo)} rows written.")
    print(f"  -> SHA-256: {meta_demo.content_hash_sha256}")

if __name__ == "__main__":
    main()
