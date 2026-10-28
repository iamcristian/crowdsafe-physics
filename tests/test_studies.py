import pytest
from src.analytics.studies import statistics, run_study, calibrate
from src.visualization.web_app import configured_engine, Controls


def build(data):
    return configured_engine(Controls(**data))


def test_statistics_and_paired_identical_runs():
    assert statistics([None])['n'] == 0
    assert statistics([2])['ci95'] is None
    assert statistics([1, 2, 3])['mean'] == 2
    settings = dict(crowd=5, duration=1, dt=.003)
    result = run_study(dict(seeds=[7,11], candidates=[settings,settings]), build, lambda *a:None, lambda:False)
    assert len(result['runs']) == 4
    for metric in result['paired'][0]['delta_vs_A'].values():
        assert metric['mean'] in (None, 0)
    assert result['summaries'][0]['metrics']['t90']['n'] == 0


def test_calibration_rejects_leaking_holdout():
    with pytest.raises(ValueError, match='disjoint'):
        calibrate(dict(observations=[dict(seed=7, split='train',rmet=1),dict(seed=7,split='validation',rmet=1)]),build,lambda *a:None,lambda:False)


def test_calibration_reports_holdout_predictions():
    request = dict(controls=dict(crowd=5,duration=1,dt=.003),speeds=[1,2],
                   observations=[dict(seed=7,split='train',rmet=1),dict(seed=11,split='validation',rmet=1)])
    result = calibrate(request, build, lambda *a:None, lambda:False)
    assert len(result['history']) == 2
    assert result['validation']['predictions'][0]['seed'] == 11
    assert result['validation']['rmse'] == pytest.approx(0)


def test_incompatible_observation_horizons_are_not_ranked():
    candidates = [dict(crowd=5, duration=1, dt=.003), dict(crowd=5, duration=2, dt=.003)]
    with pytest.raises(ValueError, match='same observation horizon'):
        run_study(dict(seeds=[7], candidates=candidates), build, lambda *a: None, lambda: False)
    from fastapi.testclient import TestClient
    from src.visualization.web_app import app
    with TestClient(app) as client:
        response = client.post('/api/studies', json=dict(seeds=[7], candidates=candidates))
        assert response.status_code == 422
        assert 'same observation horizon' in response.json()['detail']
