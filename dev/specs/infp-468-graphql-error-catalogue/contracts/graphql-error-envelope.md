# Contract: GraphQL Error Envelope

**Feature**: INFP-468 | **Created**: 2026-05-19 | **Status**: v1, breaking change for `extensions.code`

This file pins the on-the-wire shape of GraphQL error responses after this feature ships. It is the consumer-facing contract; the backend implementation in `backend/infrahub/graphql/error_formatter.py` MUST produce exactly this shape.

---

## Per-error shape (every entry in `response.errors[]`)

```jsonc
{
  // Existing GraphQL fields — preserved verbatim:
  "message":   "<human-readable text, unchanged from today>",
  "locations": [{ "line": <int>, "column": <int> }],   // when applicable
  "path":      ["<operation>", "<field>", ...],         // when applicable, required for catalogued field-level errors

  // New / changed extensions block:
  "extensions": {
    "code":        "<string from catalogue, or UNDEFINED_ERROR>",
    "http_status": <int>,
    "data":        { /* shape per catalogue entry for `code` */ }
  }
}
```

### Field rules

| Field | Type | Required | Notes |
|---|---|---|---|
| `extensions.code` | string | **Always** | Uppercase snake_case. One of the published catalogue codes or `"UNDEFINED_ERROR"`. |
| `extensions.http_status` | integer | **Always** | The HTTP status that would have been returned in the REST equivalent. For pure GraphQL errors (which return HTTP 200 with errors in the body), this is the *logical* status: 401, 403, 404, 422, 500, etc. |
| `extensions.data` | object | **Always** | Validated against the catalogue's `data_schema` for `code`. May be `{}` for codes whose payload is empty (e.g. `AUTHENTICATION_REQUIRED`, `UNDEFINED_ERROR`). No extra fields beyond those declared in the schema. |
| `message` | string | Always (existing) | Preserved exactly as today. Not part of the stable contract — consumers wanting stability MUST switch on `code`. |
| `locations` | array | When graphql-core populates it | Preserved exactly as today. |
| `path` | array | **Required for catalogued field-level errors** | Per FR-017: when `code` identifies a field-level failure (`ATTRIBUTE_*`), `path` MUST point at the failing field, e.g. `["BuiltinTagCreate", "data", "description", "value"]`. For non-field errors (e.g. `AUTHENTICATION_REQUIRED`), `path` follows graphql-core's normal rules (may be present or absent). |

### Forbidden

- `extensions.code` MUST NOT be an integer (this is the breaking change from today's behavior).
- `extensions.data` MUST NOT include fields beyond those declared in the catalogue's schema for the given `code`.
- `extensions.data` MUST NOT contain information the caller is not entitled to read (FR-013).

---

## Per-response shape

```jsonc
{
  "data": <operation result or null>,
  "errors": [
    { /* per-error shape above */ },
    { /* per-error shape above */ },
    ...
  ]
}
```

### Multi-error rules

- Multiple distinct catalogued failures within a single request MUST appear as multiple entries (FR-003, FR-016).
- For a multi-field validation failure (e.g. one missing field + one wrong-typed field), each field MUST appear in `errors[]` separately, each with its own `code`, `data`, and `path`.

---

## Worked example: `NODE_NOT_FOUND`

**Request** (GraphQL mutation against a missing node):

```graphql
mutation {
  BuiltinTagUpdate(
    data: { id: "17a90b4e-0000-0000-0000-deadbeef0000", description: { value: "renamed" } }
  ) { ok }
}
```

**Response**:

```json
{
  "data": { "BuiltinTagUpdate": null },
  "errors": [
    {
      "message": "Unable to find the node 17a90b4e-0000-0000-0000-deadbeef0000 / BuiltinTag in the database.",
      "locations": [{ "line": 2, "column": 3 }],
      "path": ["BuiltinTagUpdate"],
      "extensions": {
        "code": "NODE_NOT_FOUND",
        "http_status": 404,
        "data": {
          "node_kind": "BuiltinTag",
          "identifier": "17a90b4e-0000-0000-0000-deadbeef0000"
        }
      }
    }
  ]
}
```

---

## Worked example: multi-field validation (per FR-016 + FR-017)

**Request**:

```graphql
mutation {
  BuiltinTagCreate(data: { description: { value: 42 } }) { ok }
}
```

**Response** — one `errors` entry per failing field:

```json
{
  "data": { "BuiltinTagCreate": null },
  "errors": [
    {
      "message": "name is mandatory for BuiltinTag",
      "path": ["BuiltinTagCreate", "data", "name"],
      "extensions": {
        "code": "ATTRIBUTE_REQUIRED",
        "http_status": 422,
        "data": { "node_kind": "BuiltinTag", "field_name": "name" }
      }
    },
    {
      "message": "description must be of type Text for BuiltinTag",
      "path": ["BuiltinTagCreate", "data", "description", "value"],
      "extensions": {
        "code": "ATTRIBUTE_INVALID_TYPE",
        "http_status": 422,
        "data": {
          "node_kind": "BuiltinTag",
          "field_name": "description",
          "expected_type": "Text",
          "received_type": "Int"
        }
      }
    }
  ]
}
```

---

## Auth-short-circuit example (FastAPI exception handler path)

When the caller hits the `/graphql` endpoint without valid credentials, the request is short-circuited before graphql-core ever runs. The FastAPI exception handler now emits the GraphQL-shaped envelope:

```json
{
  "data": null,
  "errors": [
    {
      "message": "Authentication required.",
      "extensions": {
        "code": "AUTHENTICATION_REQUIRED",
        "http_status": 401,
        "data": {}
      }
    }
  ]
}
```

Before this feature, the same response had `extensions.code = 401` (integer). This is the verified breaking change called out in the spec.

---

## `UNDEFINED_ERROR` example

When an uncatalogued exception escapes a resolver:

```json
{
  "data": null,
  "errors": [
    {
      "message": "Unexpected error processing operation.",
      "path": ["SomeMutation"],
      "extensions": {
        "code": "UNDEFINED_ERROR",
        "http_status": 500,
        "data": {}
      }
    }
  ]
}
```

The occurrence of `UNDEFINED_ERROR` is observable (per SC-008) and is treated as a catalogue gap to fix.

---

## REST `/api/...` responses — NOT covered by this contract

REST endpoint bodies are explicitly unchanged. The OpenAPI schema is the discovery surface for REST errors (Future Direction in spec.md).
