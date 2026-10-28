# Learning crowd physics by reading the code

This tutorial follows a physical quantity from an equation to a NumPy tensor and then to an observable. The implementation is an educational research model based on Helbing, Farkas and Vicsek (2000), with explicit local obstacle steering, finite-duration observation, and a separate architectural search. A two-dimensional disk model can investigate mechanisms; it cannot by itself predict real injuries or validate an emergency exit.

## 1. State, dimensions, and Newton's equation

Pedestrian i has position x_i=(x_i,y_i) in meters, velocity v_i in m/s, radius r_i in meters, and mass m_i in kilograms. Newton's equation is

$$m_i\frac{d\mathbf v_i}{dt}=\mathbf f_i^0+\sum_{j\ne i}\mathbf f_{ij}+\sum_W\mathbf f_{iW},\qquad \frac{d\mathbf x_i}{dt}=\mathbf v_i.$$

The repository assumes a common mass of 80 kg, while radii are sampled uniformly from 0.28 to 0.32 m. A shared mass is an explicit specialization of the heterogeneous equation. `Simulation.positions` and `.velocities` have shape `(N,2)`; `.radii` has shape `(N,)`. Row i describes one body. `ForceResult.total` has shape `(N,2)` and units Newtons. Dividing by mass produces acceleration.

Initial positions come from a separated jittered lattice rather than an already compressed packing. `initial_state` uses a local seeded generator, so it does not alter global NumPy random state. Baseline and obstacle designs use the same people, radii, and positions for each seed. This paired design reduces noise from unrelated initial states.

The evolving arrays contain only active bodies. Stable integer IDs distinguish pedestrian identity from the current row index after exits. No wall or pillar is represented as a massive moving pedestrian: boundaries are stationary force sources with their own exact geometry.

## 2. Desired motion and relaxation

The driving force is

$$\mathbf f_i^0=\frac{m_i}{\tau}\left(v_i^0\mathbf e_i^0-\mathbf v_i\right).$$

The desired speed v_i^0 is in m/s. The target direction e_i^0 is a dimensionless unit vector. The relaxation time tau=0.5 s controls how quickly the person approaches that velocity. Without other forces and with constant direction, the exact solution is

$$\mathbf v(t)=v^0\mathbf e^0+(\mathbf v(0)-v^0\mathbf e^0)e^{-t/\tau}.$$

After one relaxation time, approximately 63% of an initial velocity difference has disappeared. Desired speed is not an instantaneous imposed speed. At high density, contact forces may prevent it from being reached.

The implementation in `desired_force` is directly readable:

```python
physics.mass * (desired_speed * directions - velocities) / physics.tau
```

`directions` and `velocities` are both `(N,2)`; the scalar mass, desired speed, and relaxation time broadcast across all rows. Units are kg × (m/s) / s = N. The isolated relaxation tests compare numerical velocities with the exact exponential and check that halving dt reduces the error.

### Local steering around a pillar

The basic target is a point 1 m beyond the center of the exit. `desired_directions` constructs a forward unit vector toward this target and a perpendicular transverse vector. It projects the pillar's relative center into these two axes to determine whether the circle is ahead and which side is closer.

A smooth weight combines a Gaussian-like lateral gate, a hyperbolic-tangent upstream gate, and decay for distant obstacles. A transverse target displacement encourages going around the circle before compression is necessary. Finally, target-minus-position is normalized row by row. There is a tiny deterministic side choice on the exact centerline, where geometric symmetry supplies no preferred route.

This is a behavioral extension to HFV, not part of the original pair force law. It does not solve a shortest-path problem and does not route through mazes. A future study should compare several heading models because pillar benefit can depend on how people choose routes.

## 3. Pair geometry and broadcasting

For two people define

$$d_{ij}=\|\mathbf x_i-\mathbf x_j\|,\quad r_{ij}=r_i+r_j,\quad
\mathbf n_{ij}=\frac{\mathbf x_i-\mathbf x_j}{d_{ij}},\quad
\mathbf t_{ij}=(-n_{ij,y},n_{ij,x}).$$

