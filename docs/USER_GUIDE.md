# Console User Guide

This guide walks through every console page and action in order. The console ships in Simplified Chinese; API and MCP details are covered in the README and the topic guides.

## 1. Sign in and workspace

1. Open the console (default `http://<host>:18080/ui/`).
2. Enter the username, password and project ID (default `1`). Accounts with two-factor enabled also ask for the six-digit code.
3. The header shows the current project; switching it scopes every page to that project.
4. The account menu offers Account security, Workspace settings and Sign out.

Roles: viewers read, editors create and change assets, approvers approve changes, and admins also manage users, membership and keys.

The console runs in Simplified Chinese and English. Switch from the login page, the header button, or Workspace settings → Interface language; the choice is remembered in the browser and Element Plus follows it.

## 2. Overview

Cards summarise data sources, flows, interfaces, quality rules, 24-hour runs and open alerts for the current project, followed by recent runs and unhandled alerts. The getting-started checklist tracks a source, pipeline, logical dataset, dashboard and API; **Create sample data** builds the whole path in one click. The bell in the header opens notifications for publishes, failures, alerts and approval requests.

## 3. Operations centre

Tabs: overview, tasks, alerts, API calls, query performance, dead letters,
timeline and audit.

- **Tasks**: retry a failed task or cancel a running one.
- **API calls**: calls, errors and average latency per interface and access key.
- Rows in tasks and recent failures link to the related object; the alerts tab links to the alert page.
- **Timeline**: alerts in time order.
- **Dependency skips**: runs skipped in the last 24 hours because an upstream dependency had not succeeded are listed in the Tasks tab. `scripts/check_dependency_health.py` reports the same state and exits non-zero when any exist.
- **Query performance**: total, failures, P50/P95, breakdowns, slowest
  statements and normalized templates.
- **Dead letters**: final failed jobs, filtered by type and replayed in bulk.
- **Audit**: the same records as the Audit page.

## 4. Data sources

- **New data source**: types are grouped into databases, analytics engines, files and APIs/search. Choosing a type renders its fields (host, port, database, account and so on); connection strings are no longer typed by hand. Passwords are stored without being shown, and leaving the field blank on edit keeps the stored value. The type cannot change after creation.
- **Capabilities**: databases and analytics engines can be tested, synchronised, queried and used as pipeline sources; PostgreSQL, MySQL/MariaDB, SQLite, TiDB and OceanBase can also be pipeline sinks. Database types cover PostgreSQL, MySQL/MariaDB, SQLite, Oracle, SQL Server, the MySQL-protocol TiDB, Apache Doris, StarRocks and OceanBase, the PostgreSQL-protocol openGauss, KingbaseES and GaussDB, and DM (达梦); analytics engines cover ClickHouse, Trino, DuckDB (a local database file) and Hive / Spark Thrift (the HiveServer2 protocol). MongoDB supports connection testing and collection field metadata (set authSource when authenticating against the admin database), but not SQL queries. S3 / MinIO supports a single object (CSV/TSV/Parquet/JSON/Excel) with testing, metadata, query and pipeline-source use; queries download the object to a temporary file, so it suits small and medium objects. Local files cover the same formats. HTTP API and Kafka work as pipeline sources/sinks only (Kafka nodes take a topic directly). Elasticsearch works as a pipeline source/sink and synchronises index metadata, but does not support SQL queries or SQL APIs.
- **Test connection** is available while creating or editing, and the list action reports a concrete failure reason such as an unreachable host or a blocked address.
- **Test** checks connectivity.
- **Health** shows recent connectivity and metadata-sync attempts with status, duration and the failure reason.
- **Auto sync**: set an interval in minutes on the source; the scheduler refreshes metadata and records the outcome. Zero disables it.
- **Quick sync** creates a pipeline from a source table to a target table with a ready-to-run source and sink.
- **Airbyte connector**: when enabled by a platform administrator, choose this type, enter an allowlisted image or local command, the runtime and the connector configuration as JSON, then Test and Sync metadata. Each discovered stream becomes an `airbyte` catalog table and can be used as a pipeline source. See [Airbyte connectors](AIRBYTE.md).
- **SSH jump host**: SQL database types accept optional SSH host, port, user and password fields; all test, sync and query traffic then goes through that host.
- **Sync metadata** reads the schema into the catalog. Existing datasets are updated in place; tags and quality rules survive.
- **Tables** lists synced schemas, tables and column counts.
- **Limits** sets queries per minute (workbench, execution plans, model
  preview, federated queries) and concurrent model/lakehouse jobs; 0 means
  unlimited and the dialog shows current usage.
