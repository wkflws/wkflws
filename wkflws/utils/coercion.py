from typing import Any


def coerce_bool(obj: Any) -> bool:
    """Convert a stringable object to a boolean.

    This function will stringify any object and return ``True`` if the value
    is ``1`` or it starts with ``t``, ``T``. False is return if these
    conditions are not met.

    Args:
        obj: any stringable object.

    Returns:
        bool
    """
    obj_as_string = str(obj).lower()
    return obj_as_string == "1" or obj_as_string.startswith("t")
