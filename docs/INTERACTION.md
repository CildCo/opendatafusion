# Editing experience

## Undo and redo

The pipeline, dashboard, application and transform-model editors share one
history stack:

- `Ctrl+Z` / `Cmd+Z` undoes, `Ctrl+Shift+Z` or `Ctrl+Y` redoes.
- History is snapshot based and debounced while typing; each editor keeps up
  to 80 steps.
- Loading an asset resets the stack, so undo never crosses saved versions.
- typing inside an input, textarea or the SQL editor keeps the editor's own
  undo behaviour; the asset-level shortcut ignores those targets.

## Pipeline canvas

- Palette entries can be clicked or dragged onto the canvas.
- Shift-click selects several nodes; `Ctrl+C` / `Ctrl+V` copies and pastes
  the selected nodes and the edges between them with an offset.
- **Auto layout** arranges nodes left-to-right by dependency level without
  changing edges.
- Nodes show the latest run status, output rows and duration from the most
  recent job; failed nodes use a red border.
- **Validate** opens a result panel listing node, field and message instead of
  a single toast.

## Dashboard canvas

- Components are added from a chart gallery with search and visual previews.
- Dragging or resizing pushes overlapping widgets down the grid, so cards do
  not stack on top of each other.
- Undo restores both the moved widget and the widgets that were pushed.

## Backfill preview

The backfill dialog has **Preview impact**. It validates the published
pipeline and shows the source nodes, their cursor columns and current cursor,
the batch size, the maximum batch count and warnings such as a large maximum
or an end cursor. Nothing is queued until **Start backfill** is clicked.

## Run matrix

The operations centre has a **Run matrix** tab: assets are rows, days are
columns, and each cell shows the number of runs with the worst status of that
day (failed, running, queued, success, skipped). The window can be 7, 14 or
30 days.
