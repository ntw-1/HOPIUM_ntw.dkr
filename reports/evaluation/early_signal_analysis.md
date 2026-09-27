# Early Signal Analysis Report

## Data Used
- Train + Validation Lots only. Blind Lots excluded.

## Parameter: Iddq

### Early-Signal Measurement (delta_24_0)
| Group | Count | Mean | Median | Std | Cohen's d vs Nominal |
|-------|-------|------|--------|-----|-----------------------|
| nominal | 1407 | 0.3459 | 0.3457 | 0.2053 | 0.0000 |
| latent_degrader_hidden | 78 | 0.0200 | 0.0075 | 0.1679 | -1.6003 |
| latent_degrader_moderate | 39 | 0.6841 | 0.6791 | 0.1961 | 1.6482 |
| latent_degrader_subtle | 54 | 0.2510 | 0.2441 | 0.2183 | -0.4608 |
| latent_degrader_strong | 22 | 1.4722 | 1.5062 | 0.3119 | 5.4281 |

### Early Signal vs Future Outcome (Correlation with value_168h)
| Group | Count | r(value_0h) | r(value_24h) | r(delta_24_0) |
|-------|-------|-------------|--------------|---------------|
| nominal | 1407 | 0.9991 | 0.9991 | 0.0179 |
| latent_degrader_hidden | 78 | 0.9995 | 0.9994 | -0.0543 |
| latent_degrader_moderate | 39 | 0.9940 | 0.9955 | -0.1421 |
| latent_degrader_subtle | 54 | 0.9964 | 0.9954 | -0.1807 |
| latent_degrader_strong | 22 | 0.9999 | 0.9999 | -0.1891 |

### Frozen Model Performance
| Group | Count | MAE | RMSE | Mean Error | Median Absolute Error |
|-------|-------|-----|------|------------|------------------------|
| nominal | 1407 | 13.3686 | 17.2014 | 13.1955 | 9.4389 |
| latent_degrader_hidden | 78 | 91.4921 | 98.9544 | -91.4905 | 95.8550 |
| latent_degrader_moderate | 39 | 107.5972 | 115.1914 | -107.2344 | 123.9233 |
| latent_degrader_subtle | 54 | 116.2241 | 120.3428 | -116.2241 | 123.5517 |
| latent_degrader_strong | 22 | 8.1662 | 9.2441 | -7.5009 | 7.5617 |

## Parameter: leakage_current

### Early-Signal Measurement (delta_24_0)
| Group | Count | Mean | Median | Std | Cohen's d vs Nominal |
|-------|-------|------|--------|-----|-----------------------|
| nominal | 1407 | 0.0989 | 0.0959 | 0.1133 | 0.0000 |
| latent_degrader_hidden | 78 | 0.0000 | -0.0048 | 0.1135 | -0.8725 |
| latent_degrader_moderate | 39 | 0.2358 | 0.2347 | 0.0974 | 1.2125 |
| latent_degrader_subtle | 54 | 0.0733 | 0.0887 | 0.1100 | -0.2262 |
| latent_degrader_strong | 22 | 0.4779 | 0.4859 | 0.0698 | 3.3604 |

### Early Signal vs Future Outcome (Correlation with value_168h)
| Group | Count | r(value_0h) | r(value_24h) | r(delta_24_0) |
|-------|-------|-------------|--------------|---------------|
| nominal | 1407 | 0.9995 | 0.9994 | -0.0072 |
| latent_degrader_hidden | 78 | 0.9996 | 0.9994 | -0.0145 |
| latent_degrader_moderate | 39 | 0.9912 | 0.9884 | -0.0951 |
| latent_degrader_subtle | 54 | 0.9832 | 0.9883 | -0.0613 |
| latent_degrader_strong | 22 | 0.9861 | 0.9922 | 0.1929 |

### Frozen Model Performance
| Group | Count | MAE | RMSE | Mean Error | Median Absolute Error |
|-------|-------|-----|------|------------|------------------------|
| nominal | 1407 | 2.2655 | 2.4119 | 2.2606 | 2.0386 |
| latent_degrader_hidden | 78 | 17.8875 | 17.9414 | -17.8875 | 18.2332 |
| latent_degrader_moderate | 39 | 17.7006 | 18.2297 | -17.7006 | 18.8406 |
| latent_degrader_subtle | 54 | 18.5720 | 18.6039 | -18.5720 | 18.9543 |
| latent_degrader_strong | 22 | 3.1206 | 6.6115 | -3.0496 | 0.2767 |

## Parameter: propagation_delay

### Early-Signal Measurement (delta_24_0)
| Group | Count | Mean | Median | Std | Cohen's d vs Nominal |
|-------|-------|------|--------|-----|-----------------------|
| nominal | 1407 | 0.5230 | 0.5090 | 1.1396 | 0.0000 |
| latent_degrader_hidden | 78 | 0.7511 | 0.7395 | 1.0536 | 0.2008 |
| latent_degrader_moderate | 39 | 0.4159 | 0.4928 | 1.0732 | -0.0941 |
| latent_degrader_subtle | 54 | 0.4734 | 0.5209 | 0.9698 | -0.0437 |
| latent_degrader_strong | 22 | 0.2482 | 0.1014 | 1.0894 | -0.2411 |

### Early Signal vs Future Outcome (Correlation with value_168h)
| Group | Count | r(value_0h) | r(value_24h) | r(delta_24_0) |
|-------|-------|-------------|--------------|---------------|
| nominal | 1407 | 0.9938 | 0.9935 | -0.0195 |
| latent_degrader_hidden | 78 | 0.9967 | 0.9969 | 0.0480 |
| latent_degrader_moderate | 39 | 0.9985 | 0.9989 | 0.0941 |
| latent_degrader_subtle | 54 | 0.9876 | 0.9859 | -0.2591 |
| latent_degrader_strong | 22 | 0.9777 | 0.9822 | -0.2774 |

### Frozen Model Performance
| Group | Count | MAE | RMSE | Mean Error | Median Absolute Error |
|-------|-------|-----|------|------------|------------------------|
| nominal | 1407 | 0.8305 | 1.0351 | -0.0191 | 0.7137 |
| latent_degrader_hidden | 78 | 0.8200 | 1.0165 | 0.1967 | 0.7130 |
| latent_degrader_moderate | 39 | 0.6958 | 0.8863 | 0.1230 | 0.4780 |
| latent_degrader_subtle | 54 | 0.8559 | 1.0892 | 0.1025 | 0.7683 |
| latent_degrader_strong | 22 | 0.7165 | 1.0599 | 0.1497 | 0.3725 |

