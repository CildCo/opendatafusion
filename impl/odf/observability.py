from odf.settings import get_settings

_configured = False


def _instrument_sql(engine, tracer=None):
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind
    from sqlalchemy import event
    tracer = tracer or trace.get_tracer("odf.sqlalchemy")

    def before(conn, cursor, statement, parameters, context, executemany):
        span = tracer.start_span("db.query", kind=SpanKind.CLIENT)
        span.set_attribute("db.system", engine.dialect.name)
        span.set_attribute("db.statement", statement[:1000])
        context._odf_otel_span = span

    def after(conn, cursor, statement, parameters, context, executemany):
        span = getattr(context, "_odf_otel_span", None)
        if span is not None:
            span.end()
            context._odf_otel_span = None

    def error(conn, cursor, statement, parameters, context, exception):
        span = getattr(context, "_odf_otel_span", None)
        if span is not None:
            span.record_exception(exception)
            span.end()
            context._odf_otel_span = None

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)
    event.listen(engine, "handle_error", error)


def configure_observability(app) -> bool:
    global _configured
    settings = get_settings()
    if not settings.otel_enabled:
        return False
    if _configured:
        return True
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter)
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    except ImportError as e:
        raise RuntimeError(
            "ODF_OTEL_ENABLED requires the 'otel' extra") from e
    from odf.db import engine
    provider = TracerProvider(
        resource=Resource.create(
            {"service.name": settings.otel_service_name}),
        sampler=TraceIdRatioBased(settings.otel_sample_ratio))
    provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=settings.otel_endpoint)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    _instrument_sql(engine)
    _configured = True
    return True
