import json

import httpx
import pytest

from odf.engine import JobSpec, JobStatus, KubernetesEngine


def _engine(handler, namespace="data"):
    client = httpx.Client(
        base_url="https://k8s.example", transport=httpx.MockTransport(handler))
    return KubernetesEngine(
        base_url="https://k8s.example", token="test-token",
        namespace=namespace, client=client)


def _spec(**overrides):
    values = dict(
        name="demo-spark",
        engine="spark",
        image="apache/spark:3.5.1",
        main_application_file="local:///opt/spark/work-dir/job.py",
        spark_version="3.5.1",
        service_account="spark-operator-spark",
        driver_cores=1,
        driver_memory="1g",
        executor_cores=1,
        executor_instances=1,
        executor_memory="1g",
        spark_conf={"spark.sql.catalog.iceberg": "org.apache.iceberg.spark.SparkCatalog"},
    )
    values.update(overrides)
    return JobSpec(**values)


def test_submit_spark_application_posts_crd():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"metadata": {"name": "demo-spark"}})

    name = _engine(handler).submit(_spec())

    assert name == "demo-spark"
    assert seen["method"] == "POST"
    assert seen["path"] == (
        "/apis/sparkoperator.k8s.io/v1beta2/namespaces/data/sparkapplications")
    assert seen["auth"] == "Bearer test-token"
    spec = seen["body"]["spec"]
    assert seen["body"]["metadata"]["name"] == "demo-spark"
    assert spec["type"] == "Python"
    assert spec["pythonVersion"] == "3"
    assert spec["mode"] == "cluster"
    assert spec["image"] == "apache/spark:3.5.1"
    assert spec["mainApplicationFile"] == "local:///opt/spark/work-dir/job.py"
    assert spec["sparkVersion"] == "3.5.1"
    assert spec["driver"]["serviceAccount"] == "spark-operator-spark"
    assert spec["executor"]["instances"] == 1
    assert spec["sparkConf"]["spark.sql.catalog.iceberg"].startswith(
        "org.apache.iceberg")


@pytest.mark.parametrize("state,expected", [
    ("SUBMITTED", JobStatus.PENDING),
    ("RUNNING", JobStatus.RUNNING),
    ("COMPLETED", JobStatus.SUCCEEDED),
    ("FAILED", JobStatus.FAILED),
    ("UNKNOWN", JobStatus.UNKNOWN),
])
def test_status_maps_spark_application_state(state, expected):
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == (
            "/apis/sparkoperator.k8s.io/v1beta2/namespaces/data/"
            "sparkapplications/demo-spark")
        return httpx.Response(
            200, json={"status": {"applicationState": {"state": state}}})

    assert _engine(handler).status("demo-spark") == expected


def test_cancel_deletes_spark_application():
    def handler(request):
        assert request.method == "DELETE"
        assert request.url.path == (
            "/apis/sparkoperator.k8s.io/v1beta2/namespaces/data/"
            "sparkapplications/demo-spark")
        return httpx.Response(200, json={"status": "Success"})

    _engine(handler).cancel("demo-spark")


def test_from_settings_reads_kubernetes_configuration():
    from types import SimpleNamespace

    engine = KubernetesEngine.from_settings(SimpleNamespace(
        k8s_api_url="https://k8s.example", k8s_token="test-token",
        k8s_namespace="odf-data", k8s_ca_file=""))
    assert engine.namespace == "odf-data"


def test_submit_mounts_volumes_on_driver_and_executor():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"metadata": {"name": "demo-spark"}})

    volume = {"name": "jars",
              "hostPath": {"path": "/opt/jars", "type": "Directory"}}
    mount = {"name": "jars", "mountPath": "/opt/jars", "readOnly": True}
    _engine(handler).submit(
        _spec(volumes=[volume], volume_mounts=[mount]))

    body = seen["body"]["spec"]
    assert body["volumes"] == [volume]
    assert body["driver"]["volumeMounts"] == [mount]
    assert body["executor"]["volumeMounts"] == [mount]
