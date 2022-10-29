from contextlib import contextmanager
from dataclasses import dataclass
import enum
from typing import Any, Optional, Mapping

# Maybe the actual tracer as a global so it can be conditionally checked by the custom
# context manager. Marked as Optional[Any] so we don't have to force the installation of
# the open telemetry libraries.
_tracer: Optional[Any] = None

# Tracks if an attempt has been made to inititalize the tracer. If this is True and
# `_tracer` is None then it is safe to consider tracing as disabled.
_tracer_initialized = False

try:
    # Try to import the optional opentelemetry libraries. If they aren't installed then
    # short circuit the initialization which results in the mock tracer being sent to
    # any traces defined in the code.
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter as OTLPGRPCSpanExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter as OTLPHTTPSpanExporter,
    )
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SpanExporter,
    )
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )
except ImportError:
    _tracer_initialized = True

# The tracer for devs to use. This will conditionally return the above real tracer if
# everything is set up properly, otherwise it returns a mock resulting in no-ops for
# tracing.
class Tracer:
    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        *args,
        carrier: Optional[Mapping[str, str]] = None,
        **kwargs,
    ):
        """Context manager for collecting traces to be sent to a collector.

        Args:
            carrier: A key/value (e.g. dict) store that may contain trace context
                information (trace id,span id,span flags)that can be used to "resume"
                a trace.
        """

        # used to resume spans across boundaries
        span_context: Optional[trace.SpanContext] = None

        if not _tracer_initialized:
            initialize_tracer()
            if carrier:
                # ignore the type because introspection says this returns a Context but
                # we expect a SpanContext
                span_context = TraceContextTextMapPropagator().extract(  # type:ignore
                    carrier=carrier,
                )

        if _tracer is not None:
            if span_context is not None and "context" not in kwargs:
                # if there was a carrier we can include the span so traces resume
                kwargs["context"] = span_context

            with _tracer.start_as_current_span(name, *args, **kwargs) as span:
                yield span
        else:
            yield pretendtracer()


tracer = Tracer()


class TraceScheme(str, enum.Enum):
    """Define supported schemes/export types.

    This is used as validation when reading environment and other configuration values.
    """

    # Note: the + is replaced with _ when dynamically selecting by key so ensure the
    # chosen name is compatible.
    otlp_https = "otlp+https"
    otlp_http = "otlp+http"
    otlp_grpc = "otlp+grpc"
    console = "console"


@dataclass
class TracerConfig:
    """Define configuration for a trace collector/exporter."""

    scheme: TraceScheme
    host: str
    username: Optional[str]
    password: Optional[str]
    secure: bool


def initialize_tracer():
    """Initialize the tracer with any exporters configured.

    This should be called once sometime during startup. If it is not pre-emptively
    called, then it will be called on first use of the ``tracer``.
    """
    from .conf import settings  # prevent circular import due to model validation

    global _tracer_initialized, _tracer

    if _tracer_initialized:
        return

    if settings.TRACING_EXPORTERS is None or len(settings.TRACING_EXPORTERS) < 1:
        _tracer_initialized = True
        return

    resource = Resource(attributes={SERVICE_NAME: settings.TRACING_RESOURCE_NAME})
    trace_provider = TracerProvider(resource=resource)
    exporter: Optional[SpanExporter] = None

    for tracer_config in settings.TRACING_EXPORTERS:
        if tracer_config.scheme == TraceScheme.console:
            exporter = ConsoleSpanExporter()
        elif tracer_config.scheme in (TraceScheme.otlp_http, TraceScheme.otlp_https):
            if tracer_config.scheme == TraceScheme.otlp_https:
                scheme = "https"
            else:
                scheme = "http"

            exporter = OTLPHTTPSpanExporter(
                endpoint=f"{scheme}://{tracer_config.host}",
            )
        elif tracer_config.scheme == TraceScheme.otlp_grpc:
            exporter = OTLPGRPCSpanExporter(
                endpoint=tracer_config.host,
                insecure=(not tracer_config.secure),
            )
        else:
            raise ValueError(
                f"{tracer_config.scheme} is not a supported tracer scheme."
                f'[{",".join(TraceScheme)}]'
            )

        trace_provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(trace_provider)

    _tracer = trace.get_tracer(settings.TRACING_RESOURCE_NAME)


class pretendtracer:
    """Class to accept anything and return nothing when tracing has not been enabled."""

    def fake_func(self, *args, **kwargs):
        """You can't fake the funk.

        Wait, we just did.
        """
        return

    def __getattr__(self, name):
        return self.fake_func

    def __setattr(self, name, value):
        return
