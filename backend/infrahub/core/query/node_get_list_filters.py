from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NODE_METADATA_PREFIX as _NODE_METADATA_PREFIX
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import extract_field_filters

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.constants.enums import OrderDirection
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.relationship_schema import RelationshipSchema

NODE_METADATA_PREFIX = f"{_NODE_METADATA_PREFIX}__"

IP_ATTRIBUTE_KINDS = frozenset({"IPHost", "IPNetwork", "IPAddress"})

INTERNAL_FILTER_NAMES = ("any", "attribute", "relationship")


class FieldAttributeRequirementType(Enum):
    FILTER = "filter"
    ORDER = "order"


@dataclass
class FieldAttributeRequirement:
    field_name: str
    field: AttributeSchema | RelationshipSchema | None
    field_attr_name: str
    field_attr_value: Any
    index: int
    types: list[FieldAttributeRequirementType] = dataclass_field(default_factory=list)
    order_direction: OrderDirection | None = None
    # created_at, updated_at, created_by, updated_by
    is_metadata: bool = False
    schema_order_position: int | None = None

    @property
    def is_attribute_value(self) -> bool:
        return bool(self.field and self.field.is_attribute and self.field_attr_name in ("value", "values", "isnull"))

    @property
    def is_filter(self) -> bool:
        return FieldAttributeRequirementType.FILTER in self.types

    @property
    def is_order(self) -> bool:
        return FieldAttributeRequirementType.ORDER in self.types

    @property
    def is_metadata_order(self) -> bool:
        return self.is_metadata and FieldAttributeRequirementType.ORDER in self.types

    @property
    def is_metadata_filter(self) -> bool:
        return self.is_metadata and FieldAttributeRequirementType.FILTER in self.types

    @property
    def node_value_query_variable(self) -> str:
        return f"attr{self.index}_node_value"

    @property
    def comparison_operator(self) -> str:
        if self.field_attr_name == "isnull":
            return "=" if self.field_attr_value is True else "<>"
        if self.field_attr_name in ("values", "ids"):
            return "IN"
        if self.field_attr_name == "before":
            return "<"
        if self.field_attr_name == "after":
            return ">"
        return "="

    @property
    def field_attr_comparison_value(self) -> Any:
        if self.field_attr_name == "isnull":
            return "NULL"
        return self.field_attr_value


def _compress_ipv6(text: str) -> str:
    """Return a complete IPv6 address or interface in its compressed form.

    Raises:
        ValueError: When the text is not a complete IPv6 address or interface.

    """
    if "/" in text:
        return ipaddress.IPv6Interface(text).with_prefixlen
    return str(ipaddress.IPv6Address(text))


def _get_metadata_field_details(filter_key: str) -> tuple[str, str] | None:
    """Parse a metadata filter key into field name and operator.

    Args:
        filter_key: Filter key like "node_metadata__created_at__before"

    Returns:
        Tuple of (field_name, operator) like ("created_at", "before"), or None if not a metadata filter.

    """
    if not filter_key.startswith(NODE_METADATA_PREFIX):
        return None
    parts = filter_key.split("__")
    metadata_field_name = parts[1]  # created_at, updated_at, created_by, updated_by
    metadata_operator = parts[2] if len(parts) > 2 else "value"  # value, before, after, ids
    return metadata_field_name, metadata_operator


def _build_metadata_filter_requirement(
    field_name: str, operator: str, value: Any, index: int
) -> FieldAttributeRequirement:
    if isinstance(value, datetime):
        value = Timestamp(value.isoformat()).to_string()
    return FieldAttributeRequirement(
        field_name=field_name,
        field=None,
        field_attr_name=operator,
        field_attr_value=value,
        index=index,
        types=[FieldAttributeRequirementType.FILTER],
        is_metadata=True,
    )


def _normalize_ip_filter_value(
    field_name: str,
    field: AttributeSchema | RelationshipSchema | None,
    attr_name: str,
    attr_value: Any,
    partial_match: bool,
) -> Any:
    """Return an IP filter value in the form IP values are saved in, so any valid notation of it matches.

    A value that does not parse as an IP is returned unchanged.
    """
    if attr_name not in ("value", "values"):
        return attr_value

    normalize: Callable[[str], str]
    if field is None and field_name in ("any", "attribute"):
        normalize = _compress_ipv6
    elif isinstance(field, AttributeSchema) and field.kind in IP_ATTRIBUTE_KINDS:
        # A full conversion would append a prefix length to IPv4 text, which then no longer matches as a substring.
        normalize = _compress_ipv6 if partial_match else field.get_class()._normalize_value
    else:
        return attr_value

    def _normalize(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return normalize(value)
        except ValueError:
            return value

    if isinstance(attr_value, list):
        return [_normalize(value) for value in attr_value]
    return _normalize(attr_value)


def _build_attribute_filter_requirement(
    field_name: str,
    field: AttributeSchema | RelationshipSchema | None,
    attr_name: str,
    attr_value: Any,
    index: int,
    partial_match: bool,
) -> FieldAttributeRequirement:
    if isinstance(attr_value, Enum):
        attr_value = attr_value.value
    return FieldAttributeRequirement(
        field_name=field_name,
        field=field,
        field_attr_name=attr_name,
        field_attr_value=_normalize_ip_filter_value(
            field_name=field_name, field=field, attr_name=attr_name, attr_value=attr_value, partial_match=partial_match
        ),
        index=index,
        types=[FieldAttributeRequirementType.FILTER],
    )


def get_filter_requirements(
    schema: MainSchemaTypes, filters: dict[str, Any] | None, partial_match: bool, start_index: int = 1
) -> list[FieldAttributeRequirement]:
    """Return one requirement per metadata, attribute and relationship filter of a list read, in filter order.

    A filter on a name the kind does not accept is left out.
    """
    if not filters:
        return []

    requirements: list[FieldAttributeRequirement] = []
    valid_field_names = [*schema.valid_input_names, *INTERNAL_FILTER_NAMES]
    processed_fields: set[str] = set()
    index = start_index

    for filter_key, filter_value in filters.items():
        metadata_details = _get_metadata_field_details(filter_key)
        if metadata_details:
            field_name, operator = metadata_details
            requirements.append(
                _build_metadata_filter_requirement(
                    field_name=field_name, operator=operator, value=filter_value, index=index
                )
            )
            index += 1
            continue

        # "height__value" -> "height"
        field_name = filter_key.split("__", maxsplit=1)[0]
        if field_name not in valid_field_names:
            continue

        # One pass over a field covers every filter on it.
        if field_name in processed_fields:
            continue
        processed_fields.add(field_name)

        attr_filters = extract_field_filters(field_name=field_name, filters=filters)
        if not attr_filters:
            continue

        field = schema.get_field(field_name, raise_on_error=False)
        for attr_name, attr_value in attr_filters.items():
            requirements.append(
                _build_attribute_filter_requirement(
                    field_name=field_name,
                    field=field,
                    attr_name=attr_name,
                    attr_value=attr_value,
                    index=index,
                    partial_match=partial_match,
                )
            )
            index += 1

    return requirements
