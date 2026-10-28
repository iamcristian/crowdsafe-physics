r"""Render the landing page and IMRaD manuscript directly from measured JSON.

All numerical prose and result tables read benchmark_summary.json. No numerical
claim is supplied by a hand-entered constant. A source index uses Python AST
line numbers to connect the educational tutorial to the exact implementation.
"""
import ast
import json
from pathlib import Path


def mean_sd(stat, digits=2):
    r"""Format a measured mean and sample SD, preserving unobserved outcomes.

    Missing event means remain 'not observed'; they are never converted to a
    numeric zero. Formatting is presentation only and does not alter data.
    """
    if stat["mean"] is None:
        return "not observed"
    return f"{stat['mean']:.{digits}f} ± {stat['sd']:.{digits}f}"


def write_reports(output="outputs", repository="."):
    r"""Generate English documentation with traceable numerical result tables.

    The report uses held-out means for percentage differences and also lists
    individual paired changes. These are distinct estimands, so the text never
    silently substitutes mean paired percentage for ratio of ensemble means.
    """
    root, destination = Path(output), Path(repository)
    summary = json.loads((root / "data/benchmark_summary.json").read_text(encoding="utf-8"))
    search = json.loads((root / "data/optimization.json").read_text(encoding="utf-8"))
    speed_rows = []
    for speed, stats in summary["speed_experiment"].items():
        speed_rows.append(f"| {float(speed):g} | {mean_sd(stats['t90'])} | {mean_sd(stats['peak_pressure'], 0)} | "
                          f"{mean_sd(stats['mean_flow_rate'])} | {mean_sd(stats['arch_duration'])} | {stats['censored_runs']} |")
    speed_table = ("| Desired speed (m/s) | T90 (s) | Peak pressure (N/m) | Flow (ped/s) | Arch time (s) | Censored runs |\n"
                   "|---|---:|---:|---:|---:|---:|\n" + "\n".join(speed_rows))
    base, opt = summary["baseline"], summary["optimized"]
    comparison_rows = []
    for key, label, digits in (("t90", "T90 (s)", 2), ("total_evacuation_time", "Total evacuation time (s)", 2),
                               ("restricted_mean_evacuation_time", "Restricted mean evacuation time (s)", 2),
                               ("peak_pressure", "Peak pair pressure (N/m)", 0), ("mean_pressure", "Agent-time mean pair pressure (N/m)", 0),
                               ("peak_boundary_inclusive_pressure", "Peak boundary-inclusive pressure (N/m)", 0),
                               ("mean_flow_rate", "Mean flow (ped/s)", 3), ("exposure_agent_seconds", "Threshold exposure (agent-s)", 2),
                               ("arch_duration", "Arch-candidate duration (s)", 2), ("max_pair_overlap", "Maximum pair overlap (m)", 4),
                               ("velocity_clamp_count", "Capped body updates", 0)):
        comparison_rows.append(f"| {label} | {mean_sd(base[key], digits)} | {mean_sd(opt[key], digits)} |")
    comparison_table = "| Outcome | Baseline | Selected pillar |\n|---|---:|---:|\n" + "\n".join(comparison_rows)
    paired_table = "| Evaluation seed | Peak-pressure reduction (%) | Mean-pressure reduction (%) | Flow change (%) |\n|---|---:|---:|---:|\n"
    paired_table += "\n".join(f"| {item['seed']} | {item['pressure_reduction_percent']:.2f} | {item['mean_pressure_reduction_percent']:.2f} | {item['flow_improvement_percent']:+.2f} |"
                              for item in summary["paired_changes"])
    convergence_rows = []
    for name, values in summary["convergence"].items():
        for resolution in ("coarse", "fine"):
            metrics = values[resolution]
            dt = values["dt"] if resolution == "coarse" else values["half_dt"]
            t90 = f"{metrics['t90']:.3f}" if metrics["t90"] is not None else "not observed"
            convergence_rows.append(f"| {name.title()} | {dt:g} | {t90} | {metrics['peak_pressure']:.1f} | {metrics['mean_flow_rate']:.3f} | {metrics['velocity_clamp_count']} |")
    convergence_table = "| Design | dt (s) | T90 (s) | Peak pressure (N/m) | Flow (ped/s) | Capped updates |\n|---|---:|---:|---:|---:|---:|\n" + "\n".join(convergence_rows)
    pillar, config = summary["selected_pillar"], summary["config"]
    x, y, radius = pillar["x"], pillar["y"], pillar["radius"]
    reduction = summary["peak_pressure_reduction_percent"]
    mean_reduction = summary["mean_pressure_reduction_percent"]
    flow_change = summary["flow_improvement_percent"]
    speeds = summary["speed_experiment"]
    minimum_speed = min((key for key in speeds if speeds[key]["t90"]["mean"] is not None), key=lambda key: speeds[key]["t90"]["mean"])
    slowdown = 100*(speeds["7.0"]["t90"]["mean"]/speeds[minimum_speed]["t90"]["mean"]-1)
    peak_ratio = speeds["7.0"]["peak_pressure"]["mean"]/speeds[minimum_speed]["peak_pressure"]["mean"]
    peak_target = "achieved" if reduction > 25 else "not achieved"
    flow_target = "achieved" if flow_change > 0 else "not achieved"
    seeds = ", ".join(map(str, summary["evaluation_seeds"]))
    training_seeds = ", ".join(map(str, summary["training_seeds"]))
    feasible_count = sum(item["feasible"] for item in search["history"])
    readme = f'''# CrowdSafe-Physics

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![License](https://img.shields.io/badge/License-MIT-green)
![Model](https://img.shields.io/badge/Model-HFV%202000-blue)
![Reproducibility](https://img.shields.io/badge/Results-seeded%20and%20archived-teal)

**A learn-by-reading research repository for crowd contact mechanics, bottleneck evacuation, and evolutionary pillar placement.** It implements the Helbing–Farkas–Vicsek social force law with vectorized NumPy, two numerical integrators, auditable safety proxies, publication figures, and an interactive Python-backed Canvas laboratory.

The included experiment measured a **{slowdown:.1f}% increase in T90 from {float(minimum_speed):g} to 7 m/s**. Independent evaluation of the selected asymmetric pillar measured **{reduction:.1f}% lower peak pair pressure**, **{mean_reduction:.1f}% lower mean pair pressure**, and **{flow_change:+.1f}% change in mean flow** relative to the baseline at 5 m/s. These are finite-model results, not a guarantee that a pillar prevents injury in a real building. Negative reductions mean an increase.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pytest -q
crowdsafe simulate --agents 40 --speed 2 --duration 60 --output outputs/example
crowdsafe serve
```

Open **http://127.0.0.1:8000** for Play/Pause/Reset, desired-speed/crowd/exit controls, a pillar toggle, pressure-colored bodies, and live telemetry. The browser uses the same physics engine as offline runs. For all command options, use `crowdsafe --help` and the [user guide](docs/USAGE_GUIDE.md).

## Measured benchmark

The room is {config['room']['width']:g} × {config['room']['height']:g} m with a {config['room']['exit_width']:g} m exit and {config['n_agents']} pedestrians. The timestep is {config['dt']:g} s and observation horizon {config['duration']:g} s. Values are mean ± sample SD over independent evaluation seeds **{seeds}**. Censoring means total evacuation was not observed; an earlier T90 may still be observed.

{speed_table}

The fastest measured T90 occurs at {float(minimum_speed):g} m/s. This experiment supports a high-speed slowdown, not a monotonic statement that every increase in desired speed worsens evacuation. Pressure rises by a factor of {peak_ratio:.2f} between that speed and 7 m/s.

The optimizer trained on seeds **{training_seeds}** and selected **(x, y, R)=({x:.4f}, {y:.4f}, {radius:.4f}) m**. It evaluated {search['evaluations']} candidates, of which {feasible_count} met geometry constraints. The independent >25% peak-pressure-reduction target was **{peak_target}**; faster mean outflow was **{flow_target}**.

{comparison_table}

See the complete [IMRaD paper](PAPER.md), including per-seed effects, censoring, and timestep sensitivity. Exact values and configuration are in [`outputs/data/benchmark_summary.json`](outputs/data/benchmark_summary.json); all search candidates are in [`optimization.json`](outputs/data/optimization.json).

## Architecture

```mermaid
flowchart TD
    A[Validated SI configuration and seeded initialization] --> B[Exact wall and circle geometry]
    B --> C[Vectorized social, compression and friction forces]
    C --> D[Euler or generalized velocity Verlet]
    D --> E[Exit events, pressure and contact graphs]
    E --> F[JSON and CSV measurements]
    F --> G[300-DPI scientific figures and manuscript]
    H[Differential evolution: x, y, radius] --> A
    E --> H
    I[FastAPI and WebSocket controls] --> D
    D --> J[HTML5 Canvas and live charts]
```

`src/physics` contains the force and integration equations; `src/analytics` contains pressure and arch candidates; `src/optimization` contains the reproducible search; and `src/visualization` contains figures and the browser application. `simulation.py` connects the components, `experiments.py` controls train/evaluation separation, and `reporting.py` derives numerical prose from stored measurements.

## Reproduce everything

```bash
crowdsafe benchmark --agents 60 --dt 0.0015 --duration 90 \\
  --iterations 3 --population 4 --train-seeds 7 11 --seeds 19 23 31
crowdsafe plots
python -m src.reporting
```

The complete benchmark performs many real simulations and takes substantially longer than the tests. It runs the five-speed sweep, differential evolution, three-seed independent comparison, and a half-timestep sensitivity check. Plotting alone requires no new simulation. To preserve alternate experiments, provide a separate `--output` directory. The commands above describe the archived default run; see the JSON configuration for any alternate output.

## Scientific figures

![Desired speed experiment](outputs/figures/faster_is_slower_curve.png)
![Spatial pressure comparison](outputs/figures/spatial_pressure_heatmap.png)

The [survival curves](outputs/figures/evacuation_survival_curves.png) and [force-chain snapshots](outputs/figures/force_chains_snapshot.png) complete the four-figure set. Figures are 300-DPI PNGs generated from real trajectories.

## Learn and extend

- [Math and physics tutorial](MATH_AND_PHYSICS_TUTORIAL.md): equations, SI dimensions, broadcasting, numerical stability, and exact source-line links.
- [Usage guide](docs/USAGE_GUIDE.md): CLI, browser controls, custom rooms, API, output schema, and troubleshooting.
- [Paper](PAPER.md): scientific question, methods, measured results, interpretation, and limitations.
- [Contributing](CONTRIBUTING.md): invariants, reproducibility, and evaluation discipline.

The requested primary radial metric is pair normal force divided by circumference in **N/m**, including social and elastic terms. Boundary-inclusive load is reported separately. The 1,600 N/m indicator is a research threshold, not a validated asphyxiation predictor. The graph detector reports slow jamb-spanning contact components; connectivity is not proof of static self-locking. The model has local obstacle steering and soft disks, not a calibrated representation of an individual human or a certified evacuation design.

## Reference and license

Helbing, D., Farkas, I., & Vicsek, T. (2000). *Simulating dynamical features of escape panic.* Nature 407, 487–490. [doi:10.1038/35035023](https://doi.org/10.1038/35035023).

Code and documentation are available under the [MIT license](LICENSE). Citation metadata is in [CITATION.cff](CITATION.cff). This repository is an independently implemented research artifact and does not claim exact reproduction of every experiment in the original paper.
'''
    paper = rf'''# Mitigating the Faster-is-Slower Effect and Crushing Pressures in Bottleneck Evacuations via Evolutionary Obstacle Optimization

**CrowdSafe-Physics contributors · Reproducible computational research manuscript · 26 October 2026**

This manuscript reports the archived numerical experiment. It is not peer reviewed, clinically validated, or a building-design certification. “Crushing pressure” below denotes a two-dimensional normal-force-per-circumference proxy, not measured tissue stress.

## Abstract

**Background.** Dense evacuation can exhibit competition between greater driving speed and dissipative contact congestion. Obstacles upstream of a narrow exit may alter contact networks, but their benefits depend on geometry and behavior.

**Methods.** We implemented the Helbing–Farkas–Vicsek social force law with vectorized pair interactions, exact segment/circle boundary distances, and local pillar steering. We simulated {config['n_agents']} soft disks in a {config['room']['width']:g} × {config['room']['height']:g} m room with a {config['room']['exit_width']:g} m exit at five prescribed desired speeds. Differential evolution selected a single asymmetric circular obstacle using training seeds {training_seeds}; evaluation seeds {seeds} were excluded from selection. We measured T90, flow, pair and boundary-inclusive normal loading, operational contact arches, censoring, and timestep sensitivity.

**Results.** Mean T90 was smallest at {float(minimum_speed):g} m/s and increased by {slowdown:.2f}% at 7 m/s. Mean peak pair pressure increased {peak_ratio:.2f}-fold across the same comparison. At 5 m/s the selected pillar produced a {reduction:.2f}% reduction in mean replicate peak pressure and a {mean_reduction:.2f}% reduction in agent-time mean pressure, with a {flow_change:+.2f}% change in mean flow. The >25% peak-reduction target was {peak_target}; the faster-outflow target was {flow_target} on the independent evaluation ensemble.

**Conclusions.** The results quantify a finite-model speed/contact tradeoff and the measured effect of one optimized obstacle. Small ensembles, a soft-disk constitutive law, local navigation, and contact sensitivity limit extrapolation. No injury-prevention guarantee follows from these simulations.

## 1. Introduction

Crowd evacuation combines purposeful movement with constraints from bodies, walls, and bottlenecks. At low density, raising desired speed usually reduces free travel time. At higher density, additional driving can increase normal compression and tangential friction, potentially slowing passage. Helbing, Farkas and Vicsek [1] demonstrated that a social force formulation with granular contact terms can reproduce qualitative features associated with escape panic.

A strategically located obstacle can redistribute approaching flow before the doorway. Its effect is not universally favorable: it can also narrow usable routes, attract contact loading, or lengthen travel paths. Architecture should therefore be treated as an experimentally testable design variable rather than an assumed remedy.

This study asks two questions. First, does a fixed seeded HFV implementation show an evacuation-time minimum followed by high-speed slowdown? Second, can a small evolutionary search improve pressure and outflow on initial conditions excluded from optimization? The repository couples an educational derivation to executable tests and an auditable record of candidate evaluations. The phrase “mitigating” in the title identifies the research aim; numerical outcomes below determine which targets were actually met.

## 2. Methods

### 2.1 Dynamics and constitutive assumptions

For each pedestrian i, Newton's equation combines driving, pedestrian-pedestrian, and stationary boundary forces:

$$m_i\dot{{\mathbf v}}_i=\frac{{m_i(v_i^0\mathbf e_i^0-\mathbf v_i)}}{{\tau}}+\sum_{{j\ne i}}\mathbf f_{{ij}}+\sum_W\mathbf f_{{iW}}.$$

With h=max(r_i+r_j-d_ij,0), each pair interaction has a normal component A exp((r_i+r_j-d_ij)/B)+kh and a tangential component kappa h ((v_j-v_i)·t_ij). Tangential velocity differences use the sign that dissipates relative sliding energy. There is no rotational degree of freedom and no Coulomb static-friction law. Boundary forces use the analogous normal law and friction against stationary walls or pillars.

Constants are m=80 kg, tau=0.5 s, A=2000 N, B=0.08 m, k=120000 N/m, and kappa=240000 kg/(m s), following the HFV parameterization [1]. Radii are independent uniform samples over [0.28,0.32] m. The desired direction points toward a location 1 m beyond the exit, with smooth local transverse steering near pillars. This explicit navigation extension is documented in the tutorial and is not presented as an exact behavioral replication of the original study.

### 2.2 Geometry and initial conditions

The room is {config['room']['width']:g} m wide and {config['room']['height']:g} m high; its single centered right-wall exit is {config['room']['exit_width']:g} m wide. Exact clipped point-to-segment projections handle both walls and jamb endpoints. Circle distance is center distance minus obstacle radius.

The {config['n_agents']} initial bodies occupy a separated, jittered upstream lattice. A fixed seed reproduces both positions and radii. The downstream design region is kept clear initially, and feasible candidates share the identical baseline state for each seed. Initial disk intersections are rejected. No stochastic forcing is applied after initialization.

### 2.3 Integration and event definition

The archived benchmark uses semi-implicit Euler with dt={config['dt']:g} s and an observation horizon of {config['duration']:g} s. A 12 m/s velocity safeguard counts every activation. The code also supplies generalized velocity Verlet with three endpoint corrector iterations for velocity-dependent force; it is independently tested but is not the integrator used for these tables.

A complete-body exit occurs when the rear edge clears the wall plane, x_center=W+r_i, and the interpolated center lies in the aperture. Linear interpolation estimates the event time within the step; the body is then removed. T90 is the ceil(0.9 N)-th exit. Completion time is null if any body remains at the horizon. Restricted mean evacuation time includes unexited bodies at the observation endpoint, without fabricating events.

### 2.4 Pressure, flow, and arch candidates

Primary radial pressure is P_i=sum_j |f_ij^normal|/(2 pi r_i), in N/m. Normal magnitude includes social and elastic pair terms and excludes tangential force. A separate boundary-inclusive metric adds wall and pillar magnitudes. Mean pressure is weighted by active agent-time; maxima are sampled at every physics step. The requested 1,600 N/m threshold defines an exposure indicator in agent-seconds and is not a medically validated threshold in this implementation.

Whole-run flow equals observed exits divided by observation duration. The dashboard additionally uses a two-second rolling event rate. Contact-graph edges require elastic load ≥100 N. A component is an arch candidate when it connects both jamb neighborhoods, lies near the opening, and has mean speed below 0.35 m/s. The state is sampled every 0.15 s; duration uses left-interval accumulation. This operational detector does not solve equilibrium or establish mechanical self-locking.

### 2.5 Experimental design and optimization

The desired-speed experiment uses 1, 2, 3.5, 5, and 7 m/s on the same evaluation seeds {seeds}. Table values are arithmetic means and sample standard deviations. Event means use only observed events and the JSON reports their observed counts. Total-evacuation censoring counts are listed explicitly. No inferential p-values are calculated from this small ensemble.

Differential evolution [2] optimizes z=(x,y,R) at 5 m/s on training seeds {training_seeds}. The objective averages 0.50 times baseline-normalized peak pressure, 0.25 times baseline-normalized mean pressure, and 0.25 times baseline-normalized restricted mean evacuation time, plus twice the fraction remaining. Pairing uses the identical seed-specific baseline denominator. The objective therefore encodes explicit pressure/efficiency preferences rather than maximizing a retrospectively chosen percentage improvement.

The bounds are x in [W−2.7,W−0.8] m, y in [H/2−1.1,H/2+1.1] m, and R in [0.18,0.65] m. Feasibility requires containment, initial-state clearance, jamb clearance, and |y−H/2|≥0.12 m. The search used seed {search['search_seed']}, population multiplier {search['popsize']}, and {search['maxiter']} generations, evaluating {search['evaluations']} distinct candidates ({feasible_count} feasible). Local polishing was disabled and evaluation used deterministic single-worker updates. The fixed budget terminated with SciPy message: “{search['scipy_message']}”. This indicates a budgeted search, not a proof of global optimality.

Independent comparison used all evaluation seeds after design selection. Percentage changes below are ratios of ensemble means; a separate table preserves paired seed percentages. Baseline and selected pillar were additionally rerun at dt/2 on evaluation seed {summary['evaluation_seeds'][0]}. This is a limited sensitivity analysis, not a full ensemble convergence study.

## 3. Results

### 3.1 Desired speed and high-speed slowdown

{speed_table}

**Table 1.** Mean ± sample SD across {len(summary['evaluation_seeds'])} initial states. “Censored” refers to total evacuation at the observation horizon, not necessarily to T90.

The minimum measured mean T90 occurred at {float(minimum_speed):g} m/s. Raising desired speed to 7 m/s increased T90 by {slowdown:.2f}% and mean replicate peak pressure by a factor of {peak_ratio:.2f}. This supports faster-is-slower over the observed high-speed branch. It does not imply that 7 m/s is slower than every lower speed: initial travel and contact delay compete.

![Speed experiment](outputs/figures/faster_is_slower_curve.png)

**Figure 1.** Desired speed versus T90 and every-step peak pair-normal pressure. Error bars are sample SD, not confidence intervals. Seeds are paired across speeds.

### 3.2 Selected pillar and independent evaluation

The selected obstacle is centered at ({x:.6f},{y:.6f}) m with radius {radius:.6f} m. Its lateral offset from the exit center is {y-config['room']['height']/2:+.6f} m. Training loss was {search['score']:.6f}, compared with {search['baseline_score']:.6f} for baseline and {search['initial_population_best']:.6f} for the best initial-population candidate. Evolutionary retention is independently unit tested; improvement in the training objective does not itself establish independent improvement.

{comparison_table}

**Table 2.** Baseline versus selected pillar at 5 m/s on independent seeds. There were {base['censored_runs']} baseline censored runs and {opt['censored_runs']} pillar censored runs. Boundary-inclusive pressure and overlap expose possible redistribution of load and numerical/constitutive sensitivity.

Relative to ensemble baseline means, peak pair pressure reduction was {reduction:.2f}%, agent-time mean pair pressure reduction was {mean_reduction:.2f}%, and flow changed by {flow_change:+.2f}%. A negative pressure reduction denotes worse loading. The requested >25% peak-reduction outcome was **{peak_target}**, and increased mean outflow was **{flow_target}**.

{paired_table}

**Table 3.** Paired seed effects. Positive pressure reductions mean lower load; positive flow changes mean faster outflow. Individual effects can differ from ratios of ensemble means.

![Pressure maps](outputs/figures/spatial_pressure_heatmap.png)

**Figure 2.** Mean sampled pressure by spatial bin for independent seed {summary['evaluation_seeds'][0]}, with a common color scale and masked unvisited cells. This conditional spatial mean differs from the every-step agent-time mean in Table 2.

![Survival curves](outputs/figures/evacuation_survival_curves.png)

**Figure 3.** Ensemble mean of event-based fractions remaining over all independent evaluation seeds. Shaded bands show the replicate minimum–maximum range, not a confidence interval. The dotted reference denotes 10% remaining; censored trajectories are not extrapolated past observation.

![Force chains](outputs/figures/force_chains_snapshot.png)

**Figure 4.** Each design at its own maximum pair-pressure instant. Cyan segments show elastic contacts ≥100 N; line widths and body colors normalize within each panel. This illustration does not imply that either instant satisfies the arch-candidate detector.

### 3.3 Numerical sensitivity

{convergence_table}

**Table 4.** Timestep-halving check for the first evaluation seed. Capped-update counts expose any activation of the nonphysical speed safeguard. Because contact rearrangements are sensitive, changes in T90 and peak pressure must be considered in judging the precision of ensemble claims. A single fine-timestep seed cannot establish convergence of the three-seed design effect.

### 3.4 Verification and artifact provenance

The repository's test suite checks pair antisymmetry, frictional dissipation, exponential and elastic magnitudes, exact wall and circle distances, force units, analytical integration, timestep refinement, bounded velocity, nonoverlapping initialization, pressure aggregation, exit interpolation, censoring, arch graph criteria, evolutionary retention and measured objective improvement, CLI output, and WebSocket control behavior. These tests validate implementation properties rather than real-world predictive accuracy.

The archived runtime used NumPy {summary['provenance']['numpy']} and SciPy {summary['provenance']['scipy']}. Full Python/platform information is in `benchmark_summary.json`; `environment.json` records the principal dependency versions. Run configurations and time series are stored in JSON/CSV, and `optimization.json` preserves the entire search. The plots are generated from those artifacts, and `python -m src.reporting` regenerates this manuscript's numerical tables.

## 4. Discussion

The observed speed curve is consistent with competition between reduced free-travel time and increased contact congestion. A high desired speed injects driving force into a constrained crowd; compression strengthens elastic load and overlap-dependent tangential damping. The resulting slowdown depends on exit width, density, steering, and parameter choices. A model trend on one geometry is not a universal speed prescription.

Pillar placement changes both approach trajectories and mechanical contacts. The explicit objective encourages reduced peak load, reduced mean load, and shorter restricted evacuation time, but these outcomes need not improve together. The independent seed table is therefore essential: it prevents a favorable training loss or one attractive trajectory from substituting for out-of-training evaluation. The >25% and faster-outflow hypotheses are reported as measured outcomes, not enforced by rescaling data or modifying the plotted metrics.

Several limitations materially constrain interpretation. First, only {len(summary['evaluation_seeds'])} evaluation seeds and one room geometry are reported. Sample SD describes these initial conditions and is not a robust population uncertainty estimate. Second, radii are soft disks with shared mass and desired speed; there are no falls, heterogeneous vulnerability, rotational dynamics, human decision changes, or three-dimensional body mechanics. Third, the local pillar-steering extension can itself influence design benefit and deserves ablation against alternative navigation models.

Fourth, radial N/m load and the 1,600 N/m exposure indicator are not clinically calibrated injury predictors. Pair-only and boundary-inclusive metrics may disagree because load can shift onto an obstacle. Fifth, the graph detector lacks an equilibrium solution and cannot prove self-locking. Sixth, finite timesteps, soft overlaps, and chaotic contact rearrangements limit numerical precision; Table 4 is a sensitivity check rather than an exhaustive convergence result. Seventh, the budgeted evolutionary search may find a useful design without finding a global optimum or a robust design across room sizes.

A stronger follow-up study would preregister geometry and objectives, increase training and fresh evaluation ensembles, compare steering models, conduct full ensemble timestep refinement, vary friction and radius distributions, and calibrate against ethically collected empirical flow/contact measurements. Real architectural proposals also require accessibility, fire engineering, and operational constraints absent from this experiment.

## 5. Conclusions

The implementation supplies a complete reproducible computational chain from SI force laws to recorded exit events, pressure metrics, evolutionary design, and scientific figures. The archived high-speed comparison increased T90 by {slowdown:.2f}%. The selected pillar yielded a {reduction:.2f}% peak-pressure reduction and {flow_change:+.2f}% mean-flow change on the independent ensemble. These measured results support only the stated finite-model conclusions; they do not establish prevention of lethal crowd events.

## Data and code availability

The complete source, tests, documentation, recorded benchmark data, candidate audit, and four PNG figures accompany this repository under the MIT license. The workflow is local and requires no proprietary service. Reproduction commands are in `README.md` and `docs/USAGE_GUIDE.md`. No human-subject data were collected; all trajectories are synthetic. No external funding or competing-interest information is asserted for this generated research artifact.

## References

1. Helbing, D., Farkas, I., & Vicsek, T. (2000). Simulating dynamical features of escape panic. *Nature*, 407, 487–490. https://doi.org/10.1038/35035023
2. Storn, R., & Price, K. (1997). Differential evolution—a simple and efficient heuristic for global optimization over continuous spaces. *Journal of Global Optimization*, 11, 341–359. https://doi.org/10.1023/A:1008202821328
'''
    # Keep the curated GitHub landing page intact when regenerating results.
    notice = "> Generated historical benchmark report. For current installation and studio usage, see [README.md](README.md). Archived values may predate steering revisions.\n\n"
    (destination / "BENCHMARK_REPORT.md").write_text(notice + readme, encoding="utf-8")
    (destination / "PAPER.md").write_text(paper, encoding="utf-8")
    tutorial = destination / "MATH_AND_PHYSICS_TUTORIAL.md"
    body = tutorial.read_text(encoding="utf-8").split("\n## Exact source-line index")[0]
    index = ["\n## Exact source-line index\n", "The links below are generated from the current Python AST. Each points to the definition whose docstring explains the equation, units, and array shapes.\n", "| Module | Function or method | Source line |", "|---|---|---:|"]
    for relative in ("src/config.py", "src/physics/geometry.py", "src/physics/forces.py", "src/physics/integrator.py", "src/analytics/telemetry.py", "src/analytics/arch_detector.py", "src/simulation.py", "src/optimization/pillar_evolver.py"):
        tree = ast.parse((destination / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                index.append(f"| `{relative}` | `{node.name}` | [L{node.lineno}]({relative}#L{node.lineno}) |")
    tutorial.write_text(body + "\n".join(index) + "\n", encoding="utf-8")
    return str(destination / "BENCHMARK_REPORT.md"), str(destination / "PAPER.md")


if __name__ == "__main__":
    print("\n".join(write_reports()))
