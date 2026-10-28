r"""Vectorized SI force kernels, exact local geometry and explicit integration.

Newton's equation $m\dot{v}=F$ connects the kernels to the integrators; positions
and velocities use (N,2) arrays, and pedestrian interactions use (N,N,2).
"""
