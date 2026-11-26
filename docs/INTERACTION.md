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

## Application canvas

- Pages use a 12-column grid. Drag a component's title bar to move it and the
  lower-right corner to resize; overlapping components are pushed down.
- The property panel edits column, row, width and height numerically. **Tidy
  layout** reflows components recursively, including nested containers.
- The left panel is an outline: search filters by title, text, id or type,
  nested items are indented, and **Add to** chooses the page, a container, or a
  specific tab as the insertion target.
- Components include text, heading, divider, image, button, progress, metric,
  table, form, container, tabs and dialog. Containers and dialogs hold child
  components on their own 12-column grid; tabs hold one grid per tab.
- Bindings support dotted paths: `{{params.city}}`, form values such as
  `{{components.form1.values.city}}`, and table selections such as
  `{{components.t1.selectedRow.city}}`. The editor offers a searchable binding
  picker built from the current page.
- Buttons can run a short action sequence: navigate, open a URL, set a page
  parameter, refresh data, or show a message. Actions run in order and are
  validated against declared pages and parameters.
- **Visibility** rules hide a component when a page parameter does not satisfy
  `=`, `!=` or `in`; **visible roles** restrict it to viewer, editor, approver
  or admin.
- The inspector splits into **Content**, **Layout** and **Interaction** tabs, so
  data fields, grid settings and behavior do not compete for one column.
- A desktop/tablet switch previews the runtime layout. Below the tablet width,
  widgets stack in reading order while keeping their configured heights.
- A drag or resize is one undo step: history pauses during the gesture and
  commits when the pointer is released.
- The editor preview reacts to parameters, form input and table row selection;
  validation reports grid bounds, undefined bindings, visibility parameters,
  role lists, container depth, image URLs and button targets/actions.

## Catalog discovery and collaboration

- The catalog tree switches between source grouping and business-domain
  grouping. Glossary terms filter the tree to their domain.
- Search returns table, column and tag matches; a column match brings its table
  into the table list with the matched columns shown inline.
- The detail page keeps a summary header and a governance rail beside the
  tabs, so quality, domain, glossary and comment state stay visible.
- The field list filters by name, type or classification and opens a column
  drawer with classification, masking, exempt roles and column rules.
- Comments are a normal activity: posting, resolving and reopening update the
  summary count and the dataset history.
- The lineage explorer focuses on a ref, follows upstream / downstream / both
  up to the chosen depth, highlights the focused node and its edges, filters
  column lineage and exports JSON or CSV.

## Workbench, favorites and alert collaboration

- The SQL editor receives the selected datasource schema and completes table
  and column names. Results can be switched to a bar, line, area or pie chart
  with explicit dimension and measure columns.
- Every asset editor and the catalog table detail expose one star button
  backed by `favorite`; the command palette loads favorites first and removes
  duplicate routes from the normal result groups.
- Alerts use one timeline: raised, acknowledged, notes and closed. Assignment
  accepts only active project members, and the list filters by assignee.
- Column glossary links live in `column_term`; the column drawer adds and
  removes them, and catalog search folds term matches into table hits.

## Scheduling resilience

- A schedule view and a run-policy board live in the operations centre.
  Policies are stored on the asset and copied to each job when it is queued.
- Retry backoff is read from the job payload, so changing an asset policy
  affects future jobs without rewriting existing queued work.
- Job rows open a detail drawer with node runs; the comparison block selects
  the previous non-skipped job for the same asset and computes per-node
  duration and output deltas.

## Authoring primitives

- `studio/shared/chartOptions.js` builds every ECharts option used by the
  dashboard, workbench and previews. Palettes and number formats live there.
- `studio/shared/grid.js` owns cell sizing, item positioning and collision
  push-down for both the dashboard grid and the app canvas.
- `studio/shared/ParamBar.vue` renders page/app parameters consistently and
  supports reset, date and number inputs.
- Workbench query tabs keep SQL, datasource, limit, result and error per tab.
  The schema tree inserts a table or column at the editor cursor.
- Dashboard click behavior is stored per widget as `interaction`
  (`navigate`/`url`); the runtime opens the target or route. `emit` remains
  the filter-parameter behavior.

## Asset catalog and trust

- The catalog switches between **Tables** and **Asset catalog**; both are
  views over existing models, not separate catalogs.
- Asset search combines text relevance with certification, trust and 30-day
  usage. Type, certification and lifecycle filters narrow the list.
- The trust drawer explains the score factor by factor, shows usage counts
  and links to similar assets through lineage, domain and name overlap.
- Approvers certify, deprecate, archive and restore from the drawer; write
  controls are hidden for viewers and editors.

## Run operations

- Run policies add priority and a duration limit next to attempts and
  backoff. Priority controls queue order; duration breaches raise a warning
  alert and final failures raise a critical alert.
- **Run health** ranks assets by success rate, P95 duration and SLA breaches;
  **Run calendar** aggregates the same jobs into a 30-day grid.

## Embedding

- The share dialog has a **Public link / Embed** switch. Embed mode returns a
  chromeless page and a snippet for `odf-embed.js`.
- The SDK mounts an iframe, forwards optional parameters and resizes the
  frame from `postMessage` height events.
- Share and embed use the same revocable token; the button is editor-only.

## Page roles, styles and highlights

- Page-level roles sit beside the page title and are enforced twice: the
  runtime removes the tab, and the data endpoint rejects a hidden page.
- Styles are whitelisted tokens (background, text color, alignment, padding,
  radius, font size); the editor exposes them in Layout.
- Conditional highlight reuses the visibility comparator and applies one of
  four tones. It is evaluated with the same parameter state as bindings.

## Bulk import and project controls

- Glossary import accepts CSV or JSON and returns created, updated, skipped and
  per-row errors; unknown domains do not create implicit domains.
- Row policies are part of every read path: dataset preview, metric, dashboard,
  visual API and catalog sample. SQL-mode APIs are blocked when a datasource
  has row policies.
- Project quota carries `max_running_jobs` and an IANA timezone. The worker
  filters saturated projects in the claim query rather than re-queueing them.
- Promotion reuses bundle export/validate/import and stops before writing when
  types conflict or datasources are missing.
