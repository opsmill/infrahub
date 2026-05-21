from dataclasses import dataclass, field

import pytest
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from infrahub.errors.catalogue import CATALOGUE
from infrahub.errors.payloads import (
    AttributeConstraintViolationData,
    AttributeInvalidTypeData,
    AttributeRequiredData,
    AuthenticationRequiredData,
    BranchNotFoundData,
    NodeNotFoundData,
    PermissionDeniedData,
    SchemaNotFoundData,
    TokenExpiredData,
    UndefinedErrorData,
)


@dataclass
class PayloadRequiredCase:
    name: str
    model: type[BaseModel]
    expected_required: set[str] = field(default_factory=set)


REQUIRED_CASES = [
    PayloadRequiredCase(name="node_not_found", model=NodeNotFoundData, expected_required={"node_kind", "identifier"}),
    PayloadRequiredCase(name="authentication_required", model=AuthenticationRequiredData),
    PayloadRequiredCase(name="token_expired", model=TokenExpiredData),
    PayloadRequiredCase(name="permission_denied", model=PermissionDeniedData),
    PayloadRequiredCase(
        name="attribute_required",
        model=AttributeRequiredData,
        expected_required={"node_kind", "field_name"},
    ),
    PayloadRequiredCase(
        name="attribute_invalid_type",
        model=AttributeInvalidTypeData,
        expected_required={"node_kind", "field_name", "expected_type", "received_type"},
    ),
    PayloadRequiredCase(
        name="attribute_constraint_violation",
        model=AttributeConstraintViolationData,
        expected_required={"node_kind", "field_name", "constraint"},
    ),
    PayloadRequiredCase(name="branch_not_found", model=BranchNotFoundData, expected_required={"branch_name"}),
    PayloadRequiredCase(name="schema_not_found", model=SchemaNotFoundData, expected_required={"kind"}),
    PayloadRequiredCase(name="undefined_error", model=UndefinedErrorData),
]


@pytest.mark.parametrize("case", REQUIRED_CASES, ids=lambda case: case.name)
def test_payload_required_fields(case: PayloadRequiredCase) -> None:
    schema = case.model.model_json_schema()
    assert set(schema.get("required", [])) == case.expected_required


@pytest.mark.parametrize("case", REQUIRED_CASES, ids=lambda case: case.name)
def test_payload_schema_forbids_additional_properties(case: PayloadRequiredCase) -> None:
    schema = case.model.model_json_schema()
    assert schema.get("additionalProperties") is False


def test_permission_denied_payload_exposes_only_action_and_resource_kind() -> None:
    expected_fields = {"action", "resource_kind"}
    actual_fields = set(PermissionDeniedData.model_fields)
    assert actual_fields == expected_fields

    schema = PermissionDeniedData.model_json_schema()
    assert set(schema.get("properties", {})) == expected_fields

    with pytest.raises(PydanticValidationError, match=r"identifier"):
        PermissionDeniedData(action="update", resource_kind="BuiltinTag", identifier="x")  # type: ignore[call-arg]  # ty: ignore[unknown-argument]
    with pytest.raises(PydanticValidationError, match=r"resource_id"):
        PermissionDeniedData(action="update", resource_kind="BuiltinTag", resource_id="x")  # type: ignore[call-arg]  # ty: ignore[unknown-argument]


def test_every_catalogue_entry_has_matching_payload_model() -> None:
    for code, entry in CATALOGUE.items():
        schema = entry.payload_model.model_json_schema()
        assert schema.get("additionalProperties") is False, code
