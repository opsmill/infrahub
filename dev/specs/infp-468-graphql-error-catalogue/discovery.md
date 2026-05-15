# Discovery: Enriched GraphQL Error Catalogue (INFP-468)

**Created**: 2026-05-13
**Companion to**: [spec.md](./spec.md)
**Status**: Findings — pending review before spec update and `/speckit-plan`.
**Code-reference baseline**: `76395fd1c` (`stable` branch tip at the time of writing, 2026-05-13). All `file:line` references in this document were verified against that commit. If implementation lands later and lines have drifted, treat the file path as the authoritative anchor and re-locate the referenced code by symbol/content rather than by line number.

This document captures the cross-transport error inventory used to (a) decide which error codes belong in the v1 catalogue and (b) confirm/adjust the spec's assumptions about REST. Three parallel audits were run: backend (Infrahub), SDK (Python SDK), REST API.

---

## 1. Key architectural revelations

These finding(s) materially affect the spec and should be reconciled before planning.

### 1a. The integer `extensions.code` is REST-only today, not GraphQL

The GraphQL app uses `graphql-core`'s default `format_error`, which produces `{"message": "...", "extensions": {...}}` **but does not populate `extensions.code` at all** from an internal exception. The integer code currently observed at `extensions.code` is set by the central FastAPI exception handler:

> `backend/infrahub/api/exception_handlers.py:17-35` — `generic_api_exception_handler` constructs `{"data": null, "errors": [{"message": ..., "extensions": {"code": <HTTP_CODE int>}}]}` and the same shape is registered against `Error` and `ForwardableError` in `server.py:213-216`.

