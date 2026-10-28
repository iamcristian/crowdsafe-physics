# Visual scenarios and routing

Exit placement edits an existing opening when clicked within its span, instead
of adding a duplicate. Centers are clamped to keep the selected width inside the
chosen wall; a full-wall exit centers itself. Widths larger than the wall and
overlaps with other exits are rejected before mutating the draft. Select any
point on an exit segment to show its Wall, Center and Width properties. Dragging
and the Update exit button use the same rules. Exact JSON editing validates
extents without silently changing coordinates. Undo/redo remains available.

Use the Visual scenario editor to draft walls, circular pillars, boundary exits
and one rectangular spawn region. Walls and spawn regions take two clicks.
The size field specifies pillar radius or exit width in meters. Select objects
near their center; drag to translate them. Exit movement follows its wall.
Inspect selected / room and Update draft object provide exact numeric editing,
including room dimensions and exit side. Undo/redo applies to draft changes.
Apply scenario validates the draft and resets the current simulation.

Use Load current run to bring an imported or numeric scenario into the editor.
Scenario export includes custom exits and the spawn region. The legacy numeric
geometry editor creates a basic single-exit room; use the visual editor to retain
multiple exits. Empty exit lists in the Python API mean the legacy right exit;
the visual editor requires at least one explicit exit.

Global routing is enabled for explicit exits or interior walls. An eight-neighbor
Dijkstra grid at 0.25 m spacing uses a shared maximum-radius clearance. Paths
and steering shortcuts are checked against walls and pillars. Routes minimize
distance to any exit by default. A nonzero queue penalty in the Model tab adds
experimental congestion-based exit choice for multiple openings. Initial
agents without a reachable grid path are rejected. Narrow passages may be
rejected conservatively. Physical contact can still impede progress after
initialization; reachability is not a guarantee of evacuation.

The single-door arch detector is disabled for any explicit-exit geometry,
including one explicitly configured opening;
its zero values must not be interpreted as measured absence of arches. The
WebSocket exposes arch_supported=false in that case. Benchmarks archived before
these steering revisions must be rerun before making numerical comparisons.
