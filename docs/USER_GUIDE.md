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

Tabs: overview, tasks, alerts, health, API calls, timeline and audit.

- **Tasks**: retry a failed task or cancel a running one.
- **Health**: flow lag, empty rounds and cursor age, plus recent health events.
- **API calls**: calls, errors and average latency per interface and access key.
- Rows in tasks and recent failures link to the related object; the alerts tab links to the alert page.
- **Timeline**: alerts and health events in time order.
- **Dependency skips**: runs skipped in the last 24 hours because an upstream dependency had not succeeded are listed in the Tasks tab. `scripts/check_dependency_health.py` reports the same state and exits non-zero when any exist.
- **Audit**: the same records as the Audit page.

## 4. Data sources

- **New data source**: types are grouped into databases, analytics engines, files and APIs/search. Choosing a type renders its fields (host, port, database, account and so on); connection strings are no longer typed by hand. Passwords are stored without being shown, and leaving the field blank on edit keeps the stored value. The type cannot change after creation.
- **Capabilities**: databases and analytics engines can be tested, synchronised, queried and used as pipeline sources; PostgreSQL, MySQL/MariaDB, SQLite, TiDB and OceanBase can also be pipeline sinks. Database types cover PostgreSQL, MySQL/MariaDB, SQLite, Oracle, SQL Server, the MySQL-protocol TiDB, Apache Doris, StarRocks and OceanBase, the PostgreSQL-protocol openGauss, KingbaseES and GaussDB, and DM (达梦); analytics engines cover ClickHouse, Trino, DuckDB (a local database file) and Hive / Spark Thrift (the HiveServer2 protocol). MongoDB supports connection testing and collection field metadata (set authSource when authenticating against the admin database), but not SQL queries. S3 / MinIO supports a single object (CSV/TSV/Parquet/JSON/Excel) with testing, metadata, query and pipeline-source use; queries download the object to a temporary file, so it suits small and medium objects. Local files cover the same formats. HTTP API and Kafka work as pipeline sources/sinks only (Kafka nodes take a topic directly). Elasticsearch works as a pipeline source/sink and synchronises index metadata, but does not support SQL queries or SQL interfaces.
- **Test connection** is available while creating or editing, and the list action reports a concrete failure reason such as an unreachable host or a blocked address.
- **Test** checks connectivity.
- **Health** shows recent connectivity and metadata-sync attempts with status, duration and the failure reason.
- **Auto sync**: set an interval in minutes on the source; the scheduler refreshes metadata and records the outcome. Zero disables it.
- **Quick sync** creates a pipeline from a source table to a target table with a ready-to-run source and sink.
- **SSH jump host**: SQL database types accept optional SSH host, port, user and password fields; all test, sync and query traffic then goes through that host.
- **Sync metadata** reads the schema into the catalog. Existing datasets are updated in place; tags and quality rules survive.
- **Tables** lists synced schemas, tables and column counts.
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

## 11. Integration

The flow list shows schedule, version and status. Run executes a flow immediately; the detail drawer exposes overview, versions, run history, downstream impact and the job queue. Flows are the legacy copy engine; **Migrate to pipeline** creates an equivalent pipeline asset and disables the flow, after which the entry links to the pipeline.

- **Run history** shows start, finish and duration; open a run for throughput and the cursor, and use Retry to queue the flow again.
- **Versions** can be compared with the current configuration, listing changed keys.
- **Downstream impact** follows the lineage of the sink table.

Scheduling dependencies live on the **Scheduling dependencies** page: a downstream flow or pipeline queues only after its upstream succeeded within the last 24 hours, and blocked schedules are recorded as skipped runs.

## 12. Data models

Datasets and metrics.

- Creating either opens the editor: choose source, table and columns, then add filters, sorting, grouping and a row limit; the preview panel shows the generated SQL and rows.
- Validate, Save and Publish; published datasets can be used by dashboards, apps and APIs.
- **Row policies** append filters per column, operator, value and role; admins are exempt.
- **Column masking** sets a classification (PII/confidential/sensitive), a mask type (redact, partial, hash, null) and exempt roles.
- **Versions** lists history and supports rollback; the list page can delete a dataset or metric.
- **Lineage** opens the upstream graph and column-level edges for the current dataset, metric, API or dashboard without leaving the editor.

## 13. Dashboards

Add metric cards, line/bar/pie charts, tables and text; drag to move and resize from the corner.

