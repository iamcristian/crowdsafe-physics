# CrowdSafe-Physics user guide

CrowdSafe-Physics is a reproducible two-dimensional research laboratory for the Helbing–Farkas–Vicsek (HFV) social force model. Its experiments measure evacuation and force-per-circumference pressure and search for a useful circular obstacle. The model and its architectural recommendations require empirical validation before application to an actual venue.

## 1. Installation and first run

Use Python 3.10 or newer. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pytest -q
crowdsafe simulate --agents 40 --speed 2 --duration 60
```

On Windows PowerShell, use `.\.venv\Scripts\Activate.ps1`, or avoid activation
and execution-policy issues by invoking `.\.venv\Scripts\python.exe` directly:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m src.cli serve --port 8001
```

The package preserves the `src` import namespace. `python -m src.cli` is
equivalent to the installed `crowdsafe` command. Run from the repository root:
benchmark design lookup, CLI outputs and study archives use the working
directory. The empirical report uses the repository's `outputs/empirical`.
Node.js is optional for `node --test tests/test_exit_editor.cjs`; it is not
required to serve or use the studio.

The default research setup uses 60 people in an 8 × 8 m room with a centered 1 m exit in the right wall. The timestep is 0.0015 s, desired speed is 5 m/s, and maximum observation duration is 90 s. Initial positions are a separated, jittered upstream lattice. The simulation can finish before the horizon if all bodies leave.

## 2. Commands

Multiline examples in this section use Bash `\` continuation. In PowerShell,
put each command on one line; when using Python directly, replace `crowdsafe`
with `.\.venv\Scripts\python.exe -m src.cli`.

### Simulate a single experiment

```bash
crowdsafe simulate --agents 60 --speed 5 --seed 7 \
  --dt 0.0015 --duration 90 --method euler --output outputs/example
crowdsafe simulate --agents 20 --speed 2 --method verlet \
  --duration 60 --output outputs/verlet
```

`simulate` writes `data/simulation.json` and `data/simulation.csv` inside the requested output directory. Repeating a command with the same directory overwrites that command's files. Use distinct directories to preserve experiments. The CLI prints a strict JSON summary; incomplete evacuation has `null` event times, not an invented completion at the horizon.

| Option | Meaning | Units / default |
|---|---|---|
| `--agents` | Initial pedestrian count | 60 |
| `--speed` | Desired walking/running speed | 5 m/s |
| `--dt` | Fixed integration step | 0.0015 s |
| `--duration` | Observation horizon | 90 s |
| `--seed` | Initial-state RNG seed | 7 |
| `--method` | `euler` or generalized `verlet` | `euler` |
| `--room` | JSON geometry file | Default room if omitted |
| `--output` | Artifact directory | `outputs` |

The upstream lattice has a finite capacity: the default room accommodates 70 bodies with the default maximum radius. The initializer rejects excessive crowd sizes, initial wall intersections, and initial pillar intersections. Enlarge the room rather than forcing overlapping initial bodies. Changing the radius distribution changes this capacity.

### Reproduce the complete benchmark

```bash
crowdsafe benchmark --agents 60 --dt 0.0015 --duration 90 \
  --iterations 3 --population 4 \
  --train-seeds 7 11 --seeds 19 23 31 --output outputs
crowdsafe plots --output outputs
```

The workflow runs five prescribed speeds, trains a differential-evolution search at 5 m/s, evaluates the selected design on unseen seeds, checks both designs at half the timestep on the first evaluation seed, and generates four figures. The speed sweep deliberately overrides `--speed`; training/evaluation seed lists override the single-run `--seed`. The common room, agent count, integration method, duration, and timestep remain shared.

The optimizer has three variables, so `--population 4` gives 12 population members. Three generations permit up to 48 objective evaluations including the initial population. Infeasible candidates do not run physics; each feasible candidate runs every training seed. Runtime depends strongly on crowd size, clogging, hardware, and horizon. The complete benchmark is materially more expensive than a single run.

Training and evaluation seeds must be disjoint. Changing the optimizer budget or objective after inspecting evaluation results requires a fresh independent evaluation before claiming generalization. The checked-in experiment is a small reproducibility study, not a statistically powered clinical or engineering validation.

### Optimize without the full benchmark

```bash
crowdsafe optimize --agents 60 --speed 5 --iterations 3 --population 4 \
  --train-seeds 7 11 --output outputs/search
