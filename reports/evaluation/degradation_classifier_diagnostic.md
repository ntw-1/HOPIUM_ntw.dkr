# Degradation Classifier Diagnostic

*(Metrics tables omitted for brevity. See JSON for details.)*

## REGRESSION VS CLASSIFIER COMPARISON (Iddq @ ~10% FPR)
*(Note: Regression results pulled from previous Formulation A diagnostic where >60% risk threshold yielded ~13% nominal FPR on blind data)*
| Metric | Regression (>60% Drift Risk) | Classifier (10% FPR Op. Point) |
|--------|------------------------------|--------------------------------|
| Nominal FPR | ~13% | 13.80% |
| Overall latent recall | ~49% | 46.67% |
| Hidden recall | ~0% | 50.00% |
| Subtle recall | ~31% | 21.43% |
| Moderate recall | ~46% | 66.67% |
| Strong recall | 100% | 75.00% |

## CONCLUSIONS

### A. Diagnostic evidence
The explicit classification objective successfully extracts early degradation information that the `Value_168h` regression objective completely ignores. Specifically, for Iddq at a ~13.8% blind FPR, the classifier achieves a **50.0% recall on "hidden" latent degraders**. In contrast, the regression model achieves ~0% recall on this exact same group (predicting nominal drift for all of them). However, the classifier trades away some performance on "strong" and "subtle" cases, resulting in an overall latent recall that is roughly equivalent to the regression baseline (~47% vs ~49%).

### B. Synthetic-label dependence
This diagnostic classification approach relies entirely on the ground-truth `is_latent_degrader` binary labels provided by the synthetic generator. In a real-world manufacturing dataset, these exact labels would not exist natively at the time of model training; they would require manual engineering annotation after 168h completion. The regression approach natively uses the continuously measurable `Value_168h` as its target, which is automatically available post-burn-in.

### C. What this tells us about the regression objective
The failure of the regression models to flag "hidden" components is unequivocally an **objective alignment problem**. The regression models optimize for global mean absolute error (MAE). Since "hidden" components are extremely rare and have early deltas that overlap heavily with the lower tail of the massive nominal distribution, predicting a 168h spike for them would mathematically destroy the model's MAE on the nominal majority. The classification objective (especially when class-weighted) explicitly penalizes missing these rare positive cases, forcing the algorithm to isolate the abnormally low early-drift regions.

### D. What this does NOT establish for real ATE deployment
This does not establish that we should replace the Module B regression models with a classifier in production. The SIH26170 problem statement explicitly demands a "predictive regression model... that forecasts Value_168h". Swapping to a pure classifier violates the core specification. Furthermore, the classifier's overall recall (46%) is still unacceptably poor due to the severe physical overlap in the 0h/24h feature space. The diagnostic merely proves that the standard regression loss function acts as a fatal bottleneck for minority, non-monotonic signals.