- **Edit** renames the source; leave the connection string blank to keep it.
- **Delete** removes the source; when datasets, tags or quality rules depend on it the console reports the counts and asks before cascading.
- **Lakehouse maintenance** (Trino sources): schema (blank uses the source default), table list (blank covers the whole schema), compaction, snapshot expiry and retention, then Run. The result lists each table.

## 5. Catalog

The tree groups source → schema → table. Selecting a table opens its dataset page.

- **Overview** shows the source, schema, table, column and rule counts, the last quality check, the last activity and the tags.
- **Data preview** reads the first 20, 50 or 100 rows from the source and applies column masking policies.
- **Columns** lists the field names and types; **Quality rules** lists the rules defined for the dataset and links to the quality page.
- **Dependencies and impact** shows downstream and column-level lineage; **Activity** records dataset-scoped actions.
- **Add tag** saves a new tag; the close button on a tag removes it.
- **Table properties** (Trino tables) submits a Spark job that sets Iceberg properties such as `gc.enabled=true`; follow it under Engines.
- **PII scan** inspects column names and sampled values, lists likely sensitive fields and can create masking policies for them in one step.
- **Search** matches table and column names and links to the dataset.
- **Domains and glossary** (sidebar): create business domains and glossary terms, assign terms to a domain, and use domains to group tables and logical assets.
- **Governance** on a table opens the domain assignment; the same drawer on a pipeline, dataset, metric, API, dashboard or app also records a data owner, SLA, contract fields, quality commitments, notes and usage analysis.

## 6. SQL workbench

- **Single source**: pick a source, run a read-only statement with a row limit, export the result as CSV.
- **Cross-source**: run queries against several sources.
- **Saved queries**: name and store the current statement, source or federation setup and row limit; open the saved list to restore or delete one.
- Governed sources (with masking policies) disable the workbench for non-admins.

## 7. Files

Upload CSV, Excel, Parquet or JSON files, then download or delete them. Uploaded files can be used as file data sources.

## 8. Pipelines

Node palette: source, filter, select columns, rename, cast, join, aggregate, union, distinct, quality check, Spark job, Flink SQL and sink.

1. Click a node type to add it; click the node to configure the source, table, key, filters and options.
2. Drag from the source handle to the target handle (or click one handle and then the other) to connect nodes.
3. Toolbar: Save draft, Validate, Preview the selected node, Run, Backfill, Cursors, Pause/Resume, Publish and Versions (with rollback).
4. **Runs** on the list page shows each node of every run with rows in/out, duration and error, so a stalled stage is easy to locate.
5. The list page can delete a pipeline together with its versions, runs and lineage.

## 9. Engines

- **Submit job**: Spark or Flink SQL.
  - Spark: name, image, main program (`local://` or `s3://`), arguments, executors and memory.
  - Flink SQL: a script that may contain several statements separated by semicolons, run synchronously or detached. Detached submissions return a job ID.
- **Run SQL** executes read-only statements through the Flink gateway.
- **Engine profile** shows the lakehouse mode, default image, gateway configuration and default Spark settings with secrets redacted.
- Row actions: Cancel a running job, trigger a Savepoint for Flink jobs (target directory optional), or open Details for spec, external ID, error and result.

## 10. Change data capture

- **New CDC source**: choose PostgreSQL, MySQL or Oracle, then fill database host, port, database, user, password, schema, tables and topic prefix. MySQL treats the schema field as the database list; Oracle uses the schema list for the owner.
- **Pause/Resume** toggles the connector.
- **Refresh status** reads the connector state from Debezium.
- **Details** opens the connector state, the task states with error traces, and the subscribed tables, which can be edited and saved.
- **Delete** removes the record and the connector.

## 11. Legacy module migration

Version 2.0 removes the legacy integration-flow and SQL-interface modules. Upgrading converts every remaining flow into a data pipeline asset and every remaining interface into a data API asset, preserving schedules, keys and published state. A notification links to each migrated asset. Old bookmarks redirect to **Pipelines** and **Data APIs**.

- Pipelines cover all copy, transformation, engine and scheduling work.
- APIs cover SQL and visual queries, typed parameters, versioning, approval, call statistics and AK/SK access.
- Scheduling dependencies accept pipelines only.

