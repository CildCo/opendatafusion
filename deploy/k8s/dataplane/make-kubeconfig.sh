#!/usr/bin/env bash
# Builds a namespace-scoped kubeconfig for the control plane and prints the
# settings it needs. Run after 60-control-plane-rbac.yaml is applied.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NS="${NAMESPACE:-data}"
SA="${SERVICE_ACCOUNT:-odf-control-plane}"
SECRET="${SA}-token"
OUT="${OUT_FILE:-$HERE/odf-k8s.kubeconfig}"
CA="${CA_FILE:-$HERE/odf-k8s-ca.crt}"

for tool in kubectl base64; do
  command -v "$tool" >/dev/null 2>&1 || { echo "error: $tool is required" >&2; exit 1; }
done

kubectl -n "$NS" get secret "$SECRET" >/dev/null 2>&1 \
  || { echo "error: secret $NS/$SECRET not found; apply 60-control-plane-rbac.yaml" >&2; exit 1; }

SERVER="$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')"
TOKEN="$(kubectl -n "$NS" get secret "$SECRET" -o jsonpath='{.data.token}' | base64 -d)"
kubectl -n "$NS" get secret "$SECRET" -o jsonpath='{.data.ca\.crt}' | base64 -d > "$CA"

umask 077
cat > "$OUT" <<KUBECONFIG
apiVersion: v1
kind: Config
clusters:
  - name: odf
    cluster:
      server: ${SERVER}
      certificate-authority: ${CA}
users:
  - name: odf-control-plane
    user:
      token: ${TOKEN}
contexts:
  - name: odf
    context:
      cluster: odf
      user: odf-control-plane
      namespace: ${NS}
current-context: odf
KUBECONFIG

cat <<SUMMARY

kubeconfig: $OUT
CA file:    $CA

Add these to the control plane environment:

ODF_K8S_API_URL=${SERVER}
ODF_K8S_TOKEN=${TOKEN}
ODF_K8S_CA_FILE=${CA}
ODF_K8S_NAMESPACE=${NS}
ODF_K8S_ALLOWED_IMAGES=apache/spark,flink,odf/spark
ODF_FLINK_SQL_GATEWAY_URL=http://<node-ip>:30083
ODF_FLINK_REST_URL=http://<flink-jobmanager>:8081

Lakehouse profile (the control plane must be able to reach these hosts):

ODF_LAKEHOUSE_ENABLED=true
ODF_LAKEHOUSE_CATALOG=iceberg
ODF_LAKEHOUSE_URI=http://<nessie-host>:19120/iceberg
ODF_LAKEHOUSE_WAREHOUSE=warehouse
ODF_LAKEHOUSE_S3_ENDPOINT=http://<s3-host>:8333
ODF_SPARK_IMAGE=odf/spark-iceberg:3.5.1
ODF_SPARK_JARS=
ODF_DEBEZIUM_URL=http://<connect-host>:8083

The token is scoped to namespace ${NS} by the Role in 60-control-plane-rbac.yaml.
Enabling ODF_K8S_TENANCY_ENABLED also needs 61-tenancy-rbac.yaml.
SUMMARY
