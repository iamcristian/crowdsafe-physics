r"""Analytical force-law verification in SI units.

These tests check physical invariants independently of a crowd animation:
Newton's third law, dissipative power, exponential length scale, and exact
wall/pillar geometry. Forces are Newtons, distances meters, velocities m/s.
"""
import numpy as np
import pytest
from src.config import Physics, Room, Pillar
from src.physics.forces import pair_forces, desired_force, boundary_forces
from src.physics.geometry import segment_distances, desired_directions


@pytest.mark.parametrize("distance", [0.0, 0.4, 0.6, 1.2])
def test_pair_newton_third_law(distance):
    r"""f_ij=-f_ji, including coincident centers and frictional contacts.

    Summing the (N,N,2) tensor over both pedestrian axes must give zero
    internal resultant; this does not constrain external driving/wall forces.
    """
    positions = np.array([[0., 0.], [distance, 0.]])
    force, normal, compression, overlap = pair_forces(positions, np.array([[1., 2.], [-2., 1.]]), np.array([.3, .3]), Physics())
    np.testing.assert_allclose(force[0, 1], -force[1, 0], atol=1e-10)
    np.testing.assert_allclose(force.sum(axis=(0, 1)), 0, atol=1e-10)
    assert np.all(np.diag(normal) == 0)
    assert np.all(np.diag(compression) == 0)
    assert np.all(np.diag(overlap) == 0)


def test_contact_formula_and_friction_sign():
    r"""A 0.1 m overlap gives k*0.1 N and opposes relative sliding.

    With A=0, isolate elasticity and friction. Receiver 0 moves upward;
    its tangential force must point down, and total friction power is negative.
    """
    p = Physics(A=0)
    positions, velocities = np.array([[0., 0.], [.5, 0.]]), np.array([[0., 1.], [0., -1.]])
    force, normal, compression, overlap = pair_forces(positions, velocities, np.array([.3, .3]), p)
    assert normal[0, 1] == pytest.approx(p.k * .1)
    assert force[0, 1, 1] == pytest.approx(-p.kappa * .1 * 2)
    assert np.sum(force.sum(axis=1) * velocities) < 0


def test_no_granular_force_outside_contact():
    r"""At d>r_i+r_j, g(overlap)=0; social exponential remains positive."""
    force, normal, compression, overlap = pair_forces(np.array([[0., 0.], [1., 0.]]), np.ones((2, 2)), np.array([.3, .3]), Physics())
    assert compression.sum() == 0
    assert overlap.sum() == 0
    assert normal[0, 1] == pytest.approx(2000 * np.exp(-.4/.08))
    assert force[0, 1, 0] < 0


def test_driving_relaxation_units():
    r"""80 kg * (2-1) m/s / 0.5 s equals 160 N along the target axis."""
    value = desired_force(np.array([[1., 0.]]), np.array([[1., 0.]]), 2, Physics())
    np.testing.assert_allclose(value, [[160, 0]])


def test_exact_segment_projection_and_endpoint():
    r"""Projection clips to endpoints; infinite-line distance would be wrong."""
    distance, normal, closest = segment_distances(np.array([[1., 1.], [3., 1.]]), np.array([[[0., 0.], [2., 0.]]]))
    np.testing.assert_allclose(distance[:, 0], [1, np.sqrt(2)])
    np.testing.assert_allclose(closest[:, 0], [[1, 0], [2, 0]])
    np.testing.assert_allclose(np.linalg.norm(normal, axis=2), 1)


def test_wall_repulsion_and_dissipation():
    r"""A disk overlapping the left wall feels rightward load and drag downward."""
    force, loads = boundary_forces(np.array([[.2, 4.]]), np.array([[0., 1.]]), np.array([.3]), Room(), Physics())
    assert force[0, 0] > 10000
    assert force[0, 1] < -20000
    assert loads.shape == (1, 5)


def test_pillar_surface_distance_and_repulsion():
    r"""At center distance 0.7 m, R=0.5 and r=0.3 imply 0.1 m contact."""
    p = Physics(A=0)
    force, loads = boundary_forces(np.array([[4.7, 4.]]), np.zeros((1, 2)), np.array([.3]), Room(pillars=(Pillar(4, 4, .5),)), p)
    np.testing.assert_allclose(force, [[p.k*.1, 0]], atol=1e-8)
    assert loads[0, -1] == pytest.approx(p.k*.1)


def test_exit_is_an_aperture_and_heading_is_normalized():
    r"""No wall spans a wide opening; local steering still returns unit vectors."""
    force, _ = boundary_forces(np.array([[8., 4.]]), np.zeros((1, 2)), np.array([.3]), Room(exit_width=2), Physics())
    assert np.linalg.norm(force) < 1
    directions = desired_directions(np.array([[2., 3.], [5., 4.5]]), np.array([.3, .3]), Room(pillars=(Pillar(6, 4.4, .4),)))
    np.testing.assert_allclose(np.linalg.norm(directions, axis=1), 1)
    assert np.all(directions[:, 0] > 0)
