# Navigating the research studio

The application is organized by task. All controls and existing calculations
remain available; navigation reuses the same DOM nodes and WebSocket session.

| Workspace | Tools |
| --- | --- |
| Simulation | Live canvas, telemetry, Run / Population / Model / Inspect tabs |
| Scenario | Visual editor, object properties, advanced basic-room editor |
| Analysis | Replay, spatial layers, agent inspector, captured A/B comparison |
| Experiments | Compare & sweep, Sensitivity, Design search, Monte Carlo, Results & archive |
| Evidence | HERMES experimental report, imported-observation calibration |
| Building | Separate capacity network with floors, stairs and visibility |

Start, Pause and Reset remain in the top bar. The bottom status bar shows the
live run and background study progress even when another workspace is open.
Switching workspace does not pause, restart or reconfigure a simulation. Apply
buttons still explicitly reset their respective run settings or geometry.

The left menu can collapse to icons on desktop; its preference is saved locally.
On small screens it becomes a drawer that closes after choosing a workspace.
The Inspector button hides or restores the settings panel. At tablet/mobile
widths the inspector opens as a side drawer. Settings use tabs and expandable
Timing, Import/export and Numerical diagnostics groups.

Find a tool (Ctrl+K, or Command+K where supported by the host browser) searches
both workspaces and nested tools. Arrow keys navigate tab lists; Escape closes
native dialogs or mobile drawers. Direct links such as #scenario,
#experiments/results and #evidence/calibration work with browser history.

Methods, assumptions and verbose numerical output are disclosed on demand.
Completing a background study does not pull the user away from another task.
Open Experiments → Results & archive, or click the study status in the bottom
bar, to review it. Complete JSON output remains downloadable.

Navigation preserves draft geometry, input values, recorded frames, captured
runs and in-memory results. Reloading still creates a new WebSocket simulation;
export scenarios/recordings first. Archived study results remain on disk.

## Verification of this interface revision

- Live run continued across workspace navigation and paused with advancing time.
- Only the selected workspace was visible; DOM IDs remained unique.
- Edited parameter values, evidence results and selected tabs survived navigation.
- Replay capture and paired A/B study completed from the relocated controls.
- Results table remained visible and detailed numerical output was collapsible.
- Tool finder opened the nested calibration view.
- At 390 px width the navigation drawer closed after selection and the scenario
  workspace had no horizontal overflow; normal viewport was restored afterward.
- Building network completed with 40/40 occupants evacuated.

Design references:
- https://www.nngroup.com/articles/complex-application-design/
- https://carbondesignsystem.com/patterns/global-header/
