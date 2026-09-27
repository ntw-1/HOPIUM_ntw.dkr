# Safety Slope Analysis Report

## Data Used
- Train + Validation Lots: ['LOT_001', 'LOT_003', 'LOT_004', 'LOT_005', 'LOT_006', 'LOT_007', 'LOT_008', 'LOT_010', 'LOT_011', 'LOT_012', 'LOT_013', 'LOT_015', 'LOT_016', 'LOT_017', 'LOT_019', 'LOT_020']
- Excluded: Blind Lots (completely untouched)

## Parameter: Iddq

### Distributions (True Slope 0->168h)
- **all** (n=1600): Mean=0.1197, Median=0.0064, p95=0.9466, Max=0.9563
- **nominal** (n=1407): Mean=0.0062, Median=0.0062, p95=0.0083, Max=0.0108
- **latent_degrader** (n=193): Mean=0.9470, Median=0.9463, p95=0.9537, Max=0.9563
- **latent_degrader_hidden** (n=78): Mean=0.9449, Median=0.9449, p95=0.9467, Max=0.9473
- **latent_degrader_moderate** (n=39): Mean=0.9489, Median=0.9488, p95=0.9507, Max=0.9526
- **latent_degrader_subtle** (n=54): Mean=0.9461, Median=0.9463, p95=0.9476, Max=0.9491
- **latent_degrader_strong** (n=22): Mean=0.9532, Median=0.9535, p95=0.9550, Max=0.9563

### Predicted Distributions (Pred Slope 0->168h)
- **all** (n=1600): Mean=0.1227, Median=0.0679, p95=0.4150, Max=0.9909
- **nominal** (n=1407): Mean=0.0847, Median=0.0619, p95=0.2094, Max=0.6824
- **latent_degrader** (n=193): Mean=0.3992, Median=0.3411, p95=0.9111, Max=0.9909
- **latent_degrader_hidden** (n=78): Mean=0.4003, Median=0.3727, p95=0.8035, Max=0.9432
- **latent_degrader_moderate** (n=39): Mean=0.3106, Median=0.2112, p95=0.8856, Max=0.9909
- **latent_degrader_subtle** (n=54): Mean=0.2542, Median=0.2113, p95=0.6078, Max=0.8991
- **latent_degrader_strong** (n=22): Mean=0.9085, Median=0.9076, p95=0.9747, Max=0.9783

### Candidate Boundaries (True Slope 0->168h)
- **p90** Boundary=0.0078
  - Nominal FPR: 10.02%
  - Latent TPR: 100.00%
    - hidden TPR: 100.00%
    - moderate TPR: 100.00%
    - subtle TPR: 100.00%
    - strong TPR: 100.00%
- **p95** Boundary=0.0083
  - Nominal FPR: 5.05%
  - Latent TPR: 100.00%
    - hidden TPR: 100.00%
    - moderate TPR: 100.00%
    - subtle TPR: 100.00%
    - strong TPR: 100.00%
- **p99** Boundary=0.0093
  - Nominal FPR: 1.07%
  - Latent TPR: 100.00%
    - hidden TPR: 100.00%
    - moderate TPR: 100.00%
    - subtle TPR: 100.00%
    - strong TPR: 100.00%

### Candidate Boundaries (Pred Slope 0->168h)
- **p90** Boundary=0.1632
  - Nominal FPR: 10.02%
  - Latent TPR: 74.61%
    - hidden TPR: 83.33%
    - moderate TPR: 61.54%
    - subtle TPR: 61.11%
    - strong TPR: 100.00%
- **p95** Boundary=0.2094
  - Nominal FPR: 5.05%
  - Latent TPR: 65.80%
    - hidden TPR: 73.08%
    - moderate TPR: 51.28%
    - subtle TPR: 51.85%
    - strong TPR: 100.00%
