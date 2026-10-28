r"""Validate load aggregation, exit counts, censoring and graph-based arches.

Opposed forces must add in pressure although their resultant is zero. Synthetic
contact networks isolate connectivity and low-speed criteria from simulation.
"""
import numpy as np
import pytest
from src.config import Room, SimulationConfig
from src.analytics.telemetry import radial_pressure, rolling_flow, Telemetry
from src.analytics.arch_detector import detect_arch, ArchTracker
from src.simulation import Simulation, simulate


def test_radial_pressure_adds_opposing_loads():
    r"""Two 100 N neighbors on r=0.5 m give 200/pi N/m, not zero."""
    normal = np.array([[0., 100., 100.], [100., 0., 0.], [100., 0., 0.]])
    pressure = radial_pressure(normal, np.array([.5, .5, .5]))
    assert pressure[0] == pytest.approx(200/np.pi)
    inclusive = radial_pressure(normal, np.array([.5, .5, .5]), np.ones((3, 2))*50)
    assert inclusive[0] == pytest.approx(300/np.pi)


def test_event_rate_window_and_censoring():
    r"""Only events in the observed window contribute to Q=delta_N/delta_t."""
    assert rolling_flow([.5, 1, 2, 4], 2, 1) == 1
    assert rolling_flow([.5], .5) == 2
    assert rolling_flow([], 0) == 0
    telemetry = Telemetry(10)
    telemetry.exit_times = list(range(1, 10))
    summary = telemetry.summary(12)
    assert summary["t90"] == 9
    assert summary["total_evacuation_time"] is None
    assert summary["restricted_mean_evacuation_time"] == 5.7
    assert summary["censored"]


def test_agent_time_mean_and_threshold_exposure():
    r"""A 2 s exposure of [1000,2000] N/m has mean 1500 and 2 agent-s above threshold."""
    telemetry = Telemetry(2)
    telemetry.observe(np.array([1000., 2000.]), np.array([1200., 2200.]), np.zeros((2, 2)), 2, 0)
    summary = telemetry.summary(2)
    assert summary["mean_pressure"] == 1500
    assert summary["exposure_agent_seconds"] == 2
    assert summary["peak_boundary_inclusive_pressure"] == 2200


def arch_fixture():
    r"""Build a three-disk chain touching both jambs of a 1 m opening."""
    positions = np.array([[7.9, 3.6], [7.9, 4.0], [7.9, 4.4]])
    compression = np.array([[0., 1000., 0.], [1000., 0., 1000.], [0., 1000., 0.]])
    return positions, np.zeros((3, 2)), np.full(3, .25), compression, Room(exit_width=1)


def test_arch_requires_connectivity_both_jambs_and_slow_motion():
    r"""Breaking an edge or imposing rapid motion must remove the arch candidate."""
    args = list(arch_fixture())
    active, members, edges = detect_arch(*args)
    assert active and len(members) == 3 and len(edges) == 2
    args[1] = np.ones((3, 2))
    assert not detect_arch(*args)[0]
    args = list(arch_fixture())
    args[3][1, 2] = args[3][2, 1] = 0
    assert not detect_arch(*args)[0]


def test_arch_duration_left_interval_accounting():
    r"""Two sampled episodes last 0.5 and 0.2 seconds, totaling 0.7 seconds."""
    tracker = ArchTracker()
    for time, active in [(0, True), (.2, True), (.5, False), (.8, True), (1., False)]:
        tracker.update(time, active)
    assert tracker.duration == pytest.approx(.7)
    assert tracker.longest == pytest.approx(.5)
    assert tracker.episodes == 2


def test_crossing_interpolation_counts_full_body_once():
    r"""A body near x=W+r exits during a step and is removed exactly once."""
    engine = Simulation(SimulationConfig(n_agents=1, duration=.1, desired_speed=2))
    engine.positions[:] = [engine.config.room.width + engine.radii[0] - .001, 4]
    engine.velocities[:] = [2, 0]
    engine.step()
    assert engine.done
    assert len(engine.telemetry.exit_times) == 1
    assert 0 < engine.telemetry.exit_times[0] < engine.config.dt
    engine.step()
    assert len(engine.telemetry.exit_times) == 1


def test_artifacts_round_trip(tmp_path):
    r"""Strict JSON retains real metrics and CSV includes telemetry columns."""
    import json
    run = simulate(SimulationConfig(n_agents=5, duration=.02))
    run.save(tmp_path, "run")
    payload = json.loads((tmp_path / "run.json").read_text())
    assert payload["metrics"] == run.metrics
    assert "flow_rate" in (tmp_path / "run.csv").read_text().splitlines()[0]
