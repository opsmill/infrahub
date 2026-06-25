from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from graphql import GraphQLError

from infrahub.errors.exceptions import (
    AttributeConstraintViolationError,
    AttributeInvalidTypeError,
    AttributeRequiredError,
)
from infrahub.errors.validation import MultiFieldValidationError
from infrahub.exceptions import (
    AuthorizationError,
    BranchAlreadyMergedError,
    BranchNeedsRebaseError,
    BranchNotFoundError,
    Error,
    MergeInProgressError,
    NodeNotFoundError,
    PermissionDeniedError,
    SchemaNotFoundError,
)
from infrahub.graphql.error_formatter import (
    UNDEFINED_ERROR_CODE,
    build_catalogue_extensions,
    catalogue_error_formatter,
    format_graphql_errors,
    resolve_catalogue_code,
)


@dataclass
class CodeCase:
    name: str
    exc: BaseException
    expected_code: str
    expected_http_status: int
    expected_data: dict[str, Any] = field(default_factory=dict)


CASES = [
    CodeCase(
        name="node_not_found",
        exc=NodeNotFoundError(node_type="BuiltinTag", identifier="abc-123"),
        expected_code="NODE_NOT_FOUND",
        expected_http_status=404,
        expected_data={"node_kind": "BuiltinTag", "identifier": "abc-123"},
    ),
    CodeCase(
        name="authentication_required",
        exc=AuthorizationError("No credentials supplied"),
        expected_code="AUTHENTICATION_REQUIRED",
        expected_http_status=401,
        expected_data={},
    ),
    CodeCase(
        name="token_expired",
        exc=AuthorizationError("Expired Signature"),
        expected_code="TOKEN_EXPIRED",
        expected_http_status=401,
        expected_data={"expired_at": None},
    ),
    CodeCase(
        name="permission_denied",
        exc=PermissionDeniedError("Not allowed"),
        expected_code="PERMISSION_DENIED",
        expected_http_status=403,
        expected_data={"action": None, "resource_kind": None},
    ),
    CodeCase(
        name="attribute_required",
        exc=AttributeRequiredError(node_kind="BuiltinTag", field_name="name"),
        expected_code="ATTRIBUTE_REQUIRED",
        expected_http_status=422,
        expected_data={"node_kind": "BuiltinTag", "field_name": "name"},
    ),
    CodeCase(
        name="attribute_invalid_type",
        exc=AttributeInvalidTypeError(
            node_kind="BuiltinTag",
            field_name="description",
            expected_type="Text",
            received_type="Int",
        ),
        expected_code="ATTRIBUTE_INVALID_TYPE",
        expected_http_status=422,
        expected_data={
            "node_kind": "BuiltinTag",
            "field_name": "description",
            "expected_type": "Text",
            "received_type": "Int",
        },
    ),
    CodeCase(
        name="attribute_constraint_violation",
        exc=AttributeConstraintViolationError(
            node_kind="BuiltinTag",
            field_name="name",
            constraint="regex",
            detail="value must match ^[a-z]+$",
        ),
        expected_code="ATTRIBUTE_CONSTRAINT_VIOLATION",
        expected_http_status=422,
        expected_data={
            "node_kind": "BuiltinTag",
            "field_name": "name",
            "constraint": "regex",
            "detail": "value must match ^[a-z]+$",
        },
    ),
    CodeCase(
        name="branch_not_found",
        exc=BranchNotFoundError(identifier="missing"),
        expected_code="BRANCH_NOT_FOUND",
        expected_http_status=400,
        expected_data={"branch_name": "missing"},
    ),
    CodeCase(
        name="schema_not_found",
        exc=SchemaNotFoundError(branch_name="main", identifier="MissingKind"),
        expected_code="SCHEMA_NOT_FOUND",
        expected_http_status=422,
        expected_data={"kind": "MissingKind"},
    ),
    CodeCase(
        name="branch_already_merged",
        exc=BranchAlreadyMergedError(identifier="feature-branch", message="Branch 'feature-branch' has been merged"),
        expected_code="BRANCH_ALREADY_MERGED",
        expected_http_status=400,
        expected_data={"branch_name": "feature-branch"},
    ),
    CodeCase(
        name="branch_needs_rebase",
        exc=BranchNeedsRebaseError(identifier="feature-branch", message="Branch feature-branch must be rebased"),
        expected_code="BRANCH_NEEDS_REBASE",
        expected_http_status=400,
        expected_data={"branch_name": "feature-branch"},
    ),
    CodeCase(
        name="merge_in_progress",
        exc=MergeInProgressError(
            identifier="main",
            message="A merge is currently in progress; writes are temporarily blocked. Please retry shortly.",
            merging_branch="feature-branch",
        ),
        expected_code="MERGE_IN_PROGRESS",
        expected_http_status=423,
        expected_data={"branch_name": "main", "merging_branch": "feature-branch"},
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_build_catalogue_extensions_per_code(case: CodeCase) -> None:
    extensions = build_catalogue_extensions(case.exc)
    assert extensions["code"] == case.expected_code
    assert extensions["http_status"] == case.expected_http_status
    assert extensions["data"] == case.expected_data


def test_undefined_error_for_uncatalogued_error_with_http_code() -> None:
    class UncataloguedError(Error):
        HTTP_CODE = 418

        def __init__(self) -> None:
            self.message = "teapot"
            super().__init__(self.message)

    extensions = build_catalogue_extensions(UncataloguedError())
    assert extensions["code"] == UNDEFINED_ERROR_CODE
    assert extensions["http_status"] == 418
    assert extensions["data"] == {}


def test_undefined_error_for_uncatalogued_plain_exception_defaults_to_500() -> None:
    extensions = build_catalogue_extensions(RuntimeError("boom"))
    assert extensions["code"] == UNDEFINED_ERROR_CODE
    assert extensions["http_status"] == 500
    assert extensions["data"] == {}


def test_undefined_error_for_missing_original_error_defaults_to_500() -> None:
    extensions = build_catalogue_extensions(None)
    assert extensions["code"] == UNDEFINED_ERROR_CODE
    assert extensions["http_status"] == 500


def test_catalogue_error_formatter_preserves_baseline_fields() -> None:
    original = NodeNotFoundError(node_type="BuiltinTag", identifier="abc-123")
    error = GraphQLError(message="Not found", original_error=original, path=["BuiltinTagUpdate"])

    formatted = catalogue_error_formatter(error)

    assert formatted["message"] == "Not found"
    assert formatted["path"] == ["BuiltinTagUpdate"]
    assert formatted["extensions"]["code"] == "NODE_NOT_FOUND"
    assert formatted["extensions"]["http_status"] == 404
    assert formatted["extensions"]["data"] == {"node_kind": "BuiltinTag", "identifier": "abc-123"}


def test_catalogue_error_formatter_emits_structlog_code(caplog: pytest.LogCaptureFixture) -> None:
    error = GraphQLError(
        message="Not found",
        original_error=NodeNotFoundError(node_type="BuiltinTag", identifier="abc-123"),
    )

    caplog.set_level("INFO", logger="infrahub")
    catalogue_error_formatter(error)

    matching = [
        record for record in caplog.records if "NODE_NOT_FOUND" in record.getMessage() or "code" in record.__dict__
    ]
    assert matching, "expected at least one structlog record with code"


def test_format_graphql_errors_fans_out_multi_field_validation() -> None:
    name_exc = AttributeRequiredError(node_kind="BuiltinTag", field_name="name")
    description_exc = AttributeInvalidTypeError(
        node_kind="BuiltinTag",
        field_name="description",
        expected_type="Text",
        received_type="Int",
    )
    multi = MultiFieldValidationError(
        [
            GraphQLError(
                message=name_exc.message,
                original_error=name_exc,
                path=["BuiltinTagCreate", "data", "name"],
            ),
            GraphQLError(
                message=description_exc.message,
                original_error=description_exc,
                path=["BuiltinTagCreate", "data", "description"],
            ),
        ]
    )
    wrapper = GraphQLError(message=str(multi), original_error=multi, path=["BuiltinTagCreate"])

    formatted = format_graphql_errors([wrapper])

    assert len(formatted) == 2
    assert formatted[0]["extensions"]["code"] == "ATTRIBUTE_REQUIRED"
    assert formatted[0]["path"] == ["BuiltinTagCreate", "data", "name"]
    assert formatted[1]["extensions"]["code"] == "ATTRIBUTE_INVALID_TYPE"
    assert formatted[1]["path"] == ["BuiltinTagCreate", "data", "description"]


class _PermissionDeniedWithExtrasError(PermissionDeniedError):
    """Subclass that simulates an attacker-controlled exception carrying extra resource identifiers.

    Real ``PermissionDeniedError`` instances do not (and should not) carry an ``identifier`` or
    ``resource_id`` attribute — this subclass exists only to prove the formatter ignores them
    if they were ever present.
    """

    identifier: str
    resource_id: str

    def __init__(self, message: str, *, identifier: str, resource_id: str) -> None:
        super().__init__(message)
        self.identifier = identifier
        self.resource_id = resource_id


def test_permission_denied_payload_strips_identifier_attributes() -> None:
    exc = _PermissionDeniedWithExtrasError("Forbidden", identifier="user-42-secret", resource_id="node-99")

    extensions = build_catalogue_extensions(exc)

    assert extensions["code"] == "PERMISSION_DENIED"
    assert set(extensions["data"]) == {"action", "resource_kind"}
    assert "identifier" not in extensions["data"]
    assert "resource_id" not in extensions["data"]


def test_resolve_catalogue_code_walks_mro_for_subclasses() -> None:
    class BuiltinTagNotFoundError(NodeNotFoundError): ...

    code = resolve_catalogue_code(BuiltinTagNotFoundError(node_type="BuiltinTag", identifier="x"))
    assert code == "NODE_NOT_FOUND"
