from decimal import Decimal

import pytest

from wkflws.utils import jsonpath

J = {
    "a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 0],
    "ea": [],
    "sa": [
        1,
    ],
    "d": {
        "a": ["a", "b", 1, 2],
        "s": "Hello, World!",
        "i": 4,
        "f": Decimal("4.8"),
    },
    # Special case of a single element array. Parsers tend to choke on this returning
    # the value instead of an array of only the value.
    "s1": [
        "p",
    ],
}


def test_get_jsonpath__multi_slice():
    # Validate return value of slice with multiple values.
    assert jsonpath.get_jsonpath_value(J, "$.a[-2:]") == [9, 0]


def test_get_jsonpath__multi_slice__more():
    # Validate return value of slice with multiple values.

    # Parsers struggle with a single element slice. IMHO if you're asking for a slice
    # and there's only 1 element in the slice then you should still get an array, not
    # just the value.
    assert jsonpath.get_jsonpath_value(J, "$.s1[-6:]") == [
        "p",
    ]


def test_get_json_path__limited_slice():
    # Validate the return value when a slice is limited.
    assert jsonpath.get_jsonpath_value(J, "$.a[3:5]") == [4, 5]


def test_get_jsonpath__empty_array():
    # Validate return value for an empty JSON array.
    assert jsonpath.get_jsonpath_value(J, "$.ea") == []


def test_get_jsonpath__empty_array__slice():
    # Validate return value for an empty JSON array when slicing.
    assert jsonpath.get_jsonpath_value(J, "$.ea[-6:]") == []


def test_get_jsonpath__single_elem_array():
    # Validate return value for a single element array.
    assert jsonpath.get_jsonpath_value(J, "$.sa") == [
        1,
    ]


def test_get_jsonpath__array_index():
    # Validate return value for an array index
    assert jsonpath.get_jsonpath_value(J, "$.sa[0]") == 1


def test_get_jsonpath__array_negative_index():
    # Validate return value for an array index
    assert jsonpath.get_jsonpath_value(J, "$.a[-4]") == 7


@pytest.mark.skip("TODO: Detect invalid JSONPath")
def test_get_jsonpath__invalid_path():
    # Test that an invalid path throws an exception

    with pytest.raises(NotImplementedError):
        jsonpath.get_jsonpath_value(J, "$.monkeys_left_after_jumping_on_beds")