```

This writes `data/optimization.json` with the selected pillar, loss, baseline metrics, feasibility checks, and every evaluated candidate. It does not assert that the selected pillar improves every metric. The objective weights peak pressure, agent-time mean pressure, and restricted mean evacuation time, plus a censoring penalty. Inspect the independent benchmark before interpreting a design as beneficial.

### Regenerate scientific figures

```bash
crowdsafe plots --output outputs
```

This reads stored benchmark data without rerunning physics and writes:

1. `figures/faster_is_slower_curve.png`: T90 and peak pressure versus desired speed, with sample standard deviations across seeds.
2. `figures/spatial_pressure_heatmap.png`: baseline and pillar conditional mean sampled pressure, using one shared color scale. Empty bins are masked.
3. `figures/evacuation_survival_curves.png`: ensemble mean fraction remaining versus exact exit-event time across all evaluation seeds, with replicate minimum–maximum bands.
4. `figures/force_chains_snapshot.png`: both designs at their own peak-pressure instant; cyan edge widths scale with elastic force within each panel.

The snapshots are generally at different times. Circle colors in the force-chain panels normalize to each panel's maximum; use the shared-scale pressure heatmap for quantitative cross-design color comparisons. Force chains can exist without satisfying the arch heuristic.

## 3. Interactive web laboratory

```bash
crowdsafe serve --host 127.0.0.1 --port 8001
```

Open `http://127.0.0.1:8001`. Keep the server terminal open. The CLI defaults
to port 8000 without `--port`. No JavaScript build, CDN, API key, or external
service is required. The browser connects to `/ws`; the server computes the
same Python force law used by offline experiments. `/health` reports readiness.
FastAPI's `/docs` describes HTTP endpoints; the WebSocket protocol is below.
Use the collapsible left menu or **Find a tool** (Ctrl+K) to navigate. See
[STUDIO_GUIDE.md](STUDIO_GUIDE.md) for the full navigation guide.

- **Start / Pause / Reset** control one isolated simulation for your browser connection.
- **Desired speed** changes desired speed live, from 0.5 to 7 m/s. It does not change mass, friction, or the speed cap.
- **Crowd size** and **Exit width** rebuild the seeded initial state and pause the simulation.
- **Asymmetric safety-pillar experiment** inserts the selected benchmark pillar when `outputs/data/benchmark_summary.json` exists. Otherwise it uses an explicitly labeled demonstration circle at (6, 4.45) m, radius 0.45 m.
- Body colors show current pair-normal radial pressure. Charts show current peak pressure and a two-second event flow window. These differ from the all-time peak and whole-run average flow in the summary.

The dashboard initially uses 40 bodies, a 1.2 m exit, dt=0.0015 s and a 120 s
horizon. These differ from the archived benchmark. Browser display rate does
not change the integration step. Workspace navigation preserves the live run
and drafts. Reloading/reconnecting starts a fresh simulation.

| Workspace | Current workflow |
| --- | --- |
| Simulation | Start/Pause/Reset; inspector Run, Population, Model and Inspect tabs. Apply buttons reset the run. |
| Scenario | Draw walls/spawn with two clicks; place pillars/exits; select/drag or edit exact JSON. Apply scenario validates and resets. |
| Analysis | Received-frame replay (up to 2,000 frames), density, velocity, paths, effective elastic contacts and sampled exposure; capture runs as A/B before reset. Seeking replay pauses the live run. |
| Experiments | Save settings as A/B or enter a sweep; supply distinct common seeds; run and review Results & archive. All candidates need the same configured horizon. |
| Evidence | Load the stored HERMES report, or upload separate train/validation RMET observations for scalar speed calibration. |
| Building | Edit network JSON and run the separate directed capacity model with stair and visibility assumptions. |

