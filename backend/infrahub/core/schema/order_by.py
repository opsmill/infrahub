from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Literal

from infrahub.constants.enums import OrderDirection
from infrahub.core.constants import NODE_METADATA_PREFIX
from infrahub.core.order import METADATA_CREATED_AT, METADATA_UPDATED_AT

if TYPE_CHECKING:
    from infrahub.core.schema.basenode_schema import BaseNodeSchema


_DIRECTION_TOKENS = {direction.value.lower() for direction in OrderDirection}


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


def parse_order_by_entry(entry: str, node_schema: BaseNodeSchema) -> ParsedOrderByEntry:
    if not entry:
        raise ValueError(f"order_by entries must be non-empty strings (entry: {entry!r}).")

    parts = entry.split("__")

    if any(not part for part in parts):
        raise ValueError(f"invalid entry (entry: {entry!r}). Entry segments must be non-empty.")

    if parts[0] == NODE_METADATA_PREFIX:
        return _parse_metadata(entry=entry, parts=parts)

    return _parse_path(entry=entry, parts=parts, node_schema=node_schema)


def _consume_direction(entry: str, parts: list[str], path_length: int) -> OrderDirection:
    if len(parts) == path_length:
        return OrderDirection.ASC
    if len(parts) == path_length + 1:
        token = parts[-1]
        if token in _DIRECTION_TOKENS:
            return OrderDirection(token.upper())
        raise ValueError(f"invalid direction (entry: {entry!r}). Direction must be 'asc' or 'desc'.")
    raise ValueError(f"invalid entry (entry: {entry!r}). Unexpected number of segments.")


def _parse_metadata(entry: str, parts: list[str]) -> ParsedMetadataOrderBy:
    if len(parts) < 2:
        raise ValueError(
            f"invalid {NODE_METADATA_PREFIX} entry (entry: {entry!r}). "
            f"Expected '{NODE_METADATA_PREFIX}__<field>' "
            f"or '{NODE_METADATA_PREFIX}__<field>__<direction>'."
        )

    field_token = parts[1]
    try:
        metadata_field = OrderByMetadataField(field_token)
    except ValueError as exc:
        supported = ", ".join(field.value for field in OrderByMetadataField)
        raise ValueError(f"unknown metadata field (entry: {entry!r}). Supported metadata fields: {supported}.") from exc

    direction = _consume_direction(entry=entry, parts=parts, path_length=2)

    return ParsedMetadataOrderBy(raw=entry, direction=direction, metadata_field=metadata_field)


def _parse_path(
    entry: str, parts: list[str], node_schema: BaseNodeSchema
) -> ParsedAttributeOrderBy | ParsedRelationshipAttributeOrderBy:
    first = parts[0]

    if first in node_schema.relationship_names:
        if len(parts) < 3:
            raise ValueError(
                f"invalid relationship path (entry: {entry!r}). "
                f"Expected '<relationship>__<attribute>__<property>' "
                f"with an optional direction suffix."
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
            raise ValueError(
                f"invalid attribute path (entry: {entry!r}). "
                f"Expected '<attribute>__<property>' with an optional direction suffix."
            )
        direction = _consume_direction(entry=entry, parts=parts, path_length=2)
        return ParsedAttributeOrderBy(
            raw=entry,
            direction=direction,
            attribute_name=parts[0],
            property_name=parts[1],
        )

    raise ValueError(f"attribute {first!r} not defined on this schema (entry: {entry!r}).")
