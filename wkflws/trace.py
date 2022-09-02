try:
    from opentelemetry import trace
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource

except ImportError:
    raise ImportError("Open Telemetry modules not installed. pip install wkflws[trace]")

resource = Resource(attributes={SERVICE_NAME: "wkflws"})

# https://www.jaegertracing.io/docs/1.19/client-libraries/#emsgsize-and-udp-buffer-limits
# On OS X this probably needs to be done:
# % sysctl net.inet.udp.maxdgram
# net.inet.udp.maxdgram: 9216
# % sudo sysctl net.inet.udp.maxdgram=65536
# net.inet.udp.maxdgram: 9216 -> 65536
# % sudo sysctl net.inet.udp.maxdgram
# net.inet.udp.maxdgram: 65536
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(jaeger_exporter)
provider.add_span_processor(processor)

# set global default trace provider
trace.set_tracer_provider(provider)

# create a tracer from the global trace provider
tracer = trace.get_tracer(__name__)
