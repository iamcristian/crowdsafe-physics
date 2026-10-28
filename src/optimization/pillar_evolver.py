r"""Differential evolution of a single asymmetric circular obstacle.

The design vector z=(x,y,R) is in meters. Candidate fitness is the training-seed
mean of 0.50*peak/peak_base + 0.25*mean/mean_base + 0.25*RMET/RMET_base,
plus a penalty for unevacuated agents. In LaTeX:
$J(z)=\langle .5 P_{max}(z)/P_{max}(0)+.25\bar P(z)/\bar P(0)
+.25\mathrm{RMET}(z)/\mathrm{RMET}(0)+2(1-N_{exit}/N)\rangle$.
RMET is restricted mean evacuation time and remains defined for censored runs.
All baseline and candidate runs use identical initial conditions per seed.
"""
from dataclasses import replace
import numpy as np
from scipy.optimize import differential_evolution
from src.config import Pillar
from src.simulation import simulate


def fitness(metrics, baseline):
    r"""Compute a dimensionless, explicitly weighted safety/efficiency loss.

    Ratios compare one candidate with the same-seed baseline; epsilon protects
    division in tiny empty-contact test cases. A missing completion event is
    never replaced by a fabricated evacuation time.
    """
    score = (0.50 * metrics["peak_pressure"] / max(baseline["peak_pressure"], 1e-9)
             + 0.25 * metrics["mean_pressure"] / max(baseline["mean_pressure"], 1e-9)
             + 0.25 * metrics["restricted_mean_evacuation_time"] /
             max(baseline["restricted_mean_evacuation_time"], 1e-9))
    return float(score + 2.0 * (1.0 - metrics["evacuated"] / metrics["n_agents"]))


def feasible_pillar(values, config):
    r"""Check asymmetry, room containment and common initial-state clearance.

    Circle-to-jamb clearance exceeds R+r_max+0.05 m; this is a geometric
    search constraint, not a code-compliance criterion. The upstream face
    stays downstream of the common spawning envelope for paired experiments.
    """
    x, y, radius = map(float, values)
    room, p = config.room, config.physics
    maximum = p.radius + p.radius_spread
    if not (radius < x < room.width - radius and radius < y < room.height - radius):
        return False
    if abs(y - room.height / 2) < 0.12 or x - radius < room.width - 3.1 + maximum + 0.05:
        return False
    low, high = room.exit_limits
    distances = [np.hypot(x-room.width, y-jamb) for jamb in (low, high)]
    return min(distances) > radius + maximum + 0.05


def optimize_pillar(config, seeds=(7, 11), maxiter=3, popsize=5, search_seed=2026):
    r"""Run reproducible SciPy differential evolution and return its full audit.

    Mutation mixes population differences; selection retains lower J. Bounds
    are in meters and do not encode a desired improvement. SciPy's deterministic
    single-worker search avoids hidden worker-dependent update ordering.
    Training and independent test metrics must be reported separately.
    """
    if maxiter < 0 or popsize < 2 or not seeds:
        raise ValueError("Search needs nonnegative iterations, population multiplier >=2 and seeds.")
    if config.room.pillars:
        raise ValueError("Start optimization from a baseline room without pillars.")
    baseline = {seed: simulate(replace(config, seed=seed), record=False).metrics for seed in seeds}
    history, cache = [], {}

    def objective(values):
        r"""Evaluate one (3,) design with paired simulations or a constraint penalty.

        Cache exact float tuples to avoid repeating identical costly trajectories.
        Feasible history entries preserve each seed's complete measured metrics.
        """
        key = tuple(float(value) for value in values)
        if key in cache:
            return cache[key]
        if not feasible_pillar(values, config):
            history.append(dict(design=list(key), feasible=False, score=1000.0, metrics=[]))
            cache[key] = 1000.0
            return 1000.0
        candidate_room = replace(config.room, pillars=(Pillar(*key),))
        metrics = [simulate(replace(config, room=candidate_room, seed=seed), record=False).metrics
                   for seed in seeds]
        score = float(np.mean([fitness(item, baseline[seed]) for item, seed in zip(metrics, seeds)]))
        history.append(dict(design=list(key), feasible=True, score=score, metrics=metrics))
        cache[key] = score
        return score

    room = config.room
    bounds = [(room.width - 2.7, room.width - 0.8),
              (room.height / 2 - 1.1, room.height / 2 + 1.1), (0.18, 0.65)]
    result = differential_evolution(objective, bounds, seed=search_seed, maxiter=maxiter,
                                    popsize=popsize, polish=False, tol=0.0, atol=0.0,
                                    updating="immediate", workers=1)
    feasible = [item for item in history if item["feasible"]]
    if not feasible:
        raise RuntimeError("No feasible design was sampled; increase the search budget.")
    best = min(feasible, key=lambda item: item["score"])
    initial_best = min((item["score"] for item in history[:3*popsize] if item["feasible"]), default=1000.0)
    return dict(config=config.to_dict(), pillar=dict(zip(("x", "y", "radius"), best["design"])),
                score=best["score"], initial_population_best=initial_best,
                baseline_score=float(np.mean([fitness(item, item) for item in baseline.values()])),
                training_seeds=list(seeds), search_seed=search_seed, maxiter=maxiter,
                popsize=popsize, evaluations=len(history), scipy_message=str(result.message),
                baseline_metrics={str(key): value for key, value in baseline.items()}, history=history)
