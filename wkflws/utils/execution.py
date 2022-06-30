"""Utilities used to manage dynamic execution of imports from strings."""
from importlib import import_module
from typing import Any

from ..logging import logger


def module_attribute_from_string(s: str) -> Any:
    """Import and returns the module attribute from the provided string.

    This function works by splitting the provided string using ``.`` where the final
    element of the resulting list is the attribute. For example if ``s`` is
    "os.path.pathsep" then "os.path" becomes the module and "pathsep" is returned.

    Args:
        s: The module string. e.g. ``"os.path.pathsep"``.

    Raises:
        ModuleNotFoundError: the module was not able to be imported.
        AttributeError: the attribute on the module does not exist.

    Returns:
        The module defined in the string.
    """
    module_name = ".".join(s.split(".")[:-1])
    attr_name = s.split(".")[-1]

    if module_name == "":
        # this is a root module like `sys` or `os`
        logger.warning(f"Importing bare module '{s}' as attribute.")
        return import_module(attr_name)

    mod = import_module(module_name)
    return getattr(mod, attr_name)
