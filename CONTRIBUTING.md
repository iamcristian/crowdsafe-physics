# Contributing

Start with the [documentation index](docs/README.md) and
[model limitations](docs/MODEL_STATUS.md). For UI changes, run
`node --test tests/test_exit_editor.cjs` as well as the Python suite.
Run `python -m pip check` and build a wheel before packaging changes.

Use English for code, tests, issues, and documentation. Describe the physical question before changing a force law or metric. Include SI units and array shapes in public docstrings, and explain broadcasting beside nontrivial tensor operations.

Run `python -m pytest -q` before proposing a change. Numerical changes need an independent analytic or invariant-based test, and timestep/seed checks when they affect experimental conclusions. Record changed model assumptions explicitly; an attractive animation is not a physical validation.

Keep generated results reproducible: preserve configurations, seeds, software versions, and the complete search history. Use new evaluation seeds if you tune on previously reported evaluation results. Never replace an unobserved exit with an artificial event at the simulation horizon.

The MIT license applies to code and documentation. Contributions should have compatible provenance. The primary scientific reference is Helbing, Farkas and Vicsek, Nature 407, 487–490 (2000), doi:10.1038/35035023.
