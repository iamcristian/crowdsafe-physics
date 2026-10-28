# HERMES bottleneck experiment (2009)

Source: Forschungszentrum Jülich Pedestrian Dynamics Data Archive.
DOI: https://doi.org/10.34735/ped.2009.6
License: CC BY 4.0, linked by the dataset landing page.
Attribution: Seyfried, Boltes, Holl, Rupprecht and Winkens / Forschungszentrum
Jülich and University of Wuppertal. See metadata.json for full archive metadata.
Retrieved 2026-10-27.

Raw download URLs:
- https://ped.fz-juelich.de/experiments/2009.05.12_Duesseldorf_Messe_Hermes/data/zip/2009bottleneck_metadata.json
- https://ped.fz-juelich.de/experiments/2009.05.12_Duesseldorf_Messe_Hermes/data/zip/2009bottleneck_trajectories_txt.zip

ZIP retained unchanged. Columns: ID, frame, x cm, y cm, z cm. Frame rate: 16 Hz.
Run python -m src.empirical to convert coordinates to SI in memory, summarize
first downstream crossings, and evaluate short-time forecasts. Raw trajectories
are camera-window observations, not complete initial populations or exit times.
Do not use their observed durations as RMET inputs to the evacuation UI.

## Recompute and view the comparison

From the repository root, after installing the project in its virtual environment:

```bash
python -m src.empirical
python -m src.cli serve --port 8001
```

On Windows without activation, invoke `.\.venv\Scripts\python.exe` instead of
`python`. The analysis expects `metadata.json` and `trajectories.zip` in this
directory. If absent, download the two source files above and save them under
these exact names. The ZIP is read directly; do not extract or modify it.

The analysis performs a speed/tau parameter search and held-out-width forecasts,
which can take time. It writes `outputs/empirical/hermes_report.json` and
`outputs/empirical/hermes_validation.png`. In the browser, open Evidence →
Experimental report → Load experimental comparison. Starting the server alone
does not regenerate this report. Export empirical report downloads the loaded JSON.

The current report uses centered initial velocities containing future frames
and overlapping tracked individuals. It is a retrospective local forecast
comparison; it does not validate full evacuation or contact loads. The evaluated
model performs worse than constant velocity on the held-out widths. See
`docs/EMPIRICAL_FINDINGS.md` from the repository root for results and limitations.
