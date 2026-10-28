# Published scientific outputs

Only these output directories are intended for source control:

- `data/`: historical synthetic benchmark configurations, per-run JSON/CSV,
  optimization history, summary and software environment.
- `figures/`: four figures generated from the historical synthetic archive.
- `empirical/`: HERMES comparison JSON and figure, used by the Evidence workspace.

Synthetic benchmark results predate the current steering and routing revisions.
See [PAPER.md](../PAPER.md) and [model status](../docs/MODEL_STATUS.md). Raw HERMES
trajectories have separate attribution and licensing in
[the dataset README](../data/experimental/hermes/README.md).

Other output folders contain local runs, interactive study archives, scenario
backups or QA files. They are ignored by Git and may be kept locally. Do not
upload the entire working folder through a file picker: use Git so exclusions
are respected. Use a new `--output` folder to preserve the published archive.