The normal points from j toward i, so a positive normal force pushes i away from j. The tangent is a 90-degree rotation. In `pair_forces`:

```python
delta = positions[:, None, :] - positions[None, :, :]
distance = np.linalg.norm(delta, axis=2)
normal = delta / np.maximum(distance[..., None], 1e-12)
tangent = np.stack((-normal[..., 1], normal[..., 0]), axis=2)
```

The first view has shape `(N,1,2)`, the second `(1,N,2)`. Broadcasting creates `(N,N,2)` displacements without explicit nested Python loops. The first index is the receiving pedestrian, the second the source, and the last the Cartesian component. The norm collapses only the Cartesian axis, leaving `(N,N)` distances. Adding `[...,None]` restores the component axis for division.

The diagonal represents self-interaction and must be zeroed. Distinct coincident centers are a geometric singularity. The implementation chooses opposite horizontal normals for opposite index orders, preserving pair antisymmetry. This fallback prevents NaNs but does not make coincident initialization physically sensible; initialization avoids it.

## 4. Three interaction mechanisms

### Anticipatory social repulsion

$$\mathbf f_{ij}^{social}=A\exp\left(\frac{r_{ij}-d_{ij}}{B}\right)\mathbf n_{ij}.$$

A=2000 N is the force scale and B=0.08 m is the decay length. Because the exponent divides a length by a length, it is dimensionless. At exact disk contact the social magnitude is A. At one B of positive clearance it is A/e. This term acts before physical overlap and represents an effective avoidance behavior rather than tissue mechanics.

### Elastic body compression

Let g(z)=max(z,0). Then

$$\mathbf f_{ij}^{body}=k g(r_{ij}-d_{ij})\mathbf n_{ij},\quad k=120000\;\mathrm{N/m}.$$

The overlap h_ij=g(r_ij-d_ij) is a nonnegative `(N,N)` matrix in meters. Multiplying it by k gives Newtons. A 0.01 m overlap gives 1200 N of elastic normal load. Disk overlap is a soft-body approximation, not a literal reconstruction of anatomy.

The total normal magnitude is social plus elastic load. The matrix is retained separately from the vector resultant so that opposite pushes do not disappear from pressure metrics.

### Tangential sliding friction

$$\Delta v_{ji}^{t}=(\mathbf v_j-\mathbf v_i)\cdot\mathbf t_{ij},\qquad
\mathbf f_{ij}^{friction}=\kappa h_{ij}\Delta v_{ji}^{t}\mathbf t_{ij}.$$

Here kappa=240000 kg/(m s), equivalently N s/m². Multiplication by overlap (m) and relative tangential speed (m/s) gives Newtons. This is a viscous sliding law, not a Coulomb friction cone with static/dynamic coefficients. It is zero without overlap.

```python
relative_velocity = velocities[None, :, :] - velocities[:, None, :]
sliding = np.sum(relative_velocity * tangent, axis=2)
friction = physics.kappa * overlap * sliding
```

The velocity order matters. If i moves upward faster than j, friction on i opposes that motion. For a pair, the summed frictional power is

$$\mathbf f_{ij}^{friction}\cdot\mathbf v_i+
\mathbf f_{ji}^{friction}\cdot\mathbf v_j
=-\kappa h_{ij}(\Delta v_{ji}^{t})^2\leq0.$$

The tests independently check this sign and Newton's third law. Total crowd momentum is not conserved because driving and walls are external forces. Mechanical energy is not conserved because driving injects energy and friction dissipates it.

## 5. Exact walls and circles

A wall segment has start a, end b, and direction u=b-a. For a body center p,

$$s=\operatorname{clip}\left(\frac{(p-a)\cdot u}{u\cdot u},0,1\right),\quad q=a+su,\quad d=\|p-q\|.$$

Without clipping, q would lie on an infinite line and incorrectly extend a wall across an exit. `segment_distances` broadcasts bodies against segments, yielding distances `(N,W)` and normals `(N,W,2)`. Door jambs are the endpoints of the two right-wall segments; no segment bridges the opening.

