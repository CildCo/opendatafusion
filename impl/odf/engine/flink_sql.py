import time

import httpx

from odf.engine.base import JobStatus

_JOB_COLUMNS = ("job id", "jobid", "job_id")

_STATUS = {
    "CREATED": JobStatus.PENDING,
    "INITIALIZING": JobStatus.PENDING,
    "RECONCILING": JobStatus.PENDING,
    "SCHEDULING": JobStatus.RUNNING,
    "RUNNING": JobStatus.RUNNING,
    "RESTARTING": JobStatus.RUNNING,
    "FINISHED": JobStatus.SUCCEEDED,
    "FAILED": JobStatus.FAILED,
    "CANCELED": JobStatus.CANCELLED,
    "CANCELLING": JobStatus.CANCELLED,
}


class FlinkSqlGateway:
    def __init__(self, base_url, client=None, timeout: float = 30.0,
                 max_polls: int = 50, rest_url: str = ""):
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout)
        self._max_polls = max_polls
        self._rest_url = rest_url.rstrip("/")

    def execute(self, statement: str, properties: dict | None = None,
                attached: bool = True) -> dict:
        props = dict(properties or {})
        if not attached:
            props["execution.attached"] = "false"
        session = self._client.post(
            "/v1/sessions", json={"properties": props})
        session.raise_for_status()
        session_id = session.json()["sessionHandle"]
        try:
            submitted = self._client.post(
                "/v1/sessions/%s/statements" % session_id,
                json={"statement": statement})
            submitted.raise_for_status()
            operation_id = submitted.json()["operationHandle"]
            path = ("/v1/sessions/%s/operations/%s/result/0"
                    % (session_id, operation_id))
            result = {}
            for _ in range(self._max_polls):
                response = self._client.get(path)
                response.raise_for_status()
                result = response.json()
                if result.get("resultType") != "NOT_READY":
                    break
                time.sleep(0.2)
            if not attached:
                return {"job_id": self._job_id(result)}
            return result
        finally:
            try:
                self._client.delete("/v1/sessions/%s" % session_id)
            except httpx.HTTPError:
                pass

    @staticmethod
    def _job_id(result: dict) -> str:
        for key in ("jobID", "jobId", "job_id"):
            value = result.get(key)
            if isinstance(value, str) and value:
                return value
        results = result.get("results") or {}
        columns = [str(c.get("name", "")).lower()
                   for c in results.get("columns") or []]
        for row in results.get("data") or []:
            for name, value in zip(columns, row):
                if name in _JOB_COLUMNS and isinstance(value, str) and value:
                    return value
        raise ValueError("detached statement did not return a job id")

    def _rest(self, path: str) -> httpx.Response:
        if not self._rest_url:
            raise ValueError("flink rest url is not configured")
        response = self._client.get("%s%s" % (self._rest_url, path))
        response.raise_for_status()
        return response

    def job_status(self, job_id: str) -> JobStatus:
        payload = self._rest("/jobs/%s" % job_id).json()
        state = (payload.get("state") or "").upper()
        return _STATUS.get(state, JobStatus.UNKNOWN)

    def cancel(self, job_id: str) -> None:
        if not self._rest_url:
            raise ValueError("flink rest url is not configured")
        response = self._client.patch(
            "%s/jobs/%s?mode=cancel" % (self._rest_url, job_id))
        response.raise_for_status()

    def savepoint(self, job_id: str, target_dir: str = "",
                  stop: bool = False) -> dict:
        if not self._rest_url:
            raise ValueError("flink rest url is not configured")
        body = {"cancel-job": bool(stop)}
        if target_dir:
            body["target-directory"] = target_dir
        response = self._client.post(
            "%s/jobs/%s/savepoints" % (self._rest_url, job_id), json=body)
        response.raise_for_status()
        trigger = response.json().get("request-id") or ""
        status, location = "", ""
        for _ in range(self._max_polls):
            poll = self._client.get(
                "%s/jobs/%s/savepoints/%s" % (self._rest_url, job_id, trigger))
            poll.raise_for_status()
            payload = poll.json()
            status = ((payload.get("status") or {}).get("id") or "").upper()
            location = (payload.get("operation") or {}).get("location") or ""
            if status and status != "IN_PROGRESS":
                break
            time.sleep(0.2)
        return {"trigger_id": trigger, "status": status,
                "location": location}
