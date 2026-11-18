"""Set Iceberg table properties from Spark.

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
