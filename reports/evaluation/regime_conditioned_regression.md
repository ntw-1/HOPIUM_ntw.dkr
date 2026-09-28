# Regime-Conditioned Regression Diagnostic

## METRICS BY PARAMETER

### Parameter: Iddq

| Configuration | Val MAE | Blind MAE | Blind RMSE | Nominal MAE | Hidden MAE | Subtle MAE | Moderate MAE | Strong MAE |
|---------------|---------|-----------|------------|-------------|------------|------------|--------------|------------|
| baseline | 25.5064 | 28.1749 | 46.7406 | 17.7661 | 113.3803 | 136.0321 | 97.8400 | 34.2808 |
| K=2 | 25.1892 | 28.0520 | 46.8152 | 17.4432 | 113.8777 | 136.2993 | 103.8951 | 33.8580 |
| K=3 | 24.8344 | 27.5428 | 46.7959 | 16.8635 | 114.7355 | 135.0811 | 104.6348 | 33.1199 |

### Parameter: leakage_current

| Configuration | Val MAE | Blind MAE | Blind RMSE | Nominal MAE | Hidden MAE | Subtle MAE | Moderate MAE | Strong MAE |
|---------------|---------|-----------|------------|-------------|------------|------------|--------------|------------|
| baseline | 3.9760 | 4.0903 | 6.6096 | 2.3076 | 18.0300 | 19.1050 | 19.3539 | 12.6855 |
| K=2 | 3.9550 | 4.1075 | 6.6708 | 2.3306 | 18.0178 | 19.0618 | 19.3050 | 12.6807 |
| K=3 | 3.9093 | 4.1966 | 6.8483 | 2.4344 | 17.6685 | 19.1147 | 19.5505 | 13.2103 |

### Parameter: propagation_delay

| Configuration | Val MAE | Blind MAE | Blind RMSE | Nominal MAE | Hidden MAE | Subtle MAE | Moderate MAE | Strong MAE |
|---------------|---------|-----------|------------|-------------|------------|------------|--------------|------------|
| baseline | 0.8116 | 0.7835 | 0.9803 | 0.7781 | 0.6455 | 0.8199 | 0.9739 | 1.3304 |
| K=2 | 0.8114 | 0.7838 | 0.9793 | 0.7791 | 0.6459 | 0.8134 | 0.9551 | 1.3289 |
| K=3 | 0.8109 | 0.7842 | 0.9806 | 0.7799 | 0.6359 | 0.8224 | 0.9441 | 1.3416 |

## CONCLUSIONS
### A. Does regime conditioning improve overall Value168 regression?
- **No.** The overall Validation MAE and Blind MAE remain essentially identical across Baseline, K=2, and K=3 for all parameters. For example, in Iddq, the Val MAE goes from 25.50 (Baseline) to 25.18 (K=2) and 24.83 (K=3), which is a negligible change on a parameter whose true value spikes heavily.

### B. Does it improve hidden/subtle latent-degrader prediction?
- **No.** The MAE for hidden and subtle degraders remains catastrophically high. For Iddq, Hidden MAE moves from 113.38 to 113.87 (K=2) and 114.73 (K=3). The regime conditioning completely fails to improve regression on these critical minorities.

### C. Does it preserve nominal performance?
- **Yes.** Nominal MAE stays roughly identical (~17 for Iddq). The regression still predominantly learns the nominal average.

### D. Does it improve predicted future slope for dangerous trajectories?
- **No.** Because the hidden/subtle degraders are not isolated and the regression still minimizes overall MAE, it continues to underpredict the slope for these degraders.

### E. Does it generalize to the locked blind lots?
- **Yes, it generalizes exactly as poorly as the baseline.** The blind metrics perfectly mirror the validation metrics, showing no overfitting but also no improvement.

### F. Are the learned regimes interpretable as meaningful early-trajectory regimes, or are they merely arbitrary clusters?
- **They are mostly arbitrary macro-clusters or tiny outlier groups.** For K=2, the clustering separates the data into one massive cluster (e.g., 1190 train components) and one tiny outlier cluster (e.g., 10 train components). For K=3, it splits the massive cluster into two large halves while keeping the tiny outlier group. In all cases, the hidden and subtle latent degraders are entirely swallowed up in the massive nominal clusters (e.g., all 18 hidden degraders in Iddq blind set land in the massive cluster "0").

### G. Is there sufficient evidence to justify considering regime-conditioned regression for production?
- **No.** Unsupervised early-feature clustering completely fails to isolate the hidden latent degraders from the nominals because, as established in previous diagnostics, the hidden degraders are not statistically distant in the 0h/24h feature space. Because they remain trapped in the same regime as the nominals, the within-regime regression still sacrifices them to optimize for the nominal majority.

