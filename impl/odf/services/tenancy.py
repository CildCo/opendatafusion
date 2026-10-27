import threading

import httpx

from odf.settings import get_settings

SPARK_SERVICE_ACCOUNT = "spark-operator-spark"
_created = set()
_lock = threading.Lock()


def project_namespace(project_id: int, settings=None) -> str:
    settings = settings or get_settings()
    prefix = (getattr(settings, "k8s_tenancy_prefix", "") or "odf").strip("-")
    return "%s-p%d" % (prefix, int(project_id))


def namespace_for_project(project_id: int, settings=None) -> str | None:
    settings = settings or get_settings()
    if not getattr(settings, "k8s_tenancy_enabled", False):
        return None
    return project_namespace(project_id, settings)


def reset_cache() -> None:
    with _lock:
        _created.clear()


class KubernetesAdmin:
    def __init__(self, base_url, token, client=None, ca_file=None,
                 timeout=10.0):
        self._headers = {"Authorization": "Bearer " + token,
                         "Accept": "application/json"}
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), headers=self._headers,
            verify=ca_file or True, timeout=timeout)

    @classmethod
    def from_settings(cls, settings) -> "KubernetesAdmin":
        return cls(settings.k8s_api_url, settings.k8s_token,
                   ca_file=settings.k8s_ca_file or None)

    def _post(self, path: str, body: dict) -> None:
        response = self._client.post(path, json=body, headers=self._headers)
        if response.status_code == 409:
            return
        response.raise_for_status()

    def ensure_namespace(self, name: str) -> None:
        self._post("/api/v1/namespaces", {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {"name": name,
                         "labels": {"app.kubernetes.io/managed-by": "odf"}},
        })

    def ensure_quota(self, namespace: str, cpu: str, memory: str,
                     pods: int) -> None:
        self._post("/api/v1/namespaces/%s/resourcequotas" % namespace, {
            "apiVersion": "v1",
            "kind": "ResourceQuota",
            "metadata": {"name": "odf-quota", "namespace": namespace},
            "spec": {"hard": {"requests.cpu": str(cpu),
                              "requests.memory": str(memory),
                              "pods": str(int(pods))}},
        })

    def ensure_network_policy(self, namespace: str) -> None:
        self._post(
            "/apis/networking.k8s.io/v1/namespaces/%s/networkpolicies"
            % namespace, {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {"name": "odf-default", "namespace": namespace},
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress"],
                    "ingress": [
                        {"from": [{"podSelector": {}}]},
                        {"from": [{"namespaceSelector": {"matchLabels": {
                            "kubernetes.io/metadata.name":
                                "spark-operator"}}}]},
                    ],
                },
            })

    def ensure_service_account(self, namespace: str, name: str) -> None:
        self._post("/api/v1/namespaces/%s/serviceaccounts" % namespace, {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": name, "namespace": namespace},
        })

    def ensure_role_binding(self, namespace: str, name: str) -> None:
        self._post(
            "/apis/rbac.authorization.k8s.io/v1/namespaces/%s/rolebindings"
            % namespace, {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding",
                "metadata": {"name": "odf-spark", "namespace": namespace},
                "subjects": [{"kind": "ServiceAccount", "name": name,
                              "namespace": namespace}],
                "roleRef": {"apiGroup": "rbac.authorization.k8s.io",
                            "kind": "ClusterRole", "name": "edit"},
            })


def ensure_project_namespace(project_id: int, settings=None,
                             admin: KubernetesAdmin | None = None) -> str:
    settings = settings or get_settings()
    name = project_namespace(project_id, settings)
    with _lock:
        if name in _created:
            return name
    admin = admin or KubernetesAdmin.from_settings(settings)
    admin.ensure_namespace(name)
    admin.ensure_quota(name, settings.k8s_quota_cpu,
                       settings.k8s_quota_memory, settings.k8s_quota_pods)
    admin.ensure_network_policy(name)
    admin.ensure_service_account(name, SPARK_SERVICE_ACCOUNT)
    admin.ensure_role_binding(name, SPARK_SERVICE_ACCOUNT)
    with _lock:
        _created.add(name)
    return name
