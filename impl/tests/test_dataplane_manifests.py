import re
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[2] / "deploy" / "k8s" / "dataplane"
TEMPLATES = BASE / "templates"

VALUES = {
    "LAKE_BUCKET": "warehouse",
    "STORAGE_SIZE": "50Gi",
    "KAFKA_SIZE": "20Gi",
    "CDC_PG_SIZE": "10Gi",
    "CDC_DB": "cdc",
    "CDC_USER": "cdc",
    "TRINO_HEAP": "3G",
    "TRINO_EXPIRE_MIN_RETENTION": "7d",
    "FLINK_TASKMANGERS": "1",
    "SQL_GATEWAY_NODEPORT": "30083",
    "KAFKA_CLUSTER_ID": "MkU3OEVBNTcwNTJENDM2Qk",
    "DEBEZIUM_PLUGIN_URL": "https://example.invalid/plugin.tar.gz",
    "ODF_METRICS_TARGET": "127.0.0.1:18080",
    "NESSIE_CONFIG_SUM": "1",
    "NESSIE_PG_SIZE": "5Gi",
    "S3_CONFIG_SUM": "2",
    "IMAGE_SEAWEEDFS": "chrislusf/seaweedfs:4.48",
    "IMAGE_AWSCLI": "amazon/aws-cli:2.15.30",
    "IMAGE_BUSYBOX": "busybox:1.36",
    "IMAGE_NESSIE": "ghcr.io/projectnessie/nessie:0.104.2",
    "IMAGE_TRINO": "trinodb/trino:484",
    "IMAGE_KAFKA": "apache/kafka:3.9.0",
    "IMAGE_POSTGRES": "postgres:16-alpine",
    "IMAGE_FLINK": "flink:1.20-scala_2.12",
    "IMAGE_PROMETHEUS": "prom/prometheus:v2.55.1",
    "IMAGE_GRAFANA": "grafana/grafana:11.3.0",
    "IMAGE_DEBEZIUM": "debezium/connect:3.0.0.Final",
    "TRINO_HOST": "trino.odf.local",
    "FLINK_HOST": "flink.odf.local",
    "GRAFANA_HOST": "grafana.odf.local",
    "ESO_STORE": "default",
    "ESO_PREFIX": "odf",
    "TRINO_NODEPORT": "30080",
    "FLINK_REST_NODEPORT": "30081",
    "NESSIE_NODEPORT": "30082",
    "S3_NODEPORT": "30084",
    "DEBEZIUM_NODEPORT": "30085",
    "FLINK_SQL_RUNNER_URL": "https://example.invalid/sql-runner.jar",
    "FLINK_OPERATOR_VERSION": "1.13.0",
    "FLINK_OPERATOR_IMAGE": "apache/flink-kubernetes-operator",
    "CERT_MANAGER_VERSION": "v1.19.6",
}

_PLACEHOLDER = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")

# Grafana dashboard inputs are resolved by Grafana when it loads the
# dashboard, not by envsubst. They must survive rendering unchanged.
GRAFANA_INPUTS = {"DS_PROMETHEUS"}


def render(path):
    def replace(match):
        name = match.group(1)
        if name in VALUES:
            return VALUES[name]
        return match.group(0)

    return _PLACEHOLDER.sub(replace, path.read_text(encoding="utf-8"))


def documents(path):
    return [doc for doc in yaml.safe_load_all(render(path)) if doc]


def _all_templates():
    return sorted(TEMPLATES.glob("*.yaml"))


def test_templates_exist():
    names = [p.name for p in _all_templates()]
    for expected in ("01-namespaces.yaml", "10-seaweedfs.yaml",
                     "25-nessie-postgres.yaml", "20-nessie.yaml", "30-trino.yaml", "40-kafka.yaml",
                     "41-cdc-postgres.yaml", "42-debezium.yaml",
                     "50-flink.yaml", "51-flink-sql-gateway.yaml",
                     "57-flink-deployment.yaml",
                     "60-control-plane-rbac.yaml", "61-tenancy-rbac.yaml",
                     "62-spark-operator-rbac.yaml",
                     "70-monitoring.yaml", "75-network-policy.yaml",
                     "76-external-secrets.yaml", "80-ingress.yaml",
                     "85-nodeports.yaml"):
        assert expected in names


