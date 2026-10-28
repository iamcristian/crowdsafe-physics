r"""Radial pressure and event-based evacuation statistics with censoring.

P_i = sum_j |f_ij^normal|/(2*pi*r_i), or
$P_i=\sum_j\|f_{ij}^{normal}\|/(2\pi r_i)$, has units N/m. The primary
metric includes social and elastic pair normal force, excludes friction,
and excludes walls. Boundary-inclusive pressure is exported separately.
The requested 1600 N/m indicator is not a validated asphyxiation threshold.
"""
from dataclasses import dataclass, field
import math
import numpy as np


def radial_pressure(normal_load, radii, boundary_load=None):
    r"""Divide scalar inward loads by each body's circumference, returning (N,).

    Sum axis 1 of (N,N) magnitudes before dividing by 2*pi*r (meters).
    Opposite normal forces add instead of canceling. Optional (N,W) boundary
    magnitudes are included only when explicitly supplied by the caller.
    """
    load = np.sum(normal_load, axis=1)
    if boundary_load is not None:
        load = load + np.sum(boundary_load, axis=1)
    return load / (2.0 * np.pi * radii)


def rolling_flow(exit_times, time, window=2.0):
    r"""Count exits in (max(0,t-window),t] / observed window, in ped/s.

    This is a finite-window event rate: $Q=\Delta N/\Delta t$. The first
    window is shortened at t=0; rates are never divided by an unobserved time.
    """
    if time <= 0:
        return 0.0
    values = np.asarray(exit_times)
    start = max(0.0, time - window)
    return float(np.count_nonzero((values > start) & (values <= time)) / min(time, window))


@dataclass
class Telemetry:
    r"""Accumulate every-step pressure and exact interpolated exit events.

    mean_pressure = integral(sum_i P_i dt)/integral(N_active dt), an
    agent-time weighted mean. Exited pedestrians are excluded thereafter.
    Exposure is reported in agent-seconds, not as a medical risk probability.
    """
    initial_count: int
    threshold: float = 1600.0
    exit_times: list = field(default_factory=list)
    peak_pressure: float = 0.0
    peak_boundary_inclusive_pressure: float = 0.0
    pressure_integral: float = 0.0
    active_agent_time: float = 0.0
    exposure_agent_seconds: float = 0.0
    clamp_count: int = 0
    max_overlap: float = 0.0
    rows: list = field(default_factory=list)

    def observe(self, pressure, boundary_pressure, overlap, dt, clamp_count):
        r"""Integrate pressure with a left rectangle rule each physics step.

        P (N/m) times dt (s), summed over bodies, gives the numerator of the
        agent-time mean. Empty arrays are legal after complete evacuation.
        """
        self.peak_pressure = max(self.peak_pressure, float(np.max(pressure, initial=0)))
        self.peak_boundary_inclusive_pressure = max(self.peak_boundary_inclusive_pressure,
                                                  float(np.max(boundary_pressure, initial=0)))
        self.pressure_integral += float(pressure.sum()) * dt
        self.active_agent_time += len(pressure) * dt
        self.exposure_agent_seconds += int(np.count_nonzero(pressure > self.threshold)) * dt
        self.clamp_count += clamp_count
        self.max_overlap = max(self.max_overlap, float(np.max(overlap, initial=0)))

    def sample(self, time, pressure, active, arch_active):
        r"""Record a decimated time series; event counts remain timestep-exact.

        The surviving fraction is active/N_initial, a dimensionless empirical
        evacuation curve. Flow is in pedestrians/s and pressures are N/m.
        """
        self.rows.append(dict(time=float(time), remaining=int(active), evacuated=len(self.exit_times),
                              mean_pressure=float(np.mean(pressure)) if len(pressure) else 0.0,
                              peak_pressure=float(np.max(pressure, initial=0)),
                              flow_rate=rolling_flow(self.exit_times, time), arch_active=bool(arch_active)))

    def summary(self, time):
        r"""Return finite JSON metrics; unobserved T90 and completion are null.

        T90 is the ceil(0.9*N)-th ordered exit. Average flow is N_exit/t_end.
        Restricted mean evacuation time integrates the survival curve using
        min(T_i,t_end); censored bodies contribute t_end without fake exits.
        """
        ordered = sorted(self.exit_times)
        rank = math.ceil(0.9 * self.initial_count)
        restricted = (sum(ordered) + (self.initial_count - len(ordered)) * time) / self.initial_count
        return dict(n_agents=self.initial_count, evacuated=len(ordered), observed_time=float(time),
                    t90=float(ordered[rank-1]) if len(ordered) >= rank else None,
                    total_evacuation_time=float(ordered[-1]) if len(ordered) == self.initial_count else None,
                    censored=len(ordered) < self.initial_count, restricted_mean_evacuation_time=restricted,
                    peak_pressure=self.peak_pressure,
                    mean_pressure=self.pressure_integral / max(self.active_agent_time, 1e-12),
                    peak_boundary_inclusive_pressure=self.peak_boundary_inclusive_pressure,
                    exposure_agent_seconds=self.exposure_agent_seconds,
                    mean_flow_rate=len(ordered) / max(time, 1e-12),
                    velocity_clamp_count=self.clamp_count, max_pair_overlap=self.max_overlap)
