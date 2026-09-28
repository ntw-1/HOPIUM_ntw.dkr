# Module B Regression Root Cause Audit

## Parameter: Iddq

### 1. Information Availability (Train + Val)
| Regime | Mean Delta (Nom) | Mean Delta (Regime) | Effect Size (Cohen's d) | Target (Nom) | Target (Regime) |
|--------|------------------|---------------------|-------------------------|--------------|-----------------|
| hidden | 0.3459 | 0.0200 | -1.6003 | 11.69 | 169.28 |
| subtle | 0.3459 | 0.2510 | -0.4608 | 11.69 | 169.24 |
| moderate | 0.3459 | 0.6841 | 1.6482 | 11.69 | 169.60 |
| strong | 0.3459 | 1.4722 | 5.4281 | 11.69 | 175.06 |

### 2. Regression Baselines (Blind)
| Model | Overall MAE | Nom MAE | Hidden MAE | Subtle MAE | Mod MAE | Strong MAE |
|-------|-------------|---------|------------|------------|---------|------------|
| Dummy | 33.4561 | 20.1956 | 137.9811 | 137.7912 | 138.1591 | 139.2005 |
| Ridge | 32.6571 | 19.2364 | 141.0922 | 139.3911 | 135.0487 | 131.8405 |
| RF | 28.1749 | 17.7661 | 113.3803 | 136.0321 | 97.8400 | 34.2808 |
| GBM | 27.7222 | 17.0816 | 115.0675 | 137.8261 | 96.7011 | 38.4502 |

### 3. Counterfactual Observability Test (Blind)
GBM model trained with explicit latent regime label to test if target is intrinsically unpredictable or just unobservable from 0h/24h features.

| Configuration | Overall MAE | Nom MAE | Hidden MAE | Subtle MAE | Mod MAE | Strong MAE |
|---------------|-------------|---------|------------|------------|---------|------------|
| Standard GBM  | 27.7222 | 17.0816 | 115.0675 | 137.8261 | 96.7011 | 38.4502 |
| Label-Oracle  | 0.1773 | 0.1648 | 0.2681 | 0.3376 | 0.2262 | 0.2079 |

---

## Parameter: leakage_current

### 1. Information Availability (Train + Val)
| Regime | Mean Delta (Nom) | Mean Delta (Regime) | Effect Size (Cohen's d) | Target (Nom) | Target (Regime) |
|--------|------------------|---------------------|-------------------------|--------------|-----------------|
| hidden | 0.0989 | 0.0000 | -0.8725 | 5.68 | 27.01 |
| subtle | 0.0989 | 0.0733 | -0.2262 | 5.68 | 26.77 |
| moderate | 0.0989 | 0.2358 | 1.2125 | 5.68 | 26.79 |
| strong | 0.0989 | 0.4779 | 3.3604 | 5.68 | 26.92 |

### 2. Regression Baselines (Blind)
| Model | Overall MAE | Nom MAE | Hidden MAE | Subtle MAE | Mod MAE | Strong MAE |
|-------|-------------|---------|------------|------------|---------|------------|
| Dummy | 5.0798 | 3.2719 | 20.3814 | 18.5978 | 18.6812 | 18.7514 |
| Ridge | 4.4158 | 2.5911 | 19.1033 | 18.8117 | 18.5718 | 18.0271 |
| RF | 4.0903 | 2.3076 | 18.0300 | 19.1050 | 19.3539 | 12.6855 |
| GBM | 4.0278 | 2.2948 | 16.9990 | 18.6043 | 19.8071 | 12.9431 |

### 3. Counterfactual Observability Test (Blind)
GBM model trained with explicit latent regime label to test if target is intrinsically unpredictable or just unobservable from 0h/24h features.

| Configuration | Overall MAE | Nom MAE | Hidden MAE | Subtle MAE | Mod MAE | Strong MAE |
|---------------|-------------|---------|------------|------------|---------|------------|
| Standard GBM  | 4.0278 | 2.2948 | 16.9990 | 18.6043 | 19.8071 | 12.9431 |
| Label-Oracle  | 0.0985 | 0.0899 | 0.2356 | 0.1063 | 0.1409 | 0.1202 |

---

## Parameter: propagation_delay

### 1. Information Availability (Train + Val)
| Regime | Mean Delta (Nom) | Mean Delta (Regime) | Effect Size (Cohen's d) | Target (Nom) | Target (Regime) |
|--------|------------------|---------------------|-------------------------|--------------|-----------------|
| hidden | 0.5230 | 0.7511 | 0.2008 | 122.04 | 122.48 |
| subtle | 0.5230 | 0.4734 | -0.0437 | 122.04 | 121.76 |
| moderate | 0.5230 | 0.4159 | -0.0941 | 122.04 | 125.98 |
| strong | 0.5230 | 0.2482 | -0.2411 | 122.04 | 121.25 |

### 2. Regression Baselines (Blind)
| Model | Overall MAE | Nom MAE | Hidden MAE | Subtle MAE | Mod MAE | Strong MAE |
|-------|-------------|---------|------------|------------|---------|------------|
| Dummy | 5.5365 | 5.2010 | 9.3670 | 6.8197 | 8.5736 | 6.7513 |
| Ridge | 0.7835 | 0.7781 | 0.6455 | 0.8199 | 0.9739 | 1.3304 |
| RF | 0.8530 | 0.8541 | 0.6081 | 0.8388 | 1.0982 | 1.3524 |
| GBM | 0.8401 | 0.8388 | 0.6398 | 0.8284 | 1.1614 | 1.1775 |

### 3. Counterfactual Observability Test (Blind)
GBM model trained with explicit latent regime label to test if target is intrinsically unpredictable or just unobservable from 0h/24h features.

| Configuration | Overall MAE | Nom MAE | Hidden MAE | Subtle MAE | Mod MAE | Strong MAE |
|---------------|-------------|---------|------------|------------|---------|------------|
| Standard GBM  | 0.8401 | 0.8388 | 0.6398 | 0.8284 | 1.1614 | 1.1775 |
| Label-Oracle  | 0.8513 | 0.8394 | 0.8014 | 0.9079 | 1.1683 | 1.2223 |

---

## CONCLUSIONS

1. **Is the 0h/24h → 168h problem actually predictable in our synthetic data?**
   - **For Iddq and leakage_current: Yes, if the latent regime is known.** The counterfactual "Label-Oracle" test dropped the MAE for hidden degraders from ~115 to 0.26 for Iddq, and from ~17 to 0.23 for leakage_current. This proves the future trajectory is highly deterministic and contains very little intrinsic noise. 
   - **For propagation_delay: No.** The Label-Oracle model showed zero improvement, proving that knowing the "latent" regime provides no mathematical advantage in predicting the 168h value.

2. **How much early signal exists for each parameter/regime?**
   - **Iddq/leakage_current:** "Hidden" and "subtle" cases technically have an early signal, but it is inverted: their early drift is *near zero* (e.g. mean delta 0.02 vs nominal 0.35), which is completely contrary to a physical "degradation" signature. Effect size is around -1.6 for hidden Iddq.
   - **propagation_delay:** None. The effect sizes are near zero across all regimes.

3. **How much does each regression model exploit that signal?**
   - **Almost zero.** RF and GBM lower the MAE on "strong" degraders (which have massively distinct early deltas), but entirely ignore "hidden" and "subtle" degraders, predicting values close to the nominal baseline for them.

4. **Are hidden/subtle failures intrinsically ambiguous from 0h/24h?**
   - **Yes.** Because the synthetic generator sets their early drift to exactly 0.0, they perfectly overlap with nominal components that simply experienced low/negative measurement noise at 24h. 

5. **Why does propagation_delay fail?**
   - **Generator flaw.** The `configs/synthetic_config.yaml` explicitly assigns `latent_degradation` for `propagation_delay` to use the exact same `stable_mild` trajectory function and constants as nominal components. Thus, a propagation_delay "latent degrader" is mathematically identical to a nominal component in both early and late stages.

6. **Is the synthetic generator faithfully testing the SIH requirement?**
   - **No.** First, `propagation_delay` is broken. Second, for Iddq and leakage_current, the generator creates "hidden" degraders by making them drift *less* than nominals early on (delta ~0), and then inexplicably exploding later. This is an unnatural data distribution that forces regression models into a mathematical trap.

7. **Is the current regression architecture actually the bottleneck?**
   - **No.** The regression architecture (Global MAE optimization) is behaving exactly as mathematically required. Because "hidden" degraders (delta ~0) overlap with nominals (delta ~0 due to noise), the regression model cannot predict a massive 168h spike for delta=0 without mathematically destroying the MAE for the nominal majority. It is a fundamental data ambiguity and class imbalance problem, severely exacerbated by the unnatural generator mechanics.

8. **What, if anything, should be changed next?**
   - **Fix the synthetic generator.** The unnatural "hidden" mechanics (where components degrade by remaining perfectly stable at first) and the broken `propagation_delay` config must be fixed before any further modeling work is done. Modeling architecture should not be tortured to fit a flawed synthetic dataset.

