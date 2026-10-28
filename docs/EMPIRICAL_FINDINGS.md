# Experimental comparison: HERMES bottleneck trajectories

Data source: https://doi.org/10.34735/ped.2009.6 (CC BY 4.0).
Raw archive and attribution: ../data/experimental/hermes/README.md.
Machine-readable results: ../outputs/empirical/hermes_report.json.
Figure: ../outputs/empirical/hermes_validation.png.

The downloaded five runs cover 2.4, 3.0, 3.6, 4.4 and 5.0 m openings.
Coordinates were converted from cm to m; timestamps use 16 Hz. Training widths
were 2.4, 3.6 and 5.0 m; 3.0 and 4.4 m were held out. The selected tested pair
was desired speed 1.0 m/s and relaxation time 0.3 s.

| Held-out run | Forecasts | Model RMSE (m) | Constant velocity (m) | Stationary (m) |
| --- | ---: | ---: | ---: | ---: |
| ao-300-400 | 492 | 0.424 | 0.071 | 0.151 |
| ao-440-400 | 391 | 0.408 | 0.075 | 0.218 |

The model does not outperform either reference under this protocol. This is
evidence of a limitation, not evidence that the model has been validated. The
first held-out run also activated 42 speed-clamped body updates. Initial body
overlaps, assumed radius, head tracking, boundary truncation and uncalibrated
force coefficients can influence the mismatch; their relative contributions
have not been isolated. Do not attribute failure to any one without an ablation.

Forecasts reconstruct 0.5 s local ensembles from observed initial states. Initial
velocities are centered estimates using frames before and after the start, so
the benchmark is retrospective rather than a causal online prediction task.
Observations share people and are not independent. The split tests widths within
one experiment, not transfer to an independent population. No measured contact
loads are included; these trajectories cannot validate injury indicators.

Run `.venv\Scripts\python.exe -m src.empirical` to reproduce both outputs.
