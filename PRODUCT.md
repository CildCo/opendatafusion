# Product

## Platform

Web

## Users

Two layered audiences share one product:

- **Builders** — data engineers, integration engineers and platform operators.
  They work in long sessions: wiring datasources, pipelines, datasets, APIs,
  approvals and operations. They need density, fast scanning, keyboard-friendly
  controls and visible system state.
- **Consumers** — business analysts, operations staff and managers. They read
  metrics, dashboards, apps, catalog search results and lineage. They need
  calmer hierarchy, legible numbers and fewer technical interruptions.

The default entry is the builder workspace; consumer-facing run views and
shared dashboards read as the quieter layer of the same system.

## Product Purpose

OpenDataFusion is an API-first, open-source low-code data platform. It lets a
team connect sources, move and transform data, model datasets and metrics,
publish governed APIs, build dashboards and apps, and operate the estate from
one project-scoped console. External operators use the same capabilities
through MCP rather than a built-in chat interface.

Success means a team can take a raw source to a governed, documented API or
business view without leaving the platform, and can diagnose failures without
logging into the server.

## Positioning

The differentiator is the closed loop from **source → pipeline → model →
API/app → governance/operations**, with human approval gates and an
external-agent surface (MCP) as first-class capabilities. It is not a
single-purpose BI tool or a visual ETL toy: lineage, masking, audit, backfill,
quality and operational health are part of the same product model.

## Operating Context

- Chinese-first interface with English technical vocabulary where that is the
  accurate term (SQL, API, MCP, Git-like versioning).
- Desktop, high-density, mouse-and-keyboard work; users monitor jobs, review
  changes, inspect tables and publish assets.
- Project and tenant switching are routine; project identity and environment
  state stay visible.
- Roles are viewer, editor, approver and admin; approval and audit are normal
  parts of publishing, not edge cases.
- Governed datasources intentionally restrict raw SQL surfaces.
- The console covers authentication, overview, datasources, catalog, pipelines,
  connector flows, API Studio, dataset and metric Studio, dashboards, apps,
  workbench, grants, webhooks, files, quality, alerts, change requests, users,
  audit, workspace branding and account security.

## Capabilities and Constraints

- Vue 3 and Vite frontend served by FastAPI at `/ui/`; Element Plus is the
  component base and may be rethemed or progressively replaced without
  changing product behavior or API contracts.
- Asset lifecycle: draft → approval → publish/rollback; pipelines also support
  cursor inspection, reset and bounded backfill.
- Connector flows and pipelines are both supported execution models: flows for
  lightweight connector-to-connector work, pipelines for the visual DAG Studio.
- Column masking, row policies and governed-datasource restrictions are
  user-visible states.
- Real-time updates are polling-based; the interface does not imply live
  streaming that does not exist.
- The console remains usable on a 1366px-wide laptop and scales to wide
  monitors; dense tables are expected on builder screens.

## Brand Commitments

- Keep **OpenDataFusion** as the product name.
- Workspace branding (brand name, primary color, welcome copy and hidden menus)
  is tenant-configurable and leaves room for that without letting arbitrary
  colors destroy legibility.
- The visual language reads as an instrument for data work, not a generic
  admin template: distinctive, but credible for an enterprise buyer.

## Product Principles

1. **Show the system, not just the screen.** Surfaces reveal state, lineage,
   ownership and consequences before the user asks.
2. **Density with air.** Builders get compact controls, but grouping and
   typography keep long sessions calm.
3. **Governance is visible.** Masks, approvals, restrictions and audit are
   designed states, never hidden error paths.
4. **One instrument, two distances.** Builder and consumer views share a visual
   language while changing proximity to detail.
5. **Agents are operators, not decoration.** MCP and agent affordances are
   precise and operational, not chat-bubble ornament.

## Accessibility & Inclusion

The console targets WCAG 2.1 AA for contrast, focus visibility and keyboard
reachability on core workflows, and does not rely on color alone to convey
status.
