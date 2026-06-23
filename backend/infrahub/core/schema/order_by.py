from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Literal

from infrahub.constants.enums import OrderDirection
from infrahub.core.constants import NODE_METADATA_PREFIX
from infrahub.core.order import METADATA_CREATED_AT, METADATA_UPDATED_AT
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from infrahub.core.schema.basenode_schema import BaseNodeSchema


_DIRECTION_TOKENS = {direction.value.lower() for direction in OrderDirection}


def strip_order_direction_suffix(entry: str) -> str:
    head, _, tail = entry.rpartition("__")
    if head and tail in _DIRECTION_TOKENS:
        return head
    return entry


class OrderByTargetKind(StrEnum):
    ATTRIBUTE = "attribute"
    RELATIONSHIP_ATTRIBUTE = "relationship_attribute"
    METADATA = "metadata"


class OrderByMetadataField(StrEnum):
    CREATED_AT = METADATA_CREATED_AT
    UPDATED_AT = METADATA_UPDATED_AT


@dataclass(frozen=True, slots=True)
class _ParsedOrderByBase:
    raw: str
    direction: OrderDirection


@dataclass(frozen=True, slots=True)
class ParsedAttributeOrderBy(_ParsedOrderByBase):
    attribute_name: str
    property_name: str
    kind: ClassVar[Literal[OrderByTargetKind.ATTRIBUTE]] = OrderByTargetKind.ATTRIBUTE

    @property
    def target_key(self) -> tuple[str, ...]:
        return (self.kind.value, self.attribute_name, self.property_name)


@dataclass(frozen=True, slots=True)
class ParsedRelationshipAttributeOrderBy(_ParsedOrderByBase):
    relationship_name: str
    attribute_name: str
    property_name: str
    kind: ClassVar[Literal[OrderByTargetKind.RELATIONSHIP_ATTRIBUTE]] = OrderByTargetKind.RELATIONSHIP_ATTRIBUTE

    @property
    def target_key(self) -> tuple[str, ...]:
        return (self.kind.value, self.relationship_name, self.attribute_name, self.property_name)


@dataclass(frozen=True, slots=True)
class ParsedMetadataOrderBy(_ParsedOrderByBase):
    metadata_field: OrderByMetadataField
    kind: ClassVar[Literal[OrderByTargetKind.METADATA]] = OrderByTargetKind.METADATA

    @property
    def target_key(self) -> tuple[str, ...]:
        return (self.kind.value, self.metadata_field.value)


type ParsedOrderByEntry = ParsedAttributeOrderBy | ParsedRelationshipAttributeOrderBy | ParsedMetadataOrderBy


def is_metadata_order_by_entry(entry: str) -> bool:
    return entry.startswith(f"{NODE_METADATA_PREFIX}__")


def parse_order_by_entry(entry: str, node_schema: BaseNodeSchema) -> ParsedOrderByEntry:
    """Parse a schema-level order-by string where direction is an optional `__asc`/`__desc` suffix.

    Raises:
        ValidationError: when the entry is empty, has empty segments, or does not match the grammar.

    """
    if not entry:
        raise ValidationError(f"order_by entries must be non-empty strings (entry: {entry!r}).")

    parts = entry.split("__")

    if any(not part for part in parts):
        raise ValidationError(f"invalid entry (entry: {entry!r}). Entry segments must be non-empty.")

    if is_metadata_order_by_entry(entry):
        return _parse_metadata(entry=entry, parts=parts)

    return _parse_path(entry=entry, parts=parts, node_schema=node_schema)


