# Generator V1 vs V2 Comparison

## Iddq

### Early Signal Effect Size (Cohen's d on delta_24_0)
| Regime | V1 Effect Size | V2 Effect Size |
|--------|----------------|----------------|
| hidden | -1.5956 | 0.2150 |
| subtle | -0.4352 | 0.3178 |
| moderate | 1.8101 | 0.7957 |
| strong | 5.2811 | 1.3411 |

### Mean Delta_24_0 by Regime
| Regime | V1 Mean Delta | V2 Mean Delta |
|--------|---------------|---------------|
| nominal | 0.3444 | 0.3444 |
| hidden | 0.0142 | 0.3889 |
| subtle | 0.2533 | 0.4109 |
| moderate | 0.7217 | 0.5104 |
| strong | 1.4588 | 0.6275 |

### Module B Regression MAE (GBM on Blind Set)
| Regime | V1 MAE | V2 MAE |
|--------|--------|--------|
| Overall | 27.7222 | 11.5993 |
| Nominal | 17.0816 | 6.7688 |
| Hidden | 115.0675 | 14.2680 |
| Subtle | 137.8261 | 45.5214 |
| Moderate | 96.7011 | 80.6186 |
| Strong | 38.4502 | 154.2758 |

---

## leakage_current

### Early Signal Effect Size (Cohen's d on delta_24_0)
| Regime | V1 Effect Size | V2 Effect Size |
|--------|----------------|----------------|
| hidden | -0.8735 | 0.1272 |
| subtle | -0.2283 | 0.1478 |
| moderate | 1.1669 | 0.4284 |
| strong | 3.2914 | 0.7986 |

### Mean Delta_24_0 by Regime
| Regime | V1 Mean Delta | V2 Mean Delta |
|--------|---------------|---------------|
| nominal | 0.0990 | 0.0990 |
| hidden | 0.0004 | 0.1134 |
| subtle | 0.0734 | 0.1156 |
| moderate | 0.2301 | 0.1471 |
| strong | 0.4682 | 0.1886 |

### Module B Regression MAE (GBM on Blind Set)
| Regime | V1 MAE | V2 MAE |
|--------|--------|--------|
| Overall | 4.0278 | 1.6140 |
| Nominal | 2.2948 | 0.9341 |
| Hidden | 16.9990 | 1.8406 |
| Subtle | 18.6043 | 5.9478 |
| Moderate | 19.8071 | 12.7076 |
| Strong | 12.9431 | 20.8045 |

---

## propagation_delay

### Early Signal Effect Size (Cohen's d on delta_24_0)
| Regime | V1 Effect Size | V2 Effect Size |
|--------|----------------|----------------|
| hidden | 0.1541 | 0.1649 |
| subtle | 0.0734 | 0.1052 |
| moderate | 0.0689 | 0.1327 |
| strong | -0.2511 | -0.1376 |

### Mean Delta_24_0 by Regime
| Regime | V1 Mean Delta | V2 Mean Delta |
|--------|---------------|---------------|
| nominal | 0.5135 | 0.5135 |
| hidden | 0.6876 | 0.6998 |
| subtle | 0.5963 | 0.6322 |
| moderate | 0.5915 | 0.6637 |
| strong | 0.2294 | 0.3577 |

### Module B Regression MAE (GBM on Blind Set)
| Regime | V1 MAE | V2 MAE |
|--------|--------|--------|
| Overall | 0.8401 | 1.8297 |
| Nominal | 0.8388 | 1.2050 |
| Hidden | 0.6398 | 1.7280 |
| Subtle | 0.8284 | 5.5003 |
| Moderate | 1.1614 | 12.0660 |
| Strong | 1.1775 | 21.8503 |

---

