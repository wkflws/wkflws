import abc
from typing import Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .interpreter import Interpreter


class IntrinsicCallable(abc.ABC):
    """Represents the callable for an intrinsic function."""

    @abc.abstractmethod
    def arity(self) -> Optional[int]:
        """Return the number of arguments this callable accepts.

        If this method returns ``None`` the the number of arguments is unbound. An
        example of a function which has a variable number of arguments is
        ``States.Format`` where the number of arguments is dependent on the first.
        """
        pass

    @abc.abstractmethod
    def call(self, interpreter: "Interpreter", arguments: List[Any]) -> Any:
        """Execute the callable with the provided arguments returning the result.

        Args:
            interpreter: The interpreter executing this callable.
            arguments: The arguments to pass to this callable.
        """
        pass
