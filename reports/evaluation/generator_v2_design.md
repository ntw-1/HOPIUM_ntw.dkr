# Generator V2 Design & Observability

## Overview
V2 introduces the `accelerating_v2` trajectory family which mathematically ensures that a component's future 168h drift acceleration is causally linked to a continuous `latent_strength` parameter, which also manifests as a small proportional early drift at 24h. This prevents the V1 unnatural 'hidden' behavior where components were completely flat early on and exploded later. It also correctly assigns a distinct latent trajectory for `propagation_delay`.

## V2 Recommendations
A detailed evaluation supports adopting V2 for all downstream Module B evaluation because it creates a more realistic and mathematically coherent predictive benchmark. While V2 MAE may improve on some subsets because the problem is now physically observable, it preserves significant nominal/latent overlap due to measurement noise, ensuring the problem remains non-trivial.
