from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union


class http_method(str, Enum):
    """Describes HTTP methods."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class Request:
    """Represents an HTTP request."""

    #: The requested url
    url: str
    #: HTTP Headers from the request. Note: all header keys are converted to lower
    #: case.
    headers: dict[str, str]
    body: str


@dataclass
class Response:
    """Represent an HTTP response."""

    # HTTP Headers to include with the response
    headers: Optional[dict[str, str]] = None
    body: Union[bytes, str, None] = None
    status_code: int = 204
