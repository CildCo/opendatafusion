DEFAULT_SPARK_IMAGE = "apache/spark:3.5.1"
ICEBERG_CATALOG_CLASS = "org.apache.iceberg.spark.SparkCatalog"
ICEBERG_EXTENSIONS = (
    "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")


def catalog_name(settings) -> str:
    return (settings.lakehouse_catalog or "iceberg").strip()


def spark_jar_volume(settings):
    directory = (getattr(settings, "spark_jars_dir", "") or "").strip()
    if not directory:
        return [], [], {}
    volumes = [{"name": "odf-jars",
                "hostPath": {"path": directory, "type": "Directory"}}]
    mounts = [{"name": "odf-jars", "mountPath": directory, "readOnly": True}]
    conf = {"spark.driver.extraClassPath": directory + "/*",
            "spark.executor.extraClassPath": directory + "/*"}
    return volumes, mounts, conf


def spark_conf_profile(settings) -> dict:
    _, _, jar_conf = spark_jar_volume(settings)
    if not getattr(settings, "lakehouse_enabled", False):
        return dict(jar_conf)
    catalog = catalog_name(settings)
    prefix = "spark.sql.catalog.%s" % catalog
    conf = {
        prefix: ICEBERG_CATALOG_CLASS,
        "%s.type" % prefix: "rest",
        "spark.sql.extensions": ICEBERG_EXTENSIONS,
        # Cross-engine reads of Spark-written Parquet need this off.
        "spark.sql.iceberg.vectorization.enabled": "false",
    }
    if settings.lakehouse_uri:
        conf["%s.uri" % prefix] = settings.lakehouse_uri
    if settings.lakehouse_warehouse:
        conf["%s.warehouse" % prefix] = settings.lakehouse_warehouse
    endpoint = getattr(settings, "lakehouse_s3_endpoint", "")
    if endpoint:
        conf["%s.io-impl" % prefix] = "org.apache.iceberg.aws.s3.S3FileIO"
        conf["%s.s3.endpoint" % prefix] = endpoint
        conf["%s.s3.path-style-access" % prefix] = "true"
    access_key = getattr(settings, "lakehouse_s3_access_key", "")
    secret_key = getattr(settings, "lakehouse_s3_secret_key", "")
    if access_key and secret_key:
        conf["%s.s3.access-key-id" % prefix] = access_key
        conf["%s.s3.secret-access-key" % prefix] = secret_key
    if settings.lakehouse_s3_region:
        conf["%s.s3.region" % prefix] = settings.lakehouse_s3_region
    if settings.spark_jars:
        conf["spark.jars"] = settings.spark_jars
    conf.update(jar_conf)
    return conf


def spark_default_image(settings) -> str:
    return settings.spark_image or DEFAULT_SPARK_IMAGE


def profiles(settings) -> dict:
    return {
        "lakehouse_enabled": bool(
            getattr(settings, "lakehouse_enabled", False)),
        "lakehouse_catalog": catalog_name(settings),
        "spark": {
            "image": spark_default_image(settings),
            "spark_conf": spark_conf_profile(settings),
        },
        "flink": {
            "sql_gateway": bool(getattr(settings, "flink_sql_gateway_url", "")),
            "rest": bool(getattr(settings, "flink_rest_url", "")),
        },
    }
