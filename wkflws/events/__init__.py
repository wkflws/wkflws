"""Describes raw events produced by a trigger node

When a trigger node's listener recieves an arbitrary payload from a source it must
return an :class:`Event` with the data as in-tact as possible.
"""
from dataclasses import asdict, dataclass, field
import json
from typing import Any, Union


def _json_default_factory() -> dict[str, Any]:
    # used for the type checker
    return {}


@dataclass
class Event:
    """Represents data that should be published to the event bus."""

    #: This is the identifier of the event. If it is not provided one will be
    #: generated. This can be used for tracing log messages. (Maps to Kafka key)
    identifier: str
    #: A dictionary containing metadata about the event.
    metadata: dict[str, Any] = field(default_factory=dict)
    #: A JSON serializable value containing the payload of the event.
    data: Union[list[dict[str, Any]], dict[str, Any]] = field(
        default_factory=_json_default_factory
    )

    def asdict(self) -> dict[str, Any]:
        """Create a dictionary representation of this object."""
        return asdict(self)

    def asjson(self) -> str:
        """Create a JSON representation of this object."""
        return json.dumps(self.asdict())


@dataclass
class Result:
    """Describes the result of a successfully produced event."""

    key: bytes
    offset: int
    latency: float
    topic: str
    message: bytes


# from dataclasses import dataclass
# from typing import Any, Dict, Optional


# Older idea:
# @dataclass
#
# class Message:
#     """Represents the a raw message from the message bus."""

#     id: str
#     source: str
#     time: str
#     metadata: Dict[str, Any]
#     data: bytes
#     version: int = 1


# def envelope_message(self, payload: bytes, metadata: Optional[Dict[str, Any]]):
#     """Wrap the provided payload in a standard envelope."""
