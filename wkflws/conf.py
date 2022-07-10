from typing import Optional

from pydantic import BaseSettings as _BaseSettings, Field


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

    class Config:
        """Global configuration for settings."""

        env_prefix = "WKFLWS_"
        case_sensitve = True


settings = Settings()  # type:ignore # pydantic takes care of required variables