def test_every_template_parses_with_kind():
    for path in _all_templates():
        for doc in documents(path):
            assert doc.get("apiVersion"), path.name
            assert doc.get("kind"), path.name
            assert doc.get("metadata", {}).get("name"), path.name


def test_no_unresolved_placeholders():
    for path in _all_templates():
        text = render(path)
        unknown = [m.group(1) for m in _PLACEHOLDER.finditer(text)
                   if m.group(1) not in VALUES
                   and m.group(1) not in GRAFANA_INPUTS]
        assert not unknown, "%s: %s" % (path.name, unknown)


def test_manifests_carry_no_literal_credentials():
    installer = (BASE / "install.sh").read_text(encoding="utf-8")
    assert "cdcpass" not in installer
    for path in _all_templates():
        text = path.read_text(encoding="utf-8").lower()
        assert "cdcpass" not in text, path.name
        assert "admin123" not in text, path.name
        assert "changeme" not in text, path.name


def test_control_plane_role_is_least_privilege():
    role = [d for d in documents(TEMPLATES / "60-control-plane-rbac.yaml")
            if d["kind"] == "Role"][0]
    spark = [r for r in role["rules"]
             if "sparkapplications" in r["resources"]]
    assert spark, "sparkapplications rule missing"
    assert set(spark[0]["verbs"]) == {"get", "list", "watch", "create",
                                      "delete"}
    assert all("secrets" not in r["resources"] for r in role["rules"])


def test_trino_mounts_catalog_properties():
    docs = documents(TEMPLATES / "30-trino.yaml")
    configmap = [d for d in docs if d["kind"] == "ConfigMap"][0]
    assert "iceberg.properties" in configmap["data"]
    deployment = [d for d in docs if d["kind"] == "Deployment"][0]
    volume = deployment["spec"]["template"]["spec"]["volumes"][0]
    items = {i["key"]: i["path"] for i in volume["configMap"]["items"]}
    assert items["iceberg.properties"] == "catalog/iceberg.properties"


def test_flink_jobmanager_exposes_blob_port():
    docs = documents(TEMPLATES / "50-flink.yaml")
    service = [d for d in docs
               if d["kind"] == "Service" and d["metadata"]["name"] ==
               "flink-jobmanager"][0]
    ports = {p["name"]: p["port"] for p in service["spec"]["ports"]}
    assert ports == {"rpc": 6123, "blob": 6124, "webui": 8081}


def test_install_script_references_every_template():
    script = (BASE / "install.sh").read_text(encoding="utf-8")
    for path in _all_templates():
        assert path.name in script, path.name


def test_helpers_have_shebang():
    for name in ("install.sh", "make-kubeconfig.sh"):
        text = (BASE / name).read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash"), name


def test_spark_image_bakes_the_iceberg_runtime():
    dockerfile = BASE / "images" / "spark-iceberg" / "Dockerfile"
    text = dockerfile.read_text(encoding="utf-8")
    assert "FROM apache/spark:3.5.1" in text
    assert "iceberg-spark-runtime" in text
    assert "iceberg-aws-bundle" in text


def test_values_example_declares_the_spark_image():
    text = (BASE / "values.env.example").read_text(encoding="utf-8")
    assert "IMAGE_SPARK=" in text


def test_tenancy_roles_grant_only_what_is_needed():
    docs = documents(TEMPLATES / "61-tenancy-rbac.yaml")
    role = [d for d in docs if d["kind"] == "ClusterRole"
            and d["metadata"]["name"] == "odf-tenancy"][0]
    namespaces = [r for r in role["rules"]
                  if "namespaces" in r["resources"]][0]
    assert set(namespaces["verbs"]) == {"get", "create"}
    assert all("secrets" not in r["resources"] for r in role["rules"])
    bind = [r for r in role["rules"] if "clusterroles" in r["resources"]][0]
    assert bind["resourceNames"] == ["edit"]