**Consequence**: when the Infrahub frontend reads `graphQLError.extensions?.code` (Apollo's `onError` link at `graphqlClientApollo.tsx:66`) and sees an integer like `401` or `403`, that response actually came from FastAPI's exception handler short-circuiting the GraphQL request (e.g. auth rejected before the GraphQL execution step). Apollo's `onError` receives both true GraphQL errors and HTTP-level errors and they're being conflated in the existing code.

**Spec impact**: the Breaking Changes section currently describes the change as repurposing a GraphQL field. It is actually more accurate to say: **REST error responses are reshaped** (existing integer at `extensions.code` moves to `extensions.http_status`, and the new string `code` is added), and **GraphQL error responses are *enriched*** (gaining `extensions.code` and `extensions.data` where they had nothing before). This is a smaller breaking change than the spec currently implies.

### 1b. REST and GraphQL share the same backend exception hierarchy — but should keep distinct wire formats

Every error condition surfaced by REST is a subclass of `backend/infrahub/exceptions.py::Error`, which carries an `HTTP_CODE` class attribute. The same classes are raised inside GraphQL resolvers. There is no "GraphQL-only" or "REST-only" subset of error *conditions* — but the appropriate *wire format* differs per transport.

**Revised position** (after reviewer feedback): the Python catalogue is the shared source of truth, but only GraphQL responses get `extensions.code` + `extensions.data` on the wire. REST keeps its current body shape; REST consumers discover the possible errors per endpoint via the OpenAPI schema, which is the idiomatic REST discovery surface. The long-term direction is for the OpenAPI schema to enumerate possible error responses per endpoint, referencing catalogue codes by name — captured as Future Direction in the spec.

**Spec impact**: the Transport assumption stays GraphQL-only on the wire, with explicit acknowledgment that (a) the Python catalogue is shared and (b) REST's discovery surface is OpenAPI, which is the long-term home for REST error documentation.

### 1c. SDK has concrete message-string parsing that the catalogue eliminates

Eight call sites in the SDK string-match against `error["message"]` text — exactly the brittleness the Jira ticket describes:

| File:Line | Pattern | Replaceable by |
|-----------|---------|----------------|
| `client.py:90`, `client.py:104` | `"Expired Signature" in [error.get("message") ...]` (relogin decorator) | `TOKEN_EXPIRED` (or similar auth code) |
| `query_groups.py:115` | `"Unable to find the node" not in exc.message` (suppress cascade-delete races) | `NODE_NOT_FOUND` |
| `file_handler.py:112`, `object_store.py:55,77,99,143,165,187` | Extract messages to raise `AuthenticationError` | `AUTHENTICATION_REQUIRED` / `PERMISSION_DENIED` |

These are deterministic adoption sites: each one becomes shorter and correct once the catalogue exists.

---

## 2. Backend exception inventory (grouped)

Only classes whose conditions are at least somewhat externally observable are listed. Counts are approximate raise-site frequency in `backend/infrahub/`.

### High-frequency / high-impact

- **`ValidationError`** — 194 sites. Attribute schema violations (mandatory fields, type mismatches, regex/length). Already carries structured `input_value: {field_name: error_message}` dict.
- **`NodeNotFoundError`** — 35 sites. Node lookups by ID/HFID. Captures `node_type`, `identifier`, `branch_name`.
- **`AuthorizationError`** (HTTP 401) — 15 sites. Auth missing/invalid.
- **`RepositoryError`** + family (`RepositoryConnectionError`, `RepositoryCredentialsError`, `RepositoryInvalidBranchError`, `RepositoryFileNotFoundError`, etc.) — 13 sites combined.
- **`ProcessingError`** (HTTP 400) — 12 sites. Generic "operation blocked by state".
- **`SchemaNotFoundError`** — 10 sites. Schema lookup failures.

### Medium

- **`ResourceNotFoundError`** — 7 sites. Generic 404 for REST.
- **`PermissionDeniedError`** (HTTP 403) — 5 sites. Authenticated user lacks permission.
- **`BranchStatusError`** + subclasses (`BranchAlreadyMergedError`, `BranchNeedsRebaseError`) — 5 sites.

### Rare / specialised

- **`HFIDViolatedError`** — 1 site, but already carries rich data (`matching_nodes_ids` set).
- **`BranchNotFoundError`** — 3 sites.
- **`QueryValidationError`** — 1 site.
- **`DiffError`** + subclasses — ~3 sites.

### Infrastructure (lower priority for v1)

`TransformError`, `CheckError`, `HTTPServerError` family, `DatabaseError`, `RPCError`, `LockError`, `QueryError`. These are mostly 5xx-class and integrators are unlikely to need fine-grained control.

### Where the integer `code` is set today

`backend/infrahub/api/exception_handlers.py:32`:

```python
error_dict: dict[str, Any] = {
    "data": None,
    "errors": [{"message": message, "extensions": {"code": http_code}} for message in messages],
}
```

This is the single migration point for REST.

---

## 3. SDK error landscape

29 concrete exception classes in `python_sdk/infrahub_sdk/exceptions.py`. Most are SDK-internal (raised by the SDK from its own logic). The interesting subset:

- **`GraphQLError`** — raised at four call sites in `client.py` (1008, 1073, 1915, 1980) whenever a GraphQL response contains an `errors` key. This is the handoff point: with the catalogue, these sites can dispatch on `extensions.code` and raise typed SDK errors instead of the generic wrapper.
- **`AuthenticationError`** — currently raised after extracting `error.get("message")` from the errors array (7 sites: `file_handler.py`, `object_store.py` x6).
- **`NodeNotFoundError`**, **`BranchNotFoundError`**, **`SchemaNotFoundError`** — SDK-internal but each corresponds 1:1 to a backend condition. With the catalogue, the SDK can raise these from the GraphQL/REST response directly rather than guessing.

The SDK already has typed exceptions for the most common backend conditions; the catalogue lets them be raised reliably instead of via message parsing.

---

## 4. REST API parity

REST routers and their relevant exception conditions:

| Router | Condition currently surfaced | Backend class | Today's HTTP |
|--------|------------------------------|---------------|--------------|
| `auth` | Missing/invalid credentials | `AuthorizationError` | 401 |
| `artifact`, `query`, `transformation` | Target not found | `NodeNotFoundError` | 404 |
| `artifact`, `query` | User not allowed | `PermissionDeniedError` | 403 |
| `schema` | Schema upload invalid | `ValidationError` | 422 |
| `schema`, `artifact` | Branch state blocks op | `BranchStatusError` | 422 |
| `file` | Commit not found | `CommitNotFoundError` | 400 |
| `*` catch-all | Generic 404 | `ResourceNotFoundError` | 404 |

**Implications** *(revised after reviewer feedback)*:

- Every REST error condition has a backend exception class that GraphQL also surfaces. **No REST-only codes required**, and equally no need to duplicate the catalogue's string `code` into REST response bodies.
- **REST wire format is unchanged**: `/api/...` responses keep their current body shape; REST consumers discover possible errors per endpoint via the OpenAPI schema. The Python catalogue is the shared source-of-truth for both transports, but each transport keeps idiomatic surface conventions.
- **Auth-short-circuit case is the seam**: the central handler at `backend/infrahub/api/exception_handlers.py:32` serves both `/api/...` routes and `/graphql` when FastAPI middleware short-circuits a request (e.g. auth). It must detect that the caller is the GraphQL route and emit GraphQL-shaped errors with the string `code` for that case, while continuing to emit today's shape for REST routes. This is the single implementation seam.
- **Blast radius unchanged**: the two frontend integer-reading sites consume GraphQL-bound responses (the auth-short-circuit path). REST consumers are not impacted.
- **Long-term direction**: the OpenAPI schema should eventually enumerate possible error responses per endpoint, referencing catalogue codes by name and ideally including the structured `data` shape for each. This becomes the authoritative discovery surface for REST consumers, analogous to the catalogue docs for GraphQL. Captured as Future Direction in `spec.md`; out of scope for v1.

---

## 5. Recommended v1 catalogue

Selection principle (per user's direction): "right and useful over many". Each code below either (a) eliminates message-string parsing in the SDK, (b) is required to migrate the 401/403 integer cases the frontend already handles, or (c) unlocks the form-validation UX explicitly named in the spec's US2.

### Codes proposed for v1

| Code | Backend class | `data` payload | Justification |
|------|---------------|----------------|---------------|
| `NODE_NOT_FOUND` | `NodeNotFoundError` | `{node_kind: str, identifier: str \| dict}` | 35 raise sites; SDK already parses message text for it (`query_groups.py:115`); REST 404 already returns it. **The single highest-value code.** |
| `AUTHENTICATION_REQUIRED` | `AuthorizationError` | `{}` (initially empty — no useful payload identified yet) | Migrates the 401 path that the frontend's `graphqlClientApollo.tsx:67-97` already branches on for token refresh. SDK has 7 sites parsing for "Expired Signature" — fold into this code or split out `TOKEN_EXPIRED` (see open question 1 below). |
| `PERMISSION_DENIED` | `PermissionDeniedError` | `{action?: str, resource?: str}` (or `{}` initially) | Migrates the 403 path that `graphqlClientApollo.tsx:98+` already branches on. Lets frontend route to permission dialog vs. toast. SA integrations benefit. |
| `VALIDATION_ERROR` | `ValidationError` | `{field_name: str, kind: str, reason: str}` — one error entry per failing field | 194 raise sites; **the primary driver of US2 (per-field form highlighting)**. Backend already carries `input_value: {field: reason}` structure; just needs to be serialised one-per-field into the GraphQL `errors` array. |
| `BRANCH_NOT_FOUND` | `BranchNotFoundError` | `{branch_name: str}` | SDK currently detects this by checking empty arrays or HTTP 400; small payload but eliminates SDK guesswork; common in branch-aware integrations. |
| `SCHEMA_NOT_FOUND` | `SchemaNotFoundError` | `{kind: str}` | SDK relies on KeyError + message; useful for SDK schema-cache logic and frontend schema-validation feedback. |

### Codes deferred to a follow-up release (rationale alongside)

- `REPOSITORY_*` family — high value for SA integrations but a whole family; better as its own iteration once the v1 contract is stable.
- `BRANCH_STATUS_*` (merged / needs-rebase) — only 5 sites; valuable but not blocking US1/US2.
- `PROCESSING_ERROR` — too generic; would need splitting into sub-codes first.
- `HFID_VIOLATED` — single raise site; rich data already captured; adopt when we touch the validation domain in a follow-up.
- `RESOURCE_NOT_FOUND` (REST catch-all) — keep until we know whether to merge into `NODE_NOT_FOUND` or keep distinct for non-node resources.
- All 5xx-class codes — out of scope for v1.

### Coverage analysis

The v1 batch above:

- Eliminates **every** message-string parsing site currently in the SDK (8/8).
- Migrates **both** integer-code branches in the frontend (401 → `AUTHENTICATION_REQUIRED`, 403 → `PERMISSION_DENIED`).
- Delivers the per-field form-validation payload required by US2.
- Covers the two codes the Jira ticket names explicitly (`NODE_NOT_FOUND`, `PERMISSION_DENIED`) plus the attribute-validation family.
- Six codes total — small enough to land cleanly in one release, large enough that the catalogue is genuinely useful on day one.

---

## 6. Open questions surfaced by discovery

1. **Auth code split**: should the auth domain be one code (`AUTHENTICATION_REQUIRED`) or two (`AUTHENTICATION_REQUIRED` for missing/invalid + `TOKEN_EXPIRED` for expired-signature)? The frontend's token-refresh path benefits from `TOKEN_EXPIRED` being distinguishable (don't show login redirect if a silent refresh succeeds), and the SDK has explicit `"Expired Signature"` detection. Recommendation: **split into two codes** — minimal extra effort, removes ambiguity for the most-handled error path.

2. **`VALIDATION_ERROR` granularity**: keep it as one code with `data` describing the failing field, or split into `ATTRIBUTE_REQUIRED`, `ATTRIBUTE_INVALID_TYPE`, `ATTRIBUTE_CONSTRAINT_VIOLATION`? Splitting matches Bilal's initial frontend draft and aligns with US2's acceptance scenarios. Recommendation: **split into the three sub-codes** — frontend can branch on the specific failure kind without parsing `reason`.

3. **`extensions.data` shape across transports** *(superseded by reviewer feedback)*: original recommendation was for REST to mirror GraphQL's `data`. Revised: REST wire format is unchanged; only GraphQL carries `extensions.code` / `extensions.data`. REST consumers discover errors per endpoint via OpenAPI (Future Direction). No cross-transport wire decision is required for v1.

If both recommendations above are taken (auth split + validation split), the v1 catalogue is **9 codes**:

`NODE_NOT_FOUND`, `AUTHENTICATION_REQUIRED`, `TOKEN_EXPIRED`, `PERMISSION_DENIED`, `ATTRIBUTE_REQUIRED`, `ATTRIBUTE_INVALID_TYPE`, `ATTRIBUTE_CONSTRAINT_VIOLATION`, `BRANCH_NOT_FOUND`, `SCHEMA_NOT_FOUND`.

If neither split is adopted, the count falls back to the 6 codes proposed in §5. With only the validation split, 8 codes. With only the auth split, 7 codes. Adopting both is the recommended position.

---

## 7. Required spec updates *(applied 2026-05-15)*

The following changes have been applied to `spec.md` after reviewer feedback. This section is kept for traceability.

1. **Breaking Changes section reframed** — clarified that the wire-format change is scoped to GraphQL only. The integer at `extensions.code` exists today in responses produced by FastAPI's exception handler at the `/graphql` route (auth-short-circuit case); only those responses change shape. REST endpoint bodies under `/api/...` are unchanged. The verified blast radius (2 frontend files, 0 SDK files) is unchanged.
2. **Transport assumption** — kept GraphQL-only on the wire, with explicit notes that (a) the Python catalogue is the shared source of truth across both transports, and (b) REST consumers discover errors per endpoint via the OpenAPI schema (Future Direction).
3. **FR-005** — replaced the abstract analysis-driven phrasing with a pointer to the v1 list in §5+§6 of this document. (Final list pending Q-D1 sign-off.)
4. **US1 / US2 acceptance scenarios** — pending tightening to require per-field sub-codes (`ATTRIBUTE_REQUIRED` / `ATTRIBUTE_INVALID_TYPE` / `ATTRIBUTE_CONSTRAINT_VIOLATION`).
5. **`UNDEFINED_ERROR` catch-all** — added to FR-015 and Edge Cases as the always-present GraphQL fallback identifier.
6. **`SC-008`** — added to require 100% `extensions.code` coverage on GraphQL responses, with `UNDEFINED_ERROR` observability driving catalogue growth.
7. **Future Direction section** — added a new section in `spec.md` capturing long-term REST OpenAPI error enrichment, third-party schema export, and catalogue coverage growth.

Pending FRs to add (driven by discovery §9; awaiting Q-D5):

- Per-error explosion for bundled validation errors.
- GraphQL `path` MUST point at the failing field for catalogued field-level errors.
- Structured logs and telemetry include the catalogue `code`.
- `data` schema evolution rules (additive non-breaking; remove/rename follows deprecation policy).

---

## 8. Worked examples

Concrete end-to-end payloads for two representative codes, to make the shape unambiguous before planning.

### 8a. `NODE_NOT_FOUND` — single-target mutation

**Triggering request** (GraphQL update mutation targeting a missing node):

```graphql
mutation {
  BuiltinTagUpdate(
    data: { id: "17a90b4e-0000-0000-0000-deadbeef0000", description: { value: "renamed" } }
  ) {
    ok
  }
}
```

**Response (GraphQL)**:

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

**Response (REST, same condition surfaced through `/api/.../{id}`)** — **unchanged by this work**. The REST exception handler at `backend/infrahub/api/exception_handlers.py:32` continues to emit today's shape, with the integer HTTP status at `extensions.code`:

```json
{
  "data": null,
  "errors": [
    {
      "message": "Unable to find the node 17a90b4e-0000-0000-0000-deadbeef0000 / BuiltinTag in the database.",
      "extensions": {
        "code": 404
      }
    }
  ]
}
```

This is what REST consumers see today and what they will keep seeing after this feature ships. REST consumers learn about possible errors per endpoint via the OpenAPI schema, not via a wire-level string identifier; enriching the OpenAPI schema with catalogue codes is the Future Direction captured in `spec.md`. The HTTP transport status itself remains `404` regardless.

**Principle for `data` field selection** (GraphQL): include only fields the consumer doesn't already know from the request. `branch` is omitted because the caller chose it. `node_kind` is included on `NODE_NOT_FOUND` because some lookup paths (e.g. generic ID-based queries, polymorphic resolvers) don't carry the kind in the request and the SDK/frontend benefits from the disambiguation. Future additions to `data` follow the same rule: it must enable the consumer to do something they couldn't do by introspecting their own request.

**What the SDK does today** (`python_sdk/infrahub_sdk/query_groups.py:115`):

```python
except GraphQLError as exc:
    if not exc.message or "Unable to find the node" not in exc.message:
        raise
```

**What the SDK does with the catalogue**:

```python
except NodeNotFoundError:
    pass  # cascade-delete race; ignore
```

### 8b. `VALIDATION_ERROR` family — multi-field form submission

**Triggering request** (create with two simultaneous failures):

```graphql
mutation {
  BuiltinTagCreate(data: { description: { value: 42 } }) {
    ok
  }
}
```

**Response (GraphQL)** — one `errors` entry **per failing field**, not one combined entry:

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
        "data": {
          "node_kind": "BuiltinTag",
          "field_name": "name"
        }
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

**Where the type check happens** — and why the backend can fill both `expected_type` and `received_type`:

Attribute input `value` fields are typed `GenericScalar` in the GraphQL schema (`backend/infrahub/graphql/mutations/attribute.py:84-100`), which makes Graphene pass any JSON value straight through to Python without rejection. The real type check is `backend/infrahub/core/attribute.py:762`:

```python
if value_to_check.__class__ != cls.type:
    raise ValidationError({name: f"{value} is not a valid {schema.kind}"})
```

At that point the backend has both `cls.type` (the expected Python type, e.g. `int`, `str`, `bool`) and `value.__class__` (what actually arrived). Both can be serialised into `data` as strings (the current message text already embeds both implicitly). **So `received_type` is something the backend determines, not something Graphene rejects on our behalf.**

**Boundary**: this is true for attribute *values* because they use `GenericScalar`. It is *not* true for GraphQL operation shape errors (unknown field names, wrong argument scalars on non-`GenericScalar` inputs, malformed queries). Those are rejected by graphql-core / Graphene before any Infrahub code runs and surface as `GraphQLError`s with no `extensions.code` today. Bringing those into the catalogue is out of scope for v1 — they're a separate problem (would require a custom error formatter that re-classifies graphql-core's own errors).

