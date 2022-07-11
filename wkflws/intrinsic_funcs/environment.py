from typing import Any, Dict, Optional

from .token import Token
from ..utils.jsonpath import get_jsonpath_value

# Our runtime error class shadows the built-in RuntimeError exception.
BuiltinRuntimeError = RuntimeError  # type: ignore
from .exceptions import RuntimeError  # noqa


class Environment:
    """Contains the interpreter environment for an intrisnic function.

    While this doesn't support user defintions (functions or variables) in theory it
    could by creating ``var``/``def`` statements which register their definitions here
    when being interpreted.
    """

    #: Holds definitions made by the system.
    system_defaults: Dict[str, Any] = {}

    def __init__(
        self,
        *,
        func_input_json: Optional[Dict[str, Any]] = None,
        context_json: Optional[Dict[str, Any]] = None,
    ):
        self.values: Dict[str, Any] = {}
        self.values.update(self.system_defaults)

        self.func_input_json = func_input_json or {}
        self.context_json = context_json or {}

    @classmethod
    def define_system_default(cls, name: str, value: Any):
        """Add ``name`` to the system defaults with value ``value``.

        This function will not add ``name`` to an existing environment. It will only
        apply to newly created environments.

        Args:
            name: the name to reference ``value`` by.
            value: the value to store.

        Raises:
            KeyError: The provided name has already been assigned.
        """
        if name in cls.system_defaults:
            raise KeyError(
                f"Name `{name}` already registered as system default. Try another name"
            )

        if name.startswith("$"):
            raise ValueError(
                "Do not define values beginning with $ as they are JSON path values."
            )

        cls.system_defaults[name] = value

    def define(self, name: str, value: Any):
        """Add ``name`` to the environment with value ``value``.

        .. warning::

           This method is currently unsupported.

        Note: This operation will overwrite any existing ``name`` with the new value
        ``value`` as it is meant for ``var variable = 1`` style operations.

        Args:
            name: the name to reference ``value`` by.
            value: the value to store.
        """
        raise NotImplementedError("There is currently no definition syntax for wkflws")

        # if name.startswith("$"):
        #     This should probably accept a token so a RuntimeError can be used.
        #     raise ValueError(
        #         "Do not define values beginning with $ as they are JSON path values."
        #     )
        # self.values[name] = value

    def assign(self, name: Token, value: Any):
        """Add ``name`` to the environment with value ``value``.

        .. warning::

           This method is currently unsupported.

        This operation is meant for ``variable = 1; variable = 2`` style operations as
        it will raise an exception if assignment is performed on a non-existant
        ``name``.

        Args:
            name: the Token to store the value for.
            value: the value to store.

        Raises:
            RuntimeWarning: ``name`` has already been assigned to a value.
        """
        raise NotImplementedError("There is currently no definition syntax for wkflws")
        # if name.lexeme not in self.values:
        #     raise RuntimeError(name, f"Undefined variable '{name.lexeme}'.")
        # self.values[name] = value

    def get(self, name: Token) -> Any:
        """Retrieve the value stored for a token.

        Args:
            The token to get the value for.

        Returns:
            The value stored at ``name``.
        """
        if name.lexeme.startswith("$"):
            return self._get_jsonpath_value(name)
        else:
            return self._get_environment_value(name)

    def _get_environment_value(self, name: Token) -> Any:
        if name.lexeme in self.values:
            return self.values[name.lexeme]
        else:
            raise RuntimeError(name, f"Undefined identifier '{name.lexeme}'.")

    def _get_jsonpath_value(self, name: Token) -> Any:
        try:
            if name.lexeme.startswith("$$"):
                values = get_jsonpath_value(self.context_json, name.lexeme[1:])
            else:
                values = get_jsonpath_value(self.func_input_json, name.lexeme)
        except ValueError:
            raise RuntimeError(
                name, f"JSON path selector value not found '{name.lexeme}'."
            ) from None

        return values
