from types import SimpleNamespace

from odf.engine.profiles import spark_conf_profile, spark_default_image
from odf.services.engine_jobs import spark_spec_from


def _settings(**overrides):
    values = dict(
        lakehouse_enabled=True,
        lakehouse_catalog="iceberg",
        lakehouse_uri="http://nessie.catalog.svc:19120/iceberg",
        lakehouse_warehouse="warehouse",
        lakehouse_s3_endpoint="http://seaweedfs-s3.storage.svc:8333",
        lakehouse_s3_region="us-east-1",
        spark_image="odf/spark-iceberg:3.5.1",
        spark_jars="s3a://jars/iceberg.jar",
        lakehouse_s3_access_key="odf",
        lakehouse_s3_secret_key="odf-secret",
        spark_jars_dir="",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_profile_is_empty_when_disabled():
    assert spark_conf_profile(_settings(lakehouse_enabled=False)) == {}


def test_profile_sets_catalog_and_storage():
    conf = spark_conf_profile(_settings())
    assert conf["spark.sql.catalog.iceberg"] == \
        "org.apache.iceberg.spark.SparkCatalog"
    assert conf["spark.sql.catalog.iceberg.type"] == "rest"
    assert conf["spark.sql.catalog.iceberg.uri"] == \
        "http://nessie.catalog.svc:19120/iceberg"
    assert conf["spark.sql.catalog.iceberg.warehouse"] == "warehouse"
    assert conf["spark.sql.catalog.iceberg.s3.endpoint"] == \
        "http://seaweedfs-s3.storage.svc:8333"
    assert conf["spark.sql.catalog.iceberg.s3.path-style-access"] == "true"
    assert conf["spark.sql.catalog.iceberg.io-impl"] ==         "org.apache.iceberg.aws.s3.S3FileIO"
    assert conf["spark.sql.catalog.iceberg.s3.access-key-id"] == "odf"
    assert conf["spark.sql.catalog.iceberg.s3.secret-access-key"] ==         "odf-secret"
    assert conf["spark.jars"] == "s3a://jars/iceberg.jar"
    assert "IcebergSparkSessionExtensions" in conf["spark.sql.extensions"]


def test_profile_honours_a_custom_catalog_name():
    conf = spark_conf_profile(_settings(lakehouse_catalog="lake"))
    assert "spark.sql.catalog.lake" in conf
    assert "spark.sql.catalog.iceberg" not in conf


def test_profile_omits_s3_keys_without_endpoint():
    conf = spark_conf_profile(_settings(lakehouse_s3_endpoint=""))
    assert not any("s3.endpoint" in key for key in conf)
    assert not any("path-style" in key for key in conf)


def test_default_image_comes_from_settings():
    assert spark_default_image(_settings()) == "odf/spark-iceberg:3.5.1"
    assert spark_default_image(
        _settings(spark_image="")) == "apache/spark:3.5.1"


def test_spark_spec_applies_profile_when_caller_is_silent():
    spec = spark_spec_from("job-1", {
        "main_application_file": "local:///app.py"}, _settings())
    assert spec.image == "odf/spark-iceberg:3.5.1"
    assert spec.spark_conf["spark.sql.catalog.iceberg.type"] == "rest"


def test_caller_spark_conf_wins_over_profile():
    spec = spark_spec_from("job-2", {
        "main_application_file": "local:///app.py",
        "spark_conf": {"spark.sql.catalog.iceberg.uri": "http://mine",
                       "spark.executor.memory": "4g"}}, _settings())
    assert spec.spark_conf["spark.sql.catalog.iceberg.uri"] == "http://mine"
    assert spec.spark_conf["spark.executor.memory"] == "4g"
    assert spec.spark_conf["spark.sql.catalog.iceberg.type"] == "rest"


def test_spark_spec_without_lakehouse_keeps_caller_conf_only():
    spec = spark_spec_from("job-3", {
        "main_application_file": "local:///app.py"}, _settings(
            lakehouse_enabled=False))
    assert spec.spark_conf == {}
    assert spec.image == "odf/spark-iceberg:3.5.1"


def test_jar_directory_adds_classpath_and_volume():
    settings = _settings(spark_jars_dir="/opt/odf-spark-jars")
    conf = spark_conf_profile(settings)
    assert conf["spark.driver.extraClassPath"] == "/opt/odf-spark-jars/*"
    assert conf["spark.executor.extraClassPath"] == "/opt/odf-spark-jars/*"

    spec = spark_spec_from("job-jars", {
        "main_application_file": "local:///app.py"}, settings)
    assert spec.volume_mounts == [
        {"name": "odf-jars", "mountPath": "/opt/odf-spark-jars",
         "readOnly": True}]
    assert spec.volumes == [
        {"name": "odf-jars",
         "hostPath": {"path": "/opt/odf-spark-jars", "type": "Directory"}}]
