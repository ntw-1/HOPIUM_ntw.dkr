# Module A Early Abnormality Diagnostic (Blind Lots)

Evaluation of existing per-lot Modified Z-Score (threshold=3.5).

*(Metrics tables omitted for brevity. See JSON for details.)*

## CONCLUSIONS
### A. Can existing Module A detect the early abnormality found by the classifier?
**No.** The existing Module A completely fails to detect the "hidden" and "moderate" early abnormalities. For `Iddq`, it only reliably detects the "strong" cases (75.0% recall). The overall latent recall for `Iddq` is a mere 13.3%, and for `leakage_current` it is 2.2%.

### B. Which parameter(s) show useful early anomaly signal?
Only `Iddq` shows any meaningful anomaly signal via Module A, and it is strictly limited to the `strong` detectability category. For `leakage_current` and `propagation_delay`, the `delta_24_0` anomaly signal is exactly 0.0%.

### C. Can Module A detect hidden degraders without knowing the latent-degrader label?
**No.** "Hidden" degraders exhibit an early delta that is lower than the median, but it is **not a statistical outlier**. The median `Iddq` early delta is ~0.35, and the hidden delta is ~0.02. This results in a Modified Z-score of roughly `-1.5` to `-2.0`, which falls entirely within the standard 3.5 anomaly threshold of normal population variance. Because they look like completely normal, stable components, an unsupervised outlier detector cannot legally flag them.

### D. How does its performance compare conceptually with the diagnostic classifier?
The diagnostic classifier successfully achieved a 50% recall on "hidden" degraders because it was explicitly taught by ground-truth labels to draw an aggressive boundary at the ~5th percentile of the nominal distribution. 
Module A, however, is a mathematically strict, unsupervised outlier detector. Since "hidden" degraders are not actual outliers in the feature space (they overlap entirely with the lowest 5% of nominal components), Module A correctly accepts them as part of the normal population distribution.

### E. Does this provide evidence for keeping Module A as the early-abnormality detector while Module B remains the future-value regression model?
It clarifies the strict limitations of the current architecture. Module A works perfectly for its intended purpose: detecting gross outliers (catching 75% of "strong" degraders at a tiny 0.28% FPR). However, this diagnostic definitively proves that **Module A CANNOT serve as a safety net for "hidden" or "subtle" latent degraders.** 
Because these dangerous components do not physically manifest as early outliers, they will cleanly pass Module A. They will then hit Module B, where the regression models will predict a perfectly safe nominal trajectory for them. Therefore, without changing the upstream data signal or introducing a new ground-truth-aware classifier, these components will always slip through the screening process.
