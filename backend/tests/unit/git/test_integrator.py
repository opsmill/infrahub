from dataclasses import dataclass
from typing import Any

import pytest
import ujson
import yaml

from infrahub.core.constants import ContentType
from infrahub.exceptions import TransformError
from infrahub.git.integrator import serialize_artifact_content


@dataclass
class SerializationCase:
    name: str
    content: Any
    content_type: str
    expected: str


SERIALIZATION_CASES = [
    SerializationCase(
        name="dict_as_json",
        content={"key1": "value1"},
        content_type=ContentType.APPLICATION_JSON.value,
        expected=ujson.dumps({"key1": "value1"}, indent=2),
    ),
    SerializationCase(
        name="dict_as_yaml",
        content={"key1": "value1"},
        content_type=ContentType.APPLICATION_YAML.value,
        expected=yaml.dump({"key1": "value1"}, indent=2),
    ),
    SerializationCase(
        name="string_as_text",
        content="Lorem ipsum",
        content_type=ContentType.TEXT_PLAIN.value,
        expected="Lorem ipsum",
    ),
    SerializationCase(
        name="empty_string_is_a_valid_payload",
        content="",
        content_type=ContentType.TEXT_PLAIN.value,
        expected="",
    ),
]


@pytest.mark.parametrize("case", SERIALIZATION_CASES, ids=lambda c: c.name)
def test_serialize_artifact_content(case: SerializationCase) -> None:
    assert (
        serialize_artifact_content(
            content=case.content,
            content_type=case.content_type,
            repository_name="my-repository",
            commit="d9b3b6f9e2c0a1d4e5f60718293a4b5c6d7e8f90",
            location="transform01.py::Transform01",
        )
        == case.expected
    )


def test_serialize_artifact_content_without_payload() -> None:
    with pytest.raises(
        TransformError, match=r"^The transform at transform01\.py::Transform01 did not return a payload$"
    ):
        serialize_artifact_content(
            content=None,
            content_type=ContentType.TEXT_PLAIN.value,
            repository_name="my-repository",
            commit="d9b3b6f9e2c0a1d4e5f60718293a4b5c6d7e8f90",
            location="transform01.py::Transform01",
        )