- **p99** Boundary=0.3376
  - Nominal FPR: 1.07%
  - Latent TPR: 50.78%
    - hidden TPR: 55.13%
    - moderate TPR: 41.03%
    - subtle TPR: 31.48%
    - strong TPR: 100.00%

### Headroom Analysis
- Mean Headroom Slope (24->168h): 0.2706
- True Slope > Headroom Rate: 12.81%
- Pred Slope > Headroom Rate: 10.88%

## Parameter: leakage_current

### Distributions (True Slope 0->168h)
- **all** (n=1600): Mean=0.0172, Median=0.0019, p95=0.1293, Max=0.1329
- **nominal** (n=1407): Mean=0.0018, Median=0.0018, p95=0.0029, Max=0.0040
- **latent_degrader** (n=193): Mean=0.1293, Median=0.1291, p95=0.1317, Max=0.1329
- **latent_degrader_hidden** (n=78): Mean=0.1285, Median=0.1285, p95=0.1296, Max=0.1299
- **latent_degrader_moderate** (n=39): Mean=0.1299, Median=0.1299, p95=0.1308, Max=0.1313
- **latent_degrader_subtle** (n=54): Mean=0.1290, Median=0.1289, p95=0.1303, Max=0.1308
- **latent_degrader_strong** (n=22): Mean=0.1315, Median=0.1316, p95=0.1323, Max=0.1329

### Predicted Distributions (Pred Slope 0->168h)
- **all** (n=1600): Mean=0.0173, Median=0.0143, p95=0.0268, Max=0.1344
- **nominal** (n=1407): Mean=0.0153, Median=0.0140, p95=0.0237, Max=0.0701
- **latent_degrader** (n=193): Mean=0.0319, Median=0.0189, p95=0.1305, Max=0.1344
- **latent_degrader_hidden** (n=78): Mean=0.0220, Median=0.0204, p95=0.0369, Max=0.0487
- **latent_degrader_moderate** (n=39): Mean=0.0246, Median=0.0176, p95=0.0755, Max=0.1298
- **latent_degrader_subtle** (n=54): Mean=0.0184, Median=0.0163, p95=0.0312, Max=0.0357
- **latent_degrader_strong** (n=22): Mean=0.1133, Median=0.1304, p95=0.1336, Max=0.1344

### Candidate Boundaries (True Slope 0->168h)
- **p90** Boundary=0.0027
  - Nominal FPR: 10.02%
  - Latent TPR: 100.00%
    - hidden TPR: 100.00%
    - moderate TPR: 100.00%
    - subtle TPR: 100.00%
    - strong TPR: 100.00%
- **p95** Boundary=0.0029
  - Nominal FPR: 5.05%
  - Latent TPR: 100.00%
    - hidden TPR: 100.00%
    - moderate TPR: 100.00%
    - subtle TPR: 100.00%
    - strong TPR: 100.00%
- **p99** Boundary=0.0034
  - Nominal FPR: 1.07%
  - Latent TPR: 100.00%
    - hidden TPR: 100.00%
    - moderate TPR: 100.00%
    - subtle TPR: 100.00%
    - strong TPR: 100.00%

### Candidate Boundaries (Pred Slope 0->168h)
- **p90** Boundary=0.0213
  - Nominal FPR: 10.02%
  - Latent TPR: 43.01%
    - hidden TPR: 48.72%
    - moderate TPR: 20.51%
    - subtle TPR: 27.78%
    - strong TPR: 100.00%
- **p95** Boundary=0.0237
  - Nominal FPR: 5.05%
  - Latent TPR: 35.23%
    - hidden TPR: 38.46%
    - moderate TPR: 17.95%
    - subtle TPR: 18.52%
    - strong TPR: 95.45%
- **p99** Boundary=0.0297
  - Nominal FPR: 1.07%
  - Latent TPR: 19.17%
    - hidden TPR: 14.10%
    - moderate TPR: 7.69%
    - subtle TPR: 5.56%
    - strong TPR: 90.91%

