from odf.services.flow import validate_dag


def test_dag_requires_source_and_sink():
    good = {"source_ds_id": 1, "sink_ds_id": 2,
            "source_table": "a", "sink_table": "b"}
    assert validate_dag(good) is True
    assert validate_dag({"source_ds_id": 1}) is False
