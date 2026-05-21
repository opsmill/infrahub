# Phase 1 Data Model: Enriched GraphQL Error Catalogue

**Feature**: INFP-468 | **Created**: 2026-05-19 | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This file pins the concrete entity shapes used by the implementation. The spec describes them abstractly; here they are typed.

---

## Entity overview

```text
┌──────────────────────┐
│   ErrorCatalogue     │  1 instance, in-process, ordered registry
│   (registry)         │
└──────────┬───────────┘
           │ 1..N
           ▼
┌──────────────────────┐       1     1     ┌──────────────────────┐
│   CatalogueEntry     │◄──────────────────│   PayloadModel       │
│   (one per code)     │                   │   (Pydantic class)   │
└──────────────────────┘                   └──────────────────────┘
           │
           │ optional 1..1
           ▼
┌──────────────────────┐
│   Adopted exception  │  Existing class from backend/infrahub/exceptions.py
│   class              │  annotated with CATALOGUE_CODE
└──────────────────────┘
```

---

## `CatalogueEntry` (Python, internal)

Lives in `backend/infrahub/errors/catalogue.py`. Not exported on the wire; the wire contract is in `contracts/`.

```python
from typing import ClassVar
from pydantic import BaseModel

class CatalogueEntry(BaseModel):
    code: str                          # uppercase snake_case, e.g. "NODE_NOT_FOUND"
    description: str                   # human-readable, used for docs page (FR-010, FR-012)
    stability: Literal["stable", "evolving"]
    http_status: int                   # 400/401/403/404/422/500 etc.
    payload_model: type[BaseModel]     # Pydantic class defining the data shape
    exception_class: type[Exception] | None = None   # for formatter lookup; None means "raised directly, not via exception"

    model_config = {"frozen": True}
```

The registry is an `OrderedDict[str, CatalogueEntry]` keyed by `code`. Insertion order is the docs order.

---

## Payload models (one per code)

