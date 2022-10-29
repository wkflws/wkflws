# wkflws

## Configuration
| name | required | description |
|-|-|-|
| `WKFLWS_WORKFLOW_LOOKUP_CLASS` | ❌ | A helper class to returns workflows that should be executed. *Default is filesystem lookup* |
| `WKFLWS_EXECUTOR_CLASS`        | ❌ | Defines the node executor method. *Default is the multiprocess executor* |
| `WKFLWS_KAFKA_HOST`            | ❌ | Hostname for the Kafka broker. |
| `WKFLWS_KAFKA_PORT`            | ❌ | Port for the Kafka broker *Default is 9092* |
| `WKFLWS_KAFKA_USERNAME`        | ❌ | If needed, username for connecting to the Kafka broker. |
| `WKFLWS_KAFKA_PASSWORD`        | ❌ | If needed, password to the Kafka broker. |

### Telemetry Configuration
The wkflws framework has first class support for Open Telemetry. By default telemetry is disabled but you can
use the following configuration values to enable it.

| name | description |
| - | - |
| `WKFLWS_TRACING_EXPORTERS` | Exporters to send traces to. This is a CSV list of hosts. Example: oltp+https://localhost:4317. Supported schemes: `otlp+https,otlp+http,otlp+grpc,console` |
| `WKFLWS_TRACING_RESOURCE_NAME` | The resource name to use for traces. Used by some exporters, such as Jaeger. *Default is wkflws* |