### Headroom Analysis
- Mean Headroom Slope (24->168h): 0.1705
- True Slope > Headroom Rate: 1.00%
- Pred Slope > Headroom Rate: 1.00%

## Parameter: propagation_delay

### Distributions (True Slope 0->168h)
- **all** (n=1600): Mean=0.0107, Median=0.0111, p95=0.0217, Max=0.0343
- **nominal** (n=1407): Mean=0.0108, Median=0.0112, p95=0.0218, Max=0.0343
- **latent_degrader** (n=193): Mean=0.0098, Median=0.0100, p95=0.0207, Max=0.0248
- **latent_degrader_hidden** (n=78): Mean=0.0101, Median=0.0108, p95=0.0206, Max=0.0248
- **latent_degrader_moderate** (n=39): Mean=0.0095, Median=0.0097, p95=0.0207, Max=0.0224
- **latent_degrader_subtle** (n=54): Mean=0.0100, Median=0.0095, p95=0.0206, Max=0.0235
- **latent_degrader_strong** (n=22): Mean=0.0091, Median=0.0109, p95=0.0196, Max=0.0206

### Predicted Distributions (Pred Slope 0->168h)
- **all** (n=1600): Mean=0.0107, Median=0.0106, p95=0.0158, Max=0.0199
- **nominal** (n=1407): Mean=0.0107, Median=0.0106, p95=0.0158, Max=0.0199
- **latent_degrader** (n=193): Mean=0.0107, Median=0.0108, p95=0.0154, Max=0.0179
- **latent_degrader_hidden** (n=78): Mean=0.0113, Median=0.0112, p95=0.0169, Max=0.0179
- **latent_degrader_moderate** (n=39): Mean=0.0103, Median=0.0105, p95=0.0143, Max=0.0146
- **latent_degrader_subtle** (n=54): Mean=0.0106, Median=0.0103, p95=0.0148, Max=0.0154
- **latent_degrader_strong** (n=22): Mean=0.0100, Median=0.0096, p95=0.0152, Max=0.0158

### Candidate Boundaries (True Slope 0->168h)
- **p90** Boundary=0.0196
  - Nominal FPR: 10.02%
  - Latent TPR: 8.29%
    - hidden TPR: 8.97%
    - moderate TPR: 7.69%
    - subtle TPR: 7.41%
    - strong TPR: 9.09%
- **p95** Boundary=0.0218
  - Nominal FPR: 5.05%
  - Latent TPR: 3.11%
    - hidden TPR: 5.13%
    - moderate TPR: 2.56%
    - subtle TPR: 1.85%
    - strong TPR: 0.00%
- **p99** Boundary=0.0266
  - Nominal FPR: 1.07%
  - Latent TPR: 0.00%
    - hidden TPR: 0.00%
    - moderate TPR: 0.00%
    - subtle TPR: 0.00%
    - strong TPR: 0.00%

### Candidate Boundaries (Pred Slope 0->168h)
- **p90** Boundary=0.0147
  - Nominal FPR: 10.02%
  - Latent TPR: 7.77%
    - hidden TPR: 11.54%
    - moderate TPR: 0.00%
    - subtle TPR: 7.41%
    - strong TPR: 9.09%
- **p95** Boundary=0.0158
  - Nominal FPR: 5.05%
  - Latent TPR: 4.66%
    - hidden TPR: 10.26%
    - moderate TPR: 0.00%
    - subtle TPR: 0.00%
    - strong TPR: 4.55%
- **p99** Boundary=0.0183
  - Nominal FPR: 1.07%
  - Latent TPR: 0.00%
    - hidden TPR: 0.00%
    - moderate TPR: 0.00%
    - subtle TPR: 0.00%
    - strong TPR: 0.00%

### Headroom Analysis
- Mean Headroom Slope (24->168h): 0.4107
- True Slope > Headroom Rate: 1.00%
- Pred Slope > Headroom Rate: 1.00%

