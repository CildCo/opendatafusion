#!/usr/bin/env bash
# Installs the OpenDataFusion lakehouse data plane on a single-node k3s cluster.
# Idempotent: re-running converges on the same state.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES="${VALUES_FILE:-$HERE/values.env}"
TEMPLATES="$HERE/templates"

say() { printf '\n==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

[ -f "$VALUES" ] || die "missing $VALUES (copy values.env.example)"
# shellcheck disable=SC1090
set -a; . "$VALUES"; set +a

for tool in kubectl helm envsubst; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required"
done
kubectl get nodes >/dev/null 2>&1 || die "kubectl cannot reach the cluster"

if [ -z "${LAKE_ACCESS_KEY:-}" ]; then
  LAKE_ACCESS_KEY="odf$(head -c 9 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')"
fi
if [ -z "${LAKE_SECRET_KEY:-}" ]; then
  LAKE_SECRET_KEY="$(head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')"
fi
export LAKE_ACCESS_KEY LAKE_SECRET_KEY

# Persist generated keys so a later run does not rotate credentials that the
# running object store already loaded.
if grep -q '^LAKE_ACCESS_KEY=$' "$VALUES"; then
  sed -i "s|^LAKE_ACCESS_KEY=$|LAKE_ACCESS_KEY=$LAKE_ACCESS_KEY|" "$VALUES"
fi
if grep -q '^LAKE_SECRET_KEY=$' "$VALUES"; then
  sed -i "s|^LAKE_SECRET_KEY=$|LAKE_SECRET_KEY=$LAKE_SECRET_KEY|" "$VALUES"
fi
if [ -z "${CDC_PASSWORD:-}" ]; then
  CDC_PASSWORD="$(head -c 24 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')"
fi
export CDC_PASSWORD
if grep -q '^CDC_PASSWORD=$' "$VALUES"; then
  sed -i "s|^CDC_PASSWORD=$|CDC_PASSWORD=$CDC_PASSWORD|" "$VALUES"
fi
if [ -z "${NESSIE_DB_PASSWORD:-}" ]; then
  NESSIE_DB_PASSWORD="$(head -c 24 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9')"
fi
export NESSIE_DB_PASSWORD
if grep -q '^NESSIE_DB_PASSWORD=$' "$VALUES"; then
  sed -i "s|^NESSIE_DB_PASSWORD=$|NESSIE_DB_PASSWORD=$NESSIE_DB_PASSWORD|" "$VALUES"
fi

# Only substitute the variables this file defines. Otherwise envsubst would
# also expand the shell variables inside the manifests' container commands.
# Only substitute variables this file defines. Otherwise envsubst would
# also expand shell variables inside the manifests' container commands.
SUBST_VARS=""
while IFS="=" read -r key _; do
  case "$key" in ""|\#*) continue ;; esac
  SUBST_VARS="$SUBST_VARS \$${key}"
done < "$VALUES"
SUBST_VARS="$SUBST_VARS \${NESSIE_CONFIG_SUM}"

render() {
  envsubst "$SUBST_VARS" < "$1"
}

# Render, validate against the API server, then apply. Catching a schema error
# here is cheaper than debugging a half-applied data plane.
apply_tpl() {
  local out
  out="$(render "$1")"
  printf '%s' "$out" | kubectl apply --dry-run=server -f - >/dev/null
  printf '%s' "$out" | kubectl apply -f -
}

# A Job's pod template is immutable, so a re-run must replace it.
drop_job() {
  kubectl -n "$1" delete job "$2" --ignore-not-found >/dev/null
}

say "namespaces"
apply_tpl "$TEMPLATES/01-namespaces.yaml"

say "secrets"
kubectl -n storage create secret generic lakehouse-s3 \
  --from-literal=access-key="$LAKE_ACCESS_KEY" \
  --from-literal=secret-key="$LAKE_SECRET_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

S3_JSON=$(cat <<JSON
{"identities":[{"name":"odf","credentials":[{"accessKey":"$LAKE_ACCESS_KEY","secretKey":"$LAKE_SECRET_KEY"}],"actions":["Admin","Read","Write"]}]}
JSON
)
kubectl -n storage create secret generic seaweedfs-s3 \
  --from-literal=s3.json="$S3_JSON" \
  --dry-run=client -o yaml | kubectl apply -f -
export S3_CONFIG_SUM
S3_CONFIG_SUM="$(printf '%s' "$S3_JSON" | cksum | cut -d' ' -f1)"

JDBC_PROPS=""
if [ "${NESSIE_VERSION_STORE}" = "JDBC2" ]; then
  JDBC_PROPS="quarkus.datasource.db-kind=postgresql
quarkus.datasource.username=nessie
quarkus.datasource.password=${NESSIE_DB_PASSWORD}
quarkus.datasource.jdbc.url=jdbc:postgresql://nessie-postgres.catalog.svc:5432/nessie
quarkus.flyway.migrate-at-start=true"
fi

NESSIE_PROPERTIES=$(cat <<PROPS
quarkus.http.port=19120
nessie.version.store.type=${NESSIE_VERSION_STORE}
${JDBC_PROPS}
nessie.catalog.default-warehouse=warehouse
nessie.catalog.warehouses.warehouse.location=s3://${LAKE_BUCKET}/iceberg
nessie.catalog.service.s3.default-options.endpoint=http://seaweedfs-s3.storage.svc:8333
nessie.catalog.service.s3.default-options.path-style-access=true
nessie.catalog.service.s3.default-options.region=us-east-1
nessie.catalog.service.s3.default-options.access-key=urn:nessie-secret:quarkus:odf-s3.default-access-key
odf-s3.default-access-key.name=${LAKE_ACCESS_KEY}
odf-s3.default-access-key.secret=${LAKE_SECRET_KEY}
PROPS
)
kubectl -n catalog create secret generic nessie-postgres   --from-literal=password="$NESSIE_DB_PASSWORD"   --dry-run=client -o yaml | kubectl apply -f -

kubectl -n catalog create secret generic nessie-config \
  --from-literal=application.properties="$NESSIE_PROPERTIES" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n stream create secret generic cdc-postgres \
  --from-literal=password="$CDC_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n monitoring create secret generic grafana-admin \
  --from-literal=password="${GRAFANA_PASSWORD:-admin}" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n stream create configmap flink-jars \
  --from-literal=urls.txt="$FLINK_JARS" \
  --dry-run=client -o yaml | kubectl apply -f -

export NESSIE_CONFIG_SUM
NESSIE_CONFIG_SUM="$(printf '%s' "$NESSIE_PROPERTIES" | cksum | cut -d' ' -f1)"

say "spark operator"
if kubectl get crd sparkapplications.sparkoperator.k8s.io >/dev/null 2>&1 \
   && kubectl -n spark-operator get deploy spark-operator-controller \
        >/dev/null 2>&1; then
  echo "already installed"
else
  helm repo add spark-operator https://kubeflow.github.io/spark-operator \
    >/dev/null 2>&1 || die "cannot reach the spark-operator chart repo"
  helm upgrade --install spark-operator spark-operator/spark-operator \
    --namespace spark-operator --version "$SPARK_OPERATOR_VERSION" \
    --set webhook.enable=true --wait --timeout 10m
fi

say "object storage"
drop_job storage seaweedfs-bucket
apply_tpl "$TEMPLATES/10-seaweedfs.yaml"
kubectl -n storage rollout status deploy/seaweedfs --timeout=10m
kubectl -n storage wait --for=condition=complete job/seaweedfs-bucket --timeout=5m || true

say "catalog"
apply_tpl "$TEMPLATES/25-nessie-postgres.yaml"
kubectl -n catalog rollout status deploy/nessie-postgres --timeout=10m

apply_tpl "$TEMPLATES/20-nessie.yaml"
kubectl -n catalog rollout status deploy/nessie --timeout=10m

say "trino"
apply_tpl "$TEMPLATES/30-trino.yaml"
kubectl -n trino rollout status deploy/trino --timeout=10m

say "streaming"
apply_tpl "$TEMPLATES/40-kafka.yaml"
kubectl -n stream rollout status deploy/kafka --timeout=10m

apply_tpl "$TEMPLATES/41-cdc-postgres.yaml"
kubectl -n stream rollout status deploy/cdc-postgres --timeout=10m

apply_tpl "$TEMPLATES/42-debezium.yaml"
kubectl -n stream rollout status deploy/debezium --timeout=10m

say "flink"
drop_job stream flink-libs-prepare
apply_tpl "$TEMPLATES/50-flink.yaml"
kubectl -n stream wait --for=condition=complete job/flink-libs-prepare --timeout=15m
kubectl -n stream rollout restart deploy/flink-jobmanager deploy/flink-taskmanager
kubectl -n stream rollout status deploy/flink-jobmanager --timeout=10m
kubectl -n stream rollout status deploy/flink-taskmanager --timeout=10m

apply_tpl "$TEMPLATES/51-flink-sql-gateway.yaml"
kubectl -n stream rollout status deploy/flink-sql-gateway --timeout=10m

say "spark operator permissions"
apply_tpl "$TEMPLATES/62-spark-operator-rbac.yaml"

say "control plane identity"
apply_tpl "$TEMPLATES/60-control-plane-rbac.yaml"
"$HERE/make-kubeconfig.sh"

if [ "${ENABLE_TENANCY:-false}" = "true" ]; then
  say "tenancy rbac"
  apply_tpl "$TEMPLATES/61-tenancy-rbac.yaml"
fi

say "node ports"
apply_tpl "$TEMPLATES/85-nodeports.yaml"

say "network policy"
apply_tpl "$TEMPLATES/75-network-policy.yaml"

if [ "${ENABLE_EXTERNAL_SECRETS:-false}" = "true" ]; then
  say "external secrets"
  apply_tpl "$TEMPLATES/76-external-secrets.yaml"
fi

say "ingress"
apply_tpl "$TEMPLATES/80-ingress.yaml"

say "monitoring"
apply_tpl "$TEMPLATES/70-monitoring.yaml"
kubectl -n monitoring rollout status deploy/prometheus --timeout=10m || true
kubectl -n monitoring rollout status deploy/grafana --timeout=10m || true

say "done"
kubectl get pods -A -l 'app in (seaweedfs,nessie,trino,kafka,debezium,flink)' \
  -o custom-columns='NS:.metadata.namespace,POD:.metadata.name,STATUS:.status.phase'
echo
echo "node IP:        $(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')"
echo "SQL gateway:    http://<node-ip>:${SQL_GATEWAY_NODEPORT}/v1/info"
echo "Trino:          kubectl -n trino port-forward svc/trino 8080:8080"
echo "Flink UI:       kubectl -n stream port-forward svc/flink-jobmanager 8081:8081"
echo "Grafana:        kubectl -n monitoring port-forward svc/grafana 3000:3000"