For a pillar centered at c with radius R, surface distance is d=|p-c|-R. It can be negative if a center lies inside the circle. The normal points radially outward. The same exponential and overlap law acts with r_i-d, and boundary sliding uses the boundary velocity zero:

$$\mathbf f_{iW}=\left[Ae^{(r_i-d_{iW})/B}+kg(r_i-d_{iW})\right]\mathbf n_{iW}
-\kappa g(r_i-d_{iW})(\mathbf v_i\cdot\mathbf t_{iW})\mathbf t_{iW}.$$

An exact-on-wall normal is ambiguous; the kernel uses a deterministic segment perpendicular. A well-resolved trajectory should rarely encounter that singular state. The soft-force formulation does not include a separate hard collision solver.

## 6. Time integration and stiffness

Semi-implicit Euler updates velocity first:

$$\mathbf v^{n+1}=\mathbf v^n+\Delta t\,\mathbf F^n/m,\qquad
\mathbf x^{n+1}=\mathbf x^n+\Delta t\,\mathbf v^{n+1}.$$

It is first-order accurate. Updating position with the new velocity generally behaves better for elastic systems than forward Euler, but does not remove stiffness. The elastic timescale is sqrt(m/k), approximately 0.0258 s for the default constants. Configuration validation requires dt≤0.2 sqrt(m/k). The benchmark uses 0.0015 s, substantially below this bound.

Friction adds another scale: m/(kappa h), further shortened by simultaneous contacts. A sufficient practical timestep must resolve both elasticity and dissipative relaxation. There is no universal stability guarantee from the single-contact elastic bound. The code also caps body speed at 12 m/s and counts every capped update. This safeguard modifies dynamics whenever active; it is not a physical law.

Velocity Verlet uses

$$\mathbf x^{n+1}=\mathbf x^n+\Delta t\,\mathbf v^n+\tfrac12\Delta t^2\mathbf a^n,$$
$$\mathbf v^{n+1}=\mathbf v^n+\tfrac12\Delta t(\mathbf a^n+\mathbf a^{n+1}).$$

For position-dependent forces this is standard Verlet. HFV force depends on velocity, so the endpoint acceleration also depends on the unknown new velocity. The implementation makes three fixed-point corrector iterations. It is not claimed to be symplectic or an exact implicit solution for this dissipative problem. Constant-acceleration and isolated-relaxation tests establish useful analytic behavior; crowd timestep studies remain necessary.

The benchmark reruns baseline and selected pillar with dt/2 on the first evaluation seed. Contact systems can amplify small trajectory changes. Compare ensemble metrics, overlap, and clamp frequency rather than expecting pointwise identical paths. A single half-step comparison is a sensitivity check, not a convergence proof.

## 7. Measuring exits and censoring

A pedestrian counts as evacuated after the rear edge clears the outer wall plane: x_center=W+r_i. Across the crossing step, interpolation finds alpha=(W+r_i-x_old)/(x_new-x_old), and t_exit=t_old+alpha dt. The interpolated center y must be within the opening. The body is then removed so it cannot be counted twice.

T90 is the ceil(0.9 N)-th ordered event. Total evacuation time exists only when every body exits. If a finite horizon stops the run, unobserved times are JSON null. The restricted mean evacuation time averages min(T_i,t_end); unexited bodies contribute t_end. This is a valid finite-horizon outcome, not a claim that those bodies exited at the horizon.

Whole-run flow is evacuated count divided by observed duration. The live chart instead uses the count in the preceding two seconds divided by that window's observed duration. A temporary zero flow need not imply a self-locking arch.

## 8. Radial pressure and exposure

The requested radial pressure proxy is

$$P_i=\frac{\sum_{j\ne i}\|\mathbf f_{ij}^{normal}\|}{2\pi r_i}.$$

This has units N/m, not pascals. Equal and opposite pushes have zero resultant but positive crushing load. `radial_pressure` sums scalar magnitudes along the neighbor axis before dividing by a `(N,)` circumference vector. Summing force vectors and taking a norm would hide precisely the balanced compressive states of interest.

