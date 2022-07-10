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
