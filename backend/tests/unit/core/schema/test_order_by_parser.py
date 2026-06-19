from dataclasses import dataclass

import pytest

from infrahub.constants.enums import OrderDirection
from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.order_by import (
    OrderByMetadataField,
    OrderByTargetKind,
    ParsedMetadataOrderBy,
    parse_order_by_entry,
    parse_order_by_path,
)
from infrahub.exceptions import ValidationError


@pytest.fixture
def node_schema() -> NodeSchema:
    return NodeSchema(
        name="Note",
        namespace="Documentation",
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(name="status", kind="Text", optional=True),
        ],
        relationships=[
            RelationshipSchema(
                name="account",
                kind=RelationshipKind.ATTRIBUTE,
                peer="CoreAccount",
                cardinality=RelationshipCardinality.ONE,
                optional=False,
            ),
        ],
    )


@dataclass
class ParserCase:
    name: str
    entry: str
    expected_kind: OrderByTargetKind
    expected_direction: OrderDirection
    expected_target_key: tuple[str, ...]


SUCCESS_CASES = [
    ParserCase(
        name="attribute_implicit_asc",
        entry="name__value",
        expected_kind=OrderByTargetKind.ATTRIBUTE,
        expected_direction=OrderDirection.ASC,
        expected_target_key=("attribute", "name", "value"),
    ),
    ParserCase(
        name="attribute_explicit_asc",
        entry="name__value__asc",
        expected_kind=OrderByTargetKind.ATTRIBUTE,
        expected_direction=OrderDirection.ASC,
        expected_target_key=("attribute", "name", "value"),
    ),
    ParserCase(
        name="attribute_desc",
        entry="status__value__desc",
        expected_kind=OrderByTargetKind.ATTRIBUTE,
        expected_direction=OrderDirection.DESC,
        expected_target_key=("attribute", "status", "value"),
    ),
    ParserCase(
        name="attribute_non_value_property",
        entry="name__binary_address",
        expected_kind=OrderByTargetKind.ATTRIBUTE,
        expected_direction=OrderDirection.ASC,
        expected_target_key=("attribute", "name", "binary_address"),
    ),
    ParserCase(
        name="attribute_non_value_property_with_direction",
        entry="name__prefixlen__desc",
        expected_kind=OrderByTargetKind.ATTRIBUTE,
        expected_direction=OrderDirection.DESC,
        expected_target_key=("attribute", "name", "prefixlen"),
    ),
    ParserCase(
        name="relationship_attribute_implicit_asc",
        entry="account__name__value",
        expected_kind=OrderByTargetKind.RELATIONSHIP_ATTRIBUTE,
        expected_direction=OrderDirection.ASC,
        expected_target_key=("relationship_attribute", "account", "name", "value"),
    ),
    ParserCase(
        name="relationship_attribute_desc",
        entry="account__name__value__desc",
        expected_kind=OrderByTargetKind.RELATIONSHIP_ATTRIBUTE,
        expected_direction=OrderDirection.DESC,
        expected_target_key=("relationship_attribute", "account", "name", "value"),
    ),
    ParserCase(
        name="metadata_created_at_implicit_asc",
        entry="node_metadata__created_at",
        expected_kind=OrderByTargetKind.METADATA,
        expected_direction=OrderDirection.ASC,
        expected_target_key=("metadata", "created_at"),
    ),
    ParserCase(
        name="metadata_updated_at_desc",
        entry="node_metadata__updated_at__desc",
        expected_kind=OrderByTargetKind.METADATA,
        expected_direction=OrderDirection.DESC,
        expected_target_key=("metadata", "updated_at"),
    ),
    ParserCase(
        name="metadata_created_at_asc",
        entry="node_metadata__created_at__asc",
        expected_kind=OrderByTargetKind.METADATA,
        expected_direction=OrderDirection.ASC,
        expected_target_key=("metadata", "created_at"),
    ),
]


@pytest.mark.parametrize("case", SUCCESS_CASES, ids=lambda c: c.name)
def test_parse_order_by_entry_success(case: ParserCase, node_schema: NodeSchema) -> None:
    parsed = parse_order_by_entry(entry=case.entry, node_schema=node_schema)

    assert parsed.kind is case.expected_kind
    assert parsed.direction is case.expected_direction
    assert parsed.target_key == case.expected_target_key
    assert parsed.raw == case.entry


def test_parse_order_by_metadata_field_populated(node_schema: NodeSchema) -> None:
    parsed = parse_order_by_entry(entry="node_metadata__updated_at__desc", node_schema=node_schema)

    assert isinstance(parsed, ParsedMetadataOrderBy)
    assert parsed.metadata_field is OrderByMetadataField.UPDATED_AT


@dataclass
class RejectionCase:
    name: str
    entry: str
    match: str


