# Early Predictive Signal Diagnostic

Using TRAIN + VALIDATION lots only.

*(Data tables omitted for brevity, see JSON for full distributions)*

## CONCLUSIONS

### A. Signal clearly present
For `Iddq` and `leakage_current`, the `delta_24_0` (and `normalized_delta`) feature contains a clearly measurable predictive signal across ALL detectability categories, including the counter-intuitive "hidden" category. 

The previous observation holds exactly:
- `Iddq` nominal mean delta: 0.346
- `Iddq` hidden mean delta: 0.020
- `Iddq` strong mean delta: 1.472

Because nominal components naturally exhibit a rapid initial burn-in rise before stabilizing, a "hidden" latent degrader (which remains flat before spiking later) is mathematically detectable precisely because it has an **abnormally low early drift**. 

### B. Signal weak/overlapping
While the signal exists, the distributions overlap. A simple one-sided threshold cannot cleanly separate the classes. However, using a two-tailed diagnostic threshold (calibrated to a 5% nominal False Positive Rate) on `delta_24_0` for Iddq captures:
- **Upper threshold**: 95.5% of `strong` and 46.2% of `moderate` degraders.
- **Lower threshold**: **64.1% of `hidden` degraders.**

This proves that the "hidden" signal is not entirely buried in noise; nearly two-thirds of it sits cleanly outside the nominal 5th percentile.

### C. Signal effectively absent
For `propagation_delay`, the early signal is effectively absent (Cohen's d is near zero, and TPRs equal the 5% FPR threshold). This aligns with the previous configuration audit showing that propagation delay latent degraders use the exact same `stable_mild` trajectory family as nominal components, meaning they literally do not diverge. 
Additionally, the absolute measurements (`value_0h`, `value_24h`) contain zero predictive signal for the *trajectory* of the degradation, serving only as a baseline offset.

### D. Implications for Module B
The permitted early telemetry (`0h`/`24h`) **DOES** contain measurable, actionable information to identify latent degraders, including the "hidden" ones. 

The failure of the current Module B models is therefore a **modeling failure**, not an absolute information-theoretic bottleneck. The danger signal in `delta_24_0` is non-monotonic: both abnormally high *and* abnormally low early deltas indicate latent degraders. The frozen regression trees, attempting to optimize global MSE on an absolute `Value_168h` target dominated by a massive `Value_0h` baseline, simply lack the capacity and objective function required to isolate this subtle, two-tailed minority signal.
