"""
src/data/synthetic/trajectories.py

Configurable trajectory family functions for synthetic burn-in data generation.

IMPORTANT: All trajectory equations in this module are SYNTHETIC MODELLING
ASSUMPTIONS chosen to produce plausible-looking burn-in trajectories for
algorithm testing. They are NOT empirically validated semiconductor degradation
laws and must NOT be represented as such.

Trajectory families implemented:
    stable_mild     — Sub-linear logarithmic stabilization curve.
    accelerating    — Super-linear post-24h acceleration (latent degradation).
    step_jump       — Abrupt step injection (reference-limit breach scenario).

All functions accept time in hours and return a scalar drift offset to be
added to the component baseline value.
"""

import numpy as np
from typing import Optional


# ---------------------------------------------------------------------------
# Trajectory family: stable_mild
# ---------------------------------------------------------------------------

def stable_mild(
    t: float,
    k: float,
    t0: float,
) -> float:
    """
    Stable / mild drift trajectory.

        f(t) = k * ln(1 + t / t0)

    Models gradual thermal stabilization of a nominal component.
    Saturates for large t; never explosive.

    SYNTHETIC MODELLING ASSUMPTION — not an empirical degradation law.

    Parameters
    ----------
    t : float
        Time in hours (0, 24, 96, 168).
    k : float
        Amplitude scale factor (configurable).
    t0 : float
        Time constant in hours (configurable).

    Returns
    -------
    float
        Drift offset added to the baseline at time t.
    """
    return k * np.log1p(t / t0)


# ---------------------------------------------------------------------------
# Trajectory family: accelerating
# ---------------------------------------------------------------------------

def accelerating(
    t: float,
    k: float,
    exponent: float,
    onset_h: float = 24.0,
    early_scale: float = 0.0,
) -> float:
    """
    Accelerating drift trajectory (latent degradation family).

        f(t) = k * ((t - onset_h) / 24) ^ exponent   for t > onset_h
             = early_scale * t / onset_h               for t <= onset_h

    Models a component that looks nearly nominal early on but accelerates
    post-onset. The early_scale parameter controls how much 0h->24h signal
    is visible (governing early detectability):

        early_scale = 0.0   -> completely hidden at 24h
        early_scale > 0.0   -> some early slope visible at 24h

    SYNTHETIC MODELLING ASSUMPTION — not an empirical degradation law.

    Parameters
    ----------
    t : float
        Time in hours.
    k : float
        Acceleration amplitude (configurable per parameter).
    exponent : float
        Super-linearity exponent (>= 1.0). Higher = more sharply accelerating.
    onset_h : float
        Time in hours at which acceleration begins (default 24h).
    early_scale : float
        Scale of early drift visible at or before onset_h.
        0.0 = completely hidden; larger = more detectable at 24h.

    Returns
    -------
    float
        Drift offset at time t.
    """
    if t <= onset_h:
        # Small early drift; magnitude controlled by early_scale
        return early_scale * (t / onset_h)
    else:
        post = t - onset_h
        return early_scale + k * ((post / 24.0) ** exponent)


# ---------------------------------------------------------------------------
# Trajectory family: step_jump
# ---------------------------------------------------------------------------

def step_jump(
    t: float,
    k: float,
    jump_time_h: float = 0.0,
) -> float:
    """
    Step / rapid jump trajectory.

        f(t) = k   if t >= jump_time_h
             = 0   otherwise

    Models a sudden parametric excursion used to inject reference_limit_breach
    scenarios. The jump may occur at t=0h (immediately visible) or later.

    SYNTHETIC MODELLING ASSUMPTION — not an empirical degradation law.

    Parameters
    ----------
    t : float
        Time in hours.
    k : float
        Step amplitude (may be negative for downward steps).
    jump_time_h : float
        Time in hours at which the step occurs (default 0h = instantly visible).

    Returns
    -------
    float
        Drift offset at time t.
    """
    return k if t >= jump_time_h else 0.0


# ---------------------------------------------------------------------------
# Dispatch function: select and evaluate trajectory family by name
# ---------------------------------------------------------------------------