## 12. Data models

Datasets and metrics.

- Creating either opens the editor: choose source, table and columns, then add filters, sorting, grouping and a row limit; the preview panel shows the generated SQL and rows.
- **SQL dataset**: switch the editor to SQL, choose a datasource and write a read-only query (joins are allowed); saving derives the output columns, and metrics, dashboards and apps can use them. SQL datasets do not take parameters; use API Studio when parameters are required.
- Metrics aggregate with sum, count, average, minimum, maximum or distinct count over the dataset output.
- **Expression metrics** switch the definition to an aggregate expression such as `sum(amount) / nullif(count(*), 0)`; only columns from the dataset output and `sum/count/avg/min/max/coalesce/nullif/round` are accepted, and expression metrics are disabled on governed datasources.
- **Time grain**: choose a time column and a day, week, month, quarter or year grain; the metric groups by that bucket and the column behaves as an extra dimension in dashboards, pivots, tables and apps.
- **Comparison**: compare with the previous period or the same period last year. Preview and dashboards return `<measure>_previous`, `_delta` and `_delta_pct`; date filters on the time column move with the comparison window.
- Validate, Save and Publish; published datasets can be used by dashboards, apps and APIs.
- **Row policies** append filters per column, operator, value and role; admins are exempt.
- **Column masking** sets a classification (PII/confidential/sensitive), a mask type (redact, partial, hash, null) and exempt roles.
- **Versions** lists history and supports rollback; the list page can delete a dataset or metric.
- **Lineage** opens the upstream graph and column-level edges for the current dataset, metric, model, API or dashboard without leaving the editor.
- **Transform models** are the third tab. A model is SQL with a materialization (view, table or incremental), a warehouse layer, optional incremental key and tests. Reference another published model with `{{ ref('key') }}`; publishing records dependencies and lineage. Preview does not materialize; Run queues a job.
- Model tables are built in a shadow table, tested, then swapped; a failing test leaves the previous table in place. Incremental models can merge by key, Trino models can declare partition columns, and **Infer from SQL** fills column-level lineage sources. See [Transform models](MODELS.md).
- **Export catalog** downloads the current project as JSON; platform administrators can also push that snapshot to an external catalog on a schedule. See [Lineage and catalog export](LINEAGE.md).

## 13. Dashboards

Add metric cards, line/bar/area/pie charts, pivot tables, tables and text; drag to move and resize from the corner.

- Save, Validate, Publish and Run.
- In the run view, **Export CSV** writes the rows of every data-bearing widget to one CSV file.
- A **pivot** widget needs a metric with two dimensions; choose the row dimension, column dimension and value column, and the console renders the cross-tab.
- **Drill-through**: click a chart point, a metric card or a metric table row to open the underlying rows in a detail drawer. Metric and widget filters, row policies and column masking apply, and the drawer exports CSV.
- **Map**: upload a GeoJSON FeatureCollection in the widget settings, choose the metric dimension that contains region names and a value column; the widget matches dimension values to feature `properties.<name_property>`, shows a visual scale and supports drill-through.
- **Scheduled report**: set a six-field cron (second minute hour day month weekday) in the report drawer. The scheduler writes a CSV snapshot file, sends a notification and a `report.ready` webhook event, and keeps the run history; **Run now** generates one immediately.
- **Share** creates a read-only link with an expiry; links can be copied, embedded with the generated iframe snippet and revoked.
- **Versions** lists history; the list page deletes dashboards and their share links.

## 14. Apps

Build pages with text, metric cards, tables and forms.

- Page parameters are passed automatically when they match a dataset parameter.
- Save, Validate, Publish, Run and Share work as for dashboards.
- Form submissions write through the app's dataset permissions.

## 15. Publishing APIs

- Create an API asset in API Studio; choose visual or SQL mode and configure source, table or SQL, columns, filters, sorting, row limit and parameters.
- Validate, Preview and Test run the configuration against real data.
- **Docs** shows the path, AK/SK + projectKey authentication and curl/Python examples.
- Publish serves the API through `/openapi/{key}`; revoke takes it offline.
- The detail panel shows the endpoint address with a copy button, SQL, parameters and a call history with caller, time and returned rows.
- **GraphQL**: the API list opens a GraphQL viewer with the signed endpoint `/openapi/graphql`, the schema generated from this project's published APIs and a copyable query example. Send the same `projectKey`, `Date` and AK/SK signature headers as the REST gateway.
- The list page can delete an API.

