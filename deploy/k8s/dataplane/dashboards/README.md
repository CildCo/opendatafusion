# Grafana dashboards

Provisioned dashboards for the Weft monitoring stack. Each JSON file in
this directory is embedded as a key of the `grafana-dashboards` ConfigMap in
`templates/72-grafana-dashboards.yaml`, and Grafana loads it from
`/var/lib/grafana/dashboards` through the provider file `dashboards.yaml`.

| File | Dashboard | UID |
| --- | --- | --- |
| `platform-health.json` | Control plane request rate, errors, latency, queue depth, alerts | `odf-platform-health` |
| `engine-jobs.json` | Engine job outcomes and pipeline job queue state | `odf-engine-jobs` |
| `lakehouse.json` | Lakehouse API health and query cache, with exporter placeholders | `odf-lakehouse` |

Every dashboard expects a Prometheus datasource named `Prometheus`, which
`70-monitoring.yaml` already provisions. The dashboards expose it as the
`${DS_PROMETHEUS}` datasource input. The same JSON works when imported through the
Grafana UI (pick the Prometheus datasource when prompted) and when provisioned
from the ConfigMap (the `DS_PROMETHEUS` template variable resolves to the
provisioned datasource by name).

## Metrics emitted today

These are the metrics the control plane produces in `impl/odf/api/metrics.py` and
the counters incremented from `odf/services`, `odf/webhooks`, `odf/modelstudio`
and `odf/api`:

| Metric | Type | Labels | Source |
| --- | --- | --- | --- |
| `odf_requests_total` | counter | `method`, `path`, `status` | HTTP middleware |
| `odf_request_duration_seconds` | histogram | `method`, `path`, `le` | HTTP middleware |
| `odf_request_seconds_sum` / `odf_request_seconds_count` | counter | none | HTTP middleware |
| `odf_queue_depth` | gauge | `status` | Pipeline `job` table grouped by status |
| `odf_webhook_pending` | gauge | none | Pending webhook deliveries |
| `odf_alerts_open` | gauge | none | Open alerts |
| `odf_db_pool_size`, `odf_db_pool_checked_in`, `odf_db_pool_checked_out`, `odf_db_pool_overflow` | gauge | none | Database pool |
| `odf_engine_jobs_total` | counter | `status` | Engine job outcomes (`running`, `succeeded`, `failed`, `cancelled`) |
| `odf_jobs_total` | counter | `status` | Pipeline job outcomes (`queued`, `success`, `failed`) |
| `odf_api_calls_total` | counter | `status` | OpenAPI gateway (`success`, `error`, `rate_limited`) |
| `odf_webhook_deliveries_total` | counter | `status` | Webhook deliveries (`success`, `failure`) |
| `odf_query_cache_hits` / `odf_query_cache_misses` | counter | `kind` | Query cache (`dashboard`, `preview`, `metric`) |
| `odf_build_info` | gauge | `version` | Build metadata |
| `odf_uptime_seconds` | gauge | none | Process uptime |
| `odf_otel_enabled` | gauge | none | OpenTelemetry flag |
| `odf_metrics_db_error` | gauge | none | Emitted only when the queue gauges fail |

The `path` label uses FastAPI route templates, for example
`/api/v1/lakehouse/tables/{table}/columns`. Select a family of routes with a
regular expression such as `path=~"/api/v1/lakehouse/.*"`.

## Metrics that need an exporter

The data plane components are not scraped today: no pod template in
`templates/` carries the `prometheus.io/scrape: "true"` annotation, and the
components do not export Prometheus text by default. The placeholder panels in
`lakehouse.json` and `engine-jobs.json` mark the gaps:

| Panels need | Metric family | Exporter to add |
| --- | --- | --- |
| Trino query rate, duration, failures | `trino_query_*` | Trino JMX/Prometheus exporter plus scrape annotations on the Trino pods |
| Object storage capacity and errors | `seaweed_*` | SeaweedFS metrics endpoint plus scrape annotations on the SeaweedFS pods |
| Kafka consumer lag | `kafka_consumergroup_lag` | Kafka lag exporter |
| Flink job state and throughput | `flink_jobmanager_*`, `flink_taskmanager_*` | Flink Prometheus metrics reporter |
| Debezium connector state | connector status metrics | Debezium/JMX exporter |
| Iceberg snapshot age and maintenance | maintenance job metric | Emit a gauge from the `expire_snapshots` job |
| Live engine job queue | `odf_engine_jobs{status}` gauge | Add a gauge in `impl/odf/api/metrics.py`; only outcome counters exist today |

After adding an exporter, add its pod annotation, confirm the series in
Prometheus, then replace the matching text panel with a query. Update this table
and the dashboard README notes in the same change.

## Adding a dashboard

1. Create the JSON in this directory. Give it a stable `uid`, keep a small panel
   count, and use `{"type": "prometheus", "uid": "${DS_PROMETHEUS}"}` as every
   panel datasource. Include both the `__inputs` entry and the `DS_PROMETHEUS`
   datasource template variable so the file works for UI import and provisioning.
2. Add the same JSON as a key under `data:` in
   `templates/72-grafana-dashboards.yaml`, indented by four spaces under a
   `name.json: |` block. The template embeds the JSON because `install.sh`
   renders templates with `envsubst` and has no file-inclusion step, so the file
   in this directory and the key in the ConfigMap must be kept identical.
3. Validate the JSON:

   ```sh
   python -c "import json,glob;[json.load(open(f,encoding='utf-8')) for f in glob.glob('deploy/k8s/dataplane/dashboards/*.json')]"
   ```

4. Apply the ConfigMap with the installer, or render and apply the template
   directly. Grafana reloads provisioned dashboards every 30 seconds.

## Provisioning contract

`templates/72-grafana-dashboards.yaml` defines the ConfigMap only. The existing
Grafana Deployment in `templates/70-monitoring.yaml` must mount it in two
places: the provider file under `/etc/grafana/provisioning/dashboards` and the
JSON files under `/var/lib/grafana/dashboards` (the path named in
`dashboards.yaml`). The exact mount lines are recorded in the delivery report
for this change; without them the dashboards appear in the ConfigMap but are not
loaded.

The `DS_PROMETHEUS` placeholder is intentionally left in the rendered manifest.
`install.sh` only substitutes variables declared in `values.env`, so the
placeholder survives unless it is added to that file. Do not add it.

## Rules

- No hostnames, IPs or credentials in these files.
- Quote every PromQL expression in JSON and use `$__rate_interval` for rates.
- Keep panel titles descriptive and prefix unfinished panels with `PLACEHOLDER:`.
