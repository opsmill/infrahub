from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.errors.exceptions import (
    AttributeConstraintViolationError,
    AttributeInvalidTypeError,
    AttributeRequiredError,
)
from infrahub.errors.validation import (
    MultiFieldValidationError,
    classify_field_reason,
    flatten_validation_input,
    raise_classified_from_validation_error,
    raise_classified_validation_errors,
)
from infrahub.exceptions import ValidationError


@dataclass
class ClassifyCase:
    name: str
    field_name: str
    reason: str
    expected_exception: type
    expected_attrs: dict[str, str]


CLASSIFY_CASES = [
    ClassifyCase(
        name="mandatory",
        field_name="name",
        reason="name is mandatory for BuiltinTag",
        expected_exception=AttributeRequiredError,
        expected_attrs={"node_kind": "BuiltinTag", "field_name": "name"},
    ),
    ClassifyCase(
        name="invalid_type",
        field_name="description",
        reason="42 is not a valid Text",
        expected_exception=AttributeInvalidTypeError,
        expected_attrs={
            "node_kind": "BuiltinTag",
            "field_name": "description",
            "expected_type": "Text",
            "received_type": "42",
        },
    ),
    ClassifyCase(
        name="constraint_regex",
        field_name="name",
        reason="value must conform with the regex: '^[a-z]+$'",
        expected_exception=AttributeConstraintViolationError,
        expected_attrs={"node_kind": "BuiltinTag", "field_name": "name"},
    ),
]


@pytest.mark.parametrize("case", CLASSIFY_CASES, ids=lambda case: case.name)
def test_classify_field_reason(case: ClassifyCase) -> None:
    exc = classify_field_reason(field_name=case.field_name, reason=case.reason, node_kind="BuiltinTag")
    assert isinstance(exc, case.expected_exception)
    for attr, expected in case.expected_attrs.items():
        assert getattr(exc, attr) == expected


def test_raise_classified_validation_errors_single_field_raises_typed_subclass() -> None:
    with pytest.raises(AttributeRequiredError) as exc_info:
        raise_classified_validation_errors(
            {"name": "name is mandatory for BuiltinTag"},
            node_kind="BuiltinTag",
            path=["BuiltinTagCreate", "data"],
        )
    assert exc_info.value.field_name == "name"


def test_raise_classified_validation_errors_multi_field_raises_wrapper() -> None:
    with pytest.raises(MultiFieldValidationError) as exc_info:
        raise_classified_validation_errors(
            {
                "name": "name is mandatory for BuiltinTag",
                "description": "Int is not a valid Text",
            },
            node_kind="BuiltinTag",
            path=["BuiltinTagCreate", "data"],
        )
    errors = exc_info.value.errors
    assert len(errors) == 2
    assert errors[0].path == ["BuiltinTagCreate", "data", "name"]
    assert errors[1].path == ["BuiltinTagCreate", "data", "description"]
    assert isinstance(errors[0].original_error, AttributeRequiredError)
    assert isinstance(errors[1].original_error, AttributeInvalidTypeError)


def test_raise_classified_validation_errors_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match=r"input_value must not be empty"):
        raise_classified_validation_errors({}, node_kind="BuiltinTag", path=[])


def test_flatten_validation_input_handles_nested_validation_errors() -> None:
    inner_one = ValidationError({"name": "name is mandatory for BuiltinTag"})
    inner_two = ValidationError({"description": "Int is not a valid Text"})
    outer = ValidationError([inner_one, inner_two])

    flat = flatten_validation_input(outer)

    assert flat == {
        "name": "name is mandatory for BuiltinTag",
        "description": "Int is not a valid Text",
    }


def test_flatten_validation_input_returns_none_for_string_input() -> None:
    exc = ValidationError("some unstructured message")
    assert flatten_validation_input(exc) is None


def test_raise_classified_from_validation_error_falls_back_to_original_when_unstructured() -> None:
    original = ValidationError("unstructured")
    with pytest.raises(ValidationError) as exc_info:
        raise_classified_from_validation_error(original, node_kind="BuiltinTag", path=[])
    assert exc_info.value is original
