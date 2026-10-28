r"""Validated SI constants, geometry, and reproducible experimental presets.

Helbing, Farkas & Vicsek (2000), doi:10.1038/35035023, motivate the default
m=80 kg, tau=0.5 s, A=2000 N, B=0.08 m, k=120000 N/m and
kappa=240000 kg/(m s). In LaTeX, the relaxation time is $\tau$ and the
contact coefficients are $k$ and $\kappa$. Geometry and desired speed are
experimental choices, not a claim of an exact reproduction of the Nature study.
"""
from dataclasses import asdict, dataclass, field
import math


@dataclass(frozen=True)
class Physics:
    r"""Force parameters in SI units, shared by every pedestrian.

    The contact oscillation time is sqrt(m/k) seconds. Explicit integration
    needs dt well below this time and below m/(kappa*overlap) when friction acts.
    Speed clamping is a numerical safeguard whose activation is always logged.
    """
    mass: float = 80.0
    tau: float = 0.5
    A: float = 2000.0
    B: float = 0.08
    k: float = 120000.0
    kappa: float = 240000.0
    radius: float = 0.30
    radius_spread: float = 0.02
    max_speed: float = 12.0
    risk_threshold: float = 1600.0

    def __post_init__(self):
        r"""Reject nonfinite or nonphysical constants before array broadcasting.

        Positive lengths and time constants keep divisions and exp(overlap/B)
        meaningful; zero force coefficients deliberately permit analytic tests.
        """
        values = asdict(self)
        if not all(math.isfinite(v) for v in values.values()):
            raise ValueError("Physical constants must be finite.")
        if any(values[key] <= 0 for key in ("mass", "tau", "B", "radius", "max_speed", "risk_threshold")):
            raise ValueError("Mass, time, length, speed and threshold must be positive.")
        if min(self.A, self.k, self.kappa, self.radius_spread) < 0 or self.radius_spread >= self.radius:
            raise ValueError("Force coefficients and radius spread are invalid.")


@dataclass(frozen=True)
class Pillar:
    r"""Circular stationary obstacle: center (x,y) and radius in meters."""
    x: float
    y: float
    radius: float

    def __post_init__(self):
        r"""Require a finite center and positive radius for circle distances."""
        if not all(math.isfinite(v) for v in (self.x, self.y, self.radius)) or self.radius <= 0:
            raise ValueError("Pillar coordinates must be finite and radius positive.")


@dataclass(frozen=True)
class Exit:
    side: str
    center: float
    width: float

    def __post_init__(self):
        if self.side not in ('left', 'right', 'top', 'bottom') or not all(math.isfinite(v) for v in (self.center, self.width)) or self.width <= 0:
            raise ValueError('Exit needs a valid side, finite center and positive width.')


@dataclass(frozen=True)
class Room:
    r"""Rectangle with a centered aperture on its right wall, measured in meters.

    Optional interior segments use ((x1,y1),(x2,y2)). They exert the same local
    force law as room walls; global route planning through arbitrary mazes is
    outside this model. In LaTeX the exit interval is $[H/2-w/2,H/2+w/2]$.
    """
    width: float = 8.0
    height: float = 8.0
    exit_width: float = 1.0
    pillars: tuple[Pillar, ...] = ()
    interior_segments: tuple = ()
    exits: tuple[Exit, ...] = ()
    spawn: tuple | None = None

    @property
    def openings(self):
        return self.exits or (Exit('right', self.height / 2, self.exit_width),)

    def __post_init__(self):
        r"""Validate nondegenerate walls and keep circular obstacles indoors."""
        if not all(math.isfinite(v) for v in (self.width, self.height, self.exit_width)):
            raise ValueError("Room dimensions must be finite.")
        if self.width < 4 or self.height < 3 or not 0 < self.exit_width <= self.height:
            raise ValueError("Room needs width >= 4 m, height >= 3 m and a valid exit.")
        for pillar in self.pillars:
            if not (pillar.radius < pillar.x < self.width - pillar.radius and
                    pillar.radius < pillar.y < self.height - pillar.radius):
                raise ValueError("Pillars must lie strictly inside the room.")
        for side in ('left', 'right', 'top', 'bottom'):
            intervals = sorted((e.center-e.width/2, e.center+e.width/2, index+1) for index,e in enumerate(self.openings) if e.side == side)
            length = self.height if side in ('left', 'right') else self.width
            previous, previous_index = -1, None
            for lo, hi, index in intervals:
                if lo < -1e-9 or hi > length+1e-9:
                    raise ValueError(f'Exit {index} on the {side} wall spans {lo:.2f}–{hi:.2f} m; the wall runs from 0 to {length:g} m. Move its center or reduce its width.')
                if lo < previous-1e-9:
                    raise ValueError(f'Exit {index} overlaps exit {previous_index} on the {side} wall. Move or resize one of these exits.')
                previous = hi
                previous_index = index
        if self.spawn is not None:
            if len(self.spawn) != 4 or not all(math.isfinite(v) for v in self.spawn):
                raise ValueError('Spawn must be [x, y, width, height].')
            x, y, w, h = self.spawn
            if min(x, y) < 0 or min(w, h) <= 0 or x+w > self.width or y+h > self.height:
                raise ValueError('Spawn rectangle must fit inside the room.')
        for start, end in self.interior_segments:
            if start == end or not all(math.isfinite(v) for point in (start, end) for v in point):
                raise ValueError("Interior wall segments must be finite and nondegenerate.")
            if not all(0 <= point[0] <= self.width and 0 <= point[1] <= self.height for point in (start, end)):
                raise ValueError("Interior wall endpoints must lie inside the room.")

    @property
    def exit_limits(self):
        r"""Return the lower and upper aperture coordinates (meters)."""
        return (self.height - self.exit_width) / 2, (self.height + self.exit_width) / 2


