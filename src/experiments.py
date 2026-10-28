r"""Auditable experiments, paired validation and timestep sensitivity.

The benchmark separates training seeds from evaluation seeds, writes individual
runs before aggregation, and reports hypotheses as observed true/false outcomes.
Between-seed standard deviations describe variability; with few runs they are
not population uncertainty guarantees. Every printed number derives from JSON.
"""
from dataclasses import replace
import json
import platform
from pathlib import Path
import sys
import numpy as np
import scipy
from src.config import PRESET_SPEEDS, Pillar
from src.simulation import simulate
from src.optimization.pillar_evolver import optimize_pillar


def aggregate(runs):
    r"""Summarize replicate metrics with sample SD and explicit observed counts.

    For x_1..x_n, mean=sum(x)/n and SD=sqrt(sum((x-mean)^2)/(n-1)).
    Null event times are excluded only from that metric and n_observed is saved;
    evacuation counts and censored-run counts always include every replicate.
    """
    keys = ("t90", "total_evacuation_time", "peak_pressure", "mean_pressure", "mean_flow_rate",
            "restricted_mean_evacuation_time", "exposure_agent_seconds", "arch_duration",
            "velocity_clamp_count", "max_pair_overlap", "peak_boundary_inclusive_pressure")
    output = {"replicates": len(runs), "censored_runs": sum(run.metrics["censored"] for run in runs)}
    for key in keys:
        values = [run.metrics[key] for run in runs if run.metrics[key] is not None]
        output[key] = dict(mean=float(np.mean(values)) if values else None,
                           sd=float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                           n_observed=len(values))
    return output


def run_benchmark(config, output="outputs", seeds=(19, 23, 31), train_seeds=(7, 11),
                  maxiter=3, popsize=5):
    r"""Execute both experiments, independent pillar evaluation and dt/2 checks.

    Five prescribed desired speeds share evaluation seeds (paired initial
    conditions). Optimization uses only training seeds at 5 m/s. Selected
    pillar and baseline are compared on every unseen evaluation seed. A
    representative trajectory at each speed and both comparison designs is
    retained for plots; all replicates retain exact scalar/time-series data.
    """
    if not seeds or not train_seeds or len(set(seeds)) != len(seeds) or len(set(train_seeds)) != len(train_seeds):
        raise ValueError("Seed ensembles must be nonempty and contain distinct seeds.")
    if config.room.pillars:
        raise ValueError("Benchmark requires a baseline room without pillars.")
    if set(seeds) & set(train_seeds):
        raise ValueError("Training and evaluation seeds must be disjoint.")
    root = Path(output)
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    experiment, speed_runs = {}, {}
    for speed in PRESET_SPEEDS:
        runs = []
        for index, seed in enumerate(seeds):
            run = simulate(replace(config, desired_speed=speed, seed=seed), record=index == 0)
            run.save(data, f"speed_{speed:g}_seed_{seed}")
            runs.append(run)
        speed_runs[speed] = runs
        experiment[str(speed)] = aggregate(runs)
        print(f"Speed {speed:g} m/s: mean T90={experiment[str(speed)]['t90']['mean']}, "
              f"peak pressure={experiment[str(speed)]['peak_pressure']['mean']:.1f} N/m", flush=True)
    optimization_config = replace(config, desired_speed=5.0)
    print("Searching pillar designs using training seeds only...", flush=True)
    search = optimize_pillar(optimization_config, train_seeds, maxiter, popsize)
    (data / "optimization.json").write_text(json.dumps(search, indent=2, allow_nan=False) + "\n")
    selected_room = replace(config.room, pillars=(Pillar(**search["pillar"]),))
    optimized = []
    for index, seed in enumerate(seeds):
        run = simulate(replace(optimization_config, room=selected_room, seed=seed), record=index == 0)
        run.save(data, f"optimized_seed_{seed}")
        optimized.append(run)
    baseline = speed_runs[5.0]
    baseline[0].save(data, "baseline")
    optimized[0].save(data, "optimized")
    base_stats, optimized_stats = aggregate(baseline), aggregate(optimized)
    paired = []
    for seed, base, opt in zip(seeds, baseline, optimized):
        paired.append(dict(seed=seed, pressure_reduction_percent=100 * (1-opt.metrics["peak_pressure"]/base.metrics["peak_pressure"]),
                           mean_pressure_reduction_percent=100 * (1-opt.metrics["mean_pressure"]/base.metrics["mean_pressure"]),
                           flow_improvement_percent=100 * (opt.metrics["mean_flow_rate"]/base.metrics["mean_flow_rate"]-1)))
    peak_reduction = 100 * (1-optimized_stats["peak_pressure"]["mean"]/base_stats["peak_pressure"]["mean"])
    mean_reduction = 100 * (1-optimized_stats["mean_pressure"]["mean"]/base_stats["mean_pressure"]["mean"])
    flow_change = 100 * (optimized_stats["mean_flow_rate"]["mean"]/base_stats["mean_flow_rate"]["mean"]-1)
    convergence = {}
    for name, room, reference in (("baseline", config.room, baseline[0]),
                                   ("optimized", selected_room, optimized[0])):
        run = simulate(replace(optimization_config, room=room, seed=seeds[0], dt=config.dt/2), record=False)
        run.save(data, f"convergence_{name}")
        convergence[name] = {"dt": config.dt, "half_dt": config.dt/2,
                             "coarse": reference.metrics, "fine": run.metrics}
    # This is an operational finite-speed comparison, not a universal theorem.
    slow = experiment["2.0"]["t90"]["mean"]
    fast = experiment["7.0"]["t90"]["mean"]
    report = dict(schema_version=1, config=config.to_dict(), evaluation_seeds=list(seeds),
                  training_seeds=list(train_seeds), speed_experiment=experiment,
                  selected_pillar=search["pillar"], baseline=base_stats, optimized=optimized_stats,
                  paired_changes=paired, peak_pressure_reduction_percent=peak_reduction,
                  mean_pressure_reduction_percent=mean_reduction, flow_improvement_percent=flow_change,
                  hypotheses=dict(faster_is_slower_t90_7_vs_2=fast > slow if slow is not None and fast is not None else None,
                                  faster_is_slower_t90_7_vs_3_5=(fast > experiment["3.5"]["t90"]["mean"])
                                  if fast is not None and experiment["3.5"]["t90"]["mean"] is not None else None,
                                  peak_pressure_reduction_above_25_percent=peak_reduction > 25,
                                  mean_pressure_reduction_above_25_percent=mean_reduction > 25,
                                  faster_outflow=flow_change > 0),
                  convergence=convergence,
                  provenance=dict(python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
                                  platform=platform.platform()))
    (data / "benchmark_summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Independent evaluation: peak pressure reduction {peak_reduction:.2f}%; "
          f"mean pressure reduction {mean_reduction:.2f}%; flow change {flow_change:+.2f}%", flush=True)
    return report
