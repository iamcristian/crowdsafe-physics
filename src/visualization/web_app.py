r"""FastAPI/WebSocket visualization using the production Python force engine.

Each socket owns an isolated Simulation. Browser messages control play, pause,
reset and parameters; snapshots report meters, seconds, N/m and pedestrians/s.
Physics work runs in a worker thread so the event loop remains responsive.
This local research service deliberately has no external CDN dependency.
"""
import asyncio
from dataclasses import replace
from pathlib import Path
import json
import threading
import uuid
import math
import platform
import hashlib
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from src.config import SimulationConfig, Room, Pillar, Physics, room_from_dict
from src.simulation import Simulation
from src.analytics.telemetry import radial_pressure, rolling_flow

app = FastAPI(title="CrowdSafe-Physics", version="0.1.0")
jobs = {}
job_lock = threading.Lock()


class Controls(BaseModel):
    r"""Validated UI settings in SI units; crowd size fits the common lattice."""
    model_config = ConfigDict(extra="forbid")
    speed: float = Field(default=5, ge=0.5, le=7, allow_inf_nan=False)
    crowd: int = Field(default=40, ge=5, le=60)
    exit_width: float = Field(default=1.2, ge=0.8, le=2.5, allow_inf_nan=False)
    pillar: bool = False
    seed: int = Field(default=7, ge=0, le=2147483647)
    duration: float = Field(default=120, ge=1, le=600, allow_inf_nan=False)
    dt: float = Field(default=0.0015, ge=0.0002, le=0.003, allow_inf_nan=False)
    method: str = "euler"
    room: dict | None = None
    speed_spread: float = Field(default=0, ge=0, lt=1, allow_inf_nan=False)
    pre_movement_max: float = Field(default=0, ge=0, le=300, allow_inf_nan=False)
    radius: float = Field(default=.30, ge=.15, le=.5, allow_inf_nan=False)
    radius_spread: float = Field(default=.02, ge=0, le=.1, allow_inf_nan=False)
    movement_model: str = 'hfv'
    group_size: int = Field(default=1,ge=1,le=20)
    cohesion: float = Field(default=0,ge=0,le=160,allow_inf_nan=False)
    congestion_weight: float = Field(default=0,ge=0,le=10,allow_inf_nan=False)


def configured_engine(controls):
    r"""Build a seeded engine and use the measured design if available locally.

    A missing benchmark uses a named demonstration geometry, not a claimed
    optimized solution. Both selections are exposed in the initial UI packet.
    """
    report = Path("outputs/data/benchmark_summary.json")
    design = json.loads(report.read_text(encoding="utf-8"))["selected_pillar"] if report.exists() else dict(x=6.0, y=4.45, radius=0.45)
    pillars = (Pillar(**design),) if controls.pillar else ()
    room = room_from_dict(controls.room) if controls.room is not None else Room(exit_width=controls.exit_width, pillars=pillars)
    if room.width > 50 or room.height > 50 or len(room.pillars) > 30 or len(room.interior_segments) > 60:
        raise ValueError("Interactive geometry limit: 50 m dimensions, 30 pillars and 60 wall segments.")
    config = SimulationConfig(n_agents=controls.crowd, desired_speed=controls.speed, dt=controls.dt,
                              duration=controls.duration, seed=controls.seed, method=controls.method, room=room,
                              speed_spread=controls.speed_spread, pre_movement_max=controls.pre_movement_max,
                              movement_model=controls.movement_model,group_size=controls.group_size,cohesion=controls.cohesion,congestion_weight=controls.congestion_weight,
                              physics=Physics(radius=controls.radius, radius_spread=controls.radius_spread))
    if controls.room is not None:
        return Simulation(config, record=False), "Custom geometry · global grid routing" if room.exits or room.interior_segments else "Custom geometry · local steering"
    return Simulation(config, record=False), ("Measured benchmark design" if report.exists() else "Demonstration design")


