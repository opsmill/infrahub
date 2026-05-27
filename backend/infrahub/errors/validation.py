from __future__ import annotations

import re
from typing import TYPE_CHECKING, NoReturn

from graphql import GraphQLError

from infrahub.exceptions import ValidationError

from .exceptions import (
    AttributeConstraintViolationError,
    AttributeInvalidTypeError,
    AttributeRequiredError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


_MANDATORY_RE = re.compile(r" is mandatory for ")
_INVALID_TYPE_RE = re.compile(r"^(?P<received>.+?) is not a valid (?P<expected>\S+)$")


ClassifiedFieldError = AttributeRequiredError | AttributeInvalidTypeError | AttributeConstraintViolationError


class MultiFieldValidationError(Exception):
    """Carries pre-built per-field GraphQL errors so the HTTP layer can fan them out."""

    def __init__(self, errors: list[GraphQLError]) -> None:
        self.errors = errors
        joined = ", ".join(error.message for error in errors)
        super().__init__(joined or "Validation failed")


def classify_field_reason(field_name: str, reason: str, *, node_kind: str) -> ClassifiedFieldError:
    """Map a single ValidationError ``{field: reason}`` entry to a typed catalogue exception.

    The resulting exception's ``message`` mirrors the legacy ``ValidationError({field: reason})``
    shape — ``"<reason> at <field>"`` — so callers that scrape error messages remain stable.
    The catalogue payload is built from the typed attributes (``field_name``, ``expected_type``,
    etc.), not from the message text.

    Note that this function should be phased out once the internals raise the more specific errors directly.
    """
    legacy_message = f"{reason} at {field_name}"
    if _MANDATORY_RE.search(reason):
        return AttributeRequiredError(node_kind=node_kind, field_name=field_name, message=legacy_message)
    match = _INVALID_TYPE_RE.match(reason)
    if match:
        return AttributeInvalidTypeError(
            node_kind=node_kind,
            field_name=field_name,
            expected_type=match.group("expected"),
            received_type=match.group("received"),
            message=legacy_message,
        )
    return AttributeConstraintViolationError(
        node_kind=node_kind,
        field_name=field_name,
        constraint=reason,
        message=legacy_message,
    )


def raise_classified_validation_errors(
    input_value: dict[str, str],
    *,
    node_kind: str,
    path: Sequence[str | int],
) -> NoReturn:
    """Classify each field reason and raise either a single typed error or a multi-error wrapper.

    Raises:
        ValueError: When ``input_value`` is empty.
        AttributeRequiredError: Single-field case, mandatory-field failure.
        AttributeInvalidTypeError: Single-field case, type mismatch.
        AttributeConstraintViolationError: Single-field case, constraint failure.
        MultiFieldValidationError: Multi-field case, carries one GraphQL error per field.

    """
    if not input_value:
        raise ValueError("input_value must not be empty")

    graphql_errors: list[GraphQLError] = []
    for field_name, reason in input_value.items():
        exc = classify_field_reason(field_name=field_name, reason=reason, node_kind=node_kind)
        graphql_errors.append(GraphQLError(message=exc.message, original_error=exc, path=[*path, field_name]))

    if len(graphql_errors) == 1:
        original = graphql_errors[0].original_error
        assert original is not None
        raise original

    raise MultiFieldValidationError(graphql_errors)


def flatten_validation_input(exc: ValidationError) -> dict[str, str] | None:
    """Flatten a ``ValidationError.input_value`` into a single ``{field: reason}`` dict.

    Returns ``None`` when the input cannot be structurally interpreted as per-field reasons,
    in which case the caller should let the original error propagate as ``UNDEFINED_ERROR``.
    """
    value = getattr(exc, "input_value", None)
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items() if isinstance(k, str)}
    if isinstance(value, list):
        flat: dict[str, str] = {}
        for item in value:
            if isinstance(item, ValidationError):
                nested = flatten_validation_input(item)
                if nested is None:
                    return None
                flat.update(nested)
            elif isinstance(item, dict):
                for k, v in item.items():
                    if not isinstance(k, str):
                        return None
                    flat[k] = str(v)
            else:
                return None
        return flat or None
    return None


def raise_classified_from_validation_error(
    exc: ValidationError,
    *,
    node_kind: str,
    path: Sequence[str | int],
) -> NoReturn:
    """Reclassify a generic ``ValidationError`` into per-field catalogued exceptions.

    Falls back to re-raising the original exception when ``input_value`` cannot be
    structurally split into field reasons.

    Raises:
        ValidationError: The original exception, when ``input_value`` is unstructured.
        AttributeRequiredError: Single-field case, mandatory-field failure.
        AttributeInvalidTypeError: Single-field case, type mismatch.
        AttributeConstraintViolationError: Single-field case, constraint failure.
        MultiFieldValidationError: Multi-field case, carries one GraphQL error per field.

    """
    flat = flatten_validation_input(exc)
    if not flat:
        raise exc
    raise_classified_validation_errors(flat, node_kind=node_kind, path=path)
