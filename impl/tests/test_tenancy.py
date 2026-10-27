import json
from types import SimpleNamespace

import httpx
import pytest

from odf.services import tenancy


def _settings(**overrides):
    values = dict(
        k8s_api_url="https://k8s.example", k8s_token="tok",
        k8s_namespace="data", k8s_ca_file="",
        k8s_tenancy_enabled=True, k8s_tenancy_prefix="odf",
        k8s_quota_cpu="4", k8s_quota_memory="8Gi", k8s_quota_pods=20,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _admin(handler, calls):
    def wrapped(request):
        calls.append(request)
        return handler(request)

    client = httpx.Client(base_url="https://k8s.example",
                          transport=httpx.MockTransport(wrapped))
    return tenancy.KubernetesAdmin("https://k8s.example", "tok", client=client)


def test_project_namespace_format():
    assert tenancy.project_namespace(7) == "odf-p7"
    assert tenancy.project_namespace(7, _settings(
        k8s_tenancy_prefix="team")) == "team-p7"


def test_namespace_for_project_is_none_when_disabled():
    assert tenancy.namespace_for_project(
        3, _settings(k8s_tenancy_enabled=False)) is None
    assert tenancy.namespace_for_project(3, _settings()) == "odf-p3"


def test_ensure_creates_namespace_quota_policy_and_identity():
    calls = []

    def handler(request):
        return httpx.Response(201, json={})

    admin = _admin(handler, calls)
    tenancy.reset_cache()
    name = tenancy.ensure_project_namespace(5, settings=_settings(), admin=admin)

    assert name == "odf-p5"
    paths = [(c.method, c.url.path) for c in calls]
    assert ("POST", "/api/v1/namespaces") in paths
    assert ("POST", "/api/v1/namespaces/odf-p5/resourcequotas") in paths
    assert ("POST", "/apis/networking.k8s.io/v1/namespaces/odf-p5/"
                    "networkpolicies") in paths
    assert ("POST", "/api/v1/namespaces/odf-p5/serviceaccounts") in paths
    assert ("POST", "/apis/rbac.authorization.k8s.io/v1/namespaces/odf-p5/"
                    "rolebindings") in paths

    quota = [c for c in calls
             if c.url.path.endswith("/resourcequotas")][0]
    body = json.loads(quota.content)
    assert body["spec"]["hard"]["requests.cpu"] == "4"
    assert body["spec"]["hard"]["requests.memory"] == "8Gi"
    assert body["spec"]["hard"]["pods"] == "20"

    sa = [c for c in calls if c.url.path.endswith("/serviceaccounts")][0]
    assert json.loads(sa.content)["metadata"]["name"] == "spark-operator-spark"

    policy = [c for c in calls if c.url.path.endswith("/networkpolicies")][0]
    assert json.loads(policy.content)["spec"]["podSelector"] == {}


def test_ensure_tolerates_existing_objects():
    def handler(request):
        return httpx.Response(409, json={"reason": "AlreadyExists"})

    admin = _admin(handler, [])
    tenancy.reset_cache()
    assert tenancy.ensure_project_namespace(
        6, settings=_settings(), admin=admin) == "odf-p6"


def test_ensure_propagates_other_failures():
    def handler(request):
        return httpx.Response(403, json={"reason": "Forbidden"})

    admin = _admin(handler, [])
    tenancy.reset_cache()
    with pytest.raises(httpx.HTTPStatusError):
        tenancy.ensure_project_namespace(7, settings=_settings(),
                                         admin=admin)


def test_ensure_is_cached_per_namespace():
    calls = []
    admin = _admin(lambda r: httpx.Response(201, json={}), calls)
    tenancy.reset_cache()
    tenancy.ensure_project_namespace(8, settings=_settings(), admin=admin)
    first = len(calls)
    tenancy.ensure_project_namespace(8, settings=_settings(), admin=admin)
    assert len(calls) == first
