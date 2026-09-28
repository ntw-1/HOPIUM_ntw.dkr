# Module B Blind Test Evaluation Report

## Metadata
- **Dataset ID**: dev_burnin_data_seed42_v2
- **Split Seed**: 42
- **Blind Lots**: LOT_009, LOT_002, LOT_018, LOT_014 (4 total)

## Parameter: Iddq
- Model ID: module_b_Iddq_v1
- Model Class: GradientBoostingRegressor
- Sample Count: 400

### Aggregate Metrics
- MAE: 11.9774
- RMSE: 27.5211
- mean_error: 1.2115
- median_absolute_error: 4.9939
- max_absolute_error: 187.7313

### Error Distribution
- Residual Mean: 1.2115
- Residual Median: 4.3431
- Residual Std: 27.4944
- Residual Quantiles:
  - q05: -41.3562
  - q25: 2.5441
  - q75: 5.9497
  - q95: 15.8171
- Absolute Error Quantiles:
  - q50: 4.9939
  - q75: 7.3380
  - q90: 20.4340
  - q95: 53.7823
  - q99: 123.6204

### Uncertainty Metrics
*(Method: quantile_interval_envelope)*
> **Note**: These are uncertainty proxies based on the method described, not necessarily formally calibrated prediction intervals.
- empirical_coverage: 77.25%
- average_interval_width: 16.3874
- median_interval_width: 12.8525

### Behavioral Groups
#### nominal (n=355)
- MAE: 7.0651
- RMSE: 15.8241
- Mean Error: 7.0596
- Median Absolute Error: 4.6161

#### latent_degradation (n=45)
- MAE: 50.7304
- RMSE: 68.9721
- Mean Error: -44.9240
- Median Absolute Error: 39.0121

### Latent Degrader Evaluation
- Count: 45
- MAE on Latent Degraders: 50.7304
- RMSE on Latent Degraders: 68.9721
> **Limitation**: Module B provides point predictions and uncertainty. The actual decision logic (flagging a component) resides in the Phase 5 Risk Engine. Therefore, false-negative/false-positive screening rates cannot be calculated strictly from Module B outputs without duplicating the Phase 5 drift logic.

## Parameter: leakage_current
- Model ID: module_b_leakage_current_v1
- Model Class: Ridge
- Sample Count: 400

### Aggregate Metrics
- MAE: 1.5749
- RMSE: 3.1974
- mean_error: 0.0789
- median_absolute_error: 0.9749
- max_absolute_error: 23.2045

### Error Distribution
- Residual Mean: 0.0789
- Residual Median: 0.8475
- Residual Std: 3.1964
- Residual Quantiles:
  - q05: -5.9461
  - q25: 0.4933
  - q75: 1.1712
  - q95: 1.6679
- Absolute Error Quantiles:
  - q50: 0.9749
  - q75: 1.3381
  - q90: 1.8681
  - q95: 5.9461
  - q99: 15.3248

### Uncertainty Metrics
*(Method: residual_std)*
> **Note**: These are uncertainty proxies based on the method described, not necessarily formally calibrated prediction intervals.
- empirical_coverage: 94.00%
- average_interval_width: 7.0927
- median_interval_width: 7.0927

### Behavioral Groups
#### nominal (n=355)
- MAE: 0.9326
- RMSE: 1.0324
- Mean Error: 0.9294
- Median Absolute Error: 0.9237

#### latent_degradation (n=45)
- MAE: 6.6422
- RMSE: 9.0809
- Mean Error: -6.6306
- Median Absolute Error: 4.7120

### Latent Degrader Evaluation
- Count: 45
- MAE on Latent Degraders: 6.6422
- RMSE on Latent Degraders: 9.0809
> **Limitation**: Module B provides point predictions and uncertainty. The actual decision logic (flagging a component) resides in the Phase 5 Risk Engine. Therefore, false-negative/false-positive screening rates cannot be calculated strictly from Module B outputs without duplicating the Phase 5 drift logic.

## Parameter: propagation_delay
- Model ID: module_b_propagation_delay_v1
- Model Class: Ridge
- Sample Count: 400

### Aggregate Metrics
- MAE: 1.6817
- RMSE: 3.2624
- mean_error: 0.0423
- median_absolute_error: 1.0881
- max_absolute_error: 22.3831

### Error Distribution
- Residual Mean: 0.0423
- Residual Median: 0.7049
- Residual Std: 3.2621
- Residual Quantiles:
  - q05: -5.1270
  - q25: -0.0090
  - q75: 1.4140
  - q95: 2.4543
- Absolute Error Quantiles:
  - q50: 1.0881
  - q75: 1.7067
  - q90: 2.6418
  - q95: 5.1270
  - q99: 19.1357

### Uncertainty Metrics
*(Method: residual_std)*
> **Note**: These are uncertainty proxies based on the method described, not necessarily formally calibrated prediction intervals.
- empirical_coverage: 93.75%
- average_interval_width: 6.8314
- median_interval_width: 6.8314

### Behavioral Groups
#### nominal (n=355)
- MAE: 1.0720
- RMSE: 1.3023
- Mean Error: 0.8668
- Median Absolute Error: 0.9883

#### latent_degradation (n=45)
- MAE: 6.4914
- RMSE: 9.0127
- Mean Error: -6.4623
- Median Absolute Error: 3.6688

### Latent Degrader Evaluation
- Count: 45
- MAE on Latent Degraders: 6.4914
- RMSE on Latent Degraders: 9.0127
> **Limitation**: Module B provides point predictions and uncertainty. The actual decision logic (flagging a component) resides in the Phase 5 Risk Engine. Therefore, false-negative/false-positive screening rates cannot be calculated strictly from Module B outputs without duplicating the Phase 5 drift logic.

