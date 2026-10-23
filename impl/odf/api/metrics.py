import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.settings import get_settings

router = APIRouter()
START = time.time()

REQUESTS = {}
LATENCY = {"sum": 0.0, "count": 0}
COUNTERS = {}
HISTOGRAMS = {}
BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0,
           10.0)
EXCLUDED = ("/metrics", "/livez", "/readyz", "/healthz", "/docs",
            "/redoc", "/openapi.json", "/ui", "/assets")


def inc(name, **labels):
    key = (name, tuple(sorted(labels.items())))
    COUNTERS[key] = COUNTERS.get(key, 0) + 1


def record(method: str, path: str, status: int, seconds: float) -> None:
    key = (method, path, str(status))
    REQUESTS[key] = REQUESTS.get(key, 0) + 1
    LATENCY["sum"] += seconds
    LATENCY["count"] += 1
    hist = HISTOGRAMS.setdefault(
        (method, path), {"buckets": [0] * len(BUCKETS),
                         "sum": 0.0, "count": 0})
    for i, bound in enumerate(BUCKETS):
        if seconds <= bound:
            hist["buckets"][i] += 1
            break
    hist["sum"] += seconds
    hist["count"] += 1


def _label(value) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace(
        "\n", " ")


def _queue_gauges(session: Session):
    from odf.models import Alert, Job, WebhookDelivery
    out = []
    for status, count in (session.query(Job.status, func.count())
                          .group_by(Job.status).all()):
        out.append(('odf_queue_depth{status="%s"}' % _label(status),
                    count))
    pending = (session.query(func.count())
               .select_from(WebhookDelivery)
               .filter(WebhookDelivery.status == "pending").scalar())
    out.append(("odf_webhook_pending", pending or 0))
    opened = (session.query(func.count()).select_from(Alert)
              .filter(Alert.status == "open").scalar())
    out.append(("odf_alerts_open", opened or 0))
    return out


def _pool_gauges():
    from odf.db import engine
    out = []
    for metric, method in (("size", "size"), ("checked_in", "checkedin"),
                           ("checked_out", "checkedout"),
                           ("overflow", "overflow")):
        try:
            value = getattr(engine.pool, method)()
        except Exception:
            continue
        out.append(("odf_db_pool_%s" % metric, value))
    return out


@router.get("/metrics", response_class=PlainTextResponse)
def metrics(s: Session = Depends(get_session)):
    settings = get_settings()
    if not settings.metrics_enabled:
        raise HTTPException(404, "metrics disabled")
    lines = ["# HELP odf_build_info Build information",
             "# TYPE odf_build_info gauge",
             'odf_build_info{version="1.0.0"} 1',
             "# HELP odf_uptime_seconds Process uptime",
             "# TYPE odf_uptime_seconds gauge",
             "odf_uptime_seconds %.3f" % (time.time() - START),
             "# HELP odf_otel_enabled OpenTelemetry tracing enabled",
             "# TYPE odf_otel_enabled gauge",
             "odf_otel_enabled %d" % (1 if settings.otel_enabled else 0),
             "# HELP odf_requests_total Total HTTP requests",
             "# TYPE odf_requests_total counter"]
    for (method, path, status), n in sorted(REQUESTS.items()):
        lines.append(
            'odf_requests_total{method="%s",path="%s",status="%s"} %d'
            % (_label(method), _label(path), _label(status), n))
    lines += ["# HELP odf_request_duration_seconds Request duration",
              "# TYPE odf_request_duration_seconds histogram"]
    for (method, path), hist in sorted(HISTOGRAMS.items()):
        cumulative = 0
        for bound, count in zip(BUCKETS, hist["buckets"]):
            cumulative += count
            lines.append(
                'odf_request_duration_seconds_bucket{method="%s",path="%s",'
                'le="%s"} %d' % (_label(method), _label(path), bound,
                                 cumulative))
        lines.append(
            'odf_request_duration_seconds_bucket{method="%s",path="%s",'
            'le="+Inf"} %d' % (_label(method), _label(path), hist["count"]))
        lines.append(
            'odf_request_duration_seconds_sum{method="%s",path="%s"} %f'
            % (_label(method), _label(path), hist["sum"]))
        lines.append(
            'odf_request_duration_seconds_count{method="%s",path="%s"} %d'
            % (_label(method), _label(path), hist["count"]))
    for (name, labels), value in sorted(COUNTERS.items()):
        label_text = ",".join('%s="%s"' % (k, _label(v))
                              for k, v in labels)
        suffix = "{%s}" % label_text if label_text else ""
        lines.append("odf_%s%s %d" % (name, suffix, value))
    lines += [
        "# HELP odf_request_seconds_sum Total request seconds",
        "# TYPE odf_request_seconds_sum counter",
        "odf_request_seconds_sum %f" % LATENCY["sum"],
        "# HELP odf_request_seconds_count Request count",
        "# TYPE odf_request_seconds_count counter",
        "odf_request_seconds_count %d" % LATENCY["count"],
        "# HELP odf_db_pool_size Database connection pool",
        "# TYPE odf_db_pool_size gauge",
    ]
    gauges = _pool_gauges()
    try:
        gauges += _queue_gauges(s)
    except Exception:
        lines.append("odf_metrics_db_error 1")
    for name, value in gauges:
        lines.append("%s %s" % (name, value))
    return PlainTextResponse(
        "\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4; charset=utf-8")
