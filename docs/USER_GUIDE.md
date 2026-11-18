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

Cards summarise data sources, flows, interfaces, quality rules, 24-hour runs and open alerts for the current project, followed by recent runs and unhandled alerts.

## 3. Operations centre

Tabs: overview, tasks, alerts, health, API calls, timeline and audit.

- **Tasks**: retry a failed task or cancel a running one.
- **Health**: flow lag, empty rounds and cursor age, plus recent health events.
- **API calls**: calls, errors and average latency per interface and access key.
- **Timeline**: alerts and health events in time order.
- **Audit**: the same records as the Audit page.

## 4. Data sources

- **New data source**: name, type and connection string. Examples:
  - PostgreSQL: `postgresql+psycopg://user:pass@host:5432/db`
  - MySQL/MariaDB: `mysql://user:pass@host:3306/db`
  - SQLite: `sqlite:////absolute/path`
  - Oracle: `oracle://user:pass@host:1521/service`
  - SQL Server: `mssql://user:pass@host:1433/db`
  - ClickHouse: `clickhouse://user:pass@host:8123/db`
  - Trino: `trino://user@host:8080/catalog/schema`
  - Files: `/data/odf/files/sales.csv`
- **Test** checks connectivity.
- **Sync metadata** reads the schema into the catalog. Existing datasets are updated in place; tags and quality rules survive.
- **Tables** lists synced schemas, tables and column counts.
- **Edit** renames the source; leave the connection string blank to keep it.
- **Delete** removes the source; when datasets, tags or quality rules depend on it the console reports the counts and asks before cascading.
- **Lakehouse maintenance** (Trino sources): schema (blank uses the source default), table list (blank covers the whole schema), compaction, snapshot expiry and retention, then Run. The result lists each table.

## 5. Catalog

The tree groups source → schema → table. Selecting a table shows columns, tags and lineage/impact.

- **Add tag** saves a new tag; the close button on a tag removes it.
- **Table properties** (Trino tables) submits a Spark job that sets Iceberg properties such as `gc.enabled=true`; follow it under Engines.
- **Search** matches table and column names and links to the dataset.

## 6. SQL workbench

- **Single source**: pick a source, run a read-only statement with a row limit, export the result as CSV.
- **Cross-source**: run queries against several sources.
- Governed sources (with masking policies) disable the workbench for non-admins.

## 7. Files

Upload CSV, Excel, Parquet or JSON files, then download or delete them. Uploaded files can be used as file data sources.

## 8. Pipelines

Node palette: source, filter, select columns, rename, cast, join, aggregate, union, distinct, quality check, Spark job, Flink SQL and sink.

1. Click a node type to add it; click the node to configure the source, table, key, filters and options.
2. Drag from the source handle to the target handle (or click one handle and then the other) to connect nodes.
3. Toolbar: Save draft, Validate, Preview the selected node, Run, Backfill, Cursors, Pause/Resume, Publish and Versions (with rollback).
4. The list page can delete a pipeline together with its versions, runs and lineage.

## 9. Engines

- **Submit job**: Spark or Flink SQL.
  - Spark: name, image, main program (`local://` or `s3://`), arguments, executors and memory.
  - Flink SQL: a script that may contain several statements separated by semicolons, run synchronously or detached. Detached submissions return a job ID.
- **Run SQL** executes read-only statements through the Flink gateway.
- **Engine profile** shows the lakehouse mode, default image, gateway configuration and default Spark settings with secrets redacted.
- Row actions: Cancel a running job, trigger a Savepoint for Flink jobs (target directory optional), or open Details for spec, external ID, error and result.

## 10. Change data capture

- **New CDC source**: name, database host, port, database, user, password, schema, tables and topic prefix.
- **Pause/Resume** toggles the connector.
- **Refresh status** reads the connector state from Debezium.
- **Delete** removes the record and the connector.

## 11. Integration

The flow list shows schedule, version and status. Run executes a flow immediately; the detail drawer exposes overview, versions, run history and the job queue.

## 12. Data models

Datasets and metrics.

- Creating either opens the editor: choose source, table and columns, then add filters, sorting, grouping and a row limit; the preview panel shows the generated SQL and rows.
- Validate, Save and Publish; published datasets can be used by dashboards, apps and APIs.
- **Row policies** append filters per column, operator, value and role; admins are exempt.
- **Column masking** sets a classification (PII/confidential/sensitive), a mask type (redact, partial, hash, null) and exempt roles.
- **Versions** lists history and supports rollback; the list page can delete a dataset or metric.

## 13. Dashboards

Add metric cards, line/bar/pie charts, tables and text; drag to move and resize from the corner.

- Save, Validate, Publish and Run.
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
- The list page can delete an interface.

## 16. Access control

- **Catalog**: published interfaces of this and other projects; request access to another project's interface.
- **My requests** and **Pending approvals** track the workflow.
- **Grants** lists and revokes access.
- **Access keys** issues AK/SK for the current project (shown once) and can revoke them.

## 17. Webhooks

Create a subscription with name, callback URL, events (blank means all) and signing secret (blank generates one, shown once). Rows support Test, Delivery records and Delete.

## 18. Data quality

Create rules by dataset, kind (not null, unique, range, freshness, schema and more), column and configuration. Run a rule and inspect Results; deleting a rule deletes its results.

## 19. Alerts

Filter by status and severity. Acknowledge records that the alert was seen; Close removes it from the open list. Alerts come from engine failures, flow health and similar events.

## 20. Changes

Propose a change (run, pause, resume or roll back a flow; publish or revoke an interface), pick the target and add a note. Approvers can approve, execute, or approve and execute. Buttons are disabled once a change is applied.

## 21. AI tools

Lists the tools exposed by the MCP server with type (read-only or change), description and parameters.

## 22. Users and members

- **New user**: username, password (upper case, lower case, digit and symbol) and role.
- Change the role inline and toggle the account on or off.
- **Project members**: choose a project, add a user with a project role, or remove a member. Users must belong to a project before they can sign in.

## 23. Workspace settings

Brand name, theme colour, welcome title and text, hidden menus and menu permissions (non-admin only). Saving applies immediately.

## 24. Account security

Changing the password requires the current one; the new password follows the same complexity rules. Two-factor setup generates a TOTP secret to scan or enter manually, then enables with a six-digit code; disabling also needs a valid code.

## 25. Audit

Every recorded action with actor, action, target, time and details, with paging.

## 26. Troubleshooting

- **Connection fails**: check the connection string, network and credentials; Trino needs a reachable coordinator.
- **Run SQL reports an engine error**: check the Flink gateway and job manager, and restart Flink after rotating S3 credentials.
- **Maintenance returns zero tables**: check the schema field; blank uses the source default.
- **Deleting a data source is refused**: review the dependent datasets, rules and tags, then confirm the cascade.
- **A new user cannot sign in**: add the user to a project.
- **An interface cannot be called**: issue AK/SK under Access control and sign requests as shown in the interface docs.
