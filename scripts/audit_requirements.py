#!/usr/bin/env python3
import json
import os

def main():
    output_dir = "reports/evaluation"
    os.makedirs(output_dir, exist_ok=True)
    
    # Audit answers
    audit = [
        {
            "question": "1. Does the PS explicitly require: Value_0h, Value_24h -> forecast Value_168h?",
            "original_ps": "NOT ESTABLISHED (Original Problem Statement document is NOT available in the repository).",
            "contract": "SUPPORTED BY OUR PROJECT CONTRACTS. (PRODUCT_SPEC.md: 'predict parameter behavior at 168h using only 0h and 24h production inputs'; ML_CONTRACT.md establishes X and y).",
            "implementation": "OUR CURRENT IMPLEMENTATION CHOICE. (Phase 3 currently uses exactly value_0h, value_24h, delta_24_0 to predict value_168h).",
            "confidence": "High (for contract/implementation), Unknown (for PS)"
        },
        {
            "question": "2. Does the wording mean Value_0h and Value_24h are the ONLY permitted production features?",
            "original_ps": "NOT ESTABLISHED (PS not found).",
            "contract": "SUPPORTED BY OUR PROJECT CONTRACTS. (ML_CONTRACT.md: 'Module B only receives early production inputs').",
            "implementation": "OUR CURRENT IMPLEMENTATION CHOICE. (Restricted to these two timepoints).",
            "confidence": "High (contract interpretation)"
        },
        {
            "question": "3. Is Value_96h explicitly prohibited as a Module B prediction input, or is it simply not mentioned?",
            "original_ps": "NOT ESTABLISHED (PS not found).",
            "contract": "SUPPORTED BY OUR PROJECT CONTRACTS. (ML_CONTRACT.md and AGENTS.md explicitly list Value_96h as 'Strictly Forbidden Inputs').",
            "implementation": "OUR CURRENT IMPLEMENTATION CHOICE. (Forbidden).",
            "confidence": "High (contract interpretation)"
        },
        {
            "question": "4. Is Value_168h explicitly the prediction target rather than an input?",
            "original_ps": "NOT ESTABLISHED (PS not found).",
            "contract": "SUPPORTED BY OUR PROJECT CONTRACTS. (ML_CONTRACT.md: 'Ground Truth Target y = value_168h').",
            "implementation": "OUR CURRENT IMPLEMENTATION CHOICE.",
            "confidence": "High"
        },
        {
            "question": "5. Are derived features such as delta_24_0 permitted?",
            "original_ps": "NOT ESTABLISHED (PS not found).",
            "contract": "SUPPORTED BY OUR PROJECT CONTRACTS. (AGENTS.md: 'and engineered features derived solely from Value_0h and Value_24h, e.g., delta_24_0').",
            "implementation": "OUR CURRENT IMPLEMENTATION CHOICE.",
            "confidence": "High"
        },
        {
            "question": "6. Does the PS permit additional derived features calculated exclusively from Value_0h and Value_24h?",
            "original_ps": "NOT ESTABLISHED (PS not found).",
            "contract": "SUPPORTED BY OUR PROJECT CONTRACTS. (AGENTS.md explicitly permits 'features derived solely from Value_0h and Value_24h').",
            "implementation": "OUR CURRENT IMPLEMENTATION CHOICE. (Permitted, though only delta_24_0 is currently used).",
            "confidence": "High"
        },
        {
            "question": "7. Does the PS permit additional EARLY timepoints before 168h, if available?",
            "original_ps": "NOT ESTABLISHED (PS not found).",
            "contract": "AMBIGUOUS / NOT ESTABLISHED. (DATA_CONTRACT.md lists 0h, 24h, 96h, 168h. 96h is forbidden. No other early timepoints like 48h or 72h are mentioned).",
            "implementation": "OUR CURRENT IMPLEMENTATION CHOICE. (Only 0h and 24h are used).",
            "confidence": "Medium (implicitly prohibited by exact whitelist of 0h/24h)"
        },
        {
            "question": "8. Would using Value_96h to predict Value_168h clearly violate the PS, or is that an interpretation that needs qualification?",
            "original_ps": "NOT ESTABLISHED (PS not found).",
            "contract": "SUPPORTED BY OUR PROJECT CONTRACTS. (It clearly violates ML_CONTRACT.md and AGENTS.md).",
            "implementation": "OUR CURRENT IMPLEMENTATION CHOICE.",
            "confidence": "High"
        },
        {
            "question": "9. Does the phrase 'takes Value_0h and Value_24h as inputs' establish a strict two-timepoint constraint, or merely describe the required/example inputs?",
            "original_ps": "NOT ESTABLISHED (PS not found).",
            "contract": "SUPPORTED BY OUR PROJECT CONTRACTS. (The project contract interpreted this as a strict, exclusive two-timepoint constraint by forbidding 96h).",
            "implementation": "OUR CURRENT IMPLEMENTATION CHOICE.",
            "confidence": "High (we established the strict constraint)"
        },
        {
            "question": "10. What exactly does the PS say about: predicted drift, safety slope, flagging components, false negatives, explainability?",
            "original_ps": "NOT ESTABLISHED (Original PS not found).",
            "contract": "SUPPORTED BY OUR PROJECT CONTRACTS. (PRODUCT_SPEC.md states 'Provide dynamic safety score and risk boundaries based on population variance, predicted drift, and distance to datasheet specs, avoiding arbitrary static limits').",
            "implementation": "OUR CURRENT IMPLEMENTATION CHOICE. (Phase 5 uses absolute drift normalized by spec range, which earlier audits showed fails to act as a proper safety slope).",
            "confidence": "High"
        }
    ]
    
    json_path = os.path.join(output_dir, "module_b_input_requirements_audit.json")
    with open(json_path, "w") as f:
        json.dump(audit, f, indent=2)
        
    md_path = os.path.join(output_dir, "module_b_input_requirements_audit.md")
    with open(md_path, "w") as f:
        f.write("# Module B Input Requirements Audit\n\n")
        f.write("## ORIGINAL PROBLEM STATEMENT STATUS\n")
        f.write("**IMPORTANT:** The original SIH26170 problem statement document is **NOT** available in the repository. Therefore, the exact, verbatim original requirements cannot be definitively verified. All constraints we currently enforce are based on the project's internal contract documents (`PRODUCT_SPEC.md`, `ML_CONTRACT.md`, `AGENTS.md`, etc.).\n\n")
        
        f.write("## AUDIT TABLE\n\n")
        f.write("| Question | Original PS evidence | Contract interpretation | Current implementation | Confidence |\n")
        f.write("|----------|----------------------|-------------------------|------------------------|------------|\n")
        
        for item in audit:
            q = item["question"]
            ps = item["original_ps"]
            con = item["contract"]
            imp = item["implementation"]
            conf = item["confidence"]
            f.write(f"| {q} | {ps} | {con} | {imp} | {conf} |\n")
            
        f.write("\n## SUMMARY\n")
        f.write("1. **Original PS**: Not found in repo.\n")
        f.write("2. **Current Constraints**: Our project contracts (`ML_CONTRACT.md`, `AGENTS.md`) strictly enforce `Value_0h` and `Value_24h` as the ONLY permitted raw timepoints, and explicitly forbid `Value_96h` and `Value_168h` as inputs.\n")
        f.write("3. **Derived Features**: The contracts explicitly permit derived features calculated *solely* from `0h` and `24h` (such as `delta_24_0`).\n")
        f.write("4. **Interpretation**: The strict prohibition of `Value_96h` is a documented contract rule (likely our own conservative interpretation of the PS phrase 'takes Value_0h and Value_24h as inputs'). Without the original PS, we cannot determine if the SIH organizers would have permitted `96h` as an additional input, but our architecture definitively forbids it.\n")

if __name__ == "__main__":
    main()
