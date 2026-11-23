import json

from odf.connectors.base import Sink, Source
from odf.services.datasource import get_dsn


def bootstrap(ds_or_dsn):
    raw = ds_or_dsn if isinstance(ds_or_dsn, str) else get_dsn(ds_or_dsn)
    return raw[len("kafka://"):] if raw.startswith("kafka://") else raw


def ping(dsn, timeout=5):
    from kafka.admin import KafkaAdminClient
    client = KafkaAdminClient(
        bootstrap_servers=bootstrap(dsn),
        request_timeout_ms=max(1000, timeout * 1000),
        api_version_auto_timeout_ms=max(1000, timeout * 1000))
    try:
        client.list_topics()
        return True
    finally:
        client.close()


class KafkaSource(Source):
    def __init__(self, ds, dag):
        self.bootstrap = bootstrap(ds)
        self.topic = dag.get("source_table") or dag.get("topic")
        if not self.topic:
            raise ValueError("kafka source needs a topic")
        self.group = dag.get("consumer_group") or "odf-pipeline"

    def read(self, cursor, limit):
        from kafka import KafkaConsumer, TopicPartition
        consumer = KafkaConsumer(
            bootstrap_servers=self.bootstrap, enable_auto_commit=False,
            auto_offset_reset="earliest", consumer_timeout_ms=1000,
            group_id=self.group)
        try:
            offsets = {}
            if cursor:
                try:
                    offsets = {int(k): int(v)
                               for k, v in json.loads(cursor).items()}
                except (TypeError, ValueError):
                    offsets = {}
            if offsets:
                partitions = [TopicPartition(self.topic, part)
                              for part in offsets]
                consumer.assign(partitions)
                for part, offset in offsets.items():
                    consumer.seek(TopicPartition(self.topic, part), offset)
            else:
                consumer.subscribe([self.topic])
            batches = consumer.poll(timeout_ms=1000, max_records=limit)
            rows = []
            for records in batches.values():
                for record in records:
                    value = record.value
                    if isinstance(value, bytes):
                        value = value.decode("utf-8", "replace")
                    rows.append(value if isinstance(value, dict)
                                else json.loads(value))
                    if record.offset + 1 > offsets.get(record.partition, 0):
                        offsets[record.partition] = record.offset + 1
            rows = rows[:limit]
            new_cursor = (json.dumps({str(k): v for k, v in offsets.items()})
                          if rows else cursor)
            return rows, new_cursor
        finally:
            consumer.close()


class KafkaSink(Sink):
    def __init__(self, ds, dag):
        self.bootstrap = bootstrap(ds)
        self.topic = dag.get("sink_table") or dag.get("topic")
        if not self.topic:
            raise ValueError("kafka sink needs a topic")

    def write(self, rows):
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=self.bootstrap, linger_ms=5,
            value_serializer=lambda v: json.dumps(
                v, ensure_ascii=False, default=str).encode("utf-8"))
        try:
            for row in rows:
                producer.send(self.topic, row)
            producer.flush(timeout=10)
        finally:
            producer.close()
        return len(rows)
