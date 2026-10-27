import json

import httpx

from odf.engine.flink_sql import FlinkSqlGateway


def test_execute_creates_session_submits_and_closes():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path,
                      json.loads(request.content or b"null")))
        if request.url.path == "/v1/sessions":
            return httpx.Response(200, json={"sessionHandle": "s1"})
        if request.url.path == "/v1/sessions/s1/statements":
            return httpx.Response(200, json={"operationHandle": "o1"})
        if request.url.path == (
                "/v1/sessions/s1/operations/o1/result/0"):
            return httpx.Response(200, json={
                "resultType": "PAYLOAD",
                "results": {"columns": [], "data": []},
            })
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        return httpx.Response(404)

    client = httpx.Client(base_url="http://gateway",
                          transport=httpx.MockTransport(handler))
    result = FlinkSqlGateway("http://gateway", client=client).execute(
        "SHOW CATALOGS", properties={"execution.runtime-mode": "streaming"})

    assert result["resultType"] == "PAYLOAD"
    assert calls[0] == ("POST", "/v1/sessions",
                        {"properties": {"execution.runtime-mode": "streaming"}})
    assert calls[1][0:2] == ("POST", "/v1/sessions/s1/statements")
    assert calls[1][2]["statement"] == "SHOW CATALOGS"
    assert calls[2][0:2] == (
        "GET", "/v1/sessions/s1/operations/o1/result/0")
    assert calls[-1][0:2] == ("DELETE", "/v1/sessions/s1")


def _client(handler):
    return httpx.Client(base_url="http://gateway",
                        transport=httpx.MockTransport(handler))


def test_execute_detached_returns_job_id_from_result_rows():
    job_id = "0123456789abcdef0123456789abcdef"

    def handler(request):
        path = request.url.path
        if path == "/v1/sessions":
            assert json.loads(request.content)["properties"] == {
                "execution.attached": "false"}
            return httpx.Response(200, json={"sessionHandle": "s1"})
        if path == "/v1/sessions/s1/statements":
            return httpx.Response(200, json={"operationHandle": "o1"})
        if path == "/v1/sessions/s1/operations/o1/result/0":
            return httpx.Response(200, json={
                "resultType": "PAYLOAD",
                "results": {"columns": [{"name": "job id"}],
                            "data": [[job_id]]}})
        return httpx.Response(200, json={})

    out = FlinkSqlGateway("http://gateway", client=_client(handler)).execute(
        "INSERT INTO t SELECT * FROM s", attached=False)
    assert out == {"job_id": job_id}


def test_execute_detached_reads_top_level_job_id():
    job_id = "fedcba9876543210fedcba9876543210"

    def handler(request):
        path = request.url.path
        if path == "/v1/sessions":
            return httpx.Response(200, json={"sessionHandle": "s1"})
        if path == "/v1/sessions/s1/statements":
            return httpx.Response(200, json={"operationHandle": "o1"})
        if path == "/v1/sessions/s1/operations/o1/result/0":
            return httpx.Response(200, json={"resultType": "PAYLOAD",
                                             "jobID": job_id})
        return httpx.Response(200, json={})

    out = FlinkSqlGateway("http://gateway", client=_client(handler)).execute(
        "INSERT INTO t SELECT * FROM s", attached=False)
    assert out == {"job_id": job_id}


def test_execute_detached_without_job_id_raises():
    def handler(request):
        if request.url.path == "/v1/sessions":
            return httpx.Response(200, json={"sessionHandle": "s1"})
        if request.url.path == "/v1/sessions/s1/statements":
            return httpx.Response(200, json={"operationHandle": "o1"})
        if request.url.path.endswith("/result/0"):
            return httpx.Response(200, json={"resultType": "PAYLOAD",
                                             "results": {"columns": [],
                                                         "data": []}})
        return httpx.Response(200, json={})

    import pytest
    with pytest.raises(ValueError, match="job id"):
        FlinkSqlGateway("http://gateway", client=_client(handler)).execute(
            "INSERT INTO t SELECT * FROM s", attached=False)


def test_job_status_maps_flink_states():
    from odf.engine import JobStatus

    states = {"RUNNING": JobStatus.RUNNING,
              "FINISHED": JobStatus.SUCCEEDED,
              "FAILED": JobStatus.FAILED,
              "CANCELED": JobStatus.CANCELLED,
              "INITIALIZING": JobStatus.PENDING,
              "RESTARTING": JobStatus.RUNNING}

    seen = []

    def handler(request):
        job_id = request.url.path.rsplit("/", 1)[-1]
        seen.append(request.url.path)
        return httpx.Response(200, json={"state": _state[job_id]})

    _state = {}
    gateway = FlinkSqlGateway("http://gateway", rest_url="http://flink:8081",
                              client=_client(handler))
    for index, (state, expected) in enumerate(states.items()):
        job_id = "job%d" % index
        _state[job_id] = state
        assert gateway.job_status(job_id) == expected
    assert seen[0] == "/jobs/job0"


def test_job_status_requires_rest_url():
    import pytest
    with pytest.raises(ValueError, match="rest url"):
        FlinkSqlGateway("http://gateway",
                        client=_client(lambda r: httpx.Response(200))).job_status(
            "j1")


def test_cancel_sends_patch():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["query"] = request.url.query
        return httpx.Response(202, json={})

    FlinkSqlGateway("http://gateway", rest_url="http://flink:8081",
                    client=_client(handler)).cancel("j1")
    assert seen["method"] == "PATCH"
    assert seen["path"] == "/jobs/j1"
    assert b"cancel" in seen["query"]
