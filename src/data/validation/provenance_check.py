"""
src/data/validation/provenance_check.py

Category 10: Reproducibility / Provenance Validation
Verifies companion .meta.json exists, contains is_synthetic=true, random_seed,
generator_version, and validates canonical UTF-8 SHA-256 hash match against CSV.
"""

import hashlib
import json
import os
from typing import Any, Dict, List


def check_provenance(csv_bytes: bytes, meta_dict: dict = None, meta_path: str = None) -> List[Dict[str, Any]]:
    findings = []

    # 1. Check meta_dict existence
    if meta_dict is None:
        if meta_path and os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_dict = json.load(f)
            except Exception as e:
                findings.append({
                    "category": "provenance",
                    "level": "HARD FAILURE",
                    "check_name": "metadata_file_readable",
                    "message": f"Could not read metadata file at '{meta_path}': {e}",
                    "details": {},
                })
                return findings
        else:
            findings.append({
                "category": "provenance",
                "level": "HARD FAILURE",
                "check_name": "metadata_file_exists",
                "message": f"Companion metadata file missing or not found at '{meta_path}'.",
                "details": {},
            })
            return findings

    findings.append({
        "category": "provenance",
        "level": "INFORMATION",
        "check_name": "metadata_file_exists",
        "message": "Companion metadata file loaded successfully.",
        "details": {},
    })

    # 2. Required metadata fields
    required_meta_keys = ["is_synthetic", "generator_version", "random_seed", "content_hash_sha256", "disclaimer"]
    missing_keys = [k for k in required_meta_keys if k not in meta_dict]

    if missing_keys:
        findings.append({
            "category": "provenance",
            "level": "HARD FAILURE",
            "check_name": "required_metadata_fields",
            "message": f"Companion .meta.json is missing required fields: {missing_keys}",
            "details": {"missing_keys": missing_keys},
        })
    else:
        findings.append({
            "category": "provenance",
            "level": "INFORMATION",
            "check_name": "required_metadata_fields",
            "message": f"All required metadata fields present in .meta.json.",
            "details": {},
        })

    # 3. is_synthetic boolean check
    if not meta_dict.get("is_synthetic", False):
        findings.append({
            "category": "provenance",
            "level": "HARD FAILURE",
            "check_name": "is_synthetic_flag",
            "message": "Field 'is_synthetic' in metadata must be true.",
            "details": {},
        })

    # 4. Canonical UTF-8 SHA-256 Hash Verification
    # Canonicalization: normalize line endings to LF, strip trailing blank lines
    if csv_bytes is not None:
        csv_text = csv_bytes.decode("utf-8", errors="replace")
        canonical_text = csv_text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"
        canonical_bytes = canonical_text.encode("utf-8")
        computed_hash = hashlib.sha256(canonical_bytes).hexdigest()
        stored_hash = meta_dict.get("content_hash_sha256", "")

        if computed_hash != stored_hash:
            findings.append({
                "category": "provenance",
                "level": "HARD FAILURE",
                "check_name": "sha256_content_hash_match",
                "message": f"SHA-256 hash mismatch! Computed: '{computed_hash}', Stored in .meta.json: '{stored_hash}'.",
                "details": {
                    "computed_hash": computed_hash,
                    "stored_hash": stored_hash,
                },
            })
        else:
            findings.append({
                "category": "provenance",
                "level": "INFORMATION",
                "check_name": "sha256_content_hash_match",
                "message": f"Canonical UTF-8 SHA-256 content hash verified ({stored_hash[:12]}...).",
                "details": {"sha256_hash": stored_hash},
            })

    return findings
