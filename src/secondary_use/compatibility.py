"""Deterministic requirement comparison; UNKNOWN is never treated as PASS."""


def assess_compatibility(evidence: dict, application: dict) -> dict:
    results = []
    for req in application.get("requirements", []):
        param, field = req.get("parameter"), req.get("evidence_field")
        value = evidence.get("measurements", {}).get(param, {}).get(field) if param and field else None
        if value is None:
            status = "UNKNOWN"
        else:
            status = "PASS"
            if "maximum" in req and value > req["maximum"]:
                status = "FAIL"
            if "minimum" in req and value < req["minimum"]:
                status = "FAIL"
        results.append({"requirement_id": req["id"], "status": status, "observed_value": value,
                        "requirement": req, "reason": "evidence unavailable" if status == "UNKNOWN" else
                        ("meets illustrative requirement" if status == "PASS" else "exceeds illustrative requirement")})
    statuses = [r["status"] for r in results]
    overall = "INCOMPATIBLE" if "FAIL" in statuses else ("INSUFFICIENT_EVIDENCE" if not statuses or "UNKNOWN" in statuses else "CANDIDATE")
    return {"application_id": application["id"], "application_name": application["name"],
            "compatibility_status": overall, "requirements": results,
            "missing_evidence": [r["requirement_id"] for r in results if r["status"] == "UNKNOWN"],
            "additional_testing_required": bool(application.get("additional_testing_required", True))}
