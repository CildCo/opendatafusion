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


def test_execute_follows_next_result_pages():
    def handler(request):
        path = request.url.path
        if path == "/v1/sessions":
            return httpx.Response(200, json={"sessionHandle": "s1"})
        if path == "/v1/sessions/s1/statements":
            return httpx.Response(200, json={"operationHandle": "o1"})
        if path == "/v1/sessions/s1/operations/o1/result/0":
            return httpx.Response(200, json={
                "resultType": "PAYLOAD",
                "results": {"columns": [{"name": "n"}], "data": []},
                "nextResultUri": "/v1/sessions/s1/operations/o1/result/1",
            })
        if path == "/v1/sessions/s1/operations/o1/result/1":
            return httpx.Response(200, json={
                "resultType": "PAYLOAD",
                "results": {"columns": [{"name": "n"}], "data": [[1]]},
            })
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        return httpx.Response(404)

    out = FlinkSqlGateway("http://gateway",
                          client=_client(handler)).execute("select 1")
    assert out["results"]["data"] == [[1]]
    assert "nextResultUri" not in out


def test_execute_waits_for_rows_behind_empty_pages(monkeypatch):
    monkeypatch.setattr("odf.engine.flink_sql.time.sleep", lambda _s: None)
    pages = {
        "/v1/sessions/s1/operations/o1/result/1": {
            "resultType": "PAYLOAD",
            "results": {"columns": [{"name": "n"}], "data": []},
            "nextResultUri": "/v1/sessions/s1/operations/o1/result/2"},
        "/v1/sessions/s1/operations/o1/result/2": {
            "resultType": "PAYLOAD",
            "results": {"columns": [{"name": "n"}], "data": [[7]]},
            "nextResultUri": "/v1/sessions/s1/operations/o1/result/3"},
        "/v1/sessions/s1/operations/o1/result/3": {
            "resultType": "PAYLOAD",
            "results": {"columns": [{"name": "n"}], "data": []},
            "nextResultUri": "/v1/sessions/s1/operations/o1/result/4"},
    }

    def handler(request):
        path = request.url.path
        if path == "/v1/sessions":
            return httpx.Response(200, json={"sessionHandle": "s1"})
        if path == "/v1/sessions/s1/statements":
            return httpx.Response(200, json={"operationHandle": "o1"})
        if path == "/v1/sessions/s1/operations/o1/result/0":
            return httpx.Response(200, json={
                "resultType": "PAYLOAD",
                "results": {"columns": [{"name": "n"}], "data": []},
                "nextResultUri": "/v1/sessions/s1/operations/o1/result/1",
            })
        if path in pages:
            return httpx.Response(200, json=pages[path])
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        return httpx.Response(404)

    out = FlinkSqlGateway("http://gateway",
                          client=_client(handler)).execute("select 7")
    assert out["results"]["data"] == [[7]]
    assert "nextResultUri" not in out


def test_execute_runs_every_statement_in_one_session():
    seen = []

    def handler(request):
        path = request.url.path
        if path == "/v1/sessions":
            return httpx.Response(200, json={"sessionHandle": "s1"})
        if path == "/v1/sessions/s1/statements":
            body = json.loads(request.content)
            seen.append(body["statement"])
            return httpx.Response(200, json={
                "operationHandle": "o%d" % len(seen)})
        if "/operations/o" in path and path.endswith("/result/0"):
            value = "ok-%s" % path.split("/operations/")[1].split("/")[0]
            return httpx.Response(200, json={
                "resultType": "PAYLOAD",
                "results": {"columns": [{"name": "result"}],
                            "data": [{"kind": "INSERT", "fields": [value]}]},
            })
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        return httpx.Response(404)

    out = FlinkSqlGateway("http://gateway", client=_client(handler)).execute(
        "create table a (x int);\ncreate table b (y int);\nselect 1")
    assert seen == ["create table a (x int)",
                    "create table b (y int)", "select 1"]
    assert out["results"]["data"] == [
        {"kind": "INSERT", "fields": ["ok-o3"]}]


def test_detached_script_returns_the_last_job_id():
    job_id = "0123456789abcdef0123456789abcdef"
    seen = []

    def handler(request):
        path = request.url.path
        if path == "/v1/sessions":
            body = json.loads(request.content)
            assert body["properties"]["execution.attached"] == "false"
            return httpx.Response(200, json={"sessionHandle": "s1"})
        if path == "/v1/sessions/s1/statements":
            seen.append(json.loads(request.content)["statement"])
            return httpx.Response(200, json={
                "operationHandle": "o%d" % len(seen)})
        if path.endswith("/result/0"):
            if "insert" in seen[-1]:
                return httpx.Response(200, json={
                    "resultType": "PAYLOAD",
                    "results": {"columns": [{"name": "job id"}],
                                "data": [{"kind": "INSERT",
                                          "fields": [job_id]}]}})
            return httpx.Response(200, json={
                "resultType": "PAYLOAD",
                "results": {"columns": [{"name": "result"}],
                            "data": [{"kind": "INSERT", "fields": ["OK"]}]}})
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        return httpx.Response(404)

    out = FlinkSqlGateway("http://gateway", client=_client(handler)).execute(
        "create table src (x int); create table sink (x int); "
        "insert into sink select x from src", attached=False)
    assert out == {"job_id": job_id}
    assert seen[-1].startswith("insert into sink")
