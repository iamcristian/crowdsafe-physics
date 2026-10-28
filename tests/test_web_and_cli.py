r"""Application integration checks for real server physics and CLI artifacts.

The WebSocket test verifies control semantics and numerical time advancement,
not merely HTTP status codes. Clients must remain isolated and reject invalid
physical parameters without crashing the simulation connection.
"""
import json
from fastapi.testclient import TestClient
from src.visualization.web_app import app
from src.cli import main


def test_dashboard_and_websocket_controls():
    r"""Load the Canvas document, advance physics, reset, and reject bad input."""
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        dashboard = client.get("/").text
        assert "<canvas" in dashboard
        assert "Evacuation laboratory" in dashboard
        assert "reconnectTimer" in dashboard
        with client.websocket_connect("/ws") as socket:
            initial = socket.receive_json()
            assert initial["time"] == 0 and len(initial["positions"]) == 40
            socket.send_json({"action": "step"})
            advanced = socket.receive_json()
            assert advanced["time"] > 0
            assert advanced["positions"] != initial["positions"]
            socket.send_json({"action": "reset", "controls": {"crowd": 10, "pillar": True}})
            reset = socket.receive_json()
            assert reset["time"] == 0 and len(reset["positions"]) == 10
            assert len(reset["room"]["pillars"]) == 1
            socket.send_json({"action": "configure", "controls": {"speed": -1}})
            assert "error" in socket.receive_json()


def test_cli_simulation_writes_real_data(tmp_path, capsys):
    r"""A short command writes strict JSON/CSV and reports censoring explicitly."""
    main(["simulate", "--agents", "5", "--duration", ".03", "--output", str(tmp_path)])
    metrics = json.loads(capsys.readouterr().out)
    assert metrics["censored"]
    assert (tmp_path / "data/simulation.csv").exists()
    assert json.loads((tmp_path / "data/simulation.json").read_text())["metrics"] == metrics


def test_invalid_json_does_not_disconnect_or_reset_the_engine():
    with TestClient(app) as client:
        with client.websocket_connect('/ws') as socket:
            initial = socket.receive_json()
            socket.send_text('{broken JSON')
            assert 'valid JSON' in socket.receive_json()['error']
            socket.send_json({'action': 'step'})
            result = socket.receive_json()
            assert result['run_id'] == initial['run_id']
            assert result['time'] > 0


def test_contact_overlay_uses_effective_model_forces():
    from dataclasses import replace
    import pytest
    from src.config import SimulationConfig
    from src.simulation import Simulation
    from src.visualization.web_app import packet
    engine = Simulation(SimulationConfig(n_agents=2))
    engine.positions[:] = [[3., 3.], [3.4, 3.]]
    engine.radii[:] = .3
    contact = packet(engine, False, 'test')['contacts']
    assert len(contact) == 1
    assert contact[0][:2] == [0, 1]
    assert contact[0][2] == pytest.approx(.2 * engine.config.physics.k)
    engine.config = replace(engine.config, movement_model='social')
    assert packet(engine, False, 'test')['contacts'] == []