## 16. Asset sharing

- **Asset catalog**: published APIs, datasets and models of this and other projects; request access to another project's asset.
- **Shared with me**: assets granted to the current project. Datasets open a masked published preview; models show layer, materialization, target and declared columns; APIs show their parameters.
- **My requests** and **Pending approvals** track the workflow.
- **Grants** lists and revokes access.
- **Access keys** issues AK/SK for the current project (shown once) and can revoke them.

Sharing is read-only: the receiving project can preview published datasets and read model metadata, but cannot edit the asset or use it to build new assets in its own project.

## 17. Webhooks

Create a subscription with name, callback URL, events (blank means all) and signing secret (blank generates one, shown once). Rows support Test, Delivery records and Delete.

## 18. Data quality

Create rules by dataset, kind (not null, unique, range, freshness, schema and more), column and configuration. Run a rule and inspect Results; deleting a rule deletes its results. Creating, running and deleting a rule is written to the audit log, searchable by `quality_rule`.

The Schedule dialog also stores an SLA percentage. The list marks rules whose recent pass rate is below SLA, and Results shows the last 30 days as a daily pass/fail table plus the current failure streak. A rule below SLA raises a deduplicated alert after a scheduled or manual run.

The list shows the last result and the pass rate over recent runs. Results summarises that trend and links to the dataset page. A rule can carry a cron schedule; the scheduler runs it automatically, and when alert-on-failure is enabled a failed run raises an alert.

- **Custom SQL** expects zero rows, at least one row, at most N rows or at least N rows; the statement is read-only-checked before execution.
- **Row-count anomaly** compares the current count with the mean of recent results and fails when the deviation exceeds the configured percentage; fewer than three samples only build the baseline.

## 19. Alerts

Filter by status and severity. Acknowledge records that the alert was seen; Close removes it from the open list. Alerts come from engine failures, job failures and similar events.

**Alert rules** below the list creates and deletes rules by name, kind and optional JSON configuration. **Subscriptions** opens webhook event subscriptions. Platform administrators can also set an **alert webhook** under Platform administration → Operations; raised alerts post a Slack-compatible JSON message to it.

## 20. Changes

Changes are proposed from the editors and API pages (publish, pause, resume, roll back, enable or revoke). Approvers can approve, execute, or approve and execute. Buttons are disabled once a change is applied.

## 21. AI tools

Lists the tools exposed by the MCP server with type (read-only or change), description and parameters.

## 22. Users and members

- **New user**: username, password (upper case, lower case, digit and symbol) and role.
- Change the role inline and toggle the account on or off. Your own role and
  active switch are locked, and the last active administrator cannot be
  demoted or disabled.
- If a workspace is locked out anyway, run
  `python -m odf.cli set-user-active --username <name> --active true` on the
  server to restore an account.
- **Project members**: platform administrators manage every project under Administration → Projects; a project administrator (project role `admin`) manages their own project from **Project members** at the bottom of the sidebar — look up a username, add it with a project role, or remove a member. Users must belong to a project before they can sign in.

## 23. Workspace settings

Brand name, theme colour, welcome title and text, hidden menus and menu permissions (non-admin only). Saving applies immediately.

## 24. Account security

Changing the password requires the current one; the new password follows the same complexity rules. Two-factor setup generates a TOTP secret to scan or enter manually, then enables with a six-digit code; disabling also needs a valid code.

## 25. Audit

Every recorded action with actor, action, target, time and details, with paging. Platform administrators can set a retention period and forward new audit records to a SIEM endpoint under Platform administration → Operations.

## 26. Troubleshooting

- **Connection fails**: check the connection string, network and credentials; Trino needs a reachable coordinator.
- **Run SQL reports an engine error**: check the Flink gateway and job manager, and restart Flink after rotating S3 credentials.
- **Maintenance returns zero tables**: check the schema field; blank uses the source default.
- **Deleting a data source is refused**: review the dependent datasets, rules and tags, then confirm the cascade.
- **A new user cannot sign in**: add the user to a project.
- **An API cannot be called**: issue AK/SK under Asset sharing and sign requests as shown in the API docs.

## 27. Platform administration

Platform administrators open **Administration** from the avatar menu or the
fixed shortcut at the bottom of the sidebar (or `#/admin`). It uses its own layout and only platform administrators can enter;
project members keep using the workspace.

