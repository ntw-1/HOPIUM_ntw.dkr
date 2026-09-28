import os
import sys
import pandas as pd
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.screening.service import ScreeningService

def main():
    print("Testing End-to-End Screening Pipeline on V2...")
    service = ScreeningService(
        registry_dir="models/registered",
        risk_config_path="configs/risk_engine_config.yaml"
    )
    
    csv_path = "data/v2/dev_burnin_data.csv"
    gt_path = "data/v2/dev_burnin_groundtruth.json"
    
    with open(gt_path, "r") as f:
        gt_dict = {c["component_id"]: c for c in json.load(f)["component_level"]}
    
    # Process using the service
    report = service.run_screening(csv_path)
    
    # Inspect Module A, Risk Engine, and Module B
    results = {
        "anomalous_count": 0,
        "risk_distribution": {"LOW": 0, "MEDIUM": 0, "HIGH": 0},
        "sample_components": []
    }
    
    # Only test with LOT_001
    lot_result = report.lot_results["LOT_001"]
    
    for c_rep in lot_result.component_results:
        if c_rep.is_population_anomaly or c_rep.is_reference_breach:
            results["anomalous_count"] += 1
            
        results["risk_distribution"][c_rep.overall_risk_level] += 1
        
    # Get representative components
    low = next((c for c in lot_result.component_results if c.overall_risk_level == "LOW"), None)
    med = next((c for c in lot_result.component_results if c.overall_risk_level == "MEDIUM"), None)
    high = next((c for c in lot_result.component_results if c.overall_risk_level == "HIGH"), None)
    anom = next((c for c in lot_result.component_results if c.is_population_anomaly), None)
    
    for rep, name in [(low, "LOW"), (med, "MEDIUM"), (high, "HIGH"), (anom, "ANOMALOUS")]:
        if not rep: continue
        results["sample_components"].append({
            "type": name,
            "component_id": rep.component_id,
            "is_anomalous": rep.is_population_anomaly,
            "risk_level": rep.overall_risk_level,
            "module_b_predictions": {
                p: {
                    "pred_168h": float(p_rep.predicted_168h),
                    "lower": float(p_rep.lower_bound_168h),
                    "upper": float(p_rep.upper_bound_168h)
                } for p, p_rep in rep.parameters.items() if p_rep.predicted_168h is not None
            },
            "reasons": rep.recommendation_context
        })
        
        # Test HITL
        decision = "PASS" if name == "LOW" else ("MONITOR" if name == "MEDIUM" else "REJECT")
        service.record_human_decision(
            component_result=rep,
            engineer_decision=decision,
            engineer_reason=f"Testing {name} decision",
        )
        
    # Export audit log
    audit_path = "reports/v2_test_audit_log.csv"
    service.export_audit_log(report, output_path=audit_path)
    
    with open("reports/evaluation/v2_pipeline_test.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print(json.dumps(results, indent=2))
    print(f"Audit log saved to {audit_path}")
    print("Testing Complete.")

if __name__ == "__main__":
    main()
