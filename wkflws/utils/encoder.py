import datetime
import decimal
import json
from typing import Any
import uuid


class WkflwsJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder adding support for additional python data types.

    Usage:

    .. code::python

       json.dumps(my_value, cls=WkflwsJSONEncoder)
    """

    def default(self, obj) -> Any:
        """Encode objects to JSON values.

        Args:
            obj: The object to encode.

        Return:
            A valid type suitable for JSON encoding.
        """
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        else:
            try:
                return super().default(obj)
            except TypeError:
                return str(obj)
