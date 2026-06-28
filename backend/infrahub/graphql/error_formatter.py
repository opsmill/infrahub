from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    BranchAlreadyMergedData,
    BranchNeedsRebaseData,
    BranchNotFoundData,
    MergeInProgressData,
    NodeNotFoundData,
    PermissionDeniedData,
    SchemaNotFoundData,
    TokenExpiredData,
    UndefinedErrorData,
)
from infrahub.exceptions import (
    AuthorizationError,
    BranchAlreadyMergedError,
    BranchNeedsRebaseError,
    BranchNotFoundError,
    Error,
    MergeInProgressError,
    NodeNotFoundError,
    SchemaNotFoundError,
)
from infrahub.log import get_logger

if TYPE_CHECKING:
    from graphql import GraphQLError, GraphQLFormattedError
    from pydantic import BaseModel


UNDEFINED_ERROR_CODE = "UNDEFINED_ERROR"
UNDEFINED_ERROR_HTTP_STATUS = 500

# Substring in an AuthorizationError message that signals an expired JWT.
_EXPIRED_SIGNATURE_MARKER = "Expired Signature"

log = get_logger()


def _build_payload(exc: BaseException | None, code: str) -> dict[str, Any]:
    payload: BaseModel = UndefinedErrorData()
    match code:
        case "NODE_NOT_FOUND" if isinstance(exc, NodeNotFoundError):
            payload = NodeNotFoundData(node_kind=exc.node_type, identifier=exc.identifier)
        case "AUTHENTICATION_REQUIRED":
            payload = AuthenticationRequiredData()
        case "TOKEN_EXPIRED":
            payload = TokenExpiredData()
        case "PERMISSION_DENIED":
            action = getattr(exc, "action", None) if exc is not None else None
            resource_kind = getattr(exc, "resource_kind", None) if exc is not None else None
            payload = PermissionDeniedData(action=action, resource_kind=resource_kind)
        case "ATTRIBUTE_REQUIRED" if isinstance(exc, AttributeRequiredError):
            payload = AttributeRequiredData(node_kind=exc.node_kind, field_name=exc.field_name)
        case "ATTRIBUTE_INVALID_TYPE" if isinstance(exc, AttributeInvalidTypeError):
            payload = AttributeInvalidTypeData(
                node_kind=exc.node_kind,
                field_name=exc.field_name,
                expected_type=exc.expected_type,
                received_type=exc.received_type,
            )
        case "ATTRIBUTE_CONSTRAINT_VIOLATION" if isinstance(exc, AttributeConstraintViolationError):
            payload = AttributeConstraintViolationData(
                node_kind=exc.node_kind,
                field_name=exc.field_name,
                constraint=exc.constraint,
                detail=exc.detail,
            )
        case "BRANCH_NOT_FOUND" if isinstance(exc, BranchNotFoundError):
            payload = BranchNotFoundData(branch_name=exc.identifier)
        case "BRANCH_ALREADY_MERGED" if isinstance(exc, BranchAlreadyMergedError):
            payload = BranchAlreadyMergedData(branch_name=exc.identifier)
        case "BRANCH_NEEDS_REBASE" if isinstance(exc, BranchNeedsRebaseError):
            payload = BranchNeedsRebaseData(branch_name=exc.identifier)
        case "MERGE_IN_PROGRESS" if isinstance(exc, MergeInProgressError):
            payload = MergeInProgressData(branch_name=exc.identifier, merging_branch=exc.merging_branch)
        case "SCHEMA_NOT_FOUND" if isinstance(exc, SchemaNotFoundError):
            payload = SchemaNotFoundData(kind=exc.identifier)
    return payload.model_dump(mode="json")


def _classify_authorization_error(exc: AuthorizationError) -> str:
    if _EXPIRED_SIGNATURE_MARKER in (exc.message or ""):
        return "TOKEN_EXPIRED"
    return "AUTHENTICATION_REQUIRED"


def resolve_catalogue_code(exc: BaseException) -> str:
    """Return the catalogue code for ``exc``, or ``UNDEFINED_ERROR`` if no mapping exists."""
    if not isinstance(exc, Exception):
        return UNDEFINED_ERROR_CODE
    if isinstance(exc, AuthorizationError):
        return _classify_authorization_error(exc)
    exc_type: type[Exception] = type(exc)
    code = EXCEPTION_TO_CODE.get(exc_type)
    if code is not None:
        return code
    for parent in exc_type.__mro__[1:]:
        if not isinstance(parent, type) or not issubclass(parent, Exception):
            continue
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

    log.info(
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