def advance(engine, steps=20):
    r"""Run a bounded physics batch; simulation time grows by steps*dt seconds.

    Batching reduces WebSocket overhead while preserving the small integration
    timestep. No variable browser frame interval enters the force equations.
    """
    for _ in range(steps):
        engine.step()
        if engine.done:
            break


def packet(engine, playing, design_label):
    r"""Export the current positions plus a live SI telemetry snapshot.

    Pressure colors use pair normal force divided by circumference; the browser
    receives actual engine arrays, not a second approximate physics model.
    """
    forces = engine.forces(engine.positions, engine.velocities)
    pressure = radial_pressure(forces.pair_normal, engine.radii)
    frame = engine.frame(pressure)
    contact_pairs = np.argwhere(np.triu(forces.compression > 0, 1))
    frame['contacts'] = [[int(i), int(j), float(forces.compression[i, j])] for i, j in contact_pairs]
    frame.update(playing=playing, done=engine.done, room=engine.config.to_dict()["room"],
                 config=engine.config.to_dict(), metrics=engine.result().metrics,
                 wall_segments=__import__('src.physics.geometry', fromlist=['wall_segments']).wall_segments(engine.config.room).tolist(),
                 arch_supported=not bool(engine.config.room.exits),
                 velocities=engine.velocities.tolist(),
                 desired_speeds=(engine.config.desired_speed*engine.speed_factors).tolist(),
                 start_times=engine.start_times.tolist(),
                 waiting=int((engine.time < engine.start_times).sum()),
                 completion_reason=("evacuated" if not len(engine.ids) else "horizon") if engine.done else None,
                 design_label=design_label, evacuated=len(engine.telemetry.exit_times),
                 flow=rolling_flow(engine.telemetry.exit_times, engine.time),
                 peak_pressure=float(pressure.max()) if len(pressure) else 0,
                 exposure=engine.telemetry.exposure_agent_seconds)
    return frame


@app.get("/", response_class=HTMLResponse)
def index():
    r"""Serve the packaged, self-contained Canvas dashboard document."""
    return (Path(__file__).with_name("dashboard.html")).read_text(encoding="utf-8")


@app.get("/health")
def health():
    r"""Expose a lightweight readiness check without creating a simulation."""
    return {"status": "ok", "model": "HFV", "version": "0.1.0"}


@app.get("/workspace.js")
def workspace_script():
    return Response(Path(__file__).with_name("workspace.js").read_text(encoding="utf-8"), media_type="text/javascript")

@app.get("/editor.js")
def editor_script():
    return Response(Path(__file__).with_name("editor.js").read_text(encoding="utf-8"), media_type="text/javascript")


@app.get('/exit-geometry.js')
def exit_geometry_script():
    return Response(Path(__file__).with_name('exit-geometry.js').read_text(encoding='utf-8'), media_type='text/javascript')


@app.get('/analysis.js')
def analysis_script():
    return Response(Path(__file__).with_name('analysis.js').read_text(encoding='utf-8'), media_type='text/javascript')

@app.get('/advanced.js')
def advanced_script():
    return Response(Path(__file__).with_name('advanced.js').read_text(encoding='utf-8'), media_type='text/javascript')

@app.get('/extensions.js')
def extensions_script():
    return Response(Path(__file__).with_name('extensions.js').read_text(encoding='utf-8'), media_type='text/javascript')


@app.get('/studio.js')
def studio_script():
    return Response(Path(__file__).with_name('studio.js').read_text(encoding='utf-8'), media_type='text/javascript')


@app.get('/studio.css')
def studio_styles():
    return Response(Path(__file__).with_name('studio.css').read_text(encoding='utf-8'), media_type='text/css')

@app.get('/api/empirical')
def empirical_report():
    report=Path(__file__).resolve().parents[2]/'outputs/empirical/hermes_report.json'
    if not report.exists():
        raise HTTPException(404,'Run python -m src.empirical to generate the experimental comparison.')
    return json.loads(report.read_text(encoding='utf-8'))