REJECTION_CASES = [
    RejectionCase(
        name="empty_string",
        entry="",
        match=r"order_by entries must be non-empty strings",
    ),
    RejectionCase(
        name="unsupported_metadata_field",
        entry="node_metadata__created_by",
        match=r"unknown metadata field.*Supported metadata fields: created_at, updated_at",
    ),
    RejectionCase(
        name="malformed_direction_descending",
        entry="name__value__descending",
        match=r"invalid direction.*Direction must be 'asc' or 'desc'",
    ),
    RejectionCase(
        name="malformed_direction_uppercase",
        entry="name__value__ASC",
        match=r"invalid direction.*Direction must be 'asc' or 'desc'",
    ),
    RejectionCase(
        name="empty_direction_tail",
        entry="name__value__",
        match=r"Entry segments must be non-empty",
    ),
    RejectionCase(
        name="empty_middle_segment",
        entry="name____value",
        match=r"Entry segments must be non-empty",
    ),
    RejectionCase(
        name="empty_leading_segment",
        entry="__value",
        match=r"Entry segments must be non-empty",
    ),
    RejectionCase(
        name="unknown_attribute",
        entry="nonexistent__value",
        match=r"attribute 'nonexistent' not defined on this schema",
    ),
    RejectionCase(
        name="metadata_malformed_direction",
        entry="node_metadata__created_at__descending",
        match=r"invalid direction",
    ),
    RejectionCase(
        name="relationship_attribute_missing_property",
        entry="account__name__desc",
        match=r"direction token 'desc' cannot be used as a property name",
    ),
    RejectionCase(
        name="attribute_missing_property",
        entry="name__desc",
        match=r"direction token 'desc' cannot be used as a property name",
    ),
]


@pytest.mark.parametrize("case", REJECTION_CASES, ids=lambda c: c.name)
def test_parse_order_by_entry_rejection(case: RejectionCase, node_schema: NodeSchema) -> None:
    with pytest.raises(ValidationError, match=case.match):
        parse_order_by_entry(entry=case.entry, node_schema=node_schema)


@dataclass
class PathCase:
    name: str
    field: str
    direction: OrderDirection
    expected_kind: OrderByTargetKind
    expected_target_key: tuple[str, ...]


PATH_SUCCESS_CASES = [
    PathCase(
        name="attribute_asc",
        field="name__value",
        direction=OrderDirection.ASC,
        expected_kind=OrderByTargetKind.ATTRIBUTE,
        expected_target_key=("attribute", "name", "value"),
    ),
    PathCase(
        name="attribute_desc",
        field="status__value",
        direction=OrderDirection.DESC,
        expected_kind=OrderByTargetKind.ATTRIBUTE,
        expected_target_key=("attribute", "status", "value"),
    ),
    PathCase(
        name="relationship_attribute_asc",
        field="account__name__value",
        direction=OrderDirection.ASC,
        expected_kind=OrderByTargetKind.RELATIONSHIP_ATTRIBUTE,
        expected_target_key=("relationship_attribute", "account", "name", "value"),
    ),
    PathCase(
        name="relationship_attribute_desc",
        field="account__name__value",
        direction=OrderDirection.DESC,
        expected_kind=OrderByTargetKind.RELATIONSHIP_ATTRIBUTE,
        expected_target_key=("relationship_attribute", "account", "name", "value"),
    ),
    PathCase(
        name="metadata_asc",
        field="node_metadata__created_at",
        direction=OrderDirection.ASC,
        expected_kind=OrderByTargetKind.METADATA,
        expected_target_key=("metadata", "created_at"),
    ),
    PathCase(
        name="metadata_desc",
        field="node_metadata__updated_at",
        direction=OrderDirection.DESC,
        expected_kind=OrderByTargetKind.METADATA,
        expected_target_key=("metadata", "updated_at"),
    ),
]


@pytest.mark.parametrize("case", PATH_SUCCESS_CASES, ids=lambda c: c.name)
def test_parse_order_by_path_success(case: PathCase, node_schema: NodeSchema) -> None:
    parsed = parse_order_by_path(field=case.field, direction=case.direction, node_schema=node_schema)

    assert parsed.kind is case.expected_kind
    assert parsed.direction is case.direction
    assert parsed.target_key == case.expected_target_key
    assert parsed.raw == case.field


@dataclass
class PathRejectionCase:
    name: str
    field: str
    match: str


PATH_REJECTION_CASES = [
    PathRejectionCase(
        name="empty_field",
        field="",
        match=r"order field must be a non-empty string",
    ),
    PathRejectionCase(
        name="empty_segment",
        field="name____value",
        match=r"Field segments must be non-empty",
    ),
    PathRejectionCase(
        name="attribute_missing_property",
        field="name",
        match=r"invalid attribute path",
    ),
    PathRejectionCase(
        name="attribute_too_many_segments",
        field="name__value__asc",
        match=r"invalid attribute path",
    ),
    PathRejectionCase(
        name="relationship_missing_property",
        field="account__name",
        match=r"invalid relationship path",
    ),
    PathRejectionCase(
        name="attribute_direction_token_as_property",
        field="name__desc",
        match=r"direction token 'desc' cannot be used as a property name",
    ),
    PathRejectionCase(
        name="relationship_direction_token_as_property",
        field="account__name__asc",
        match=r"direction token 'asc' cannot be used as a property name",
    ),
    PathRejectionCase(
        name="metadata_too_many_segments",
        field="node_metadata__created_at__asc",
        match=r"invalid node_metadata field",
    ),
    PathRejectionCase(
        name="metadata_unknown_field",
        field="node_metadata__created_by",
        match=r"unknown metadata field.*Supported metadata fields: created_at, updated_at",
    ),
    PathRejectionCase(
        name="unknown_attribute",
        field="nonexistent__value",
        match=r"attribute 'nonexistent' not defined on this schema",
    ),
]


@pytest.mark.parametrize("case", PATH_REJECTION_CASES, ids=lambda c: c.name)
def test_parse_order_by_path_rejection(case: PathRejectionCase, node_schema: NodeSchema) -> None:
    with pytest.raises(ValidationError, match=case.match):
        parse_order_by_path(field=case.field, direction=OrderDirection.ASC, node_schema=node_schema)
