# Research modules and empirical evidence

All UI controls are English. Research jobs use the existing progress/cancel,
archive and export workflow. Configure a short pilot horizon before expensive
parameter sweeps. Increase it for conclusions about completed evacuation.

## Movement

HFV retains elastic and frictional forces. Social-only sets k=kappa=0, retaining
the same driving, exponential repulsion and routing. It can overlap and is not a
collision-free model. Groups are contiguous initial ID blocks; attraction toward
a visible centroid begins beyond 0.8 m and is capped at 160 N. Congestion cost is
distance plus weight × nearby agents / exit width, updated every 0.15 s, with
0.5 m hysteresis. These extensions are experimental behavioral assumptions.

## Global studies

Sobol jobs use independent uniform inputs, A/B sample matrices and A-with-B-column
hybrids. Saltelli first-order and Jansen total-order estimates are reported for
RMET, peak pair load and exposure, after averaging common-seed replicates. Small
budgets are for diagnostics; run multiple larger budgets to assess convergence.
Zero output variance produces null indices. This does not measure model bias.

Sequential Monte Carlo checks mean-RMET Student-t interval half-width after at
least four complete replicates. Censoring prevents early stopping. Repeated
checking is exploratory and does not provide fixed 95% simultaneous coverage.

Automatic geometry search draws one downstream circle per candidate from a
seeded RNG, rejects infeasible initialization/routes, and evaluates the sampled
set on training seeds. Only training Pareto candidates proceed to held-out
seeds. Baseline is included; it may dominate the obstacle designs. Geometry
effects do not establish code compliance or injury prevention.

## Open experimental data

Data: Forschungszentrum Jülich, HERMES bottleneck, DOI 10.34735/ped.2009.6,
CC BY 4.0. Raw ZIP and metadata are in data/experimental/hermes. Source files
are unmodified; loader converts cm to m in memory and uses 16 Hz timestamps.
Metadata obstacle polygons determine walls. A 0.2 m body radius is assumed.

Reproduce: `.venv\Scripts\python.exe -m src.empirical`.
It writes outputs/empirical/hermes_report.json and hermes_validation.png.
Widths 2.4, 3.6 and 5.0 m select desired speed and relaxation time on a 3×3 grid;
3.0 and 4.4 m are held out. Eight uniformly spaced observation frames per run
seed 0.5 s ensemble forecasts, integrated in 167 steps. Centered initial velocity
uses future observations: this is retrospective motion reconstruction, not a
causal forecasting benchmark. Missing tracks at the camera boundary and assumed
body size limit interpretation. Samples share individuals and are dependent.

Observed held-out RMSE: model 0.424/0.408 m, constant velocity 0.071/0.075 m.
The model fails to outperform this reference. That result is retained, not
converted into a validation claim. No real contact forces, complete initial
populations or full evacuation times were measured by this imported dataset.

## Building network

The network is a separate model with directed links, lengths (m), capacities
(persons/s), node floor metadata and population placement. Stair links multiply
walking speed by stair_factor. Visibility schedules use entries
`{"node":"lobby","time":30,"meters":5}`. Affected link speed is multiplied by
visibility/10 in the 1–10 m range; below 1 m it closes. These are explicit user
assumptions, not a calibrated smoke response. Existing travelers stop on closed
links. Routes are recalculated from available links; queuing uses deterministic
population order. No CFD, fire growth, toxicity, density coupling or physical
contact is included. External visibility time series may be supplied in JSON.