Only one background study can run at once. Completed results persist in
`outputs/studies` and can be opened through Results & archive. Running jobs
and progress are held in server memory; restarting the server interrupts them.
Export scenarios and recorded frames before reloading. A snapshot export
contains current state and metrics, not a complete trajectory.

The basic exit slider and pillar toggle are disabled for custom geometry;
edit it in Scenario instead. Population changes can exceed spawn capacity.
HFV supports elastic/frictional contact; the alternative social-only model
does not. Group cohesion and queue-based exit choice are experimental controls
in the Model tab; see [RESEARCH_MODULES.md](RESEARCH_MODULES.md).

A client may send:

```json
{"action":"configure","controls":{"speed":5,"crowd":40,"exit_width":1.2,"pillar":true}}
```

Other actions are `play`, `pause`, `reset`, and `step`. A `step` request advances 20 small physics steps. Replies contain `time`, `positions`, `radii`, `pressure`, `room`, `evacuated`, `flow`, `playing`, and `done`. Invalid settings produce an `error` reply and preserve the connection. Every position is in meters and every pressure in N/m.

## 4. Custom rooms and obstacles

Save this as `room.json`:

```json
{
  "width": 10.0,
  "height": 8.0,
  "exit_width": 1.4,
  "pillars": [{"x": 8.0, "y": 4.55, "radius": 0.4}],
  "interior_segments": [[[7.0, 0.5], [7.5, 0.5]]]
}
```

Then run:

```bash
crowdsafe simulate --room room.json --agents 60 --speed 3.5 \
  --output outputs/custom-room
```

Coordinates use a bottom-left origin, x increases rightward, and y upward.
Without explicit `exits`, `exit_width` defines the centered right-wall opening.
Wall segments exert shortest-point-distance forces, including at endpoints.
Pillars use exact circle-surface distance. Interior segments are two-sided;
obstacles must fit inside the rectangle and must not intersect initial bodies.

For multiple exits, add `"exits":[{"side":"right","center":4,"width":3},
{"side":"top","center":5,"width":2}]` to the example above. Center is the
distance along the wall: y on left/right walls, x on top/bottom walls.
Each opening must fit its wall; openings on the same wall must not overlap.
Full-wall openings are supported. An empty exit list falls back to the legacy
right opening. Optional `"spawn":[0.5,0.5,5,7]` sets [x,y,width,height] in meters.

Explicit exits or interior walls enable an eight-neighbor Dijkstra router with
a 0.25 m clearance grid. Unreachable initial agents are rejected; narrow
passages can be rejected conservatively. Reachability does not guarantee
evacuation under physical congestion. Arch detection is unavailable for any
explicit-exit configuration, including a single explicit exit. See
[SCENARIO_EDITOR.md](SCENARIO_EDITOR.md). Interactive rooms are limited to
50 m dimensions, 30 pillars and 60 interior wall segments. Arbitrary outer
polygons are unsupported. Stairs belong to the separate Building network.

For differential evolution, start with no existing pillar. The search inserts one asymmetric circle in a constrained region near the exit. Its geometry constraints preserve common initial conditions but do not represent a building code, wheelchair clearance specification, or evacuation standard.

## 5. Python API

```python
from dataclasses import replace
from src.config import Physics, Room, Pillar, SimulationConfig
from src.simulation import Simulation, simulate

physics = Physics(tau=0.5, kappa=240000.0)
baseline = SimulationConfig(n_agents=40, desired_speed=5, physics=physics)
room = replace(baseline.room, pillars=(Pillar(6.1, 4.5, 0.4),))
result = simulate(replace(baseline, room=room))
result.save("outputs/api/data", "pillar")
print(result.metrics)

engine = Simulation(baseline, record=False)
for step_index in range(100):
    engine.step()
print(engine.time, engine.positions.shape)
```

