r"""Detect slow, compressive paths connecting both doorway jambs.

A graph edge denotes elastic pair load k*overlap above a threshold in Newtons.
A connected component touching both jambs is an arch *candidate*. Requiring
low mean speed and upstream location rejects many moving contact networks.
Graph connectivity does not establish static force balance or self-locking.
"""
from dataclasses import dataclass
import numpy as np
from src.config import Room


def detect_arch(positions, velocities, radii, compression, room: Room,
                force_threshold=100.0, speed_threshold=0.35):
    r"""Return arch existence, component indices and strong contact edges.

    adjacency[i,j] = (k*h_ij >= threshold). In LaTeX
    $G_{ij}=\mathbf{1}[kh_{ij}\geq F_{min}]$. The boolean (N,N) matrix
    is traversed by depth-first search. Endpoints must touch circular disks
    around both jambs within radius+0.025 m; all graph vertices must be within
    1.8 m upstream or 0.35 m downstream of the exit plane.
    """
    n = len(positions)
    near = (positions[:, 0] > room.width - 1.8) & (positions[:, 0] < room.width + 0.35)
    adjacency = (compression >= force_threshold) & near[:, None] & near[None, :]
    np.fill_diagonal(adjacency, False)
    edges = np.argwhere(np.triu(adjacency, 1)).tolist()
    low, high = room.exit_limits
    lower = np.linalg.norm(positions - [room.width, low], axis=1) <= radii + 0.025
    upper = np.linalg.norm(positions - [room.width, high], axis=1) <= radii + 0.025
    seen = np.zeros(n, dtype=bool)
    for root in np.flatnonzero(near):
        if seen[root]:
            continue
        stack, component = [int(root)], []
        seen[root] = True
        while stack:
            node = stack.pop()
            component.append(node)
            neighbors = np.flatnonzero(adjacency[node] & ~seen)
            seen[neighbors] = True
            stack.extend(neighbors.tolist())
        members = np.asarray(component)
        if lower[members].any() and upper[members].any() and len(members) >= 2:
            if np.mean(np.linalg.norm(velocities[members], axis=1)) < speed_threshold:
                return True, component, edges
    return False, [], edges


@dataclass
class ArchTracker:
    r"""Accumulate sampled arch durations in seconds with left-interval timing."""
    duration: float = 0.0
    longest: float = 0.0
    episodes: int = 0
    current: float = 0.0
    previous_time: float = 0.0
    previous_active: bool = False

    def update(self, time, active):
        r"""Assign [previous_time,time) to the previous sampled graph state.

        The estimated integral is sum(I_arch*delta_t), or
        $T_{arch}\approx\sum I_{arch}(t_n)\Delta t_n$. Sampling uncertainty
        is at least one recording interval per transition; this is documented.
        """
        if self.previous_active:
            interval = time - self.previous_time
            self.duration += interval
            self.current += interval
            self.longest = max(self.longest, self.current)
        if active and not self.previous_active:
            self.episodes += 1
            self.current = 0.0
        if not active:
            self.current = 0.0
        self.previous_active, self.previous_time = bool(active), float(time)
