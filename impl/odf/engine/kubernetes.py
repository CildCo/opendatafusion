import httpx

from odf.engine.base import JobSpec, JobStatus

_API_GROUP = "sparkoperator.k8s.io"
_API_VERSION = "v1beta2"

_STATUS = {
    "SUBMITTED": JobStatus.PENDING,
    "RUNNING": JobStatus.RUNNING,
    "COMPLETED": JobStatus.SUCCEEDED,
    "FAILED": JobStatus.FAILED,
    "SUBMISSION_FAILED": JobStatus.FAILED,
}


class KubernetesEngine:
    def __init__(self, base_url: str, token: str, namespace: str = "data",
                 client: httpx.Client | None = None,
                 ca_file: str | None = None, timeout: float = 10.0):
        self.namespace = namespace
        self._headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
        }
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), headers=self._headers,
            verify=ca_file or True, timeout=timeout)

    @classmethod
    def from_settings(cls, settings) -> "KubernetesEngine":
        return cls(
            base_url=settings.k8s_api_url,
            token=settings.k8s_token,
            namespace=settings.k8s_namespace,
            ca_file=settings.k8s_ca_file or None,
        )

    def _path(self, name: str | None = None,
              namespace: str | None = None) -> str:
        ns = namespace or self.namespace
        path = ("/apis/%s/%s/namespaces/%s/sparkapplications"
                % (_API_GROUP, _API_VERSION, ns))
        return path if name is None else path + "/" + name

    def submit(self, spec: JobSpec) -> str:
        driver = {
            "cores": spec.driver_cores,
            "memory": spec.driver_memory,
            "serviceAccount": spec.service_account,
        }
        executor = {
            "cores": spec.executor_cores,
            "instances": spec.executor_instances,
            "memory": spec.executor_memory,
            "serviceAccount": spec.service_account,
        }
        if spec.volume_mounts:
            driver["volumeMounts"] = [dict(m) for m in spec.volume_mounts]
            executor["volumeMounts"] = [dict(m) for m in spec.volume_mounts]
        body = {
            "apiVersion": "%s/%s" % (_API_GROUP, _API_VERSION),
            "kind": "SparkApplication",
            "metadata": {"name": spec.name,
                         "namespace": spec.namespace or self.namespace},
            "spec": {
                "type": "Python",
                "pythonVersion": "3",
                "mode": "cluster",
                "image": spec.image,
                "mainApplicationFile": spec.main_application_file,
                "arguments": list(spec.args),
                "sparkVersion": spec.spark_version,
                "driver": driver,
                "executor": executor,
                "sparkConf": dict(spec.spark_conf),
            },
        }
        if spec.volumes:
            body["spec"]["volumes"] = [dict(v) for v in spec.volumes]
        response = self._client.post(
            self._path(namespace=spec.namespace), json=body,
            headers=self._headers)
        response.raise_for_status()
        return response.json().get("metadata", {}).get("name", spec.name)

    def status(self, name: str, namespace: str | None = None) -> JobStatus:
        response = self._client.get(
            self._path(name, namespace), headers=self._headers)
        response.raise_for_status()
        state = (response.json().get("status", {})
                 .get("applicationState", {}).get("state", ""))
        return _STATUS.get(state, JobStatus.UNKNOWN)

    def cancel(self, name: str, namespace: str | None = None) -> None:
        response = self._client.delete(
            self._path(name, namespace), headers=self._headers)
        response.raise_for_status()

    def result(self, name: str, namespace: str | None = None) -> dict:
        response = self._client.get(
            self._path(name, namespace), headers=self._headers)
        response.raise_for_status()
        payload = response.json().get("status", {})
        state = payload.get("applicationState", {})
        return {"state": state.get("state", ""),
                "error": state.get("errorMessage", "") or "",
                "attempts": payload.get("executionAttempts", 0)}