def parse_order_by_path(field: str, direction: OrderDirection, node_schema: BaseNodeSchema) -> ParsedOrderByEntry:
    """Parse a suffix-free order-by path with an explicit direction.

    Unlike the schema-level string grammar, `field` must not carry a trailing `__asc`/`__desc`
    token; the direction is supplied separately, so every segment is part of the path.

    Raises:
        ValidationError: when the field is empty, has empty segments, or does not match the grammar.

    """
    if not field:
        raise ValidationError(f"order field must be a non-empty string (field: {field!r}).")

    parts = field.split("__")

    if any(not part for part in parts):
        raise ValidationError(f"invalid field (field: {field!r}). Field segments must be non-empty.")

    if is_metadata_order_by_entry(field):
        if len(parts) != 2:
            raise ValidationError(
                f"invalid {NODE_METADATA_PREFIX} field (field: {field!r}). Expected '{NODE_METADATA_PREFIX}__<field>'."
            )
        metadata_field = _resolve_metadata_field(entry=field, field_token=parts[1])
        return ParsedMetadataOrderBy(raw=field, direction=direction, metadata_field=metadata_field)

    first = parts[0]

    if first in node_schema.relationship_names:
        if len(parts) != 3:
            raise ValidationError(
                f"invalid relationship path (field: {field!r}). Expected '<relationship>__<attribute>__<property>'."
            )
        if parts[2] in _DIRECTION_TOKENS:
            raise ValidationError(
                f"invalid relationship path (field: {field!r}). The property segment is missing; "
                f"direction token {parts[2]!r} cannot be used as a property name (supply direction via 'direction')."
            )
        return ParsedRelationshipAttributeOrderBy(
            raw=field,
            direction=direction,
            relationship_name=parts[0],
            attribute_name=parts[1],
            property_name=parts[2],
        )

    if first in node_schema.attribute_names:
        if len(parts) != 2:
            raise ValidationError(f"invalid attribute path (field: {field!r}). Expected '<attribute>__<property>'.")
        if parts[1] in _DIRECTION_TOKENS:
            raise ValidationError(
                f"invalid attribute path (field: {field!r}). The property segment is missing; "
                f"direction token {parts[1]!r} cannot be used as a property name (supply direction via 'direction')."
            )
        return ParsedAttributeOrderBy(
            raw=field,
            direction=direction,
            attribute_name=parts[0],
            property_name=parts[1],
        )

    raise ValidationError(f"attribute {first!r} not defined on this schema (field: {field!r}).")


def _consume_direction(entry: str, parts: list[str], path_length: int) -> OrderDirection:
    if len(parts) == path_length:
        return OrderDirection.ASC
    if len(parts) == path_length + 1:
        token = parts[-1]
        if token in _DIRECTION_TOKENS:
            return OrderDirection(token.upper())
        raise ValidationError(f"invalid direction (entry: {entry!r}). Direction must be 'asc' or 'desc'.")
    raise ValidationError(f"invalid entry (entry: {entry!r}). Unexpected number of segments.")


def _resolve_metadata_field(entry: str, field_token: str) -> OrderByMetadataField:
    try:
        return OrderByMetadataField(field_token)
    except ValueError as exc:
        supported = ", ".join(field.value for field in OrderByMetadataField)
        raise ValidationError(
            f"unknown metadata field (entry: {entry!r}). Supported metadata fields: {supported}."
        ) from exc


def _parse_metadata(entry: str, parts: list[str]) -> ParsedMetadataOrderBy:
    if len(parts) < 2:
        raise ValidationError(
            f"invalid {NODE_METADATA_PREFIX} entry (entry: {entry!r}). "
            f"Expected '{NODE_METADATA_PREFIX}__<field>' "
            f"or '{NODE_METADATA_PREFIX}__<field>__<direction>'."
        )

    metadata_field = _resolve_metadata_field(entry=entry, field_token=parts[1])

    direction = _consume_direction(entry=entry, parts=parts, path_length=2)

    return ParsedMetadataOrderBy(raw=entry, direction=direction, metadata_field=metadata_field)


def _parse_path(
    entry: str, parts: list[str], node_schema: BaseNodeSchema
) -> ParsedAttributeOrderBy | ParsedRelationshipAttributeOrderBy:
    first = parts[0]

    if first in node_schema.relationship_names:
        if len(parts) < 3:
            raise ValidationError(
                f"invalid relationship path (entry: {entry!r}). "
                f"Expected '<relationship>__<attribute>__<property>' "
                f"with an optional direction suffix."
            )
        if len(parts) == 3 and parts[2] in _DIRECTION_TOKENS:
            raise ValidationError(
                f"invalid relationship path (entry: {entry!r}). "
                f"Property segment is missing; "
                f"direction token {parts[2]!r} cannot be used as a property name."
            )
        direction = _consume_direction(entry=entry, parts=parts, path_length=3)
        return ParsedRelationshipAttributeOrderBy(
            raw=entry,
            direction=direction,
            relationship_name=parts[0],
            attribute_name=parts[1],
            property_name=parts[2],
        )

    if first in node_schema.attribute_names:
        if len(parts) < 2:
            raise ValidationError(
                f"invalid attribute path (entry: {entry!r}). "
                f"Expected '<attribute>__<property>' with an optional direction suffix."
            )
        if len(parts) == 2 and parts[1] in _DIRECTION_TOKENS:
            raise ValidationError(
                f"invalid attribute path (entry: {entry!r}). "
                f"Property segment is missing; "
                f"direction token {parts[1]!r} cannot be used as a property name."
            )
        direction = _consume_direction(entry=entry, parts=parts, path_length=2)
        return ParsedAttributeOrderBy(
            raw=entry,
            direction=direction,
            attribute_name=parts[0],
            property_name=parts[1],
        )

    raise ValidationError(f"attribute {first!r} not defined on this schema (entry: {entry!r}).")
