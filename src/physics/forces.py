r"""Helbing-Farkas-Vicsek social, elastic and dissipative contact forces.

For d_ij=|x_i-x_j|, n_ij=(x_i-x_j)/d_ij, t_ij=(-n_y,n_x), and
h=max(r_i+r_j-d_ij,0), f_ij=[A exp((r_i+r_j-d_ij)/B)+k h] n_ij
+ kappa h ((v_j-v_i) dot t_ij) t_ij. In LaTeX:
$f_{ij}=[Ae^{(r_{ij}-d_{ij})/B}+kg(r_{ij}-d_{ij})]n_{ij}
+\kappa g(r_{ij}-d_{ij})\Delta v_{ji}^t t_{ij}$.
Normal magnitudes are retained separately: vector cancellation must never
hide compressive load when computing radial pressure in N/m.
"""
from dataclasses import dataclass
import numpy as np
from src.config import Physics, Room
from src.physics.geometry import desired_directions, segment_distances, wall_segments


@dataclass
class ForceResult:
    r"""SI force tensors and overlap diagnostics for one instantaneous state."""
    total: np.ndarray
    pair_normal: np.ndarray
    compression: np.ndarray
    boundary_normal: np.ndarray
    overlap: np.ndarray


def desired_force(velocities, directions, desired_speed, physics: Physics):
    r"""Compute m*(v0*e-v)/tau in Newtons for arrays of shape (N,2).

    In LaTeX $f_i^0=m(v_0e_i^0-v_i)/\tau$. A 0.5 s relaxation time
    expresses finite biomechanical acceleration. Scalars broadcast over both
    the pedestrian axis and the two Cartesian components.
    """
    speed = np.asarray(desired_speed)
    if speed.ndim:
        speed = speed[:, None]
    return physics.mass * (speed * directions - velocities) / physics.tau


def pair_forces(positions, velocities, radii, physics: Physics):
    r"""Return pair forces (N,N,2), normal load, compression and overlap (N,N).

    Axis 0 is the receiving body i, axis 1 the source j. The relative velocity
    v_j-v_i makes friction dissipative: summed mechanical friction power is
    nonpositive. Diagonals are explicitly zero, since a body cannot push itself.
    Coincident distinct centers get antisymmetric horizontal normals so even
    the singular fallback respects Newton's third law.
    """
    delta = positions[:, None, :] - positions[None, :, :]
    distance = np.linalg.norm(delta, axis=2)
    normal = delta / np.maximum(distance[..., None], 1e-12)
    n = len(positions)
    orientation = np.sign(np.arange(n)[:, None] - np.arange(n)[None, :])
    normal[..., 0] = np.where(distance < 1e-12, orientation, normal[..., 0])
    tangent = np.stack((-normal[..., 1], normal[..., 0]), axis=2)
    signed_overlap = radii[:, None] + radii[None, :] - distance
    overlap = np.maximum(signed_overlap, 0.0)
    np.fill_diagonal(overlap, 0.0)
    compression = physics.k * overlap
    # Clipping at 50 only guards pathological input overflow; normal runs are
    # far below it. Negative exponents underflow harmlessly at long distances.
    normal_load = physics.A * np.exp(np.clip(signed_overlap / physics.B, -745, 50)) + compression
    np.fill_diagonal(normal_load, 0.0)
    relative_velocity = velocities[None, :, :] - velocities[:, None, :]
    sliding = np.sum(relative_velocity * tangent, axis=2)
    friction = physics.kappa * overlap * sliding
    forces = normal_load[..., None] * normal + friction[..., None] * tangent
    return forces, normal_load, compression, overlap


def boundary_forces(positions, velocities, radii, room: Room, physics: Physics):
    r"""Compute exact wall/circle forces and individual normal loads in Newtons.

    For a circle, surface distance is |x-c|-R (negative inside). For a wall,
    it is the shortest segment distance. Stationary boundary friction is
    -kappa*g(r-d)*(v dot t)*t, or $-\kappa g(r-d)(v\cdot t)t$.
    Distances broadcast (N,W) against radii[:,None]; summing axis 1 yields
    the (N,2) resultant, while retaining loads enables boundary pressure.
    """
    distance, normal, _ = segment_distances(positions, wall_segments(room))
    for pillar in room.pillars:
        delta = positions - np.array([pillar.x, pillar.y])
        norm = np.linalg.norm(delta, axis=1)
        direction = delta / np.maximum(norm[:, None], 1e-12)
        direction[norm < 1e-12] = [1.0, 0.0]
        distance = np.concatenate((distance, (norm - pillar.radius)[:, None]), axis=1)
        normal = np.concatenate((normal, direction[:, None, :]), axis=1)
    tangent = np.stack((-normal[..., 1], normal[..., 0]), axis=2)
    signed_overlap = radii[:, None] - distance
    overlap = np.maximum(signed_overlap, 0.0)
    load = physics.A * np.exp(np.clip(signed_overlap / physics.B, -745, 50)) + physics.k * overlap
    sliding = np.sum(velocities[:, None, :] * tangent, axis=2)
    force = load[..., None] * normal - (physics.kappa * overlap * sliding)[..., None] * tangent
    return force.sum(axis=1), load


def total_forces(positions, velocities, radii, room: Room, physics: Physics, desired_speed, directions=None):
    r"""Assemble m*dv/dt = f_desired + sum_j f_ij + sum_W f_iW.

    Pair tensor reduction over axis 1 adds neighbors, not Cartesian axes.
    All outputs are Newtons except the diagnostic overlap matrix (meters).
    """
    pair, normal, compression, overlap = pair_forces(positions, velocities, radii, physics)
    boundary, boundary_load = boundary_forces(positions, velocities, radii, room, physics)
    drive = desired_force(velocities, desired_directions(positions, radii, room) if directions is None else directions, desired_speed, physics)
    return ForceResult(drive + pair.sum(axis=1) + boundary, normal, compression, boundary_load, overlap)