The public kernels in `src.physics.forces` accept floating NumPy arrays: positions and velocities `(N,2)`, radii `(N,)`. `pair_forces` returns force `(N,N,2)` and scalar load/contact matrices `(N,N)`. `total_forces` returns a `ForceResult` with total forces, pair normal load, elastic compression, boundary normal load, and overlaps. Calling low-level kernels assumes valid SI arrays; configuration validation applies at the simulation interface.

`record=False` avoids sampled trajectory storage but still computes every-step maxima, exit events, CSV telemetry, and sampled arch durations. Memory and compute for the pair kernel grow quadratically with active crowd size. No spatial cutoff is imposed on the exponential force.

## 6. Reading the data

Each run JSON has `config`, `metrics`, `telemetry`, `exit_times`, `frames`, and `snapshot`. Frames are intentionally omitted for nonrepresentative benchmark replicates; their full time-series telemetry and scalar metrics are still saved. The benchmark summary records dependency versions and the exact seeds/configuration.

| Metric | Definition and interpretation |
|---|---|
| `t90` | Time of the ceil(0.9 N)-th full-body exit; null if unobserved |
| `total_evacuation_time` | Last full-body exit if all leave; otherwise null |
| `observed_time` | Actual stopping time, at completion or the observation horizon |
| `restricted_mean_evacuation_time` | Mean min(exit time, stopping time), including censored bodies |
| `peak_pressure` | Largest every-step pair-normal load/circumference, N/m |
| `mean_pressure` | Pressure integral divided by active agent-time, N/m |
| `peak_boundary_inclusive_pressure` | Parallel peak metric including wall and pillar normal loads |
| `exposure_agent_seconds` | Sum of time above the requested 1,600 N/m pair-pressure indicator |
| `mean_flow_rate` | Number evacuated divided by actual observed time, pedestrians/s |
| `arch_duration` | Integral of sampled slow jamb-spanning contact-graph indicator, seconds |
| `velocity_clamp_count` | Number of capped body updates, not number of distinct bodies |
| `max_pair_overlap` | Largest disk overlap, meters; diagnostic of model deformation |

Do not confuse force per circumference (N/m) with pressure in pascals (N/m²), or exposure agent-seconds with a probability of death. Psychological repulsion contributes to the requested primary normal-force metric even before contact. The code additionally retains elastic compression for contact graphs. Arch duration has uncertainty at the recording interval, normally 0.15 s, around each transition.

## 7. Numerical checks and troubleshooting

A configuration rejects dt above 0.2 sqrt(m/k), but friction and multiple neighbors can impose a stricter limit. Halve dt, compare aggregate metrics across seeds, inspect maximum overlap, and inspect clamp counts. Capping stabilizes otherwise excessive speeds but modifies the equations; a run with frequent caps is unsuitable for an unqualified physical claim. Exact contact sequences may change under refinement even when aggregate trends remain stable.

If T90 is null, increase the horizon or inspect congestion and routing; do not interpret null as zero. If the initial lattice is full, decrease crowd size or enlarge the room/spawn area. If an initial disk intersects a custom wall, revise the geometry. If plots fail because data are absent, run `benchmark` first. If the browser disconnects, check the server terminal and `/health`. Reinstall with `python -m pip install -e .` if WebSocket support is missing; plain Uvicorn without its standard extra is insufficient. Reloading discards the live run.

If port 8001 is occupied, choose another `--port` and open that port in the
browser. Stop the existing server with Ctrl+C before restarting after Python
changes. For missing empirical results, run `python -m src.empirical` from
the root with the HERMES files described in its dataset README. The resulting
local forecasts currently perform worse than constant velocity and use future
frames to estimate initial velocity; they are retrospective comparisons.

Run `python -m pytest -q` and, with Node.js installed,
`node --test tests/test_exit_editor.cjs` after relevant modifications. Rerun
benchmarks when physics, geometry, integration, metrics or optimization changes;
archived numbers are not automatically updated by code changes.