@app.post('/api/building')
async def building_job(request: dict):
    from src.building import run_building
    try:
        if len(request.get('nodes',[]))>100 or len(request.get('links',[]))>300:
            raise ValueError('Network limit: 100 nodes, 300 links.')
        return await asyncio.to_thread(run_building,request)
    except (ValueError,KeyError,TypeError) as error:
        raise HTTPException(422,str(error)) from error


@app.post('/api/studies')
def start_study(request: dict):
    from src.analytics.studies import run_study, calibrate, validate_horizons
    from src.analytics.research import sensitivity, design_search, monte_carlo
    try:
        mode = request.get('mode', 'study')
        if mode=='monte_carlo':
            Controls(**request['controls'])
            seeds=request['seeds']
            if not 4<=len(seeds)<=12 or len(set(seeds))!=len(seeds) or not 4<=request.get('minimum',4)<=len(seeds) or not math.isfinite(request.get('half_width',.5)) or request.get('half_width',.5)<=0:
                raise ValueError('Use 4–12 distinct seeds, minimum >=4 and positive finite RMET half-width.')
            for seed in seeds:Controls(**dict(request['controls'],seed=seed))
        elif mode in ('sensitivity','geometry_search'):
            Controls(**request['controls'])
            seeds=request['seeds']
            if not 1<=len(seeds)<=3 or len(set(seeds))!=len(seeds):
                raise ValueError('Research jobs need 1–3 distinct training seeds.')
            for seed in seeds:
                Controls(**dict(request['controls'],seed=seed))
            if mode=='sensitivity':
                fields={'speed','pre_movement_max','speed_spread','radius'}
                if not 1<=len(request['bounds'])<=3 or set(request['bounds'])-fields or not 4<=request.get('samples',8)<=16:
                    raise ValueError('Use 1–3 supported parameters and 4–16 base samples.')
                for field,bounds in request['bounds'].items():
                    if len(bounds)!=2 or not bounds[0]<bounds[1]:
                        raise ValueError('Bounds must be [minimum, maximum].')
                    for value in bounds:
                        Controls(**dict(request['controls'],**{field:value}))
            else:
                holdout=request['validation_seeds']
                if not 1<=len(holdout)<=3 or len(set(holdout))!=len(holdout) or set(seeds)&set(holdout) or not 2<=request.get('budget',6)<=12:
                    raise ValueError('Use 1–3 distinct held-out seeds, disjoint from training, and budget 2–12.')
                for seed in holdout:
                    Controls(**dict(request['controls'],seed=seed))
        elif mode == 'calibration':
            Controls(**request['controls'])
            speeds, records = request['speeds'], request['observations']
            if not 1 <= len(speeds) <= 8 or not 2 <= len(records) <= 12:
                raise ValueError('Use 1–8 speed candidates and 2–12 observations.')
            for speed in speeds:
                Controls(**dict(request['controls'], speed=speed))
            for row in records:
                Controls(**dict(request['controls'], seed=row['seed']))
                if row['split'] not in ('train', 'validation') or not math.isfinite(row['rmet']) or row['rmet'] < 0:
                    raise ValueError('Observations require seed, split (train/validation) and nonnegative finite rmet in seconds.')
                if row['rmet'] > request['controls'].get('duration', 120):
                    raise ValueError('Observed RMET cannot exceed the configured observation horizon.')
            if len(set(row['seed'] for row in records)) != len(records):
                raise ValueError('Each observation must have a distinct seed.')
        elif mode == 'study':
            seeds, candidates = request['seeds'], request['candidates']
            if not 1 <= len(candidates) <= 6 or not 1 <= len(seeds) <= 12 or len(set(seeds)) != len(seeds):
                raise ValueError('Use 1–6 candidates and 1–12 distinct seeds.')
            for candidate in candidates:
                for seed in seeds:
                    Controls(**dict(candidate, seed=seed))
            validate_horizons([Controls(**candidate).duration for candidate in candidates])
        else:
            raise ValueError('Unknown study mode.')
    except (ValueError, TypeError, KeyError) as error:
        raise HTTPException(422, str(error)) from error
    with job_lock:
        if any(job['status'] == 'running' for job in jobs.values()):
            raise HTTPException(409, 'A study is already running. Cancel it or wait for completion.')
        while len(jobs) >= 8:
            jobs.pop(next(iter(jobs)))
        identity = uuid.uuid4().hex
        job = dict(status='running', completed=0, total=0, cancel=False, result=None, error=None)
        jobs[identity] = job
    def work():
        def progress(completed,total):
            job.update(completed=completed,total=total)
        try:
            worker={'calibration':calibrate,'study':run_study,'sensitivity':sensitivity,'geometry_search':design_search,'monte_carlo':monte_carlo}[mode]
            job['result'] = worker(request,
                lambda data: configured_engine(Controls(**data)), progress, lambda:job['cancel'])
            if job['result'] is not None:
                job['result']['request'] = request
                job['result']['provenance'] = dict(python=platform.python_version(), platform=platform.platform(),
                    request_sha256=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest())
                directory = Path('outputs/studies')
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f'{identity}.json').write_text(json.dumps(job['result'],allow_nan=False,indent=2),encoding='utf-8')
            job['status'] = 'cancelled' if job['cancel'] else 'complete'
        except Exception as error:
            job.update(status='cancelled' if job['cancel'] else 'failed', error=str(error))
    threading.Thread(target=work,daemon=True).start()
    return {'id':identity}