The primary metric includes social and elastic pair normal load but excludes tangential friction and boundaries, matching the requested pair-force expression. A separately named boundary-inclusive metric adds wall and pillar normal loads. Distinguishing the two matters because an obstacle can reduce person-person contact while increasing person-obstacle loading.

Mean pressure is weighted by active agent-time:

$$\bar P=\frac{\int\sum_{i\in active}P_i(t)\,dt}{\int N_{active}(t)\,dt}.$$

Every physics step contributes to this mean and the maximum. The 1,600 N/m indicator accumulates exposure in agent-seconds. It is a user-specified operational threshold; no mortality model or clinical calibration is supplied. A publication must avoid interpreting it as a validated prediction of traumatic asphyxia.

Spatial heatmaps use a different statistic: sampled observations within each spatial bin. Weighted histogram divided by count gives mean sampled pressure conditional on being in that bin. Empty cells are masked. They do not mean that an unvisited region has zero physical stress.

## 9. Contact graphs and clogging candidates

`detect_arch` constructs a boolean adjacency matrix from elastic compression ≥100 N. It restricts bodies to the doorway neighborhood, finds connected components, and tests whether one touches both jambs and has mean speed below 0.35 m/s. A depth-first traversal visits each reachable body.

An accepted graph is an arch candidate. Connectivity alone cannot prove static equilibrium, load-bearing capacity, or self-locking. In particular, the model has viscous tangential friction, so a true static friction analysis would require a different constitutive law and force-balance checks.

`ArchTracker` treats each sampled state as constant until the next sample and integrates that indicator. At a 0.15 s sample interval, short events can be missed and transition timing is approximate. This uncertainty is independent of the much smaller physics timestep. The force-chain figure displays all strong elastic contacts at a peak-pressure instant, including contacts that do not form a detected arch.

## 10. Why faster can become slower

Increasing v0 raises driving force when actual motion is obstructed. More pushing increases overlap, which strengthens compression and tangential damping. Near a narrow exit, dense contact networks can then prolong intermittent blocking. There is competition: greater desired speed helps free movement but may worsen congestion. Consequently, the evacuation-time curve can have a minimum at an intermediate speed.

The speed sweep uses exactly [1,2,3.5,5,7] m/s with fixed geometry, mechanics, and paired evaluation seeds. The code reports actual values. Faster-is-slower is supported only where increasing speed increases measured evacuation time; it need not hold for every pair of speeds. Rising pressure alone is not proof of slower evacuation. Few seeds and finite horizons limit the generality of a quantitative statement.

## 11. Differential evolution as an architectural experiment

The design vector z=(x,y,R) has three meter-valued coordinates. Differential evolution mutates population members using scaled differences, crosses components, and retains candidates with smaller objective. The objective is

$$J=\left\langle0.50\frac{P_{max}(z)}{P_{max}(0)}+0.25\frac{\bar P(z)}{\bar P(0)}
+0.25\frac{RMET(z)}{RMET(0)}+2\left(1-\frac{N_{exit}}N\right)\right\rangle_{train}.$$

Every ratio compares the same initial seed, making the loss dimensionless. Weights encode a research choice and are reported explicitly. An obstacle may shield a dense exit region, divide approach streams, or add harmful resistance. The algorithm measures those tradeoffs; it cannot guarantee a 25% reduction or improved flow.

The selected pillar must remain inside the room, avoid the common initial-state envelope, clear both jambs, and be asymmetric by at least 0.12 m. These constraints keep experiments comparable. Independent evaluation seeds test whether training improvements survive a small change of initial arrangement. They are not used to select the best candidate. Full candidate history is retained so the result is auditable.

## 12. Reading and extending the repository

Start with `config.py`, then `geometry.py`, `forces.py`, `integrator.py`, and `simulation.py`. Read `telemetry.py` before interpreting figures, and `pillar_evolver.py` before interpreting architectural claims. The unit tests supply independent analytic examples for the sign, shape, and unit reasoning above.

