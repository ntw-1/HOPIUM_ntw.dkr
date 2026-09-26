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
) -> float:
    """
    Dispatch function: evaluate the named trajectory family at time t.

    Parameters
    ----------
    family : str
        One of "stable_mild", "accelerating", "step_jump".
    t : float
        Time in hours.
    param_cfg : dict
        Per-parameter configuration block from synthetic_config.yaml.
    early_detectability : str or None
        One of "hidden", "subtle", "moderate", "strong".
        Only used for "accelerating" family.
    step_k : float or None
        Step amplitude. Only used for "step_jump" family.
    jump_time_h : float
        Jump onset. Only used for "step_jump" family.

    Returns
    -------
    float
        Drift offset at time t.

    Raises
    ------
    ValueError
        If an unknown trajectory family name is given.
    """
    if family == "stable_mild":
        return stable_mild(
            t=t,
            k=param_cfg["stable_mild_k"],
            t0=param_cfg["stable_mild_t0"],
        )

    elif family == "accelerating":
        scale = EARLY_DETECTABILITY_SCALE.get(early_detectability or "hidden", 0.0)
        # early_scale is expressed in parameter units: scale * latent_drift_k
        early = scale * param_cfg["latent_drift_k"]
        return accelerating(
            t=t,
            k=param_cfg["latent_drift_k"],
            exponent=param_cfg["accelerating_exponent"],
            onset_h=24.0,
            early_scale=early,
        )

    elif family == "step_jump":
        if step_k is None:
            raise ValueError("step_k must be provided for step_jump trajectory family.")
        return step_jump(t=t, k=step_k, jump_time_h=jump_time_h)

    else:
        raise ValueError(
            f"Unknown trajectory family: '{family}'. "
            f"Valid options: 'stable_mild', 'accelerating', 'step_jump'."
        )
