import numpy as np
import pytest
from dataclasses import replace
from src.analytics.research import sobol_indices
from src.building import run_building
from src.config import SimulationConfig,Room,Exit
from src.simulation import Simulation
from src.empirical import observed_crossings


def test_sobol_against_additive_analytic_model():
    rng=np.random.default_rng(42);a=rng.random((100000,2));b=rng.random((100000,2))
    function=lambda x:x[:,0]+2*x[:,1]
    hybrids=[]
    for i in range(2):
        h=a.copy();h[:,i]=b[:,i];hybrids.append(function(h))
    result=sobol_indices(function(a),function(b),hybrids)
    np.testing.assert_allclose(result['first_order'],[.2,.8],atol=.025)
    np.testing.assert_allclose(result['total_order'],[.2,.8],atol=.025)


def network(**kwargs):
    data=dict(nodes=[dict(id='room',kind='room',floor=1),dict(id='safe',kind='safe',floor=0)],
        links=[dict(**{'from':'room','to':'safe'},length=1,capacity=1,kind='corridor')],
        populations=[dict(node='room',count=1)],dt=.1,duration=20,speed=1,seed=7)
    return dict(data,**kwargs)


def test_network_travel_capacity_and_conservation():
    result=run_building(network())
    assert result['evacuated']==1
    assert result['completion_time']==pytest.approx(2,abs=.11)
    assert result['link_departures']==[1]
    assert all(r['evacuated']+r['remaining']==1 for r in result['telemetry'])


def test_network_always_records_completion_between_sample_times():
    data = network()
    data['links'][0].update(length=.2, capacity=10)
    result = run_building(data)
    assert result['completion_time'] < 1
    final = result['telemetry'][-1]
    assert final['time'] == result['time']
    assert final['evacuated'] == result['evacuated'] == 1
    assert final['remaining'] == 0
    assert sum(final['occupants'].values()) == 0


def test_stair_factor_and_visibility_closure():
    data=network()
    data['links'][0]['kind']='stair'
    slower=run_building(dict(data,stair_factor=.5))
    assert slower['completion_time']>2.5
    closed=run_building(network(visibility=[dict(node='room',time=.5,meters=0)]))
    assert closed['censored'] and closed['evacuated']==0


def test_high_capacity_is_not_limited_to_one_per_step():
    data=network(populations=[dict(node='room',count=20)])
    data['links'][0]['capacity']=100
    result=run_building(data)
    assert result['evacuated']==20
    assert result['completion_time']<1.5


def test_empirical_crossing_interpolation_and_gap_rejection():
    rows=np.array([[1,0,0,1,0],[1,1,0,-1,0],[2,0,0,1,0],[2,2,0,-1,0]],dtype=float)
    assert observed_crossings(rows,fps=1)==[.5]


def test_social_only_removes_elastic_contact():
    engine=Simulation(SimulationConfig(n_agents=2,movement_model='social'))
    engine.positions[:]=[[3.,3.],[3.4,3.]]
    assert engine.forces(engine.positions,engine.velocities).compression.sum()==0
    engine.config=replace(engine.config,movement_model='hfv')
    assert engine.forces(engine.positions,engine.velocities).compression.sum()>0


def test_cohesion_and_queue_routing_are_finite():
    room=Room(exits=(Exit('left',4,2),Exit('right',4,2)))
    engine=Simulation(SimulationConfig(n_agents=5,room=room,group_size=2,cohesion=30,congestion_weight=1))
    engine.step()
    assert np.isfinite(engine.positions).all()
    assert np.linalg.norm(engine.group_force,axis=1).max()<=160


def test_small_automatic_search_has_disjoint_evaluation():
    from src.analytics.research import design_search
    from src.visualization.web_app import Controls,configured_engine
    result=design_search(dict(controls=dict(crowd=5,duration=1,dt=.003),seeds=[7],validation_seeds=[11],budget=2),
        lambda c:configured_engine(Controls(**c)),lambda *args:None,lambda:False)
    assert len(result['candidates'])==2
    assert all(row['seed']==11 for row in result['validation']['runs'])
    assert all(row['seed']==7 for row in result['training']['runs'])


def test_sensitivity_job_completes_with_expected_points():
    from src.analytics.research import sensitivity
    from src.visualization.web_app import Controls,configured_engine
    result=sensitivity(dict(controls=dict(crowd=5,duration=1,dt=.003),bounds=dict(speed=[1,2]),seeds=[7],samples=4),
        lambda c:configured_engine(Controls(**c)),lambda *args:None,lambda:False)
    assert len(result['runs'])==12
    assert result['indices']['restricted_mean_evacuation_time']['total_order'] is None


def test_monte_carlo_does_not_stop_on_censored_precision():
    from src.analytics.research import monte_carlo
    from src.visualization.web_app import Controls,configured_engine
    result=monte_carlo(dict(controls=dict(crowd=5,duration=1,dt=.003),seeds=[7,11,19,23,31],minimum=4,half_width=1),
        lambda c:configured_engine(Controls(**c)),lambda *args:None,lambda:False)
    assert len(result['runs'])==5
    assert not result['precision_reached']


def test_research_http_validation_and_persistence(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from src.visualization.web_app import app
    import time
    monkeypatch.chdir(tmp_path)
    with TestClient(app) as client:
        response=client.post('/api/studies',json=dict(mode='geometry_search',controls={},seeds=[7],validation_seeds=[7],budget=2))
        assert response.status_code==422
        response=client.post('/api/studies',json=dict(mode='monte_carlo',controls=dict(crowd=5,duration=1,dt=.003),seeds=[7,11,19,23],minimum=4,half_width=.5))
        assert response.status_code==200
        identity=response.json()['id'];deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            state=client.get('/api/studies/'+identity).json()
            if state['status']!='running':break
            time.sleep(.02)
        assert state['status']=='complete'
        assert (tmp_path/'outputs'/'studies'/(identity+'.json')).is_file()
