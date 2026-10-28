r"""Reproducible simulation lifecycle, crossing events and portable artifacts.

This module connects F=m*a to evacuation measurement. Bodies are removed only
when their rear edge clears the exit plane: x_center=W+r. Event time is
linearly interpolated across the last numerical step, not rounded to a frame.
Initial placement is independent of pillar design to support paired trials.
"""
from dataclasses import dataclass, replace
import csv
import json
import uuid
from pathlib import Path
import numpy as np
from src.config import SimulationConfig
from src.physics.geometry import segment_distances, wall_segments
from src.physics.forces import total_forces
from src.physics.integrator import semi_implicit_euler, velocity_verlet
from src.analytics.telemetry import Telemetry, radial_pressure
from src.analytics.arch_detector import ArchTracker, detect_arch


def initial_state(config: SimulationConfig):
    r"""Sample an upstream separated lattice and radii using a local RNG.

    Lattice spacing exceeds 2*r_max; independent jitter is limited to preserve
    nonoverlap. The final 3.1 m upstream of the exit is left clear for design
    comparisons. Positions are (N,2) meters, velocities (N,2) m/s, radii (N,).
    Custom walls/pillars cannot intersect initial disks: invalid runs fail
    clearly rather than relocating agents differently between treatments.
    """
    rng = np.random.default_rng(config.seed)
    p, room = config.physics, config.room
    maximum = p.radius + p.radius_spread
    spacing = 2 * maximum + 0.09
    xs = np.arange(maximum + 0.15, room.width - 3.1, spacing)
    ys = np.arange(maximum + 0.15, room.height - maximum - 0.1, spacing)
    if room.spawn is not None:
        x, y, w, h = room.spawn
        xs = np.arange(x+maximum+.03, x+w-maximum-.03, spacing)
        ys = np.arange(y+maximum+.03, y+h-maximum-.03, spacing)
    lattice = np.array([(x, y) for x in xs for y in ys])
    if room.spawn is not None and len(lattice):
        distance, _, _ = segment_distances(lattice, wall_segments(room))
        valid = (distance >= maximum+.03).all(axis=1)
        for pillar in room.pillars:
            valid &= np.linalg.norm(lattice-[pillar.x,pillar.y], axis=1) >= pillar.radius+maximum+.03
        lattice = lattice[valid]
    if len(lattice) < config.n_agents:
        raise ValueError(f"Upstream lattice holds {len(lattice)} agents; reduce crowd size or enlarge the room.")
    chosen = rng.permutation(len(lattice))[:config.n_agents]
    positions = lattice[chosen] + rng.uniform(-0.025, 0.025, (config.n_agents, 2))
    radii = rng.uniform(p.radius - p.radius_spread, maximum, config.n_agents)
    distance, _, _ = segment_distances(positions, wall_segments(room))
    if np.any(distance < radii[:, None]):
        raise ValueError("An initial body intersects a wall; revise geometry or seed.")
    for pillar in room.pillars:
        if np.any(np.linalg.norm(positions - [pillar.x, pillar.y], axis=1) < radii + pillar.radius):
            raise ValueError("An initial body intersects a pillar; preserve the upstream design clearance.")
    return positions, np.zeros_like(positions), radii


