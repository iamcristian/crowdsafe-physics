import numpy as np
import pytest
from src.config import Room, Exit, SimulationConfig
from src.physics.routing import Router
from src.simulation import Simulation


def test_route_around_barrier_and_blocked_region():
    room = Room(interior_segments=(((4.,0.),(4.,6.)),))
    router = Router(room, .34)
    p = np.array([2.,3.])
    for _ in range(200):
        q = router.waypoint(p)
        assert q is not None
        assert router.visible(p,q)
        delta = q-p
        p += delta/max(np.linalg.norm(delta),1e-9)*min(.1, np.linalg.norm(delta))
        if p[0] > 8:
            break
    assert p[0] > 8
    closed = Router(Room(interior_segments=(((4.,0.),(4.,8.)),)), .34)
    assert closed.waypoint(np.array([2.,3.])) is None


@pytest.mark.parametrize('side,point,velocity', [('left',[0,4],[-2,0]),('right',[8,4],[2,0]),('top',[4,8],[0,2]),('bottom',[4,0],[0,-2])])
def test_exit_crossing_each_wall(side, point, velocity):
    room = Room(exits=(Exit(side,4,2),))
    engine = Simulation(SimulationConfig(n_agents=1,room=room))
    direction = np.array(velocity)/2
    engine.positions[:] = np.array(point)+direction*(engine.radii[0]-.001)
    engine.velocities[:] = velocity
    engine.step()
    assert engine.done
    assert len(engine.telemetry.exit_times) == 1


def test_exit_overlap_rejected():
    with pytest.raises(ValueError):
        Room(exits=(Exit('top',4,2),Exit('top',4.5,2)))


def test_physical_agent_traverses_barrier_route():
    from src.simulation import simulate
    room=Room(interior_segments=(((4.,0.),(4.,6.)),),spawn=(1.,2.,1.5,1.5))
    result=simulate(SimulationConfig(n_agents=1,room=room,desired_speed=1.3,dt=.003,duration=20))
    assert result.metrics['evacuated']==1
    assert result.metrics['velocity_clamp_count']==0
