"""
src/model_lab/__init__.py

Phase 3 — Module B Model Lab package for HOPIUM_sih26170.

Provides a parameter-specific regression pipeline with deterministic
lot-level Train/Validation/Blind-Test splits, validation-driven model
selection, and a production inference interface.

Production Feature Boundary (enforced in features.py):
    X = [value_0h, value_24h, delta_24_0]     (inputs at 0h and 24h only)
    y = value_168h                              (prediction target)
    FORBIDDEN FROM X: value_96h, value_168h, any ground-truth labels

Blind Test:
    The blind-test lot partition is created and locked in Phase 3.
    Blind-test evaluation is DEFERRED to Phase 8.
"""
