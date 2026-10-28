# Model scope and scientific limitations

## Implemented

The 2-D engine implements HFV social, elastic and frictional contact forces,
Euler and generalized Verlet integration, full-body crossing events and censored
evacuation metrics. Population options include radius and desired-speed variation
and start delays from seeded streams. Waiting bodies still respond to forces.

Rectangular rooms support pillars, interior walls, exits on all four sides and a
rectangular spawn area. Explicit exits or interior walls enable a clearance-aware
0.25 m routing grid. Wide openings target usable aperture points rather than a
single center. Congestion-based exit choice and visible-centroid group attraction
are experimental options. The social-only alternative disables granular contact.

The studio provides replay, spatial layers, replicated comparisons, sampled Pareto
sets, one-factor studies, Sobol estimates, sequential precision stopping and a
random single-pillar search with separate evaluation seeds. Completed studies
retain requests, configurations and provenance. All compared candidates must use
the same observation horizon.

A separate directed building network supports capacities, floor metadata, stairs
and externally supplied visibility schedules. It is independent of the 2-D engine.

## Interpretation limits

- HERMES local forecasts perform worse than constant velocity; see
  [empirical findings](EMPIRICAL_FINDINGS.md). Centered initial velocity uses future
  observations, so this is a retrospective evaluation.
- Full evacuation and contact loads lack independent empirical validation.
  Load references in N/m are not validated injury probabilities.
- Group attraction and queue penalties are heuristic, not independently calibrated.
- Pareto ranking uses sample means without uncertainty in dominance. Seed intervals
  quantify simulation variability, not model bias. Small Sobol budgets require
  convergence checks; sequential stopping has repeated-checking coverage limits.
- Route reachability is conservative near grid resolution and does not guarantee
  physical evacuation. Arch detection is unavailable with explicit exits.
- No polygon/CAD outer boundaries, ORCA/JuPedSim adapter, physical 3-D stairs,
  wheelchair dynamics, CFD, fire transport or toxic-dose calculation is implemented.

The next scientific priority is past-only velocity estimation with recalibration
and held-out trajectory evaluation, then independent flow and force benchmarks.
Archived benchmark values in PAPER.md predate aperture/routing revisions and
must be regenerated before drawing conclusions about the current engine.