@dataclass(frozen=True)
class SimulationConfig:
    r"""A complete seeded run; dt and recording interval are in seconds.

    Default 60 agents occupy a jittered, separated upstream lattice. The same
    seed gives identical initial bodies in baseline and pillar experiments.
    """
    n_agents: int = 60
    desired_speed: float = 5.0
    dt: float = 0.0015
    duration: float = 90.0
    sample_interval: float = 0.15
    seed: int = 7
    method: str = "euler"
    speed_spread: float = 0.0
    pre_movement_max: float = 0.0
    movement_model: str = 'hfv'
    group_size: int = 1
    cohesion: float = 0.0
    congestion_weight: float = 0.0
    physics: Physics = field(default_factory=Physics)
    room: Room = field(default_factory=Room)

    def __post_init__(self):
        r"""Check scalar domains and a conservative elastic timestep limit.

        dt <= 0.2 sqrt(m/k), or $\Delta t \leq 0.2\sqrt{m/k}$, is a
        preliminary check; multi-contact friction still requires convergence
        studies. It is not a general proof of stability.
        """
        if isinstance(self.n_agents, bool) or not isinstance(self.n_agents, int) or self.n_agents < 1:
            raise ValueError("Crowd size must be a positive integer.")
        if not all(math.isfinite(v) and v > 0 for v in (self.dt, self.duration, self.sample_interval, self.desired_speed)):
            raise ValueError("Time intervals and desired speed must be finite and positive.")
        if self.physics.k and self.dt > 0.2 * math.sqrt(self.physics.mass / self.physics.k):
            raise ValueError("Timestep exceeds the conservative elastic stability limit.")
        if self.method not in ("euler", "verlet"):
            raise ValueError("Integrator must be euler or verlet.")
        if not math.isfinite(self.speed_spread) or not 0 <= self.speed_spread < 1:
            raise ValueError('Relative speed spread must be in [0, 1).')
        if not math.isfinite(self.pre_movement_max) or self.pre_movement_max < 0:
            raise ValueError('Maximum pre-movement delay must be finite and nonnegative.')
        if self.movement_model not in ('hfv','social'):
            raise ValueError('Movement model must be hfv or social.')
        if not isinstance(self.group_size,int) or not 1 <= self.group_size <= 20:
            raise ValueError('Group size must be 1–20.')
        if any(not math.isfinite(v) or v<0 for v in (self.cohesion,self.congestion_weight)):
            raise ValueError('Cohesion and congestion weight must be nonnegative finite values.')

    def to_dict(self):
        r"""Serialize parameters without losing SI values or reproducibility."""
        return asdict(self)


def room_from_dict(data):
    r"""Parse JSON geometry into immutable circles and segment tuples.

    Each pillar is {x, y, radius} in meters. Segment nesting is converted to
    tuples so geometry is immutable and equality remains scalar, not an array.
    """
    if not isinstance(data, dict):
        raise ValueError('Room must be a JSON object.')
    data = dict(data)
    allowed = {'width','height','exit_width','pillars','interior_segments','exits','spawn'}
    if set(data)-allowed:
        raise ValueError('Unknown room fields: '+', '.join(sorted(set(data)-allowed)))
    for field_name in ('pillars','exits','interior_segments'):
        if not isinstance(data.get(field_name, []), (list,tuple)):
            raise ValueError(field_name+' must be an array.')
    if any(not isinstance(item,dict) or set(item) != {'x','y','radius'} for item in data.get('pillars', [])):
        raise ValueError('Each pillar needs exactly x, y and radius.')
    if any(not isinstance(item,dict) or set(item) != {'side','center','width'} for item in data.get('exits', [])):
        raise ValueError('Each exit needs exactly side, center and width.')
    for segment in data.get('interior_segments', []):
        if not isinstance(segment,(list,tuple)) or len(segment)!=2 or any(not isinstance(p,(list,tuple)) or len(p)!=2 for p in segment):
            raise ValueError('Walls need two points with two coordinates each.')
    data['exits'] = tuple(Exit(**item) for item in data.get('exits', ()))
    if data.get('spawn') is not None:
        data['spawn'] = tuple(data['spawn'])
    data["pillars"] = tuple(Pillar(**item) for item in data.get("pillars", ()))
    data["interior_segments"] = tuple(tuple(tuple(point) for point in segment)
                                       for segment in data.get("interior_segments", ()))
    return Room(**data)


PRESET_SPEEDS = (1.0, 2.0, 3.5, 5.0, 7.0)