def test_ingress_routes_use_traefik():
    docs = documents(TEMPLATES / "80-ingress.yaml")
    assert len(docs) == 3
    for doc in docs:
        assert doc["kind"] == "Ingress"
        assert doc["spec"]["ingressClassName"] == "traefik"
        assert doc["spec"]["rules"][0]["host"].endswith(".odf.local")


def test_data_namespace_denies_cross_namespace_ingress():
    docs = documents(TEMPLATES / "75-network-policy.yaml")
    policy = [d for d in docs if d["metadata"]["name"] ==
              "data-default-deny-ingress"][0]
    assert policy["spec"]["podSelector"] == {}
    assert policy["spec"]["policyTypes"] == ["Ingress"]
    sources = [src for rule in policy["spec"]["ingress"]
               for src in rule["from"]]
    assert any("podSelector" in item for item in sources)
    assert any("namespaceSelector" in item for item in sources)


def test_external_secrets_target_the_generated_secret_names():
    docs = documents(TEMPLATES / "76-external-secrets.yaml")
    names = {d["spec"]["target"]["name"] for d in docs}
    assert names == {"lakehouse-s3", "cdc-postgres", "grafana-admin"}


def test_nodeports_select_the_manifest_labels():
    docs = documents(TEMPLATES / "85-nodeports.yaml")
    selectors = {d["metadata"]["name"]: d["spec"]["selector"] for d in docs}
    assert selectors["trino-node"] == {"app": "trino"}
    assert selectors["flink-rest-node"] == {"app": "flink",
                                            "component": "jobmanager"}
    assert selectors["s3-node"] == {"app": "seaweedfs"}
    assert selectors["debezium-node"] == {"app": "debezium"}
    for doc in docs:
        assert doc["spec"]["type"] == "NodePort"


def test_spark_operator_binding_covers_controller_and_webhook():
    docs = documents(TEMPLATES / "62-spark-operator-rbac.yaml")
    bindings = [d for d in docs if d["kind"] == "ClusterRoleBinding"]
    subjects = {(b["subjects"][0]["name"]) for b in bindings}
    assert subjects == {"spark-operator-controller", "spark-operator-webhook"}


def test_driver_service_account_can_create_pods():
    docs = documents(TEMPLATES / "60-control-plane-rbac.yaml")
    binding = [d for d in docs if d["kind"] == "RoleBinding"
               and d["metadata"]["name"] == "spark-driver-edit"][0]
    assert binding["subjects"][0]["name"] == "spark-operator-spark"
    assert binding["roleRef"]["name"] == "edit"


