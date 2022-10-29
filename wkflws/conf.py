from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING
from urllib.parse import urlparse, parse_qs

from pydantic import BaseSettings as _BaseSettings, Field, validator

from .tracing import TracerConfig, TraceScheme
from .utils.coercion import coerce_bool


class Settings(_BaseSettings):
    """System-wide settings."""

    #: Host to Kafka broker
    KAFKA_HOST: Optional[str] = None
    #: Port for Kafka broker.
    KAFKA_PORT: int = 9092
    #: Username to Kafka broker.
    KAFKA_USERNAME: Optional[str] = None
    #: Password to Kafka broker.
    KAFKA_PASSWORD: Optional[str] = None

    #: Disable colorful logs (https://no-color.org)
    NO_COLOR: bool = Field(False, env="NO_COLOR")

    #: Define the class which looks up state-language workflows to execute based on an
    #: Event.
    WORKFLOW_LOOKUP_CLASS: str = "wkflws.lookup.filesystem.FileSystemLookup"

    #: Define the class to use when executing nodes.
    EXECUTOR_CLASS: str = "wkflws.executors.mp.MultiProcessExecutor"

    #: Tracing resource name. This is used by some exporters (Jaeger).
    TRACING_RESOURCE_NAME: str = "wkflws"

    #: Optional list of hosts to send traces to. For example:
    #: otlp+http://localhost:4317?secure=false,otlp+grpc://remote.com:4317?secure=true
    TRACING_EXPORTERS: Optional[list[TracerConfig]] = None

    @validator("TRACING_EXPORTERS", each_item=True, pre=True)
    def validate_tracing_exporters(cls, value: str):
        """Validate the entries for tracing exporters."""
        parts = urlparse(value)

        if parts.scheme not in TraceScheme.__members__.values():
            raise ValueError(
                f"{value} does not define a valid scheme: " f'[{",".join(TraceScheme)}]'
            )

        if "@" in parts.netloc:
            user_pass, hostname = parts.netloc.split("@")
            username, password = user_pass.split(":")
        else:
            hostname = parts.netloc
            username = None
            password = None

        options = parse_qs(parts.query)

        return TracerConfig(
            scheme=TraceScheme[parts.scheme.replace("+", "_")],
            host=hostname,
            username=username,
            password=password,
            secure=coerce_bool(options["secure"]) if "secure" in options else True,
        )

    class Config:
        """Global configuration for settings."""

        env_prefix = "WKFLWS_"
        case_sensitve = True

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> Any:
            """Parse environment variables to their custom type."""
            if field_name == "TRACING_EXPORTERS":
                return list(host for host in raw_val.split(","))
            return cls.json_loads(raw_val)  # type:ignore # json_loads undefined


Settings.update_forward_refs()
settings = Settings()  # pyright: ignore
