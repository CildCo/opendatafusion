from odf.connectors.base import Source
from odf.filesource import read_rows


class FileSource(Source):
    def __init__(self, ds, dag):
        self.ds, self.dag = ds, dag

    def read(self, cursor, limit):
        return read_rows(self.ds, self.dag["source_table"],
                         self.dag.get("cursor_column"), self.dag["pk"],
                         cursor, limit)
