from copy import deepcopy
from typing import Any, Optional, Union

from jsonpath_ng.parser import JsonPathParser  # type:ignore # no stubs


def get_jsonpath_value(
    data: dict[str, Any],
    jsonpath_expr: str,
) -> Union[Any, tuple[Any, ...]]:
    """Parse a JSONPath expression and return the value from ``data``.

    Args:
        data: The context data to search
        jsonpath_expr: The JSONPath expression.

    Return:
        The value for the provided expression.
    """
    jparser = JsonPathParser()
    parser = jparser.parse(jsonpath_expr)

    result = parser.find(data)
    r = tuple(v.value for v in result)

    try:
        return r if len(r) > 1 else r[0]
    except IndexError:
        raise ValueError(f"'{jsonpath_expr}' was not found") from None


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
    jparser = JsonPathParser()
    parser = jparser.parse(jsonpath_expr)

    data_copy: Optional[dict[str, Any]] = None
    if use_copy:
        data_copy = deepcopy(data)

    if create_if_missing:
        parser.update_or_create(data_copy if data_copy else data, new_data)
    else:
        parser.update(data_copy if data_copy else data, new_data)

    return data_copy if data_copy else data
