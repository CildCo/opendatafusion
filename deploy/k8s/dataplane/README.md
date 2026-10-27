# Lakehouse data plane

The data plane gives the control plane a lakehouse to run on: object storage,
an Iceberg catalog, a query engine, CDC streaming and two compute engines.

```text
SeaweedFS S3  ──  Nessie catalog  ──  Iceberg tables
                        │
        ┌───────────────┼────────────────┐
      Trino           Spark            Flink
   (SQL, read)     (batch jobs)     (SQL, CDC)
                        ▲
   PostgreSQL ── Debezium ── Kafka ──┘
```

Everything runs on a single-node k3s cluster. Each component is a plain
Deployment with a Service; nothing here depends on a cloud provider.

## Prerequisites

- A Linux host with k3s 1.30 or newer, at least 8 vCPU, 24 GB RAM and 200 GB
  disk.
- `kubectl`, `helm` 3.12 or newer, and `envsubst` (`gettext-base`).
- Container registry access. Behind a restrictive network, configure k3s
  registry mirrors first; see "Registry mirrors" below.

## Install

```bash
cd deploy/k8s/dataplane
cp values.env.example values.env
vi values.env          # image tags, sizes, bucket name
./install.sh
```

The installer creates namespaces and Secrets, installs the Spark Operator with
Helm, applies every workload, waits for rollouts, and registers the Debezium
connector. Re-running it is safe.

At the end it prints the node IP and the SQL Gateway address.

## Connect the control plane

```bash
./make-kubeconfig.sh
```

This creates a namespace-scoped kubeconfig and prints the environment the
control plane needs:

```text
ODF_K8S_API_URL=https://<node-ip>:6443
ODF_K8S_TOKEN=...
ODF_K8S_CA_FILE=/path/to/odf-k8s-ca.crt
ODF_K8S_NAMESPACE=data
ODF_K8S_ALLOWED_IMAGES=apache/spark,flink
ODF_FLINK_SQL_GATEWAY_URL=http://<node-ip>:30083
ODF_FLINK_REST_URL=http://flink-jobmanager:8081
```

The service account can only touch Spark applications and read pods in the
`data` namespace. It cannot read Secrets.

## Access

| Component | How |
|---|---|
| Trino | `kubectl -n trino port-forward svc/trino 8080:8080` |
| Flink UI | `kubectl -n stream port-forward svc/flink-jobmanager 8081:8081` |
| Flink SQL Gateway | `http://<node-ip>:30083/v1/info` |
| Nessie | `kubectl -n catalog port-forward svc/nessie 19120:19120` |
| Kafka Connect | `kubectl -n stream port-forward svc/debezium 8083:8083` |
| Grafana | `kubectl -n monitoring port-forward svc/grafana 3000:3000` |

Create the project schema and a first table through the platform, then sync the
datasource so the tables appear in the catalog browser.

## Secrets

`install.sh` generates S3 keys once and writes them into Kubernetes Secrets and
into `values.env`, so a later run does not rotate credentials the running pods
already loaded. `values.env` is therefore sensitive: keep it at mode 600 and out
of version control. To rotate them:

```bash
kubectl -n storage delete secret lakehouse-s3 seaweedfs-s3
LAKE_ACCESS_KEY=... LAKE_SECRET_KEY=... ./install.sh
```

Rolling the storage credentials requires restarting Trino, Nessie and Flink,
because each reads them at start-up.

## Registry mirrors

On a network without direct Docker Hub access, add mirrors to
`/etc/rancher/k3s/registries.yaml` on the node and restart k3s:

```yaml
mirrors:
  docker.io:
    endpoint:
      - "https://docker.m.daocloud.io"
  ghcr.io:
    endpoint:
      - "https://ghcr.nju.edu.cn"
      - "https://ghcr.io"
```

## Known constraints

- One replica per component. This is a development and evaluation environment,
  not a highly available deployment.
- Flink's extra jars are fetched into a volume at install time, because the
  Iceberg and Hadoop classes must sit next to Flink's own libraries. If a
  download fails, `install.sh` stops before starting the cluster.
- Trino runs with a 3 GB heap and a 1 GB per-node query memory limit so that the
  coordinator and heap headroom fit the container limit.
- The SQL Gateway has no authentication. Keep it on a trusted network, or put
  it behind an authenticating proxy.

## Spark image

The Spark Operator runs whatever image a job names. The default image comes from
`ODF_SPARK_IMAGE`, and for lakehouse work it must already carry the Iceberg
runtime:

```bash
cd deploy/k8s/dataplane/images/spark-iceberg
docker build -t registry.local/odf/spark-iceberg:3.5.1 .
docker push registry.local/odf/spark-iceberg:3.5.1
```

Set `ODF_SPARK_IMAGE` to that reference. `GET /api/v1/engine/profiles` shows the
image and the Iceberg catalog configuration the control plane will apply, so an
operator can confirm what a job will actually run with before submitting it.

If the cluster cannot pull a custom image, leave `ODF_SPARK_IMAGE` at the stock
`apache/spark` tag and set `ODF_SPARK_JARS` to a comma-separated list of jar
URIs the driver and executors can reach.

## Isolation and exposure

- `75-network-policy.yaml` denies ingress into `data` from other namespaces and
  allows same-namespace, `spark-operator` and `kube-system` traffic. Egress is
  left open because drivers reach object storage, the catalog and DNS.
- `80-ingress.yaml` publishes Trino, the SQL Gateway and Grafana through Traefik
  on the host names in `values.env`. TLS is commented out; uncomment the
  cert-manager annotation and the `tls` block once an issuer exists.
- `61-tenancy-rbac.yaml` is applied only with `ENABLE_TENANCY=true`. It lets the
  control plane create a namespace, quota, network policy and service account
  per project. Without it, every job lands in `data`.
- `62-spark-operator-rbac.yaml` gives the operator controller and its admission
  webhook the permissions the chart's minimal ClusterRole lacks. Without it a
  SparkApplication is accepted but its driver pod is rejected.
- `60-control-plane-rbac.yaml` also creates the `spark-operator-spark` service
  account and binds it to `edit`, because in cluster mode the driver creates its
  own executor pods.
- `85-nodeports.yaml` publishes Trino, Flink, Nessie, S3 and Kafka Connect on
  fixed node ports so an off-cluster control plane can reach them.
- `76-external-secrets.yaml` is applied only with
  `ENABLE_EXTERNAL_SECRETS=true`, and replaces the generated secrets with
  values pulled from a `ClusterSecretStore`.
