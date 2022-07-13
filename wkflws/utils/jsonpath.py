from copy import deepcopy
from typing import Any, Optional, Union

from jsonpath_ng.jsonpath import (  # type:ignore # no stubs
    Child as _Child,
    DatumInContext,
    Root as _Root,
    Slice as _Slice,
)
from jsonpath_ng.parser import parse  # type:ignore # no stubs


def get_jsonpath_value(
    data: dict[str, Any],
    jsonpath_expr: str,
) -> Union[Any, list[Any]]:  # list returned because that's what JSON does
    """Parse a JSONPath expression and return the value from ``data``.

    Args:
        data: The context data to search
        jsonpath_expr: The JSONPath expression.

    Return:
        The value for the provided expression.
    """
    parser = parse(jsonpath_expr)

    # These parsers always return an array of something (strings, numbers, other arrays)
    # or an empty array. It's difficult to determine what should be returned so the len
    # extension is used to try to determine the intention.

    result: list[DatumInContext] = parser.find(
        data
    )  # An array of `DatumInContext` objects.

    # ### V1: Original silly hack

    # try:
    #     return tuple(r.value for r in result) if len(result) > 1 else result[0].value
    # except IndexError:
    #     return ()

    # ### V2: Slightly smarter but still hacky hack

    # If this is an array of stuff, just return the stuff.
    # This happens with array slices such as [-2:]
    if len(result) > 1:
        return list(r.value for r in result)

    if len(result) == 1:
        # If the result isn't just a value it's safe to say it's of the correct type.
        if isinstance(result[0].value, (dict, list)):
            return result[0].value

        # When the result is a value it's hard to tell if it was meant to be in an
        # array. Here the parser tree is walked to see if any part of it is a slice.
        c = parser
        while True:
            # If the right hand expression is a slice return an array
            if isinstance(parser.right, _Slice):
                return [
                    result[0].value,
                ]

            elif isinstance(c, _Child):
                # Next node
                c = c.left
                continue

            elif isinstance(c, _Root):
                # This was a value
                return result[0].value

    # Otherwise the result is an empty array. The library gives no difference to an
    # invalid path and an empty slice so all that's left to do is return the result.
    return list()


def set_jsonpath_value(
    data: dict[str, Any],
    new_data: dict[str, Any],
    jsonpath_expr: str,
    create_if_missing: bool = True,
    use_copy: bool = True,
) -> dict[str, Any]:
    """Set the value of ``new_data`` at the provided JSONPath expression in ``data``.

    This function is useful for updating a JSON with more JSON at a path defined by a
    JSONPath expression.

    Args:
        data: The original JSON to alter.
        new_data: The JSON to add to ``data``.
        jsonpath_expr: The JSONPath expression to insert ``new_data`` at.
        create_if_missing: Create the data structures needed if they don't
            exist. *Default is True*
        use_copy: Python is pass-by-reference. Make a copy of data and don't modify the
            original. *Default is True*

    Return:
        The modified JSON.
    """
    parser = parse(jsonpath_expr)

    data_copy: Optional[dict[str, Any]] = None
    if use_copy:
        data_copy = deepcopy(data)

    if create_if_missing:
        parser.update_or_create(data_copy if data_copy else data, new_data)
    else:
        parser.update(data_copy if data_copy else data, new_data)

    return data_copy if data_copy else data
