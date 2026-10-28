"""Scientific workspace configuration and transactional rejection tests."""
from fastapi.testclient import TestClient
from src.visualization.web_app import app


def test_custom_geometry_and_reproducible_settings():
    with TestClient(app) as client, client.websocket_connect('/ws') as ws:
        ws.receive_json()
        ws.send_json({'action': 'reset', 'controls': {'crowd': 5, 'seed': 23,
                     'method': 'verlet', 'dt': .002, 'duration': 1,
                     'room': {'width': 10, 'height': 8, 'exit_width': 2,
                              'pillars': [{'x': 8, 'y': 5, 'radius': .4}]}}})
        state = ws.receive_json()
        assert state['config']['seed'] == 23
        assert state['config']['method'] == 'verlet'
        assert state['room']['width'] == 10
        assert len(state['room']['pillars']) == 1
        ws.send_json({'action': 'step'})
        state = ws.receive_json()
        assert abs(state['time'] - .04) < 1e-9
        assert state['metrics']['velocity_clamp_count'] == 0
        ws.send_json({'action': 'reset', 'controls': {'room': {'width': 2}}})
        assert 'error' in ws.receive_json()
        ws.send_json({'action': 'step'})
        preserved = ws.receive_json()
        assert preserved['config']['seed'] == 23
        assert preserved['time'] > state['time']
