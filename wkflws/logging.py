import enum
import logging
from logging import getLogger as _getLogger
import logging.config
import re
from typing import Any, Optional

from wkflws.conf import settings


class LogLevel(int, enum.Enum):
    """A convient namespaced list of possible log levels.

    An nicer alternative to doing something like:

    .. code-block:: python

       from wkflws.logging import DEBUG
       from wkflws.logging import DEBUG as LOG_LEVEL_DEBUG
    """

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    WARN = logging.WARN
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


#: Defines the pattern for the log messages emitted by rdkafka
RE_RDKAFKA_CONSUMER = re.compile(r".*#(producer|consumer)-\d+")

# from uvicorn.logging import AccessFormatter
LOG_FORMAT: str = (
    "%(levelname)s | %(asctime)s | pid:%(process)d | %(name)s | %(message)s"
)
LOGGING: dict[str, Any] = {
    "loggers": {
        "": {
            "level": "WARNING",
            "handlers": [
                "console",
            ],
        },
        "asyncio": {
            "level": "ERROR",
            "handlers": [
                "console",
            ],
            "propagate": False,
        },
        # "uvicorn": {
        #     "level": "WARNING",
        #     "handlers": [
        #         "console",
        #     ],
        #     "propagate": False,
        # },
        # "uvicorn.access": {
        #     "level": "INFO",
        #     "handlers": [
        #         "console",
        #     ],
        #     "propagate": False,
        # },
        # "gunicorn": {
        #     "level": "INFO",
        #     "handlers": [
        #         "console",
        #     ],
        #     "propagate": False,
        # },
    }
}


class ColorizedFormatter(logging.Formatter):
    """A simple log formatter with colors."""

    COLOR_RESET = "\u001b[0m"

    @staticmethod
    def get_level_color(levelno: int) -> str:
        """Calculate the color based on the log level.

        Args:
            levelno: the log level number.

        Returns:
            A terminal escape sequence for the color.
        """
        if levelno <= 10:
            # DEBUG
            return "\u001b[38;5;14m"
        elif levelno <= 20:
            # INFO
            return "\u001b[38;5;27m"
        elif levelno <= 30:
            # WARNING
            return "\u001b[38;5;214m"
        elif levelno <= 40:
            # ERROR
            return "\u001b[38;5;9m"
        else:
            # CRITICAL
            return "\u001b[38;5;124m"

    def format(self, record):
        """Format the record based on color preferences.

        Args:
            record: The log record to format.
        """
        if (
            len(record.args) > 1
            and isinstance(record.args[1], str)
            and (
                record.args[1].startswith("rdkafka")
                or RE_RDKAFKA_CONSUMER.match(record.args[1])
            )
        ):
            # Special handling for logs that come from the c library.
            record.msg = f"[RDKAFKA] {record.msg}" % record.args
            record.args = ()

        elif len(record.args) > 1:
            record.msg = f"{record.msg}" % record.args
            record.args = ()

        if not settings.NO_COLOR:
            record.levelname = "{}{:8}{}".format(
                self.get_level_color(record.levelno),
                record.levelname,
                self.COLOR_RESET,
            )

        return super().format(record)


config = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "colorized": {
            "format": LOG_FORMAT,  # settings.LOG_FORMAT
            "()": ColorizedFormatter,
        },
        # "access": {
        # UVICorn
        #     "()": AccessFormatter,
        # },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "colorized",
            "stream": "ext://sys.stderr",
        },
        # "access": {
        #     "class": "logging.StreamHandler",
        #     "formatter": "access",
        #     "stream": "ext://sys.stdout",
        # },
    },
}
config.update(LOGGING)  # settings.LOGGING

logging.config.dictConfig(config)

logger = _getLogger("wkflws")


def getLogger(name: Optional[str]) -> logging.Logger:
    """Create and return a logger.

    This function will copy the log level set on the main logger by the command line
    arguments.

    Args:
        name: The name of the logger.

    Returns:
        An object suitable for logging
    """
    new_logger = _getLogger(name)
    new_logger.setLevel(logger.getEffectiveLevel())
    return new_logger
