from decimal import Decimal, ROUND_HALF_UP
import json
from typing import Any, List, Optional, TYPE_CHECKING

from .environment import Environment
from .intrinsic_callable import IntrinsicCallable

if TYPE_CHECKING:
    from .interpreter import Interpreter


def register(*, name: str, arity: Optional[int]):
    """Register a Python function as an intrinsic function callable by the user.

    Args:
        name: The function name users can call this function by. For example
            ``States.Format``.
        arity: The number of arguments the function accepts where ``None`` is unbound
            for functions such as string formatting..
    """

    def decorator(func):
        def wrapper(*args: object):
            return func(*args)

        class f(IntrinsicCallable):
            def arity(self) -> Optional[int]:
                return arity

            def call(self, interpreter: "Interpreter", arguments: List[Any]) -> Any:
                return wrapper(*arguments)

        Environment.define_system_default(name, f())

        return wrapper

    return decorator


@register(name="States.Format", arity=None)
def format_string(template: str, *args: object) -> str:
    """Format a string.

    This function implements the ``States.Format`` function.
    """
    return template.format(*args)


@register(name="States.StringToJson", arity=1)
def str_to_json(value: str) -> Any:
    """Deserialize a JSON string into a data structure.

    Args:
        value: The serialized JSON value to process.
    """
    return json.loads(value)


@register(name="States.JsonToString", arity=1)
def json_to_str(value: Any) -> str:
    """Serialize a JSON into a string.

    Args:
        value: The JSON value to process.
    """
    return json.dumps(value)


@register(name="States.Array", arity=None)
def array_create(*values: Any) -> tuple[Any, ...]:
    """Return a JSON array containing the values of the arguments in the order.

    Args:
        values: The values to include in the array
    """
    return values


@register(name="Array.Append", arity=None)
def array_append(array: tuple[Any, ...], *values: Any) -> tuple[Any, ...]:
    """Append n number of values to an array.

    Args:
        array: The original array to modify.
        values: The value(s) to append to ``array``.
    """
    array += values
    return array


@register(name="Array.Join", arity=2)
def array_join(join_val: str, array: tuple[Any, ...]) -> str:
    r"""Join all values of an array with the given join_val.

    Args:
        join_val: the value to join the array by. (e.g. ``,`` or ``\n``.)
        array: The array containing the values you wish to join.
    """
    return join_val.join(array)


@register(name="String.Trim", arity=1)
def string_trim(value: str) -> str:
    """Trim all whitespace at the beginning and end of the string."""
    return value.strip()


@register(name="Cast.ToNumber", arity=1)
def to_number(value: str) -> Decimal:
    """Typecast a string to a number."""
    return Decimal(value)


@register(name="Format.Currency", arity=2)
def format_currency(value: Decimal, currency: str) -> str:
    """Format monetary value to the requested currency.

    For example ``Format.Currency("10.999", "USD")`` would return ``$10.99``.
    """

    def quantize(n: Decimal, places: int = 2, mode: str = ROUND_HALF_UP) -> Decimal:
        """Accurately round a ``Decimal``.

        By default this function will round ``n`` to 2 decimal places, suitable
        for most currencies.

        Args:
           n: The number to round.
           places: The number of decimal places to round to. *Default is 2*
           mode: Rounding strategy. *Default is ROUND_HALF_UP*

        Raises:
           decimal.InvalidOperation: The rounding precision requested is
                greater than the value provided.

        Returns:
            The rounded value
        """
        exp = Decimal(10) ** -places

        if not isinstance(n, Decimal):
            n = Decimal(n)

        return n.quantize(exp, rounding=mode)

    value = quantize(value)
    if currency in ("USD", "$"):
        return f"${value}"
    else:
        return f"{value} {currency}"
