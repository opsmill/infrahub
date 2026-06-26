from collections import OrderedDict
from typing import Literal

from pydantic import BaseModel, ConfigDict

from infrahub.exceptions import (
    AuthorizationError,
    BranchNotFoundError,
    NodeNotFoundError,
    PermissionDeniedError,
    SchemaNotFoundError,
)

from .exceptions import (
    AttributeConstraintViolationError,
    AttributeInvalidTypeError,
    AttributeRequiredError,
)
from .payloads import (
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


class CatalogueEntry(BaseModel):
    description: str
    stability: Literal["stable", "evolving"]
    http_status: int
    payload_model: type[BaseModel]
    exception_class: type[Exception] | None = None

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)


CATALOGUE: "OrderedDict[str, CatalogueEntry]" = OrderedDict(
    [
        (
            "NODE_NOT_FOUND",
            CatalogueEntry(
                description="The requested node does not exist in the database.",
                stability="stable",
                http_status=404,
                payload_model=NodeNotFoundData,
                exception_class=NodeNotFoundError,
            ),
        ),
        (
            "AUTHENTICATION_REQUIRED",
            CatalogueEntry(
                description="The request requires authentication and none was provided or it was invalid.",
                stability="stable",
                http_status=401,
                payload_model=AuthenticationRequiredData,
                exception_class=AuthorizationError,
            ),
        ),
        (
            "TOKEN_EXPIRED",
            CatalogueEntry(
                description="The authentication token has expired and a silent refresh is required.",
                stability="stable",
                http_status=401,
                payload_model=TokenExpiredData,
                exception_class=AuthorizationError,
            ),
        ),
        (
            "PERMISSION_DENIED",
            CatalogueEntry(
                description="The authenticated user is not permitted to perform the requested action.",
                stability="stable",
                http_status=403,
                payload_model=PermissionDeniedData,
                exception_class=PermissionDeniedError,
            ),
        ),
        (
            "ATTRIBUTE_REQUIRED",
            CatalogueEntry(
                description="A mandatory node attribute was not provided.",
                stability="stable",
                http_status=422,
                payload_model=AttributeRequiredData,
                exception_class=AttributeRequiredError,
            ),
        ),
        (
            "ATTRIBUTE_INVALID_TYPE",
            CatalogueEntry(
                description="A node attribute received a value that does not match its declared type.",
                stability="stable",
                http_status=422,
                payload_model=AttributeInvalidTypeData,
                exception_class=AttributeInvalidTypeError,
            ),
        ),
        (
            "ATTRIBUTE_CONSTRAINT_VIOLATION",
            CatalogueEntry(
                description="A node attribute value failed a schema-defined constraint (e.g. regex, length, range).",
                stability="evolving",
                http_status=422,
                payload_model=AttributeConstraintViolationData,
                exception_class=AttributeConstraintViolationError,
            ),
        ),
        (
            "BRANCH_NOT_FOUND",
            CatalogueEntry(
                description="The requested branch does not exist.",
                stability="stable",
                http_status=400,
                payload_model=BranchNotFoundData,
                exception_class=BranchNotFoundError,
            ),
        ),
        (
            "SCHEMA_NOT_FOUND",
            CatalogueEntry(
                description="The requested schema kind is not registered in the active schema.",
                stability="stable",
                http_status=422,
                payload_model=SchemaNotFoundData,
                exception_class=SchemaNotFoundError,
            ),
        ),
        (
            "UNDEFINED_ERROR",
            CatalogueEntry(
                description=(
                    "An error not yet covered by the catalogue. "
                    "Its occurrence indicates a catalogue gap and should be triaged."
                ),
                stability="stable",
                http_status=500,
                payload_model=UndefinedErrorData,
                exception_class=None,
            ),
        ),
    ]
)


# Reverse map: exception class → catalogue code. AuthorizationError is intentionally excluded
# because it routes to two codes (AUTHENTICATION_REQUIRED vs TOKEN_EXPIRED) at the formatter,
# not via class identity.
EXCEPTION_TO_CODE: dict[type[Exception], str] = {
    entry.exception_class: code
    for code, entry in CATALOGUE.items()
    if entry.exception_class is not None and entry.exception_class is not AuthorizationError
}
