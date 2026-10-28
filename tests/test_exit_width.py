"""Regression tests for aperture-aware steering and fully open walls."""
import numpy as np
from src.config import Room, Exit
import pytest
from src.physics.geometry import desired_directions, wall_segments
from src.physics.forces import boundary_forces
from src.config import Physics


def test_full_width_exit_preserves_lanes():
    room = Room(exit_width=8)
    positions = np.array([[2., 1.], [2., 4.], [2., 7.]])
    directions = desired_directions(positions, np.full(3, .3), room)
    np.testing.assert_allclose(directions, [[1, 0]] * 3)
    assert len(wall_segments(room)) == 3
    force, _ = boundary_forces(positions, np.zeros((3, 2)), np.full(3, .3), room, Physics())
    assert np.isfinite(force).all()


def test_narrow_exit_targets_cleared_aperture():
    room = Room(exit_width=1)
    positions = np.array([[2., 1.], [2., 7.]])
    directions = desired_directions(positions, np.full(2, .3), room)
    crossing_y = positions[:, 1] + (8 - positions[:, 0]) * directions[:, 1] / directions[:, 0]
    np.testing.assert_allclose(crossing_y, [3.85, 4.15])


@pytest.mark.parametrize('side',['left','right','top','bottom'])
def test_three_meter_exit_fits_eight_meter_wall(side):
    room=Room(exits=(Exit(side,4,3),))
    assert room.openings[0].width==3


def test_exit_validation_reports_bounds_and_overlap_separately():
    with pytest.raises(ValueError,match='spans 5.50–8.50 m'):
        Room(exits=(Exit('right',7,3),))
    with pytest.raises(ValueError,match='overlaps exit'):
        Room(exits=(Exit('right',4,1.2),Exit('right',4,3)))


def test_all_boundaries_open_have_zero_boundary_force_and_can_simulate():
    from src.config import SimulationConfig
    from src.simulation import Simulation
    room = Room(exits=tuple(Exit(side, 4, 8) for side in ('left', 'right', 'top', 'bottom')))
    assert wall_segments(room).shape == (0, 2, 2)
    positions = np.array([[2., 4.]])
    force, load = boundary_forces(positions, np.zeros((1, 2)), np.array([.3]), room, Physics())
    np.testing.assert_array_equal(force, [[0., 0.]])
    assert load.shape == (1, 0)
    engine = Simulation(SimulationConfig(n_agents=1, room=room, duration=.006))
    while not engine.done:
        engine.step()
    assert np.isfinite(engine.positions).all()