@dataclass
class SimulationResult:
    r"""Serializable summary, sampled trajectory and peak-pressure snapshot."""
    config: dict
    metrics: dict
    telemetry: list
    exit_times: list
    frames: list
    snapshot: dict

    def save(self, directory, name):
        r"""Write strict JSON plus a CSV time series under an explicit stem.

        allow_nan=False rejects nonfinite scientific output. CSV uses one
        sampled time per row; JSON also preserves configuration and trajectories.
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        payload = dict(config=self.config, metrics=self.metrics, telemetry=self.telemetry,
                       exit_times=self.exit_times, frames=self.frames, snapshot=self.snapshot)
        (directory / f"{name}.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
        with (directory / f"{name}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.telemetry[0]))
            writer.writeheader()
            writer.writerows(self.telemetry)


class Simulation:
    r"""Stateful engine shared by offline experiments and the web visualizer.

    active IDs retain stable identity despite deleting exited array rows.
    Each step computes left-end forces/pressure, advances motion, then detects
    complete-body crossing through the real opening. No exit timer is guessed.
    """
    def __init__(self, config: SimulationConfig, record=True):
        r"""Create deterministic SI arrays, telemetry and graph-duration state."""
        self.config, self.record = config, record
        self.positions, self.velocities, self.radii = initial_state(config)
        self.ids = np.arange(config.n_agents)
        self.run_id = uuid.uuid4().hex
        population_rng = np.random.default_rng(np.random.SeedSequence([config.seed, 991]))
        self.speed_factors = population_rng.uniform(1-config.speed_spread, 1+config.speed_spread, config.n_agents)
        self.start_times = population_rng.uniform(0, config.pre_movement_max, config.n_agents)
        self.time = 0.0
        self.telemetry = Telemetry(config.n_agents, config.physics.risk_threshold)
        self.arch = ArchTracker()
        self.frames, self.snapshot = [], {}
        self.next_sample = 0.0
        self.peak_snapshot_pressure = -1.0
        self.done = False
        self.router = None
        self.route_time = -1
        self.route_directions = None
        self.exit_routers=[]
        self.exit_assignments=np.zeros(config.n_agents,dtype=int)
        self.group_force=np.zeros_like(self.positions)
        if config.room.exits or config.room.interior_segments or config.congestion_weight or config.cohesion:
            from src.physics.routing import Router
            self.router = Router(config.room, config.physics.radius+config.physics.radius_spread+.02)
            if any(self.router.waypoint(p) is None for p in self.positions):
                raise ValueError('Spawn contains agents without a clearance-safe route to an exit (routing grid: 0.25 m).')
            if config.congestion_weight and len(config.room.openings)>1:
                self.exit_routers=[Router(replace(config.room,exits=(e,)),config.physics.radius+config.physics.radius_spread+.02) for e in config.room.openings]

    def forces(self, positions, velocities):
        r"""Evaluate Newtons for the current active radii and fixed environment."""
        if self.router is not None and (self.route_directions is None or self.time-self.route_time >= .15):
            self.route_directions = self.router.directions(positions)
            if self.exit_routers:
                queues=[]
                for opening in self.config.room.openings:
                    axis=0 if opening.side in ('left','right') else 1
                    boundary=(self.config.room.width if axis==0 else self.config.room.height) if opening.side in ('right','top') else 0
                    near=(abs(positions[:,axis]-boundary)<2)&(abs(positions[:,1-axis]-opening.center)<opening.width/2+1)
                    queues.append(int(near.sum())/opening.width)
                for i,p in enumerate(positions):
                    scores=[router.cost(p)+self.config.congestion_weight*queue for router,queue in zip(self.exit_routers,queues)]
                    choice=int(np.argmin(scores))
                    # Small hysteresis reduces rapid switching between exits.
                    old=self.exit_assignments[i]
                    if scores[old]<=scores[choice]+.5:
                        choice=old
                    target=self.exit_routers[choice].waypoint(p)
                    if target is not None:
                        delta=target-p
                        self.route_directions[i]=delta/max(np.linalg.norm(delta),1e-12)
                        self.exit_assignments[i]=choice
            self.group_force=np.zeros_like(positions)
            if self.config.cohesion and self.config.group_size>1:
                groups=self.ids//self.config.group_size
                for group in np.unique(groups):
                    members=np.flatnonzero(groups==group)
                    center=positions[members].mean(axis=0)
                    for i in members:
                        delta=center-positions[i];length=np.linalg.norm(delta)
                        if length>.8 and self.router.visible(positions[i],center):
                            self.group_force[i]=delta/length*min(160,self.config.cohesion*(length-.8))
            self.route_time = self.time
        physics=self.config.physics if self.config.movement_model=='hfv' else replace(self.config.physics,k=0,kappa=0)
        result=total_forces(positions, velocities, self.radii, self.config.room,
                            physics, self.config.desired_speed*self.speed_factors*(self.time >= self.start_times), self.route_directions)
        result.total+=self.group_force*(self.time>=self.start_times)[:,None]
        return result

    def frame(self, pressure):
        r"""Return a JSON-ready sampled state with SI positions and N/m colors."""
        return dict(time=float(self.time), run_id=self.run_id, model_revision='population-grid-v3', ids=self.ids.tolist(), positions=self.positions.tolist(),
                    radii=self.radii.tolist(), pressure=pressure.tolist())

    def step(self):
        r"""Advance one bounded timestep and update pressure/event observables.

        Exit interpolation uses alpha=(W+r-x_old)/(x_new-x_old), unitless,
        and t_exit=t_old+alpha*dt. The interpolated y must lie in the opening.
        Arch duration is estimated only at recording times, unlike pressure
        maxima and crossing events, which are evaluated every physics step.
        """
        if self.done:
            return
        c = self.config
        dt = min(c.dt, c.duration - self.time)
        force = self.forces(self.positions, self.velocities)
        pressure = radial_pressure(force.pair_normal, self.radii)
        inclusive = radial_pressure(force.pair_normal, self.radii, force.boundary_normal)
        if self.time + 1e-10 >= self.next_sample:
            active, members, edges = (False, [], []) if c.room.exits else detect_arch(self.positions, self.velocities, self.radii,
                                                 force.compression, c.room)
            self.arch.update(self.time, active)
            self.telemetry.sample(self.time, pressure, len(self.ids), active)
            if self.record:
                self.frames.append(self.frame(pressure))
            self.next_sample += c.sample_interval
        if self.record and float(np.max(pressure, initial=0)) > self.peak_snapshot_pressure:
            self.peak_snapshot_pressure = float(np.max(pressure, initial=0))
            self.snapshot = self.frame(pressure)
            edges = np.argwhere(np.triu(force.compression >= 100, 1))
            self.snapshot["edges"] = edges.tolist()
            self.snapshot["edge_loads"] = [float(force.compression[i, j]) for i, j in edges]
        if c.method == "euler":
            position, velocity, clamped = semi_implicit_euler(self.positions, self.velocities,
                                                            force.total, c.physics.mass, dt, c.physics.max_speed)
        else:
            position, velocity, clamped = velocity_verlet(self.positions, self.velocities,
                                                         lambda x, v: self.forces(x, v).total,
                                                         c.physics.mass, dt, c.physics.max_speed)
        if not np.isfinite(position).all() or not np.isfinite(velocity).all():
            raise FloatingPointError("Nonfinite trajectory; decrease the timestep.")
        self.telemetry.observe(pressure, inclusive, force.overlap, dt, clamped)
        crossed = np.zeros(len(self.ids), dtype=bool)
        for opening in c.room.openings:
            axis = 0 if opening.side in ('left', 'right') else 1
            sign = 1 if opening.side in ('right', 'top') else -1
            boundary = (c.room.width if axis == 0 else c.room.height) if sign == 1 else 0
            plane = sign*boundary+self.radii
            old, new = sign*self.positions[:,axis], sign*position[:,axis]
            indices = np.flatnonzero((old < plane) & (new >= plane) & ~crossed)
            if len(indices):
                fraction = (plane[indices]-old[indices])/(new[indices]-old[indices])
                lateral = self.positions[indices,1-axis]+fraction*(position[indices,1-axis]-self.positions[indices,1-axis])
                valid = abs(lateral-opening.center) <= opening.width/2
                crossed[indices[valid]] = True
                self.telemetry.exit_times.extend((self.time+dt*fraction[valid]).tolist())
        keep = ~crossed
        self.positions, self.velocities = position[keep], velocity[keep]
        self.radii, self.ids = self.radii[keep], self.ids[keep]
        self.speed_factors, self.start_times = self.speed_factors[keep], self.start_times[keep]
        self.exit_assignments,self.group_force=self.exit_assignments[keep],self.group_force[keep]
        if self.route_directions is not None:
            self.route_directions = self.route_directions[keep]
        self.time += dt
        self.done = len(self.ids) == 0 or self.time >= c.duration - 1e-10
        if self.done:
            self.arch.update(self.time, False)
            # The final recorded state is evaluated at the actual endpoint.
            final = self.forces(self.positions, self.velocities)
            final_pressure = radial_pressure(final.pair_normal, self.radii)
            self.telemetry.sample(self.time, final_pressure, len(self.ids), False)
            if self.record:
                self.frames.append(self.frame(final_pressure))

    def result(self):
        r"""Collect current measurements and explicitly describe arch heuristics."""
        metrics = self.telemetry.summary(self.time)
        metrics.update(arch_duration=self.arch.duration, longest_arch=self.arch.longest,
                       arch_episodes=self.arch.episodes)
        return SimulationResult(self.config.to_dict(), metrics, self.telemetry.rows,
                                sorted(self.telemetry.exit_times), self.frames, self.snapshot)


def simulate(config: SimulationConfig, record=True):
    r"""Run until every body exits or the observation horizon is reached.

    A horizon stops observation, not physical time to evacuation. The summary
    represents unfinished evacuation by null completion time and censored=True.
    """
    engine = Simulation(config, record=record)
    while not engine.done:
        engine.step()
    return engine.result()
