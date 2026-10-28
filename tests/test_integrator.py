r"""Analytic integration and numerical stability regression tests.

A constant-acceleration solution is exact for Verlet; a damped isolated body
converges to its target speed. Timestep refinement is checked against analytic
motion, avoiding fragile exact trajectories for chaotic contacting crowds.
"""
from dataclasses import replace
import numpy as np
import pytest
from src.config import Physics, SimulationConfig, Room
from src.physics.integrator import semi_implicit_euler, velocity_verlet, clamp_velocity
from src.simulation import simulate, initial_state


def test_velocity_verlet_constant_acceleration():
    r"""x=x0+v0*t+a*t²/2 and v=v0+a*t provide an independent exact oracle."""
    position, velocity, count = velocity_verlet(np.zeros((1, 2)), np.array([[1., 0.]]),
                                              lambda x, v: np.array([[160., 0.]]), 80, .1, 12)
    np.testing.assert_allclose(position, [[.11, 0]])
    np.testing.assert_allclose(velocity, [[1.2, 0]])
    assert count == 0


def test_clamp_preserves_direction_and_zero_velocity():
    r"""A 3-4-5 velocity capped at 2 m/s scales both components by 2/5."""
    velocity, count = clamp_velocity(np.array([[3., 4.], [0., 0.]]), 2)
    np.testing.assert_allclose(velocity, [[1.2, 1.6], [0, 0]])
    assert count == 1


def relaxation_error(dt, method):
    r"""Integrate dv/dt=(v0-v)/tau and compare with v0*(1-exp(-t/tau)).

    An isolated body has a closed solution in m/s. Halving dt should decrease
    error without needing crowd-contact trajectories to remain phase aligned.
    """
    positions, velocities = np.zeros((1, 2)), np.zeros((1, 2))
    for _ in range(round(1/dt)):
        if method == "euler":
            positions, velocities, _ = semi_implicit_euler(positions, velocities, 80*(2-velocities)/.5, 80, dt, 12)
        else:
            positions, velocities, _ = velocity_verlet(positions, velocities, lambda x, v: 80*(2-v)/.5, 80, dt, 12)
    return float(np.max(np.abs(velocities - 2*(1-np.exp(-2)))))


@pytest.mark.parametrize("method", ["euler", "verlet"])
def test_analytic_relaxation_converges(method):
    r"""Smaller timesteps reduce analytic velocity error for both schemes."""
    assert relaxation_error(.01, method) < relaxation_error(.02, method) * .6


def test_configuration_rejects_unstable_and_nonfinite_steps():
    r"""Elastic stability check and finite domains reject invalid input early."""
    for dt in (.1, -1, float("nan")):
        with pytest.raises(ValueError):
            SimulationConfig(dt=dt)
    with pytest.raises(ValueError):
        Physics(B=0)
    with pytest.raises(ValueError):
        Room(exit_width=9)


def test_seeded_initial_conditions_are_nonoverlapping():
    r"""Common random numbers reproduce (N,2) positions without body contact."""
    config = SimulationConfig(n_agents=40)
    positions, velocities, radii = initial_state(config)
    other = initial_state(config)[0]
    np.testing.assert_array_equal(positions, other)
    distance = np.linalg.norm(positions[:, None] - positions[None, :], axis=2)
    np.fill_diagonal(distance, np.inf)
    assert np.all(distance >= radii[:, None] + radii[None, :])
    assert not velocities.any()


@pytest.mark.parametrize("method", ["euler", "verlet"])
def test_short_crowd_run_is_finite_and_reproducible(method):
    r"""Finite histories, stable identities and bounded trajectories survive integration."""
    config = SimulationConfig(n_agents=10, duration=.12, method=method)
    run = simulate(config)
    repeated = simulate(config)
    assert run.metrics == repeated.metrics
    assert run.metrics["velocity_clamp_count"] == 0
    assert run.metrics["censored"]
    assert run.metrics["total_evacuation_time"] is None
    assert np.isfinite(np.asarray(run.frames[-1]["positions"])).all()
