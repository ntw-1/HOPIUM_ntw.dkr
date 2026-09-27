# SIH26170 Authoritative Input Requirements

## A. Source found / not found
**NOT FOUND.** 
A comprehensive search of the repository, including all documentation (`docs/`), root directory files, and data directories, yielded no PDF, DOCX, TXT, or XLSX file containing the original authoritative SIH26170 problem statement. 

## B. Exact relevant wording
**N/A.** Because the original problem statement document is missing from the repository, no authoritative verbatim wording can be extracted.

## C. Explicitly required inputs
**UNKNOWN.** Without the original document, it is impossible to determine what the SIH organizers explicitly demanded as absolute requirements.

## D. Explicitly prohibited inputs
**UNKNOWN.** We cannot verify whether the SIH organizers explicitly prohibited `Value_96h` or `Value_168h` as prediction inputs, or if they simply omitted them from an example list.

## E. Ambiguous/unspecified inputs
**UNKNOWN.** Any assessment of ambiguity requires analyzing the original phrasing, which is currently unavailable.

## F. Consequences for our current 0h/24h-only contract
Because the authoritative source is missing, our current `ML_CONTRACT.md` restriction—which strictly limits Module B to `[value_0h, value_24h, delta_24_0]` and explicitly forbids `value_96h`—must be treated as an internal project decision rather than a verified external requirement. 
However, without confirming the true external requirements, we cannot justify abandoning our current contract yet. Our restrictive `0h/24h-only` policy must remain in effect until the original problem statement is recovered and proves that additional early telemetry is permitted.