Useful research extensions include heterogeneous mass and desired speed, empirical trajectory calibration, multiple exits with navigation fields, contact-pressure validation, larger independent seed ensembles, and sensitivity to steering and friction. Each extension should preserve its exact configuration in artifacts and add a test based on a physical invariant or independent analytic result.

## Exact source-line index

The links below are generated from the current Python AST. Each points to the definition whose docstring explains the equation, units, and array shapes.

| Module | Function or method | Source line |
|---|---|---:|
| `src/config.py` | `room_from_dict` | [L134](src/config.py#L134) |
| `src/config.py` | `__post_init__` | [L32](src/config.py#L32) |
| `src/config.py` | `__post_init__` | [L54](src/config.py#L54) |
| `src/config.py` | `__post_init__` | [L74](src/config.py#L74) |
| `src/config.py` | `exit_limits` | [L91](src/config.py#L91) |
| `src/config.py` | `__post_init__` | [L113](src/config.py#L113) |
| `src/config.py` | `to_dict` | [L129](src/config.py#L129) |
| `src/physics/geometry.py` | `wall_segments` | [L11](src/physics/geometry.py#L11) |
| `src/physics/geometry.py` | `segment_distances` | [L24](src/physics/geometry.py#L24) |
| `src/physics/geometry.py` | `desired_directions` | [L45](src/physics/geometry.py#L45) |
| `src/physics/forces.py` | `desired_force` | [L27](src/physics/forces.py#L27) |
| `src/physics/forces.py` | `pair_forces` | [L37](src/physics/forces.py#L37) |
| `src/physics/forces.py` | `boundary_forces` | [L68](src/physics/forces.py#L68) |
| `src/physics/forces.py` | `total_forces` | [L94](src/physics/forces.py#L94) |
| `src/physics/integrator.py` | `clamp_velocity` | [L11](src/physics/integrator.py#L11) |
| `src/physics/integrator.py` | `semi_implicit_euler` | [L23](src/physics/integrator.py#L23) |
| `src/physics/integrator.py` | `velocity_verlet` | [L34](src/physics/integrator.py#L34) |
| `src/analytics/telemetry.py` | `radial_pressure` | [L14](src/analytics/telemetry.py#L14) |
| `src/analytics/telemetry.py` | `rolling_flow` | [L27](src/analytics/telemetry.py#L27) |
| `src/analytics/telemetry.py` | `observe` | [L60](src/analytics/telemetry.py#L60) |
| `src/analytics/telemetry.py` | `sample` | [L75](src/analytics/telemetry.py#L75) |
| `src/analytics/telemetry.py` | `summary` | [L86](src/analytics/telemetry.py#L86) |
| `src/analytics/arch_detector.py` | `detect_arch` | [L13](src/analytics/arch_detector.py#L13) |
| `src/analytics/arch_detector.py` | `update` | [L60](src/analytics/arch_detector.py#L60) |
| `src/simulation.py` | `initial_state` | [L21](src/simulation.py#L21) |
| `src/simulation.py` | `simulate` | [L180](src/simulation.py#L180) |
| `src/simulation.py` | `save` | [L61](src/simulation.py#L61) |
| `src/simulation.py` | `__init__` | [L85](src/simulation.py#L85) |
| `src/simulation.py` | `forces` | [L98](src/simulation.py#L98) |
| `src/simulation.py` | `frame` | [L103](src/simulation.py#L103) |
| `src/simulation.py` | `step` | [L108](src/simulation.py#L108) |
| `src/simulation.py` | `result` | [L171](src/simulation.py#L171) |
| `src/optimization/pillar_evolver.py` | `fitness` | [L18](src/optimization/pillar_evolver.py#L18) |
| `src/optimization/pillar_evolver.py` | `feasible_pillar` | [L32](src/optimization/pillar_evolver.py#L32) |
| `src/optimization/pillar_evolver.py` | `optimize_pillar` | [L51](src/optimization/pillar_evolver.py#L51) |
| `src/optimization/pillar_evolver.py` | `objective` | [L66](src/optimization/pillar_evolver.py#L66) |