- **Overview**: users, projects, assets, queue, open alerts and recent
  administrative actions.
- **Users and access**: create, reset, deactivate users; grant the platform
  administrator flag (the last one cannot be removed); review login state.
- **Projects and tenants**: create, rename, disable projects, set an
  environment label, set asset and job quotas, open a usage drawer and manage
  members with project roles. **Export bundle** downloads published assets,
  datasource names, domains and terms as JSON; **Import bundle** validates and
  imports them as drafts, reporting missing datasources and type conflicts.
- **Sign-in and identity**: session length, roles that must use two-factor
  authentication, OIDC discovery test and LDAP bind test.
- **Brand and content**: platform name, theme colour, welcome text, default
  language, announcement and feature flags (workbench, CDC, AI tools, apps,
  dashboards).
- **Data plane**: default Spark image, Flink SQL Gateway address, SQL write
  switch, CDC topic prefix and Kafka bootstrap defaults.
- **Airbyte connectors**: enable the connector type and set image/command
  allowlists and a timeout. See [Airbyte connectors](AIRBYTE.md).
- **Lineage and catalog sync**: OpenLineage endpoint, token and namespace;
  external catalog endpoint, token and sync interval. Send a test event or
  push the catalog immediately. See [Lineage and catalog export](LINEAGE.md).
- **Operations**: runtime and high-availability state, MCP activity, queue
  health, feature state, data retention with a manual prune action, system
  check, audit retention and SIEM forwarding, and backup export/restore. Restore replaces control-plane data from a downloaded
  archive and requires typing `RESTORE` to confirm.
- **Platform audit**: every administrative action, filterable and exportable.

Enable required two-factor authentication only after the selected roles have
enrolled; otherwise those users cannot sign in.

## 28. Lakehouse tables

Select a Trino datasource and schema to inspect Iceberg tables.

- **Health** shows file count and size, small files, snapshots, partitions and issues.
- **Snapshots** lists Iceberg snapshots with time and operation.
- **Time travel** queries a snapshot id or timestamp.
- **Maintain** runs file optimization and snapshot expiry with a retention and size threshold.
- **Schedule** stores a cron maintenance plan; the scheduler queues a job and failures raise an alert.
- Reading requires a signed-in project user; maintenance and schedules require an editor. See [Lakehouse table management](LAKEHOUSE.md).

## 29. Query history and performance

The workbench records every executed statement.

- **History** lists the latest runs with status, source, duration, rows and
  user. Select a run to restore its SQL. Federated runs cannot be restored.
- **Execution plan** runs `EXPLAIN` for the current single-source statement.
- **Operations centre → Query performance** summarises the last 7 or 30 days:
  total, failures, average, P50 and P95, counts by source, datasource and user,
  the ten slowest statements, and normalized statement templates.

See [Query workbench and performance](QUERY.md).

## 30. Data contracts

**Governance → Data contracts** lists datasets and transform models with
their contract.

- **Generate** reads the live table structure into the contract.
- **Check** compares the live structure with the contract and shows missing,
  unexpected or mistyped columns.
- **Enforce** makes a model run fail when its output drifts from the contract.
- **No extra columns** also rejects columns that the contract does not list.
- **Freshness** sets a time column and maximum age; checks report stale, empty
  or non-time values.
- **Check schedule** runs the check on a six-field cron through the normal job
  queue; **Check history** lists stored results.
- **Quality checks** add not-null, unique, accepted-values, null-rate and
  read-only SQL assertions to the contract.
- Publishing a model copies column classifications from its source table or
  parent models to the model's physical target; manual policies are never
  overwritten.

