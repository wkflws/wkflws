class WkflwException(Exception):
    """Generic exception."""


class WkflwConfigurationException(WkflwException):
    """Indicates a configuration error.

    This can be corrected by a developer.
    """


class WkflwKafkaException(WkflwException):
    """An exception has occurred in Kafka."""


class WkflwExecutionException(WkflwException):
    """An exception occurred while executing the workflow."""


class WkflwExecutionAlreadyStartedError(WkflwExecutionException):
    """The workflow is unable to be started because it is already running."""


class WkflwStateError(WkflwExecutionException):
    """An error occured with the state."""


class WkflwStateNotFoundError(WkflwStateError):
    """The state with the requested name was not found."""
