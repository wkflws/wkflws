from .token import Token


class RuntimeError(Exception):
    """Represents an error when the interpreter encounters an unrecoverable error."""

    def __init__(self, token: Token, message: str, *args: object):
        """Construct the error.

        Args:
            token: The token the interpreter was on when the error occured.
            message: The error message to display.
        """
        self.token = token
        self.message = message

        super().__init__(message, *args)
