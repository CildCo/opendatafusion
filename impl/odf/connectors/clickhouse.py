from odf.clickhouse import read_rows
from odf.connectors.base import Source


class ClickHouseSource(Source):
    def __init__(self, ds, dag):
        self.ds, self.dag = ds, dag

    def read(self, cursor, limit):
        return read_rows(self.ds, self.dag["source_table"],
                         self.dag.get("cursor_column"), self.dag["pk"],
                         cursor, limit)
