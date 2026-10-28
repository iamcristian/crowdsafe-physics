# Replay, studies and calibration

Population distributions and one-factor studies are available under Population
& design exploration. Speed factors and pre-movement times use independent
uniform samples from a separate seeded random stream. Radius changes affect
initial placement and clearance. Delayed agents remain physically movable.

The parameter selector supports speed, crowd size, timestep, delay, speed spread
and radius. Enter dt, dt/2 and dt/4 to compare integration sensitivity. These are
one-factor studies, not global sensitivity indices. Common seeds reduce initial
condition variation when the geometry and body size distributions are unchanged.

Append room objects to Candidate design set and evaluate them to obtain a
finite-candidate Pareto front. Plot coordinates are mean RMET and peak pair load;
dominance also includes threshold exposure. Membership is based on means, not
uncertainty bounds, and needs independent evaluation before selecting a design.

Completed results are automatically saved under outputs/studies, including the
request, model revision, environment and SHA-256 request checksum. Refresh saved
studies and Open saved results restore them after a server restart. Reconnection
creates a new run and synchronizes initial controls; run IDs separate replay
recordings even when reset occurs at t=0. Export scenarios to preserve geometry.

All analysis controls are in English. Replay records at most 2,000 received
WebSocket frames in browser memory. Reset/reconnect starts a new recording.
Capture A/B before resetting; captured runs remain until the page is reloaded.
Scrubbing pauses the server and renders the selected recorded state. The main
metric cards, agent inspection and spatial layers use the replay frame; the
bottom status bar and live charts retain server context. The A/B canvases use
nearest recorded times, explicitly shown.
Export recorded frames before closing the page to preserve them.

Layers: pair normal load (N/m), density in 1 m square counting bins (persons/m²,
not Voronoi density), velocity vectors (0.4 s vector length), agent trajectories,
elastic contact links, and sampled time above the reference load. Sampled
exposure uses received frames and differs from every-step server telemetry.
The retained recording window bounds path and sampled exposure history.

Save current settings as A and B, enter distinct seeds, then Run experiment.
Alternatively enter desired-speed values for a sweep of the current settings.
The server runs each candidate with the same seeds. Results contain all configs,
metrics, censoring counts, sample SD, Student-t 95% intervals of the seed mean,
and paired candidate-minus-A differences. Unobserved event times remain null;
their observed counts are shown. Intervals quantify between-seed sampling
variation, not model bias or empirical accuracy. One seed yields no interval.

Studies run one at a time; cancellation is cooperative. Up to eight jobs remain
in server memory; completed results persist on disk. Jobs support 1–6 candidates
and 1–12 seeds; long horizons and small time steps can take considerable time.

## Calibration observation format

Upload a JSON array of rows, for example:

```json
[
  {"seed": 7, "split": "train", "rmet": 22.4},
  {"seed": 11, "split": "train", "rmet": 23.1},
  {"seed": 19, "split": "validation", "rmet": 24.0}
]
```

These numbers illustrate the schema only; they are not experimental data.
RMET is the mean of min(exit time, observation horizon) across all initial
agents. Configure matching geometry, population and horizon before fitting.
Seeds identify the simulated initial conditions associated with each observation.
The finite desired-speed candidate grid minimizes training RMSE. Held-out seeds
are evaluated only after selection. Export includes observations, candidate
scores and held-out predictions. This is scalar calibration; trajectory fitting,
multi-parameter inference and independent empirical validation are not included.
