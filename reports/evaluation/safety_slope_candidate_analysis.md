# Safety Slope Candidate Analysis

## Parameter: Iddq

### Validation Candidates
| Formulation | Nom FPR | Latent TPR | Hidden TPR | Subtle TPR | Moderate TPR | Strong TPR | Nom Flagged | Latent Flagged |
|-------------|---------|------------|------------|------------|--------------|------------|-------------|----------------|
| A_P95 | 0.0904 | 0.4783 | 0.5500 | 0.1818 | 0.3333 | 1.0000 | 32 | 22 |
| A_P97.5 | 0.0480 | 0.3913 | 0.3500 | 0.1818 | 0.3333 | 1.0000 | 17 | 18 |
| A_P99 | 0.0311 | 0.3261 | 0.2500 | 0.0909 | 0.3333 | 1.0000 | 11 | 15 |
| A_P99.5 | 0.0282 | 0.3261 | 0.2500 | 0.0909 | 0.3333 | 1.0000 | 10 | 15 |
| B_Headroom | 0.0395 | 0.3696 | 0.3500 | 0.0909 | 0.3333 | 1.0000 | 14 | 17 |
| C_LotRelative_Z3 | 0.0028 | 0.2391 | 0.1000 | 0.0909 | 0.2222 | 1.0000 | 1 | 11 |
| Current_DriftFrac_0.20 | 0.5876 | 0.8478 | 0.9000 | 0.6364 | 0.8889 | 1.0000 | 208 | 39 |
| Current_DriftFrac_0.60 | 0.1215 | 0.5217 | 0.5500 | 0.2727 | 0.4444 | 1.0000 | 43 | 24 |

**Selected Formulation:** `A_P97.5`

### Blind Evaluation (Frozen)
| Formulation | Nom FPR | Latent TPR | Hidden TPR | Subtle TPR | Moderate TPR | Strong TPR | Nom Flagged | Latent Flagged |
|-------------|---------|------------|------------|------------|--------------|------------|-------------|----------------|
| A_P97.5 | 0.0845 | 0.3778 | 0.5000 | 0.0714 | 0.4444 | 0.7500 | 30 | 17 |

---

## Parameter: leakage_current

### Validation Candidates
| Formulation | Nom FPR | Latent TPR | Hidden TPR | Subtle TPR | Moderate TPR | Strong TPR | Nom Flagged | Latent Flagged |
|-------------|---------|------------|------------|------------|--------------|------------|-------------|----------------|
| A_P95 | 0.0565 | 0.3043 | 0.2000 | 0.2727 | 0.1111 | 1.0000 | 20 | 14 |
| A_P97.5 | 0.0169 | 0.1739 | 0.1000 | 0.0000 | 0.0000 | 1.0000 | 6 | 8 |
| A_P99 | 0.0141 | 0.1522 | 0.1000 | 0.0000 | 0.0000 | 0.8333 | 5 | 7 |
| A_P99.5 | 0.0085 | 0.1087 | 0.0000 | 0.0000 | 0.0000 | 0.8333 | 3 | 5 |
| B_Headroom | 0.0113 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 4 | 0 |
| C_LotRelative_Z3 | 0.0028 | 0.0870 | 0.0000 | 0.0000 | 0.0000 | 0.6667 | 1 | 4 |
| Current_DriftFrac_0.20 | 0.0085 | 0.1087 | 0.0000 | 0.0000 | 0.0000 | 0.8333 | 3 | 5 |
| Current_DriftFrac_0.60 | 0.0000 | 0.0870 | 0.0000 | 0.0000 | 0.0000 | 0.6667 | 0 | 4 |

**Selected Formulation:** `A_P97.5`

### Blind Evaluation (Frozen)
| Formulation | Nom FPR | Latent TPR | Hidden TPR | Subtle TPR | Moderate TPR | Strong TPR | Nom Flagged | Latent Flagged |
|-------------|---------|------------|------------|------------|--------------|------------|-------------|----------------|
| A_P97.5 | 0.0535 | 0.0889 | 0.0556 | 0.0714 | 0.0000 | 0.5000 | 19 | 4 |

---

## Parameter: propagation_delay

### Validation Candidates
| Formulation | Nom FPR | Latent TPR | Hidden TPR | Subtle TPR | Moderate TPR | Strong TPR | Nom Flagged | Latent Flagged |
|-------------|---------|------------|------------|------------|--------------|------------|-------------|----------------|
| A_P95 | 0.0395 | 0.0217 | 0.0500 | 0.0000 | 0.0000 | 0.0000 | 14 | 1 |
| A_P97.5 | 0.0254 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 9 | 0 |
| A_P99 | 0.0169 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 6 | 0 |
| A_P99.5 | 0.0056 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 2 | 0 |
| B_Headroom | 0.0113 | 0.0217 | 0.0500 | 0.0000 | 0.0000 | 0.0000 | 4 | 1 |
| C_LotRelative_Z3 | 0.0028 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1 | 0 |
| Current_DriftFrac_0.20 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| Current_DriftFrac_0.60 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |

**Selected Formulation:** `A_P95`

### Blind Evaluation (Frozen)
| Formulation | Nom FPR | Latent TPR | Hidden TPR | Subtle TPR | Moderate TPR | Strong TPR | Nom Flagged | Latent Flagged |
|-------------|---------|------------|------------|------------|--------------|------------|-------------|----------------|
| A_P95 | 0.0479 | 0.0222 | 0.0556 | 0.0000 | 0.0000 | 0.0000 | 17 | 1 |

---