All live in `backend/infrahub/errors/payloads.py`. Field names below match the canonical shapes in [discovery.md](./discovery.md) §8 and may be refined in implementation (per FR-005's allowance).

### `NODE_NOT_FOUND`

```python
class NodeNotFoundData(BaseModel):
    node_kind: str
    identifier: str   # UUID, slug, or HFID — backend never reveals which path was attempted
```

- Raised by adopted exception: `NodeNotFoundError`.
- HTTP status: 404.
- Stability: stable.

### `AUTHENTICATION_REQUIRED`

```python
class AuthenticationRequiredData(BaseModel):
    pass   # ships with empty payload per spec FR-005
```

- Raised by adopted exception: `AuthorizationError` (when no/invalid creds present).
- HTTP status: 401.
- Stability: stable.

### `TOKEN_EXPIRED`

```python
class TokenExpiredData(BaseModel):
    expired_at: datetime | None = None   # optional; only populated when the token carries an exp claim we can surface
```

- Raised by adopted exception: `AuthorizationError` with the "Expired Signature" sub-condition (split from `AUTHENTICATION_REQUIRED`).
- HTTP status: 401.
- Stability: stable.

### `PERMISSION_DENIED`

```python
class PermissionDeniedData(BaseModel):
    action: str | None = None      # e.g. "update", "delete", "read" — optional, only when the backend has it
    resource_kind: str | None = None
```

- Raised by adopted exception: `PermissionDeniedError`.
- HTTP status: 403.
- Stability: stable.
- Per FR-013: MUST NOT include `identifier` of the resource if the user has no read permission.

### `ATTRIBUTE_REQUIRED`

```python
class AttributeRequiredData(BaseModel):
    node_kind: str
    field_name: str
```

- Raised by new exception: `AttributeRequiredError` (in `backend/infrahub/errors/exceptions.py`), classified from `ValidationError.input_value` reasons matching "mandatory".
- HTTP status: 422.
- Stability: stable.

### `ATTRIBUTE_INVALID_TYPE`

```python
class AttributeInvalidTypeData(BaseModel):
    node_kind: str
    field_name: str
    expected_type: str       # e.g. "Text", "Number", "Boolean"
    received_type: str       # e.g. "Int", "Str", "Bool"
```

- Raised by new exception: `AttributeInvalidTypeError`, classified from `ValidationError.input_value` reasons matching "not a valid <type>".
- HTTP status: 422.
- Stability: stable.

### `ATTRIBUTE_CONSTRAINT_VIOLATION`

```python
class AttributeConstraintViolationData(BaseModel):
    node_kind: str
    field_name: str
    constraint: str          # e.g. "regex", "min_length", "max_value"
    detail: str | None = None
```

- Raised by new exception: `AttributeConstraintViolationError`, classified from any `ValidationError.input_value` reason that does not match the required/invalid-type patterns.
- HTTP status: 422.
- Stability: evolving (constraint/detail wording may stabilise after a release of observation).

### `BRANCH_NOT_FOUND`

```python
class BranchNotFoundData(BaseModel):
    branch_name: str
```

- Raised by adopted exception: `BranchNotFoundError`.
- HTTP status: 404.
- Stability: stable.

### `SCHEMA_NOT_FOUND`

```python
class SchemaNotFoundData(BaseModel):
    kind: str
```

- Raised by adopted exception: `SchemaNotFoundError`.
- HTTP status: 404.
- Stability: stable.

### `UNDEFINED_ERROR` (always present fallback)

```python
class UndefinedErrorData(BaseModel):
    pass   # always {}
```

- Raised by: anything not in the catalogue (catch-all in the formatter, per FR-015).
- HTTP status: 500 (or `exc.HTTP_CODE` when the exception derives from `infrahub.exceptions.Error`).
- Stability: stable (the contract of the fallback is stable, even though its occurrence is treated as a bug).

---

## Wire contract (GraphQL `extensions`)

Defined formally in [contracts/graphql-error-envelope.md](./contracts/graphql-error-envelope.md). Summary:

```jsonc
{
  "extensions": {
    "code": "<one of the catalogue codes or UNDEFINED_ERROR>",
    "http_status": 4xx | 5xx,
    "data": { /* validated against the code's payload_model JSON Schema */ }
  }
}
```

The `data` object's keys are exactly the fields declared by the corresponding `PayloadModel` (no extras). All payload models MUST set `model_config = {"extra": "forbid"}`; Pydantic v2's default is `ignore`, which would silently drop undocumented fields rather than catch them. Pydantic v2 `model_dump(mode="json")` produces JSON-safe values.

---

## Exception → catalogue mapping

```text
backend/infrahub/exceptions.py classes  →  catalogue code
─────────────────────────────────────────────────────────
NodeNotFoundError                       →  NODE_NOT_FOUND
AuthorizationError (no creds branch)    →  AUTHENTICATION_REQUIRED
AuthorizationError (expired branch)     →  TOKEN_EXPIRED
PermissionDeniedError                   →  PERMISSION_DENIED
BranchNotFoundError                     →  BRANCH_NOT_FOUND
SchemaNotFoundError                     →  SCHEMA_NOT_FOUND
ValidationError (resolver classifies)   →  ATTRIBUTE_REQUIRED |
                                            ATTRIBUTE_INVALID_TYPE |
                                            ATTRIBUTE_CONSTRAINT_VIOLATION
*anything else*                         →  UNDEFINED_ERROR
```

Implementation note: the `AuthorizationError` split is handled at the catalogue-mapping layer (read the exception's existing fields, decide between the two codes). This avoids changing the exception class hierarchy.

---

## Registry construction

```python
# backend/infrahub/errors/catalogue.py (sketch)
from collections import OrderedDict

CATALOGUE: OrderedDict[str, CatalogueEntry] = OrderedDict([
    ("NODE_NOT_FOUND", CatalogueEntry(
        code="NODE_NOT_FOUND",
        description="The requested node does not exist in the database.",
        stability="stable",
        http_status=404,
        payload_model=NodeNotFoundData,
        exception_class=NodeNotFoundError,
    )),
    # ... 8 more entries ...
    ("UNDEFINED_ERROR", CatalogueEntry(
        code="UNDEFINED_ERROR",
        description="An error not yet covered by the catalogue. Its occurrence indicates a catalogue gap.",
        stability="stable",
        http_status=500,
        payload_model=UndefinedErrorData,
        exception_class=None,
    )),
])
```

The export step (`backend/infrahub/errors/export.py`) walks this registry and produces `schema/error-catalogue.json`.

---

## Stability transitions

A code's `stability` value follows the rules in spec FR-014 and FR-019:

- **Adding a new code**: non-breaking, can land any release.
- **Adding an optional field to an existing code's `data`**: non-breaking.
- **Removing a code, removing a field, renaming a field, changing a field type, making an optional field required**: breaking, follows Infrahub's deprecation policy.
- **`evolving` → `stable`**: non-breaking promotion, can happen any release after one full release at `evolving`.
- **`stable` → `evolving`**: not allowed; demotion is effectively a breaking change.
