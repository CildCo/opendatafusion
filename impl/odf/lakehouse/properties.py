import re

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_PROPERTY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")

# Spark image jobs run a file that already exists inside the driver. The
# operator must place this program at the path in `lakehouse_property_script`
# (default local:///opt/odf-spark-jars/set_properties.py) and expose that path
# through `spark_jars_dir`; the platform does not upload it.
SCRIPT = '''"""Set Iceberg table properties from Spark.

Usage: set_properties.py <catalog.schema.table> <name=value> [...]
"""
import sys

from pyspark.sql import SparkSession

if len(sys.argv) < 3:
    raise SystemExit("usage: set_properties.py <table> <name=value> ...")

spark = SparkSession.builder.appName("odf-set-properties").getOrCreate()
pairs = []
for arg in sys.argv[2:]:
    name, _, value = arg.partition("=")
    # Iceberg property names contain dots and dashes; Spark needs them quoted.
    pairs.append("'%s'=%s" % (name.replace("'", "''"), value))
spark.sql("ALTER TABLE %s SET TBLPROPERTIES (%s)"
          % (sys.argv[1], ", ".join(pairs)))
spark.stop()
'''


def _table(name: str) -> str:
    parts = name.split(".") if isinstance(name, str) else []
    if len(parts) != 3 or not all(_IDENT.match(part) for part in parts):
        raise ValueError("table must be catalog.schema.table")
    return name


def _property_name(name: str) -> str:
    if not isinstance(name, str) or not _PROPERTY.match(name):
        raise ValueError("invalid property name")
    return name


def _property_value(value) -> str:
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (int, float)):
        text = repr(value)
    elif isinstance(value, str):
        text = value
    else:
        raise ValueError("property values must be scalars")
    return "'" + text.replace("'", "''") + "'"


def build_spec(table: str, properties: dict, settings) -> dict:
    table = _table(table)
    if not properties:
        raise ValueError("at least one property is required")
    args = [table]
    for name, value in properties.items():
        args.append("%s=%s" % (_property_name(name), _property_value(value)))
    return {
        "image": settings.spark_image,
        "main_application_file": settings.lakehouse_property_script,
        "args": args,
        "executor_instances": 1,
        "memory": "1g",
        "spark_conf": {},
    }