def test_nessie_has_a_persistent_catalog_database():
    docs = documents(TEMPLATES / "25-nessie-postgres.yaml")
    kinds = {d["kind"] for d in docs}
    assert kinds == {"PersistentVolumeClaim", "Deployment", "Service"}
    deploy = [d for d in docs if d["kind"] == "Deployment"][0]
    env = {e["name"] for e in
           deploy["spec"]["template"]["spec"]["containers"][0]["env"]}
    assert {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"} <= env
    assert deploy["spec"]["template"]["spec"]["containers"][0]["image"] ==         VALUES["IMAGE_POSTGRES"]


def test_installer_points_nessie_at_its_database():
    script = (BASE / "install.sh").read_text(encoding="utf-8")
    assert "nessie.version.store.type=${NESSIE_VERSION_STORE}" in script
    assert "jdbc:postgresql://nessie-postgres.catalog.svc:5432/nessie" in script
    assert "quarkus.flyway.migrate-at-start=true" in script
    assert "25-nessie-postgres.yaml" in script


def test_flink_operator_install_is_idempotent():
    script = (BASE / "install.sh").read_text(encoding="utf-8")
    assert "flinkdeployments.flink.apache.org" in script
    assert "flink-kubernetes-operator" in script
    assert "helm upgrade --install flink-kubernetes-operator" in script
    assert '--version "$FLINK_OPERATOR_VERSION"' in script
    assert '--set image.repository="$FLINK_OPERATOR_IMAGE"' in script
    # The chart webhooks need cert-manager, so the installer provisions it.
    assert "certificates.cert-manager.io" in script
    assert "helm upgrade --install cert-manager jetstack/cert-manager" in script
    assert "crds.enabled=true" in script


def test_values_example_declares_the_flink_operator():
    text = (BASE / "values.env.example").read_text(encoding="utf-8")
    assert "FLINK_OPERATOR_VERSION=" in text
    assert "FLINK_OPERATOR_IMAGE=" in text
    assert "CERT_MANAGER_VERSION=" in text
    assert "FLINK_SQL_RUNNER_URL=" in text


def test_flink_deployment_is_managed_by_the_operator():
    docs = documents(TEMPLATES / "57-flink-deployment.yaml")
    deployment = [d for d in docs if d["kind"] == "FlinkDeployment"][0]
    assert deployment["apiVersion"] == "flink.apache.org/v1beta1"
    spec = deployment["spec"]
    assert spec["image"] == VALUES["IMAGE_FLINK"]
    assert spec["flinkVersion"] == "v1_20"
    config = spec["flinkConfiguration"]
    assert config["state.checkpoints.dir"] == (
        "s3://%s/checkpoints" % VALUES["LAKE_BUCKET"])
    assert config["state.savepoints.dir"] == (
        "s3://%s/savepoints" % VALUES["LAKE_BUCKET"])
    assert config["restart-strategy.type"] == "fixed-delay"
    assert spec["job"]["jarURI"].endswith("/sql-runner.jar")
    assert spec["job"]["upgradeMode"] == "savepoint"
    assert spec["job"]["state"] == "running"


def test_flink_deployment_uses_the_shared_secret_and_volumes():
    docs = documents(TEMPLATES / "57-flink-deployment.yaml")
    deployment = [d for d in docs if d["kind"] == "FlinkDeployment"][0]
    pod = deployment["spec"]["podTemplate"]["spec"]
    env = {item["name"]: item["valueFrom"]["secretKeyRef"]
           for item in pod["containers"][0]["env"]}
    assert env["AWS_ACCESS_KEY_ID"]["name"] == "lakehouse-s3"
    assert env["AWS_ACCESS_KEY_ID"]["key"] == "access-key"
    assert env["AWS_SECRET_ACCESS_KEY"]["name"] == "lakehouse-s3"
    assert env["AWS_SECRET_ACCESS_KEY"]["key"] == "secret-key"
    claims = {volume["persistentVolumeClaim"]["claimName"]
              for volume in pod["volumes"]
              if "persistentVolumeClaim" in volume}
    assert claims == {"flink-libs", "flink-plugins"}


def test_flink_deployment_moves_the_cdc_topic_into_iceberg():
    docs = documents(TEMPLATES / "57-flink-deployment.yaml")
    configmap = [d for d in docs if d["kind"] == "ConfigMap"][0]
    sql = configmap["data"]["events.sql"]
    assert "'connector' = 'kafka'" in sql
    assert "'topic' = 'odf.public.events'" in sql
    assert "'format' = 'debezium-json'" in sql
    assert "iceberg.odf_check.events" in sql


def test_spark_operator_watches_every_namespace():
    script = (BASE / "install.sh").read_text(encoding="utf-8")
    assert "spark.jobNamespaces={}" in script


def test_property_script_matches_the_platform_copy():
    from odf.lakehouse.properties import SCRIPT

    path = BASE / "scripts" / "set_properties.py"
    assert path.read_text(encoding="utf-8") == SCRIPT
