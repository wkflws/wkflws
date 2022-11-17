from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Optional, Mapping


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
    # This indicates we don't have the libraries installed, thus disable tracing.
    trace: Optional[Any] = None  # type:ignore # already defined by import


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

    This should be called once sometime during startup.
    """
    from .conf import settings  # prevent circular import due to model validation
    from .logging import logger  # prevent circular import

    if (
        not trace
        or settings.TRACING_EXPORTERS is None
        or len(settings.TRACING_EXPORTERS) < 1
    ):
        return

    logger.debug("Initializing tracing...")
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


def get_tracer(*args, **kwargs) -> Any:
    """Get a tracer that can be used if tracing is enabled."""

    from .conf import settings  # prevent circular import due to model validation

    if trace is not None:
        return trace.get_tracer(settings.TRACING_RESOURCE_NAME, *args, *kwargs)
    else:
        return pretendtracer()


def get_span_context(
    carrier: Optional[Mapping[str, str]] = None,
) -> Optional[trace.SpanContext]:  # type:ignore # trace may be None
    """Attempt to load trace info from a carrier which can be used to resume a trace.

    Args:
        carrier: A mapping which may contain information (trace_id, span_id, trace
            flags) about a trace. For example: event metadata, http headers, etc.
    """
    if not carrier:
        return None

    # ignore the type because introspection says this returns a Context but
    # we expect a SpanContext
    return TraceContextTextMapPropagator().extract(carrier=carrier)  # type:ignore


def inject_span_context(carrier: Mapping[str, Any]):
    """Injects the span context into the provided mapping."""
    TraceContextTextMapPropagator().inject(carrier)


class pretendtracer:
    """Class to accept anything and return nothing when tracing has not been enabled."""

    def fake_func(self, *args, **kwargs):
        """You can't fake the funk.

        Wait, we just did.
        """
        return

    def __getattr__(self, name):
        return self.fake_func

    def __setattr__(self, name, value):
        return