@app.get('/api/studies/{identity}')
def study_status(identity: str):
    if identity not in jobs:
        if len(identity)!=32 or any(c not in '0123456789abcdef' for c in identity):
            raise HTTPException(404, 'Study not found.')
        file = Path('outputs/studies') / f'{identity}.json'
        if file.is_file():
            return dict(status='archived',result=json.loads(file.read_text(encoding='utf-8')),completed=0,total=0,error=None)
        raise HTTPException(404, 'Study not found.')
    return dict(jobs[identity])


@app.get('/api/study-archive')
def study_archive():
    directory = Path('outputs/studies')
    return [{'id':file.stem,'bytes':file.stat().st_size} for file in sorted(directory.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:50]]


@app.post('/api/studies/{identity}/cancel')
def cancel_study(identity: str):
    if identity not in jobs:
        raise HTTPException(404, 'Study not found.')
    jobs[identity]['cancel'] = True
    return {'requested':True}


@app.websocket("/ws")
async def websocket_simulation(websocket: WebSocket):
    r"""Own one client simulation and process bounded, validated commands.

    A 30 ms receive timeout schedules updates during play. Reset and geometry
    changes rebuild initial conditions; desired-speed changes are applied live.
    Validation errors become readable packets and do not kill the connection.
    """
    await websocket.accept()
    controls = Controls()
    engine, label = await asyncio.to_thread(configured_engine, controls)
    playing = False
    first = packet(engine, playing, label)
    first['controls'] = controls.model_dump()
    await websocket.send_json(first)
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=0.03 if playing else 60)
            except asyncio.TimeoutError:
                message = {"action": "tick"}
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Commands must contain valid JSON."})
                continue
            try:
                if not isinstance(message, dict):
                    raise ValueError("Commands must be JSON objects.")
                action = message.get("action")
                if action in ("reset", "configure"):
                    new_controls = Controls(**message.get("controls", {}))
                    geometry_changed = new_controls.model_dump(exclude={"speed"}) != controls.model_dump(exclude={"speed"})
                    if action == "reset" or geometry_changed:
                        engine, label = await asyncio.to_thread(configured_engine, new_controls)
                        playing = False
                    else:
                        engine.config = replace(engine.config, desired_speed=new_controls.speed)
                    controls = new_controls
                elif action == "play":
                    playing = not engine.done
                elif action == "pause":
                    playing = False
                elif action not in ("tick", "step"):
                    raise ValueError("Unknown action; use play, pause, reset, configure or step.")
                if playing or action == "step":
                    await asyncio.to_thread(advance, engine)
                if engine.done:
                    playing = False
                await websocket.send_json(packet(engine, playing, label))
            except (ValidationError, ValueError, TypeError) as error:
                await websocket.send_json({"error": str(error)})
    except WebSocketDisconnect:
        return