See [Data contracts](GOVERNANCE.md#data-contracts).

## 31. CDC pipelines

**Change data capture → Create pipeline** builds a pipeline from a Debezium
source.

- Choose a Kafka datasource, a target datasource and a primary key.
- One branch per subscribed table reads the Debezium topic and writes the
  target table.
- The source node unwraps `payload.after` and, with **Propagate deletes**,
  sends `payload.before` delete rows.
- Sinks run in `cdc` mode: delete rows remove by primary key, others upsert.
- Generated sinks evolve the target: new source columns are added with an
  inferred type before writing.
- Target tables must exist first; validation reports missing tables.

See [Change data capture](STREAMING.md).

## 32. Templates

Model and pipeline lists have a **Templates** button.

- Model templates: standard staging model, incremental merge model,
  deduplicated mart.
- Pipeline template: table sync by primary key.
- Choose a datasource and table; the draft opens in the normal editor.

See [Templates](TEMPLATES.md).

## 33. Operations and retention

- **Data retention** prunes terminal jobs, query history, notifications,
  closed alerts, webhook deliveries and contract checks on daily windows;
  administration shows counts, a manual prune action and an archive-and-prune
  action that writes gzip JSON before deleting.
- **System check** reports database reachability, migration revision and disk
  headroom; `python -m odf.cli doctor` prints the same report.
- `python -m odf.cli backup-check --path <file>` validates a backup file.
- `scripts/ha_smoke.py` checks every API replica's `/livez` and `/readyz`.

See [Operations](OPERATIONS.md).

## 34. Editing experience

- Pipeline, dashboard, app and model editors support undo (`Ctrl+Z`) and redo
  (`Ctrl+Shift+Z`).
- Pipeline nodes support Shift multi-select, copy/paste and auto layout; the
  canvas shows the latest run status, rows and duration per node.
- **Validate** lists node/field/message results instead of a single toast.
- Dashboards add components from a searchable chart gallery; dragging a widget
  pushes overlapping widgets down.
- Backfill has **Preview impact** before anything is queued.
- The operations centre adds a **Run matrix** by asset and day.


## 35. Low-code application canvas

The **Apps** editor uses a 12-column free-form canvas:

- Drag a component title bar to move it and the lower-right corner to resize;
  overlapping components are pushed down.
- The property panel accepts column, row, width and height directly, and
  **Tidy layout** reflows components in order, including nested content.
- Components include text, heading, divider, image, button, progress, metric,
  table, form, container, tabs and dialog. Containers and dialogs hold child
  components; tabs hold components per tab.
- The outline panel searches components and indents nested items. **Add to**
  selects the page, a container or a tab as the destination for new components.
- Text and headings interpolate page parameters and component values:
  `{{params.city}}`, `{{components.form1.values.city}}` and
  `{{components.orders.selectedRow.amount}}`.
- Buttons run an ordered action sequence: navigate to a page, open a URL, set a
  page parameter, refresh data, or show a message.
- **Visibility** uses `=`, `!=` or `in` page-parameter conditions; **visible
  roles** limits a component to selected roles.
- The inspector separates **Content**, **Layout** and **Interaction** settings.
- The **Desktop / Tablet** switch previews the responsive runtime; at tablet
  width components stack in their configured order.
- Parameter filters, form input and table selection update the preview;
  validation checks grid bounds, undefined bindings, roles, container depth,
  image URLs and button targets/actions.
- A drag or resize is one undo step.

The editing shortcuts apply to the transform-model editor as well; all editors
share one history stack.

## 36. Catalog collaboration

- The catalog tree groups by source or business domain; the glossary panel
  filters the tree to the selected term's domain.
- Search matches table names, schemas, column names and tags, and shows the
  matched columns and tags inline.
- The detail header summarises columns, rules, metrics, open comments and the
  latest quality status; the governance rail shows the domain, classified
  columns, glossary terms, comments and recent activity.
- **Fields** filters by name, type or classification; opening a column shows
  its classification, masking, exempt roles and quality rules.
- **Comments** supports posting, resolving and reopening threads; counts appear
  in the summary and the activity history.
- **Impact** uses the lineage explorer: choose upstream, downstream or both,
  set a depth, click a node to focus, filter column lineage and export JSON or
  CSV.

## 37. Workbench, favorites and alert collaboration

- **SQL workbench**: after choosing a datasource, the editor completes table
  and column names from synchronized metadata. Results switch between table,
  bar, line, area and pie views with dimension and measure pickers.
- **Favorites**: dataset, metric, model, pipeline, API, dashboard, app and
  catalog table editors have a star button. The command palette (`Ctrl+K`)
  shows Favorites before Recent.
- **Alert collaboration**: alerts can be assigned to active project members.
  A timeline records acknowledgement, notes and closure; the list filters by
  assignee and the drawer acknowledges or closes directly.
- **Glossary links**: catalog columns can be linked to glossary terms; the
  field list and column drawer show them, and catalog search matches term
  names to their tables and columns.

## 38. Scheduling resilience and run detail

- **Schedules** lists every scheduled asset with its cron, next run, enabled
  state, latest status and last run time.
- **Run policies** set maximum attempts (1–10) and retry backoff seconds
  (0–3600) per asset; queued jobs inherit the policy and retries use the
  configured interval.
- **Job detail** opens from any task row and shows status, attempts, worker,
  error and per-node input/output rows and duration.
- **Run comparison** diffs the open job against the previous run of the same
  asset, including duration and output-row deltas per node.

## 39. Authoring experience

- **SQL workbench** supports multiple query tabs, a schema tree that inserts
  tables/columns, SQL formatting and a result inspector.
- The inspector has table, chart, stats, request and JSON views; charts share
  the dashboard palette and number formats.
- **Dashboard widgets** add style controls: palette, legend, data labels,
  smooth lines, X/Y axis titles and number format.
- **Click behavior** can filter a parameter, navigate to an in-app path or open
  an external URL.
- Dashboard and app filters are written to the URL, so shared links keep the
  current selection; **Reset** restores defaults.
- Parameter bars support string, number, date and boolean inputs.

The shared chart, grid and parameter primitives serve dashboards, the
workbench and the app runtime.

## 40. Asset trust and lifecycle

- The catalog has two views: **Tables** for physical metadata and **Asset
  catalog** for logical assets (datasets, metrics, pipelines, APIs,
  dashboards, apps and models).
- Asset catalog search ranks exact names, certified assets, trust and usage;
  filters cover type, certification and lifecycle.
- **Trust** is a 0–100 score built from certification, owner, domain,
  contract, the latest contract check and 30-day usage (job runs, API calls
  and downstream references). The drawer shows every factor and similar
  assets.
- Approvers can certify an asset, revoke certification, deprecate, archive or
  restore it. Deprecation and archive require a note; both revoke
  certification. Archived assets are hidden from the default list and from
  recommendations.
- The **Recommended** strip surfaces published, active assets with the
  strongest trust and usage signals.

## 41. Run health, priority and duration SLA

- **Run policies** add a priority (0–100) and an optional maximum duration
  (0–86400 seconds, 0 disables it). New jobs inherit both.
- Queued jobs are claimed by priority first, then by scheduled time.
- A job that exceeds its duration limit raises a warning alert; a job that
  finally fails raises a critical alert, in addition to the job
  notification and `job.failed` webhook.
- **Run health** shows the last 7/30/90 days per asset: success rate, average
  and P95 duration, SLA breaches, priority, last status and a health score.
- **Run calendar** renders a 30-day grid with failed, running, queued and
  successful days.

## 42. Embedded dashboards and applications

- Shared links support two modes: **Public link** and **Embed**.
- Embed mode opens a chromeless page and reports its content height to the
  parent window. The share dialog generates a ready-to-use snippet with
  `odf-embed.js`.
- The SDK is served at `/ui/odf-embed.js` and exposes
  `ODFEmbed.mount({target, token, height, params})` plus
  `ODFEmbed.url(token, params)`.
- Embed tokens are the same bearer share tokens described in
  [EMBEDDING.md](EMBEDDING.md); revocation and expiry apply immediately.

## 43. Page roles, component styles and highlights

- Every application page can declare **visible roles**. The runtime hides
  other pages, and the data endpoint refuses to load a page the caller cannot
  see.
- Components support background, text color, alignment, padding, radius and
  font size. Values are validated when the app is saved.
- **Conditional highlight** applies an info, success, warning or danger tone
  when a page parameter matches a rule.
- The editor exposes page roles beside the page title, styles in the Layout
  tab and highlight rules in the Interaction tab.

## 44. Bulk glossary import and row policies

- The glossary tab imports CSV or JSON. Existing terms update by name; unknown
  domains are reported with the source row number.
- Row policies now apply to dataset previews, metrics, dashboards, visual API
  queries and catalog samples. A missing role is treated as viewer, not as an
  administrator.
- SQL-mode APIs are disabled when the datasource has row policies, because a
  free-form query cannot be rewritten safely.

## 45. Project concurrency, timezone and promotion

- Project quota adds **max running jobs**. The worker skips a saturated
  project while keeping global priority order.
- Project quota adds an IANA timezone such as `Asia/Shanghai`; asset, quality,
  contract, lakehouse and report schedules use it.
- Platform administrators can **promote** a project bundle into another
  project. Assets arrive as drafts; type conflicts and missing datasources
  block the promotion before anything is written.
