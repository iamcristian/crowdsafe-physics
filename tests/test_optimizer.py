r"""Evolutionary selection, geometric feasibility and measured-objective tests.

A small real-physics search verifies retained improvement without asserting
that every geometry or held-out seed must benefit from obstacle insertion.
Search quality and scientific generalization are deliberately distinct tests.
"""
import numpy as np
import pytest
from src.config import SimulationConfig
from src.optimization.pillar_evolver import fitness, feasible_pillar, optimize_pillar


def test_fitness_ratios_and_censoring_penalty():
    r"""Identical complete runs score 1; a 50% pressure reduction scores 0.625."""
    baseline = dict(peak_pressure=100, mean_pressure=50, restricted_mean_evacuation_time=10, evacuated=10, n_agents=10)
    assert fitness(baseline, baseline) == 1
    candidate = dict(baseline, peak_pressure=50, mean_pressure=25)
    assert fitness(candidate, baseline) == pytest.approx(.625)
    assert fitness(dict(candidate, evacuated=5), baseline) == pytest.approx(1.625)


def test_geometry_constraints_exclude_blocked_or_symmetric_designs():
    r"""Search constraints preserve upstream clearance and require asymmetry."""
    config = SimulationConfig()
    assert feasible_pillar([6.1, 4.5, .4], config)
    assert not feasible_pillar([6.1, 4., .4], config)
    assert not feasible_pillar([7.8, 4.4, .5], config)
    assert not feasible_pillar([5.2, 4.4, .5], config)


def test_real_evolution_retains_best_and_improves_measured_load():
    r"""A seeded physical search reduces its measured objective and normal load.

    Each candidate is a complete simulation, not an artificial objective.
    Elitism guarantees nonincreasing best loss across generations; the recorded
    baseline provides an independent denominator for pressure improvement.
    """
    config = SimulationConfig(n_agents=16, duration=45, dt=.003)
    result = optimize_pillar(config, seeds=(7,), maxiter=1, popsize=3, search_seed=2026)
    feasible = [item for item in result["history"] if item["feasible"]]
    assert result["score"] <= result["initial_population_best"]
    assert result["score"] == min(item["score"] for item in feasible)
    best = min(feasible, key=lambda item: item["score"])
    assert result["score"] < result["baseline_score"]
    assert best["metrics"][0]["peak_pressure"] < result["baseline_metrics"]["7"]["peak_pressure"]
    assert feasible_pillar(list(result["pillar"].values()), config)
    assert np.isfinite(result["score"])
