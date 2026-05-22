from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from graphql.error.graphql_error import format_error

from infrahub.errors.catalogue import CATALOGUE, EXCEPTION_TO_CODE
from infrahub.errors.exceptions import (
    AttributeConstraintViolationError,
    AttributeInvalidTypeError,
    AttributeRequiredError,
)
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
from infrahub.exceptions import (
    AuthorizationError,
    BranchNotFoundError,
    Error,
    NodeNotFoundError,
    SchemaNotFoundError,
)

if TYPE_CHECKING:
    from graphql import GraphQLError, GraphQLFormattedError


UNDEFINED_ERROR_CODE = "UNDEFINED_ERROR"
UNDEFINED_ERROR_HTTP_STATUS = 500

# Substring in an AuthorizationError message that signals an expired JWT.
_EXPIRED_SIGNATURE_MARKER = "Expired Signature"

_logger = structlog.get_logger("infrahub.graphql.errors")


def _build_payload(exc: BaseException | None, code: str) -> dict[str, Any]:  # noqa: PLR0911
    if code == "NODE_NOT_FOUND" and isinstance(exc, NodeNotFoundError):
        return NodeNotFoundData(node_kind=exc.node_type, identifier=exc.identifier).model_dump(mode="json")
    if code == "AUTHENTICATION_REQUIRED":
        return AuthenticationRequiredData().model_dump(mode="json")
    if code == "TOKEN_EXPIRED":
        return TokenExpiredData().model_dump(mode="json")
    if code == "PERMISSION_DENIED":
        action = getattr(exc, "action", None) if exc is not None else None
        resource_kind = getattr(exc, "resource_kind", None) if exc is not None else None
        return PermissionDeniedData(action=action, resource_kind=resource_kind).model_dump(mode="json")
    if code == "ATTRIBUTE_REQUIRED" and isinstance(exc, AttributeRequiredError):
        return AttributeRequiredData(node_kind=exc.node_kind, field_name=exc.field_name).model_dump(mode="json")
    if code == "ATTRIBUTE_INVALID_TYPE" and isinstance(exc, AttributeInvalidTypeError):
        return AttributeInvalidTypeData(
            node_kind=exc.node_kind,
            field_name=exc.field_name,
            expected_type=exc.expected_type,
            received_type=exc.received_type,
        ).model_dump(mode="json")
    if code == "ATTRIBUTE_CONSTRAINT_VIOLATION" and isinstance(exc, AttributeConstraintViolationError):
        return AttributeConstraintViolationData(
            node_kind=exc.node_kind,
            field_name=exc.field_name,
            constraint=exc.constraint,
            detail=exc.detail,
        ).model_dump(mode="json")
    if code == "BRANCH_NOT_FOUND" and isinstance(exc, BranchNotFoundError):
        return BranchNotFoundData(branch_name=exc.identifier).model_dump(mode="json")
    if code == "SCHEMA_NOT_FOUND" and isinstance(exc, SchemaNotFoundError):
        return SchemaNotFoundData(kind=exc.identifier).model_dump(mode="json")
    return UndefinedErrorData().model_dump(mode="json")


def _classify_authorization_error(exc: AuthorizationError) -> str:
    if _EXPIRED_SIGNATURE_MARKER in (exc.message or ""):
        return "TOKEN_EXPIRED"
    return "AUTHENTICATION_REQUIRED"


def resolve_catalogue_code(exc: BaseException) -> str:
    """Return the catalogue code for ``exc``, or ``UNDEFINED_ERROR`` if no mapping exists."""
    if isinstance(exc, AuthorizationError):
        return _classify_authorization_error(exc)
    code = EXCEPTION_TO_CODE.get(type(exc))
    if code is not None:
        return code
    for parent in type(exc).__mro__[1:]:
        parent_code = EXCEPTION_TO_CODE.get(parent)
        if parent_code is not None:
            return parent_code
    return UNDEFINED_ERROR_CODE


def _resolve_http_status(exc: BaseException | None, code: str) -> int:
    entry = CATALOGUE.get(code)
    if entry is None or code == UNDEFINED_ERROR_CODE:
        if isinstance(exc, Error):
            return exc.HTTP_CODE
        return UNDEFINED_ERROR_HTTP_STATUS
    return entry.http_status


def build_catalogue_extensions(exc: BaseException | None) -> dict[str, Any]:
    """Return the catalogue-aware ``extensions`` block for ``exc``."""
    if exc is None:
        code = UNDEFINED_ERROR_CODE
    else:
        code = resolve_catalogue_code(exc)
    return {
        "code": code,
        "http_status": _resolve_http_status(exc, code),
        "data": _build_payload(exc, code),
    }


def catalogue_error_formatter(error: GraphQLError) -> GraphQLFormattedError:
    """graphql-core ``error_formatter`` that adds catalogue ``code``/``http_status``/``data``."""
    formatted: dict[str, Any] = dict(format_error(error))
    extensions = build_catalogue_extensions(error.original_error)

    base_extensions: dict[str, Any] = dict(formatted.get("extensions") or {})
    base_extensions.update(extensions)
    formatted["extensions"] = base_extensions

    _logger.info(
        "graphql.error",
        code=extensions["code"],
        http_status=extensions["http_status"],
        path=list(error.path) if error.path is not None else None,
    )

    return formatted  # type: ignore[return-value]


def format_graphql_errors(errors: list[GraphQLError]) -> list[GraphQLFormattedError]:
    """Format a list of GraphQL errors, expanding any ``MultiFieldValidationError`` fan-outs."""
    from infrahub.errors.validation import MultiFieldValidationError

    out: list[GraphQLFormattedError] = []
    for error in errors:
        original = error.original_error
        if isinstance(original, MultiFieldValidationError):
            out.extend(catalogue_error_formatter(child) for child in original.errors)
            continue
        out.append(catalogue_error_formatter(error))
    return out
