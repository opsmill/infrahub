import tempfile
import uuid
from pathlib import Path

import pytest
from graphql import parse

from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.utils import (
    base16decode,
    base16encode,
    base36decode,
    base36encode,
    compare_lists,
    deep_merge_dict,
    dict_hash,
    duplicates,
    extract_fields,
    get_flat_value,
    is_valid_url,
    is_valid_uuid,
    str_to_bool,
    write_to_file,
)


def test_is_valid_uuid():
    assert is_valid_uuid(uuid.uuid4()) is True
    assert is_valid_uuid(uuid.UUID("ba0aecd9-546a-4d77-9187-23e17a20633e")) is True
    assert is_valid_uuid("ba0aecd9-546a-4d77-9187-23e17a20633e") is True

    assert is_valid_uuid("xxx-546a-4d77-9187-23e17a20633e") is False
    assert is_valid_uuid(222) is False
    assert is_valid_uuid(False) is False
    assert is_valid_uuid("Not a valid UUID") is False
    assert is_valid_uuid(uuid.UUID) is False


@pytest.mark.parametrize(
    "input,result",
    [
        (55, False),
        ("https://", False),
        ("my-server", False),
        ("http://my-server", True),
        ("http://my-server:8080", True),
        ("http://192.168.1.10", True),
        ("/test", True),
        ("/", True),
        ("http:/192.168.1.10", False),
    ],
)
def test_is_valid_url(input, result):
    assert is_valid_url(input) is result


def test_duplicates():
    assert duplicates([2, 4, 6, 8, 4, 6, 12]) == [4, 6]
    assert duplicates(["first", "second", "first", "third", "first", "last"]) == ["first"]
    assert not duplicates([2, 8, 4, 6, 12])
    assert duplicates([]) == []
    assert duplicates([None, None]) == []


def test_compare_lists():
    list_a = ["black", "blue", "red"]
    list_b = ["black", "green"]
    list_c = ["purple", "yellow"]

    both, in1, in2 = compare_lists(list_a, list_b)
    assert both == ["black"]
    assert in1 == ["blue", "red"]
    assert in2 == ["green"]

    both, in1, in2 = compare_lists(list_c, list_b)
    assert both == []
    assert in1 == list_c
    assert in2 == list_b

    both, in1, in2 = compare_lists(list_c, ["yellow"])
    assert both == ["yellow"]
    assert in1 == ["purple"]
    assert in2 == []


def test_deep_merge_dict():
    a = {"keyA": 1}
    b = {"keyB": {"sub1": 10}}
    c = {"keyB": {"sub2": 20}}
    assert deep_merge_dict(a, b) == {"keyA": 1, "keyB": {"sub1": 10}}
    assert deep_merge_dict(c, b) == {"keyB": {"sub1": 10, "sub2": 20}}


def test_str_to_bool():
    assert str_to_bool(True) is True
    assert str_to_bool(False) is False

    assert str_to_bool(1) is True
    assert str_to_bool(0) is False

    assert str_to_bool("True") is True
    assert str_to_bool("TRUE") is True
    assert str_to_bool("Yes") is True
    assert str_to_bool("yes") is True
    assert str_to_bool("1") is True
    assert str_to_bool("on") is True
    assert str_to_bool("y") is True

    assert str_to_bool("No") is False
    assert str_to_bool("False") is False
    assert str_to_bool("f") is False

    with pytest.raises(ValueError):
        str_to_bool("NotABool")

    with pytest.raises(TypeError):
        str_to_bool(tuple("a", "b", "c"))


def test_base36():
    assert base36encode(1412823931503067241) == "AQF8AA0006EH"
    assert base36decode("AQF8AA0006EH") == 1412823931503067241
    assert base36decode(base36encode(-9223372036721928027)) == -9223372036721928027
    assert base36decode(base36encode(1412823931503067241)) == 1412823931503067241


def test_base16():
    assert base16encode(1412823931503067241) == "139b5be157694069"
    assert base16decode("139b5be157694069") == 1412823931503067241
    assert base16decode(base16encode(-9223372036721928027)) == -9223372036721928027
    assert base16decode(base16encode(1412823931503067241)) == 1412823931503067241


def test_get_flat_value(client, tag_schema, tag_green_data):
    tag = InfrahubNode(client=client, schema=tag_schema, data=tag_green_data)
    assert get_flat_value(obj=tag, key="name__value") == "green"
    assert get_flat_value(obj=tag, key="name__source__display_label") == "CRM"
    assert get_flat_value(obj=tag, key="name.source.display_label", separator=".") == "CRM"


def test_dict_hash():
    assert dict_hash({"a": 1, "b": 2}) == "608de49a4600dbb5b173492759792e4a"
    assert dict_hash({"b": 2, "a": 1}) == "608de49a4600dbb5b173492759792e4a"
    assert dict_hash({"b": 2, "a": {"c": 1, "d": 2}}) == "4d8f1a3d03e0b487983383d0ff984d13"
    assert dict_hash({"b": 2, "a": {"d": 2, "c": 1}}) == "4d8f1a3d03e0b487983383d0ff984d13"
    assert dict_hash({}) == "99914b932bd37a50b983c5e7c90ae93b"


async def test_extract_fields(query_01):
    document = parse(query_01)
    expected_response = {
        "TestPerson": {
            "edges": {
                "node": {
                    "cars": {"edges": {"node": {"name": {"value": None}}}},
                    "name": {"value": None},
                },
            },
        },
    }
    assert await extract_fields(document.definitions[0].selection_set) == expected_response


async def test_extract_fields_fragment(query_02):
    document = parse(query_02)

    expected_response = {
        "TestPerson": {
            "edges": {
                "node": {
                    "cars": {
                        "edges": {
                            "node": {
                                "member_of_groups": {
                                    "edges": {"node": {"id": None}},
                                },
                                "mpg": {"is_protected": None, "value": None},
                                "name": {"value": None},
                                "nbr_engine": {"value": None},
                            },
                        },
                    },
                    "name": {"value": None},
                },
            },
        },
    }

    assert await extract_fields(document.definitions[0].selection_set) == expected_response


def test_write_to_file():
    tmp_dir = tempfile.TemporaryDirectory()
    directory = Path(tmp_dir.name)

    with pytest.raises(FileExistsError):
        write_to_file(directory, "placeholder")

    assert write_to_file(directory / "file.txt", "placeholder") is True
    assert write_to_file(directory / "file.txt", "placeholder") is True
    assert write_to_file(directory / "file.txt", "") is True
    assert write_to_file(directory / "file.txt", None) is True
    assert write_to_file(directory / "file.txt", 1234) is True
    assert write_to_file(directory / "file.txt", {"key": "value"}) is True

    tmp_dir.cleanup()
