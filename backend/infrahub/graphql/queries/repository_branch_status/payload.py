from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.query.repository import RepositoryBranchAttributeValue
    from infrahub.core.schema.attribute_schema import AttributeSchema

log = get_logger()


def build_attribute_payload(
    value: RepositoryBranchAttributeValue | None, attribute_schema: AttributeSchema
) -> dict[str, Any] | None:
    """Map a resolved attribute value onto the payload the GraphQL attribute types consume.

    Args:
        value: Resolved value, or None when nothing resolved for the attribute.
        attribute_schema: Schema of the attribute, carrying the dropdown choices when it has any.

    Returns:
        The payload, or None when no value resolved. This never raises for a value that is
        absent from the schema's choices.

    """
    if value is None:
        return None

    # The GraphQL attribute types expose updated_at as a DateTime, which refuses a string.
    payload: dict[str, Any] = {
        "id": value.attribute_id,
        "value": value.value,
        "updated_at": Timestamp(value.updated_at).to_datetime() if value.updated_at else None,
        "is_default": None,
        "is_protected": None,
        "is_from_profile": None,
        "permissions": None,
        "source": None,
        "owner": None,
    }

    if attribute_schema.choices is None:
        return payload

    choice = next((choice for choice in attribute_schema.choices if choice.name == value.value), None)
    if choice is None:
        log.debug(
            "No dropdown choice matches the resolved attribute value",
            attribute=attribute_schema.name,
            value=value.value,
        )
    payload["label"] = choice.label if choice is not None else None
    payload["color"] = choice.color if choice is not None else None
    payload["description"] = choice.description if choice is not None else None

    return payload
