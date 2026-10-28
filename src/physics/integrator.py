r"""Explicit Newtonian timestepping with observable speed safeguards.

Semi-implicit Euler uses v[n+1]=v[n]+dt*a[n], then x[n+1]=x[n]+dt*v[n+1].
Velocity Verlet uses x[n+1]=x[n]+dt*v[n]+dt²*a[n]/2 and the average of old
and new acceleration for velocity. Velocity-dependent HFV damping requires
iterated endpoint evaluation; the resulting method is not symplectic.
"""
import numpy as np


def clamp_velocity(velocity, max_speed):
    r"""Return direction-preserving capped velocities and a count of capped rows.

    Multiplication by min(1,vmax/|v|), or $\min(1,v_{max}/\|v\|)$,
    broadcasts a (N,1) dimensionless scale onto (N,2) velocities in m/s.
    This is a numerical modification; its frequency must be reported.
    """
    norm = np.linalg.norm(velocity, axis=1)
    factor = np.minimum(1.0, max_speed / np.maximum(norm, 1e-12))
    return velocity * factor[:, None], int(np.count_nonzero(norm > max_speed))


def semi_implicit_euler(positions, velocities, force, mass, dt, max_speed):
    r"""Advance one first-order step; return positions, velocities, clamp count.

    Newtons/kg gives m/s². Multiplication by dt gives m/s; the subsequent
    position increment is dt*v_new in meters. The new velocity improves
    elastic stability compared with forward Euler's old-velocity drift.
    """
    next_velocity, count = clamp_velocity(velocities + dt * force / mass, max_speed)
    return positions + dt * next_velocity, next_velocity, count


def velocity_verlet(positions, velocities, force_function, mass, dt, max_speed):
    r"""Advance generalized Verlet using three endpoint corrector iterations.

    force_function(x,v) returns (N,2) Newtons. For velocity-independent force
    this reduces exactly to standard velocity Verlet. With damping, fixed
    point iteration approximates v_new=v_old+dt*(a_old+a(x_new,v_new))/2.
    Three corrections avoid claiming an exact implicit solve; refinement is
    required for stiff contact. Return coordinates, velocity, clamp count.
    """
    acceleration = force_function(positions, velocities) / mass
    next_position = positions + dt * velocities + 0.5 * dt * dt * acceleration
    estimate = velocities + dt * acceleration
    for _ in range(3):
        endpoint = force_function(next_position, estimate) / mass
        estimate = velocities + 0.5 * dt * (acceleration + endpoint)
    next_velocity, count = clamp_velocity(estimate, max_speed)
    # If a safeguard activated, keep displacement consistent with bounded speed.
    if count:
        next_position = positions + 0.5 * dt * (velocities + next_velocity)
    return next_position, next_velocity, count
