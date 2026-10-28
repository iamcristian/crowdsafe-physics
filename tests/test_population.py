import numpy as np
import pytest
from src.config import SimulationConfig, Physics, room_from_dict
from src.simulation import Simulation
from src.analytics.studies import pareto_front


def test_population_is_seeded_and_waiting_is_not_a_fixed_body():
    config = SimulationConfig(n_agents=5,speed_spread=.3,pre_movement_max=10)
    a, b = Simulation(config), Simulation(config)
    np.testing.assert_array_equal(a.speed_factors,b.speed_factors)
    np.testing.assert_array_equal(a.start_times,b.start_times)
    assert np.all((a.speed_factors>=.7)&(a.speed_factors<=1.3))
    a.start_times[:] = 10
    # Suppress repulsion: a waiting body with no initial velocity stays still.
    from dataclasses import replace
    a.config=replace(config,physics=Physics(A=0,k=0,kappa=0))
    before=a.positions.copy()
    a.step()
    np.testing.assert_array_equal(before,a.positions)
    a.time=10
    a.step()
    assert np.linalg.norm(a.velocities)>0


def test_pareto_front_keeps_tradeoffs_and_removes_dominated():
    keys=('restricted_mean_evacuation_time','peak_pressure','exposure_agent_seconds')
    summaries=[dict(metrics={k:dict(mean=v) for k,v in zip(keys,p)}) for p in [(1,5,2),(2,3,1),(3,6,3)]]
    assert pareto_front(summaries)==[0,1]


@pytest.mark.parametrize('data',[{'exits':[{}]},{'pillars':None},{'interior_segments':[[[1,2]]]},{'unsupported':1}])
def test_malformed_room_rejected(data):
    with pytest.raises(ValueError):
        room_from_dict(data)


def test_socket_rejects_malformed_geometry_and_preserves_population():
    from fastapi.testclient import TestClient
    from src.visualization.web_app import app
    with TestClient(app) as client, client.websocket_connect('/ws') as socket:
        initial=socket.receive_json()
        assert initial['controls']['speed_spread']==0
        socket.send_json({'action':'reset','controls':{'speed_spread':.2,'pre_movement_max':3}})
        configured=socket.receive_json()
        assert configured['config']['speed_spread']==.2
        assert configured['run_id']!=initial['run_id']
        socket.send_json({'action':'reset','controls':{'room':{'exits':[{}]}}})
        assert 'error' in socket.receive_json()
        socket.send_json({'action':'step'})
        state=socket.receive_json()
        assert state['run_id']==configured['run_id']
        assert len(state['desired_speeds'])==40


def test_archive_retrieval_and_invalid_id(tmp_path,monkeypatch):
    import json
    from fastapi.testclient import TestClient
    from src.visualization.web_app import app
    monkeypatch.chdir(tmp_path)
    directory=tmp_path/'outputs'/'studies'
    directory.mkdir(parents=True)
    identity='a'*32
    (directory/(identity+'.json')).write_text(json.dumps({'summaries':[]}),encoding='utf-8')
    with TestClient(app) as client:
        assert client.get('/api/study-archive').json()[0]['id']==identity
        assert client.get('/api/studies/'+identity).json()['status']=='archived'
        assert client.get('/api/studies/not-a-valid-id').status_code==404
