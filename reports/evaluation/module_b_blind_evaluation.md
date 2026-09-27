# Module B Blind Test Evaluation Report

## Metadata
- **Dataset ID**: dev_burnin_data_seed42_v1
- **Split Seed**: 42
- **Blind Lots**: LOT_002, LOT_018, LOT_014, LOT_009 (4 total)

## Parameter: Iddq
- Model ID: module_b_Iddq_v1
- Model Class: GradientBoostingRegressor
- Sample Count: 400

### Aggregate Metrics
- MAE: 27.7466
- RMSE: 47.5746
- mean_error: 3.0001
- median_absolute_error: 10.4001
- max_absolute_error: 152.7444

### Error Distribution
- Residual Mean: 3.0001
- Residual Median: 8.8450
- Residual Std: 47.4800
- Residual Quantiles:
  - q05: -138.3792
  - q25: 6.3551
  - q75: 15.7464
  - q95: 53.0158
- Absolute Error Quantiles:
  - q50: 10.4001
  - q75: 25.5079
  - q90: 82.9013
  - q95: 139.9648
  - q99: 150.3308

### Uncertainty Metrics
*(Method: quantile_interval_envelope)*
> **Note**: These are uncertainty proxies based on the method described, not necessarily formally calibrated prediction intervals.
- empirical_coverage: 81.25%
- average_interval_width: 54.1624
- median_interval_width: 14.1114

### Behavioral Groups
#### nominal (n=355)
- MAE: 17.3351
- RMSE: 27.4089
- Mean Error: 17.1834
- Median Absolute Error: 9.4026

#### latent_degradation (n=45)
- MAE: 109.8817
- RMSE: 119.1306
- Mean Error: -108.8908
- Median Absolute Error: 132.1734

### Latent Degrader Evaluation
- Count: 45
- MAE on Latent Degraders: 109.8817
- RMSE on Latent Degraders: 119.1306
> **Limitation**: Module B provides point predictions and uncertainty. The actual decision logic (flagging a component) resides in the Phase 5 Risk Engine. Therefore, false-negative/false-positive screening rates cannot be calculated strictly from Module B outputs without duplicating the Phase 5 drift logic.

## Parameter: leakage_current
- Model ID: module_b_leakage_current_v1
- Model Class: RandomForestRegressor
- Sample Count: 400

### Aggregate Metrics
- MAE: 4.1261
- RMSE: 6.6472
- mean_error: 0.0262
- median_absolute_error: 2.0887
- max_absolute_error: 20.5580

### Error Distribution
- Residual Mean: 0.0262
- Residual Median: 1.9616
- Residual Std: 6.6472
- Residual Quantiles:
  - q05: -19.1748
  - q25: 1.6836
  - q75: 2.4729
  - q95: 3.9807
- Absolute Error Quantiles:
  - q50: 2.0887
  - q75: 3.0971
  - q90: 17.3263
  - q95: 19.1748
  - q99: 19.8711

### Uncertainty Metrics
*(Method: rf_tree_std)*
> **Note**: These are uncertainty proxies based on the method described, not necessarily formally calibrated prediction intervals.
- empirical_coverage: 8.25%
- average_interval_width: 3.1241
- median_interval_width: 2.2190

### Behavioral Groups
#### nominal (n=355)
- MAE: 2.3403
- RMSE: 2.5311
- Mean Error: 2.3383
- Median Absolute Error: 2.0157

#### latent_degradation (n=45)
- MAE: 18.2138
- RMSE: 18.4992
- Mean Error: -18.2138
- Median Absolute Error: 19.1050

### Latent Degrader Evaluation
- Count: 45
- MAE on Latent Degraders: 18.2138
- RMSE on Latent Degraders: 18.4992
> **Limitation**: Module B provides point predictions and uncertainty. The actual decision logic (flagging a component) resides in the Phase 5 Risk Engine. Therefore, false-negative/false-positive screening rates cannot be calculated strictly from Module B outputs without duplicating the Phase 5 drift logic.

## Parameter: propagation_delay
- Model ID: module_b_propagation_delay_v1
- Model Class: Ridge
- Sample Count: 400

### Aggregate Metrics
- MAE: 0.7839
- RMSE: 0.9806
- mean_error: -0.0704
- median_absolute_error: 0.6573
- max_absolute_error: 2.7561

### Error Distribution
- Residual Mean: -0.0704
- Residual Median: -0.0678
- Residual Std: 0.9781
- Residual Quantiles:
  - q05: -1.7957
  - q25: -0.7176
  - q75: 0.5967
  - q95: 1.4935
- Absolute Error Quantiles:
  - q50: 0.6573
  - q75: 1.1045
  - q90: 1.6416
  - q95: 1.9480
  - q99: 2.4855

### Uncertainty Metrics
*(Method: residual_std)*
> **Note**: These are uncertainty proxies based on the method described, not necessarily formally calibrated prediction intervals.
- empirical_coverage: 71.50%
- average_interval_width: 2.0771
- median_interval_width: 2.0771

### Behavioral Groups
#### nominal (n=355)
- MAE: 0.7785
- RMSE: 0.9733
- Mean Error: -0.0595
- Median Absolute Error: 0.6505

#### latent_degradation (n=45)
- MAE: 0.8263
- RMSE: 1.0367
- Mean Error: -0.1565
- Median Absolute Error: 0.7109

### Latent Degrader Evaluation
- Count: 45
- MAE on Latent Degraders: 0.8263
- RMSE on Latent Degraders: 1.0367
> **Limitation**: Module B provides point predictions and uncertainty. The actual decision logic (flagging a component) resides in the Phase 5 Risk Engine. Therefore, false-negative/false-positive screening rates cannot be calculated strictly from Module B outputs without duplicating the Phase 5 drift logic.