# Early detectability -> early_scale mapping.
# These values are SYNTHETIC MODELLING ASSUMPTIONS.
EARLY_DETECTABILITY_SCALE = {
    "hidden":   0.00,   # No visible early signal; only noise at 24h
    "subtle":   0.15,   # Slightly elevated Delta_24_0; partially visible
    "moderate": 0.40,   # Clearly elevated Delta_24_0
    "strong":   0.80,   # Very steep early slope
}


def evaluate_trajectory(
    family: str,
    t: float,
    param_cfg: dict,
    early_detectability: Optional[str] = None,
    step_k: Optional[float] = None,
    jump_time_h: float = 0.0,
    comp_id: str = "",
) -> float:
    """
    Dispatch function: evaluate the named trajectory family at time t.
    """
    if family == "stable_mild":
        return stable_mild(
            t=t,
            k=param_cfg["stable_mild_k"],
            t0=param_cfg["stable_mild_t0"],
        )

    elif family == "accelerating":
        scale = EARLY_DETECTABILITY_SCALE.get(early_detectability or "hidden", 0.0)
        early = scale * param_cfg["latent_drift_k"]
        return accelerating(
            t=t,
            k=param_cfg["latent_drift_k"],
            exponent=param_cfg["accelerating_exponent"],
            onset_h=24.0,
            early_scale=early,
        )

    elif family == "accelerating_v2":
        import hashlib
        # Deterministic but continuous latent strength per component
        seed_str = f"{comp_id}_{param_cfg['unit']}_{early_detectability}"
        seed_int = int(hashlib.md5(seed_str.encode('utf-8')).hexdigest(), 16) % (2**32)
        rng = np.random.RandomState(seed_int)
        
        # Overlapping distributions for latent_strength
        # hidden ~ N(0.1, 0.05), subtle ~ N(0.3, 0.1), mod ~ N(0.6, 0.15), strong ~ N(1.0, 0.2)
        means = {"hidden": 0.1, "subtle": 0.3, "moderate": 0.6, "strong": 1.0}
        stds = {"hidden": 0.05, "subtle": 0.1, "moderate": 0.15, "strong": 0.2}
        
        ed = early_detectability or "hidden"
        mu = means.get(ed, 0.1)
        sigma = stds.get(ed, 0.05)
        
        latent_strength = max(0.0, rng.normal(mu, sigma))
        
        return accelerating_v2(
            t=t,
            k=param_cfg["latent_drift_k"],
            exponent=param_cfg["accelerating_exponent"],
            onset_h=24.0,
            latent_strength=latent_strength,
            stable_k=param_cfg["stable_mild_k"],
            stable_t0=param_cfg["stable_mild_t0"],
        )

    elif family == "step_jump":
        if step_k is None:
            raise ValueError("step_k must be provided for step_jump trajectory family.")
        return step_jump(t=t, k=step_k, jump_time_h=jump_time_h)

    else:
        raise ValueError(
            f"Unknown trajectory family: '{family}'."
        )

# ---------------------------------------------------------------------------
# Trajectory family: accelerating_v2
# ---------------------------------------------------------------------------

def accelerating_v2(
    t: float,
    k: float,
    exponent: float,
    onset_h: float = 24.0,
    latent_strength: float = 0.0,
    stable_k: float = 0.0,
    stable_t0: float = 24.0,
) -> float:
    """
    V2 Accelerating drift trajectory.
    
    Fixes the V1 observability issue:
    1. Early drift is base_nominal_drift + (latent_strength * k * 0.1) * (t/onset)
    2. Late drift continues accelerating scaled by latent_strength.
    
    This ensures latent degraders always drift AT LEAST as much as nominals,
    and their future acceleration is causally linked to their early extra drift.
    """
    base_drift = stable_k * np.log1p(t / stable_t0)
    
    extra = 0.0
    if t <= onset_h:
        extra = latent_strength * k * 0.15 * (t / onset_h)
    else:
        post = t - onset_h
        early_accum = latent_strength * k * 0.15
        extra = early_accum + latent_strength * k * ((post / 24.0) ** exponent)
        
    return base_drift + extra