- Save, Validate, Publish and Run.
- In the run view, **Export CSV** writes the rows of every data-bearing widget to one CSV file.
- **Share** creates a read-only link with an expiry; links can be copied and revoked.
- **Versions** lists history; the list page deletes dashboards and their share links.

## 14. Apps

Build pages with text, metric cards, tables and forms.

- Page parameters are passed automatically when they match a dataset parameter.
- Save, Validate, Publish, Run and Share work as for dashboards.
- Form submissions write through the app's dataset permissions.

## 15. Interfaces

- Create an interface, then choose visual or SQL mode and configure source, table, columns, filters, sorting, row limit and parameters.
- Validate, Preview and Test run the configuration against real data.
- **Docs** shows the path, AK/SK + projectKey authentication and curl/Python examples.
- Publish serves the interface through the open API; take it offline to revoke.
- Interfaces are the legacy SQL interface centre; **Migrate to API** creates an API Studio asset with the same SQL and key, and disables the old interface.
- The detail panel shows the endpoint address with a copy button, SQL, parameters and a call history with caller, time and returned rows.
- The list page can delete an interface.

## 16. Access control

- **Catalog**: published interfaces of this and other projects; request access to another project's interface.
- **My requests** and **Pending approvals** track the workflow.
- **Grants** lists and revokes access.
- **Access keys** issues AK/SK for the current project (shown once) and can revoke them.

## 17. Webhooks

Create a subscription with name, callback URL, events (blank means all) and signing secret (blank generates one, shown once). Rows support Test, Delivery records and Delete.

## 18. Data quality

Create rules by dataset, kind (not null, unique, range, freshness, schema and more), column and configuration. Run a rule and inspect Results; deleting a rule deletes its results. Creating, running and deleting a rule is written to the audit log, searchable by `quality_rule`.

The list shows the last result and the pass rate over recent runs. Results summarises that trend and links to the dataset page. A rule can carry a cron schedule; the scheduler runs it automatically, and when alert-on-failure is enabled a failed run raises an alert.

- **Custom SQL** expects zero rows, at least one row, at most N rows or at least N rows; the statement is read-only-checked before execution.
- **Row-count anomaly** compares the current count with the mean of recent results and fails when the deviation exceeds the configured percentage; fewer than three samples only build the baseline.

## 19. Alerts

Filter by status and severity. Acknowledge records that the alert was seen; Close removes it from the open list. Alerts come from engine failures, flow health and similar events.

**Alert rules** below the list creates and deletes rules by name, kind and optional JSON configuration. **Subscriptions** opens webhook event subscriptions. Platform administrators can also set an **alert webhook** under Platform administration → Operations; raised alerts post a Slack-compatible JSON message to it.

## 20. Changes

Propose a change (run, pause, resume or roll back a flow; publish or revoke an interface), pick the target and add a note. Approvers can approve, execute, or approve and execute. Buttons are disabled once a change is applied.

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
- **An interface cannot be called**: issue AK/SK under Access control and sign requests as shown in the interface docs.

## 27. Platform administration

Platform administrators open **Administration** from the avatar menu or the
fixed shortcut at the bottom of the sidebar (or `#/admin`). It uses its own layout and only platform administrators can enter;
project members keep using the workspace.

- **Overview**: users, projects, assets, queue, open alerts and recent
  administrative actions.
- **Users and access**: create, reset, deactivate users; grant the platform
  administrator flag (the last one cannot be removed); review login state.
- **Projects and tenants**: create, rename, disable projects, set asset and job
  quotas, open a usage drawer and manage members with project roles.
- **Sign-in and identity**: session length, roles that must use two-factor
  authentication, OIDC discovery test and LDAP bind test.
- **Brand and content**: platform name, theme colour, welcome text, default
  language, announcement and feature flags (workbench, CDC, AI tools, apps,
  dashboards).
- **Data plane**: default Spark image, Flink SQL Gateway address, SQL write
  switch, CDC topic prefix and Kafka bootstrap defaults.
- **Operations**: runtime and high-availability state, MCP activity, queue
  health, feature state, audit retention and SIEM forwarding, and backup
  export/restore. Restore replaces control-plane data from a downloaded
  archive and requires typing `RESTORE` to confirm.
- **Platform audit**: every administrative action, filterable and exportable.

Enable required two-factor authentication only after the selected roles have
enrolled; otherwise those users cannot sign in.