**Frontend consumer (with generated bindings)**:

```ts
const fieldErrors = response.errors
  .filter(e => e.extensions.code === "ATTRIBUTE_REQUIRED"
            || e.extensions.code === "ATTRIBUTE_INVALID_TYPE"
            || e.extensions.code === "ATTRIBUTE_CONSTRAINT_VIOLATION")
  .map(e => ({ field: e.extensions.data.field_name, message: e.message }));

fieldErrors.forEach(({ field, message }) => form.setFieldError(field, message));
```

Both `extensions.data.field_name` and the GraphQL `path` carry the field identity — `data.field_name` is the canonical machine identifier; `path` lets sophisticated consumers walk the GraphQL operation tree if they want.

---

## 9. Other gaps the discovery surfaced

Not blocking spec sign-off, but each is something we should not lose track of.

### Belongs in the spec (proposed additions)

- **`data` schema evolution rules**: FR-014 covers stability of `code` values but not what counts as a breaking change to a `data` payload. Recommendation — additive changes (adding new optional fields to an existing code's `data`) are non-breaking; removing or renaming an existing `data` field, or making an optional field required, is breaking and follows the same deprecation policy as removing a code.
- **Per-error explosion of bundled validation errors**: today `ValidationError` carries an `input_value: {field_name: error_message}` dict (1 backend exception, N fields). The catalogue contract requires N entries in `errors` (one per field). This belongs as an explicit functional requirement so it isn't lost.
- **GraphQL `path` requirement**: the spec already says `path` is preserved (FR-002) but doesn't explicitly require it to point at the failing field for catalogued field-level errors. Worth tightening — consumers like form validators rely on this.
- **Telemetry / logging integration**: when an error is raised, the backend's structured logs and telemetry should include the catalogue `code` so on-call and analytics get the same identity. Cheap to add at the formatter, easy to forget if not stated.

### Belongs in the plan (implementation notes to carry forward)

- **GraphQL custom error formatter**: graphql-core's default `format_error` does not populate `extensions.code`/`data`. A custom formatter must be installed in `backend/infrahub/graphql/app.py` (around the place identified by the backend audit). This is also where exceptions wrapped via `GraphQLError(original_error=exc)` get their `extensions` field rendered.
- **GraphQL/auth-short-circuit handler split**: the central handler at `backend/infrahub/api/exception_handlers.py:32` currently serves both `/api/...` and `/graphql` routes. It must detect when the caller is the `/graphql` route and emit GraphQL-shaped errors with the string `code` for that case (replacing the integer at `extensions.code` with the string identifier from the catalogue, and adding `http_status` + `data`). For `/api/...` routes the handler keeps its current shape — REST wire format is unchanged.
- **Apollo `errorLink` migration**: `frontend/app/src/shared/api/graphql/graphqlClientApollo.tsx:66` switches on `extensions?.code` as integer — must be rewritten to switch on the string code (`AUTHENTICATION_REQUIRED` / `TOKEN_EXPIRED` for refresh, `PERMISSION_DENIED` for the silent path) with `http_status` consulted only as a tie-breaker if needed. Same release as the backend formatter.
- **Catalogue source-of-truth file**: open question — where in `backend/infrahub/` does the catalogue live? (`backend/infrahub/errors/catalogue.py`, alongside `exceptions.py`, or a new package?). Affects how generators discover it.
- **Binding generators**: two generators are needed — frontend TypeScript (lives in this repo) and SDK Python (lives in the `python_sdk/` submodule = separate repo). The frontend generator runs in this repo's CI as `regenerate && git diff --exit-code` (the FR-009 sync check). The SDK generator runs in the SDK repository's own CI against the catalogue's published machine-readable schema (FR-012) — Infrahub's CI cannot enforce SDK freshness because submodule contents are managed by the submodule's repo, not the parent.
- **Schema export**: the machine-readable schema file (FR-012) should be a build artefact, not a source file — same source as the bindings, just rendered to a third output (e.g. JSON Schema).
- **Backward-compat shim consideration**: if we want a soft migration window for the GraphQL endpoint, the formatter could temporarily emit *both* `extensions.code` (string) AND a legacy `extensions.legacy_code` (int) for one release. Probably not worth it given the verified small blast radius (2 frontend files, both in this repo); flag for explicit decision.
- **OpenAPI enrichment (Future Direction, out of scope for v1)**: scaffolding for per-endpoint error documentation in the OpenAPI schema. Each REST route would declare its possible error responses with catalogue code names. The catalogue source-of-truth file structure should be designed so this layering is straightforward later, even though no code in this release produces or consumes the enriched OpenAPI.

### Belongs in the rollout plan / release notes

- **Same-release coupling**: backend catalogue + GraphQL error formatter + auth-short-circuit GraphQL emission + frontend binding + Apollo errorLink migration MUST land in the same release (or the frontend will break on the auth path). REST endpoint bodies are not part of this coupling because their wire format is unchanged.
- **SDK release coupling**: SDK bindings live in a separate repository (the `python_sdk/` submodule) with its own release cadence. Backend-side catalogue changes can land independently; the SDK repository pulls the catalogue's published schema and regenerates its bindings on its own schedule. The typed-exception adoption inside the SDK (the 8 message-string sites) is a discrete piece of work in the SDK repo that follows once its bindings are generated — coordinating release notes across the two repos is worth doing but the SDK is not blocked by Infrahub's CI and Infrahub is not blocked by the SDK's binding work.
- **Documentation**: the docs page (FR-012) must list every v1 code with a worked example like §8a/§8b so integrators have a copy-pasteable starting point.

---

## 10. Decisions needed from reviewer

Please confirm or revise:

- **Q-D1**: Adopt the v1 catalogue list as proposed in §5 + §6 (9 codes, including auth split and validation split)?
- **Q-D2** *(resolved 2026-05-15)*: ~~Adopt REST + GraphQL as a unified wire-format catalogue.~~ **Resolved**: REST keeps its current wire format; only GraphQL responses gain `extensions.code` + `extensions.data`. The Python catalogue is the shared source of truth across both transports, and OpenAPI is the long-term home for REST error documentation (captured as Future Direction in `spec.md`).
- **Q-D3** *(partially applied 2026-05-15)*: Spec updates listed in §7 — Breaking Changes reframe, Transport assumption, `UNDEFINED_ERROR` catch-all (FR-015 + Edge Cases), `SC-008`, Future Direction section are **applied**. Outstanding: FR-005 final list (pending Q-D1), US1/US2 sub-code tightening (pending Q-D1), and the four FRs from Q-D5.
- **Q-D4**: Adopt the worked example shapes in §8 as the canonical reference shape (acknowledging field names like `node_kind`, `field_name`, `expected_type` may still be refined during planning)?
- **Q-D5**: Of the "Belongs in the spec" items in §9, which should be promoted into `spec.md` now (data evolution rules, per-error explosion, `path` requirement, telemetry/logging)? Default: all four.
