# Early Feature Representation Comparison

*(Metrics tables omitted for brevity. See JSON for details.)*

## CONCLUSIONS

### A. Does feature representation improve overall Value168 regression?
**No.** The overall Validation and Blind MAE metrics are essentially identical across all four feature sets. For example, in `Iddq`, the Blind MAE fluctuates trivially from `27.74` (F0) to `27.98` (F3). Adding normalized or standardized features does not help a tree-based model (which is invariant to monotonic transformations), and adding the absolute z-score (F3) provides negligible overall lift.

### B. Does it improve latent-degrader prediction?
**No.** The primary failure mode—predicting the "hidden" and "subtle" latent degraders—remains entirely unsolved. 
- For `Iddq` `latent_hidden`, the MAE went from `111.94` (F0) to `112.41` (F3).
- For `leakage_current` `latent_hidden`, the MAE went from `18.41` (F0) to `17.83` (F3).
While F3 (`abs_delta_zscore`) provided a very minor improvement on `moderate` and `strong` cases (by explicitly exposing the two-tailed magnitude of the early drift), it completely failed to help the `hidden` cases. The models still predict the nominal mean for these dangerous components. 

### C. Does it preserve nominal performance?
**Yes.** Because the new features don't fundamentally change the tree splits for the vast majority of the data, the nominal performance remains virtually untouched (e.g., `Iddq` nominal MAE shifts only from `17.34` to `17.85`).

### D. Is there sufficient evidence to justify a production Phase 3 feature change?
**No.** Modifying the feature representation provides zero meaningful improvement on the core SIH requirement (detecting the dangerous latent degraders). 

The problem is not that the model doesn't "understand" the format of the early delta. The problem is that the "hidden" latent degraders (with a `delta_24_0` of ~`0.02`) sit at roughly `-1.5` standard deviations from the nominal mean (`0.34`). While this is lower than average, it is not an extreme enough outlier in the feature space for an MSE-optimized regression tree to confidently predict a massive `168h` degradation spike, especially when 90% of the dataset is nominal. Feature engineering cannot fix this fundamental information overlap.
