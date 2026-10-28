# Third-party data and software

Project code and documentation are MIT licensed; see [LICENSE](LICENSE).
Python dependencies retain their own licenses.

## HERMES bottleneck archive

`data/experimental/hermes/metadata.json` and `trajectories.zip` are third-party
experimental data, not MIT-licensed project code. Source: Forschungszentrum
Jülich Pedestrian Dynamics Data Archive, HERMES bottleneck experiment (2009),
Seyfried, Boltes, Holl, Rupprecht and Winkens / Forschungszentrum Jülich and
University of Wuppertal. Dataset license: CC BY 4.0.

- Dataset DOI: https://doi.org/10.34735/ped.2009.6
- Attribution, original URLs and format: [dataset README](data/experimental/hermes/README.md).
- Raw files are retained unchanged. Analysis converts centimeters to meters in memory.
- Derived comparison: [empirical findings](docs/EMPIRICAL_FINDINGS.md).

Redistribution and reuse of these data require preserving the dataset attribution
and complying with its license. The repository adds no validation claim to them.
