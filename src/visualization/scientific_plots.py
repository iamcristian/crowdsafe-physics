r"""Generate four reproducible, high-resolution Matplotlib research figures.

Pressure heatmaps average sampled agent observations in spatial bins; empty
bins are masked, never interpreted as zero load. Force-chain widths encode
elastic contact Newtons. Error bars show replicate sample SD, not confidence
intervals. All axes explicitly name physical units.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle
import numpy as np
from src.config import room_from_dict
from src.physics.geometry import wall_segments


plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 300, "figure.constrained_layout.use": True})


def draw_room(ax, config):
    r"""Draw exact segments and circle boundaries in meters at equal aspect.

    Segment arrays have shape (W,2,2); a LineCollection draws all walls without
    adding a false line across the aperture. Pillars retain their true radius.
    """
    room = room_from_dict(config["room"])
    ax.add_collection(LineCollection(wall_segments(room), colors="#343e50", linewidths=2))
    for pillar in room.pillars:
        ax.add_patch(Circle((pillar.x, pillar.y), pillar.radius, facecolor="#97a6b7", edgecolor="#24344a", zorder=5))
    ax.set(xlim=(-0.2, room.width + 0.65), ylim=(-0.2, room.height + 0.2), xlabel="x (m)", ylabel="y (m)")
    ax.set_aspect("equal")


def pressure_grid(run, bins=40):
    r"""Return mean sampled pressure (N/m) in each two-dimensional spatial bin.

    histogram2d with weights P gives sum(P); a second histogram gives count.
    Their ratio is a conditional observation mean, not a continuum stress.
    Sample spacing is approximately constant; this is not the every-step mean.
    """
    frames = [frame for frame in run["frames"] if frame["positions"]]
    positions = np.concatenate([np.asarray(frame["positions"]) for frame in frames])
    pressure = np.concatenate([np.asarray(frame["pressure"]) for frame in frames])
    room = run["config"]["room"]
    extent = [[0, room["width"]], [0, room["height"]]]
    total, x, y = np.histogram2d(*positions.T, bins=bins, range=extent, weights=pressure)
    count, _, _ = np.histogram2d(*positions.T, bins=bins, range=extent)
    mean = np.divide(total, count, out=np.zeros_like(total), where=count > 0)
    return np.ma.masked_where(count == 0, mean).T, x, y


def generate_plots(output="outputs"):
    r"""Read benchmark artifacts and save all four requested 300-DPI figures.

    T90 points without enough exits are shown as missing rather than assigned
    horizon values. Survival curves average the independent seed ensemble with min/max bands.
    Spatial and contact snapshots use the first independent seed.
    """
    root = Path(output)
    data, figures = root / "data", root / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    summary = json.loads((data / "benchmark_summary.json").read_text())
    baseline = json.loads((data / "baseline.json").read_text())
    optimized = json.loads((data / "optimized.json").read_text())
    speeds = np.array([float(key) for key in summary["speed_experiment"]])
    stats = list(summary["speed_experiment"].values())
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, key, label, color in ((axes[0], "t90", "Time to 90% evacuation (s)", "#2369a4"),
                                 (axes[1], "peak_pressure", "Peak radial pressure (N/m)", "#c4423e")):
        values = [item[key]["mean"] if item[key]["mean"] is not None else np.nan for item in stats]
        ax.errorbar(speeds, values, yerr=[item[key]["sd"] for item in stats], marker="o", capsize=4, color=color)
        ax.set(xlabel="Desired speed (m/s)", ylabel=label)
        ax.grid(alpha=0.2)
    fig.suptitle("Desired speed experiment · mean ± replicate SD")
    fig.savefig(figures / "faster_is_slower_curve.png")
    plt.close(fig)

    grids = [pressure_grid(run) for run in (baseline, optimized)]
    vmax = max(float(grid[0].max()) for grid in grids)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8))
    for ax, run, title, (grid, x, y) in zip(axes, (baseline, optimized), ("Baseline", "Optimized pillar"), grids):
        mesh = ax.pcolormesh(x, y, grid, cmap="inferno", vmin=0, vmax=vmax, shading="flat", rasterized=True)
        draw_room(ax, run["config"])
        ax.set_title(title)
    fig.colorbar(mesh, ax=axes, label="Mean sampled radial pressure (N/m)", shrink=0.8)
    fig.suptitle(f"Spatial exposure · independent seed {baseline['config']['seed']}")
    fig.savefig(figures / "spatial_pressure_heatmap.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    groups = []
    for prefix, label, color in (("speed_5", "Baseline", "#c4423e"),
                                  ("optimized", "Optimized pillar", "#2369a4")):
        runs = [json.loads((data / f"{prefix}_seed_{seed}.json").read_text())
                for seed in summary["evaluation_seeds"]]
        groups.append((runs, label, color))
    all_runs = [run for runs, _, _ in groups for run in runs]
    censored_limits = [run["metrics"]["observed_time"] for run in all_runs if run["metrics"]["censored"]]
    limit = min(censored_limits) if censored_limits else max(run["metrics"]["observed_time"] for run in all_runs)
    # Exact event times form the plotting grid. Completed runs stay at zero;
    # censored runs are never extrapolated past their observed follow-up.
    grid = np.unique(np.r_[0, limit, *[run["exit_times"] for run in all_runs]])
    grid = grid[grid <= limit]
    for runs, label, color in groups:
        survival = np.asarray([1-np.searchsorted(run["exit_times"], grid, side="right") / run["config"]["n_agents"]
                               for run in runs])
        ax.fill_between(grid, survival.min(axis=0), survival.max(axis=0), step="post", color=color, alpha=.13)
        ax.step(grid, survival.mean(axis=0), where="post", label=label, color=color, linewidth=2)
    ax.axhline(0.1, color="gray", linestyle=":", label="10% remaining")
    ax.set(xlabel="Time (s)", ylabel="Mean fraction remaining", ylim=(-0.02, 1.02),
           title="Evacuation survival · ensemble mean and replicate range")
    ax.grid(alpha=0.2)
    ax.legend()
    fig.savefig(figures / "evacuation_survival_curves.png")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8))
    for ax, run, title in zip(axes, (baseline, optimized), ("Baseline", "Optimized pillar")):
        snapshot = run["snapshot"]
        positions = np.asarray(snapshot["positions"])
        pressure = np.asarray(snapshot["pressure"])
        for position, radius, value in zip(positions, snapshot["radii"], pressure):
            ax.add_patch(Circle(position, radius, color=plt.cm.inferno(min(value / max(1, pressure.max()), 1)), alpha=0.8))
        edges = np.asarray(snapshot["edges"], dtype=int)
        if len(edges):
            loads = np.asarray(snapshot["edge_loads"])
            ax.add_collection(LineCollection(positions[edges], colors="#00b9d8", linewidths=0.4 + 3*loads/max(1, loads.max())))
        draw_room(ax, run["config"])
        ax.set_title(f"{title} · t={snapshot['time']:.2f} s")
    fig.suptitle("Peak-pressure snapshots · cyan widths ∝ elastic contact load")
    fig.savefig(figures / "force_chains_snapshot.png")
    plt.close(fig)
    return [str(figures / name) for name in ("faster_is_slower_curve.png", "spatial_pressure_heatmap.png",
                                             "evacuation_survival_curves.png", "force_chains_snapshot.png")]
