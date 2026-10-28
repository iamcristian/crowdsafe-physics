r"""Exact wall projections and smooth local steering around circular obstacles.

Distance to a segment uses q=a+clip(((p-a) dot (b-a))/|b-a|²,0,1)*(b-a).
In LaTeX: $q=a+\operatorname{clip}((p-a)\cdot u/(u\cdot u),0,1)u$.
Clipping is essential: door jambs are endpoints, not infinite walls.
"""
import numpy as np
from src.config import Room


def wall_segments(room: Room):
    r"""Return (W,2,2) segment endpoints in meters, leaving the exit open.

    The right wall is split into two segments. No phantom segment spans the
    doorway; exact endpoint distances nevertheless repel bodies near jambs.
    """
    w, h = room.width, room.height
    low, high = room.exit_limits
    segments = list(room.interior_segments)
    for side in ('left', 'right', 'top', 'bottom'):
        length = h if side in ('left', 'right') else w
        def point(t):
            return (0 if side == 'left' else w, t) if side in ('left', 'right') else (t, 0 if side == 'bottom' else h)
        cursor = 0
        for e in sorted((e for e in room.openings if e.side == side), key=lambda e: e.center):
            segments.append((point(cursor), point(e.center-e.width/2)))
            cursor = e.center+e.width/2
        segments.append((point(cursor), point(length)))
    # Keep the geometry tensor shape when every boundary is an opening.
    return np.asarray([segment for segment in segments if segment[0] != segment[1]], dtype=float).reshape(-1, 2, 2)


def segment_distances(positions, segments):
    r"""Return distances (N,W), outward normals (N,W,2), closest points.

    positions[:,None,:] (N,1,2) minus starts[None,:,:] (1,W,2) broadcasts
    all pedestrian-wall displacements. Projection coefficients are unitless;
    distances and closest points are meters. Exact on-wall points use a
    deterministic unit perpendicular, avoiding division by zero.
    """
    starts, vectors = segments[:, 0], segments[:, 1] - segments[:, 0]
    relative = positions[:, None, :] - starts[None, :, :]
    fraction = np.sum(relative * vectors[None, :, :], axis=2) / np.sum(vectors * vectors, axis=1)
    closest = starts[None, :, :] + np.clip(fraction, 0, 1)[..., None] * vectors[None, :, :]
    delta = positions[:, None, :] - closest
    distance = np.linalg.norm(delta, axis=2)
    normal = delta / np.maximum(distance[..., None], 1e-12)
    perpendicular = np.stack((-vectors[:, 1], vectors[:, 0]), axis=1)
    perpendicular /= np.linalg.norm(perpendicular, axis=1)[:, None]
    normal = np.where((distance < 1e-12)[..., None], perpendicular[None, :, :], normal)
    return distance, normal, closest


def desired_directions(positions, radii, room: Room):
    r"""Return unit target directions (N,2) with smooth pillar detours.

    The nearest radius-cleared point on the aperture attracts pedestrians.
    Targets inside the room lie on the exit plane, so approaches outside the
    opening do not cut through a jamb. Once at the plane, the target extends
    downstream. This is geometric steering, not congestion-aware routing.
    An obstacle adds a
    transverse waypoint displacement weighted by a Gaussian of signed
    clearance and a smooth upstream gate. The sign selects the nearer side;
    tanh makes the side switch continuous. This behavioral extension is
    distinct from the original HFV force law and is tested as an assumption.
    In LaTeX $e_i^0=(q_i-x_i)/\|q_i-x_i\|$; the final normalization is
    dimensionless and desired speed supplies m/s in the driving force.
    """
    target = np.tile([room.width + 1.0, room.height / 2], (len(positions), 1))
    low, high = room.exit_limits
    margin = np.minimum(radii + 0.05, room.exit_width / 2)
    target[:, 1] = np.clip(positions[:, 1], low + margin, high - margin)
    target[:, 0] = np.where(positions[:, 0] < room.width - 0.05, room.width, room.width + 1.0)
    for pillar in room.pillars:
        center = np.array([pillar.x, pillar.y])
        displacement = target - positions
        length = np.linalg.norm(displacement, axis=1)
        forward = displacement / np.maximum(length[:, None], 1e-12)
        transverse = np.stack((-forward[:, 1], forward[:, 0]), axis=1)
        relative = center - positions
        ahead = np.sum(relative * forward, axis=1)
        side = np.sum(relative * transverse, axis=1)
        clearance = pillar.radius + radii + 0.18
        # Gaussian blending avoids discontinuous heading jumps at a hard cone.
        weight = np.exp(-(side / clearance) ** 4) * (0.5 + 0.5 * np.tanh(ahead / 0.25))
        weight *= np.exp(-np.maximum(ahead - 2.0, 0.0) / 2.0)
        turn = -np.tanh(side / 0.12)
        # Exact centerline symmetry has a deterministic, very small bias.
        turn = np.where(np.abs(side) < 1e-10, 1.0, turn)
        target += transverse * (weight * turn * 2.5 * clearance)[:, None]
    delta = target - positions
    return delta / np.maximum(np.linalg.norm(delta, axis=1)[:, None], 1e-12)
