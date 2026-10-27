"""Writes a synthetic events table into Iceberg. Submitted by bench_lakehouse.py.

    spark-submit ingest.py <catalog.schema.table> <rows> [partitions]
"""

import sys

from pyspark.sql import SparkSession, functions as F

target = sys.argv[1]
rows = int(sys.argv[2])
partitions = int(sys.argv[3]) if len(sys.argv) > 3 else 32
catalog, schema, table = target.split(".")

spark = (SparkSession.builder
         .appName("odf-bench-ingest")
         .getOrCreate())

reset = len(sys.argv) > 4 and sys.argv[4] == "1"

spark.sql("CREATE NAMESPACE IF NOT EXISTS %s.%s" % (catalog, schema))
if reset:
    spark.sql("DROP TABLE IF EXISTS %s" % target)
spark.sql("""
CREATE TABLE IF NOT EXISTS %s (
  id bigint,
  event_ts timestamp,
  user_id bigint,
  city string,
  amount double,
  payload string,
  trace string
) USING iceberg
PARTITIONED BY (days(event_ts))
""" % target)

cities = F.array(*[F.lit(c) for c in
                   ("beijing", "shanghai", "shenzhen", "hangzhou",
                    "chengdu", "wuhan", "xian", "nanjing")])

frame = (spark.range(rows, numPartitions=partitions)
         .select(
             F.col("id"),
             F.to_timestamp(F.from_unixtime(
                 F.lit(1750000000) + F.col("id") % 2592000)).alias("event_ts"),
             (F.col("id") % 1000000).alias("user_id"),
             F.element_at(cities, (F.col("id") % 8 + 1).cast("int"))
              .alias("city"),
             ((F.col("id") % 100000) / 100.0).alias("amount"),
             # High-entropy columns so the table is not trivially compressed.
             F.sha2(F.col("id").cast("string"), 256).alias("payload"),
             F.sha2(F.concat(F.col("id").cast("string"),
                             F.lit("-trace")), 256).alias("trace")))

frame.writeTo(target).append()

count = spark.sql("SELECT count(*) FROM %s" % target).collect()[0][0]
print("INGESTED_ROWS=%d TABLE_ROWS=%d" % (rows, count))
spark.stop()
