# Feature Specification: Enriched GraphQL Error Catalogue

**Feature Branch**: `graphql-error-catalogue-infp-468`
**Created**: 2026-05-13
**Last updated**: 2026-05-19
**Status**: Ready for planning
**Jira Issue**: INFP-468
**Linked Epic**: IFC-2279
**Code-reference baseline**: `76395fd1c` (`stable` branch tip at the time of writing, 2026-05-13). All `file:line` references in this spec — and in the companion [discovery.md](./discovery.md) — were verified against that commit. If implementation lands later and lines have drifted, treat the file path as the authoritative anchor and re-locate the referenced code by symbol/content rather than by line number.
**Input**: "Enrich GraphQL errors raised by Infrahub with a structured error code and a typed data payload exposed via the GraphQL `extensions` field, backed by an authoritative error catalogue used to generate bindings for the frontend and the Python SDK, with a CI check enforcing that those bindings stay in sync with the backend."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Structured Error Codes and Data in GraphQL Responses (Priority: P1)

When a GraphQL query or mutation fails inside Infrahub, the response includes — for every error in the `errors` array — an `extensions` object containing a stable machine-readable `code` (such as `NODE_NOT_FOUND` or `PERMISSION_DENIED`) and a `data` object carrying the contextual information that is specific to that error kind (e.g. which node identifier was missing, which attribute violated which rule). The existing human-readable `message` is preserved unchanged so logs and ad-hoc tooling keep working.

**Why this priority**: This is the foundation. Without a stable backend contract, no downstream consumer (frontend, SDK, integrations) can move off text parsing. Once this is in place, every other consumer story can be unblocked independently and incrementally. It also unlocks the multi-release rollout described in the Jira ticket, where additional error sites can opt into the catalogue over time.

**Independent Test**: Can be fully tested by issuing a GraphQL request that triggers each error in the initial catalogue and asserting that the response includes `errors[*].extensions.code` matching the documented value and `errors[*].extensions.data` matching the documented shape for that code. No frontend or SDK changes are needed to verify this slice.

**Acceptance Scenarios**:

1. **Given** a node ID that does not exist in the database, **When** a client issues an update or delete mutation targeting that ID, **Then** the response contains an entry in `errors` whose `extensions.code` equals `NODE_NOT_FOUND` and whose `extensions.data` identifies which kind and which identifier were searched for. (Note: GraphQL list queries for missing nodes return an empty array rather than an error — `NODE_NOT_FOUND` is surfaced by operations that require a specific node, e.g. update/delete mutations or single-node lookups.)
2. **Given** a user without permission on a target node, **When** the user mutates that node, **Then** the response contains an entry in `errors` whose `extensions.code` equals `PERMISSION_DENIED` and whose `extensions.data` identifies the action and target sufficient for an integrator to log or message about it.
3. **Given** a create or update mutation that omits a mandatory attribute, **When** the mutation is executed, **Then** an `errors` entry has `extensions.code` equal to `ATTRIBUTE_REQUIRED` and `extensions.data` includes the attribute name and node kind.
4. **Given** a mutation that fails multiple field validations at once (e.g. one missing required field plus one wrong-typed field), **When** the mutation is executed, **Then** the response contains one entry in `errors` per failing field (rather than a single combined message), each carrying the specific sub-code that classifies the failure (`ATTRIBUTE_REQUIRED`, `ATTRIBUTE_INVALID_TYPE`, or `ATTRIBUTE_CONSTRAINT_VIOLATION`) and its own `data` payload.
5. **Given** any error that is not yet covered by the catalogue, **When** that error is raised, **Then** the response still returns a well-formed GraphQL error (with `message`) so that uncovered errors degrade gracefully rather than breaking clients that already opted into structured handling.

---

### User Story 2 - Frontend Type-Safe Error Handling (Priority: P2)

Frontend developers can import generated bindings that map each error `code` to the precise TypeScript type of its `data` payload, so the UI can branch on `code` and consume `data` with full type-safety — enabling field-level form validation (highlighting every invalid field in one pass) and reliable code-based control flow (e.g. permission dialogs vs. toast).

**Why this priority**: Form-level validation and reliable control flow are the two most concrete UX wins called out by the frontend team in INFP-468 (Bilal's comment). Delivering this slice is what makes the catalogue user-visible in the product. It depends on US1 but is otherwise self-contained.

**Independent Test**: Can be fully tested by generating the frontend bindings from the backend catalogue, writing a small consumer that switches on `code` and reads `data`, and confirming the consumer compiles with strict typing against each documented error. Form-validation use can be demonstrated by submitting a mutation with multiple invalid fields and verifying the UI highlights all of them simultaneously based solely on the structured response.

**Acceptance Scenarios**:

1. **Given** the generated frontend bindings, **When** a developer writes a handler that switches on the error `code`, **Then** the corresponding `data` payload is statically typed without manual casts and unknown codes are surfaced as a typed fallback branch.
2. **Given** a form for creating a node, **When** the user submits with multiple invalid fields and the mutation returns multiple structured errors, **Then** the UI displays per-field error indicators on every offending field in a single round-trip.
3. **Given** an error with `code` `PERMISSION_DENIED`, **When** the frontend receives the response, **Then** the UI routes the error through the permission-handling path (not the generic toast) based on `code` alone.

---

### User Story 3 - Python SDK Typed Errors (Priority: P3)

Python SDK users receive errors from the SDK in a typed form (rather than parsing strings), aligned to the same catalogue, so SDK callers and SA-team integrations (Ansible, Nornir) can branch on a stable identifier and access the structured `data` per error.

**Why this priority**: The SDK is the second-largest consumer of GraphQL errors after the frontend, and SDK consumers (including SA integrations) currently screen-scrape error text — a fragility called out in the Jira ticket. Like US2, this is self-contained on top of US1.

**Independent Test**: Can be fully tested by invoking each catalogue error through the SDK, asserting the caller can branch on the typed identifier and read structured fields without parsing `message`, and confirming SDK behaviour does not depend on the wording of any error string.

**Acceptance Scenarios**:

1. **Given** a Python script using the SDK, **When** the script makes a call that triggers `NODE_NOT_FOUND`, **Then** the caller can detect that condition by inspecting a typed identifier (not by string-matching the message) and read the missing identifier from a typed `data` field.
2. **Given** a script that currently checks for "unable to find the node" in `message`, **When** rewritten to use the catalogue, **Then** it no longer depends on message wording and remains correct if the message is later rephrased.
3. **Given** any error in the initial catalogue, **When** raised through the SDK, **Then** the SDK exposes the same `code` and the same `data` structure as the GraphQL response, with no information loss.

---

### User Story 4 - CI Enforcement of Frontend Binding Sync (Priority: P3)

The Infrahub repository's CI fails any pull request in which the committed frontend bindings are out of date with the backend's authoritative error catalogue — preventing the catalogue from drifting silently between releases. SDK binding freshness is enforced by the SDK repository's own CI (since the SDK is a separate repo brought in here as a submodule) and is therefore out of scope for this user story.

**Why this priority**: Without this, US2 will rot the first time a contributor adds, removes, or changes an error in the backend without regenerating the frontend bindings. It is cheap to add once US2 exists, and high-leverage for long-term maintainability. SDK sync is the SDK repo's responsibility against the catalogue's published schema (FR-012).

**Independent Test**: Can be fully tested by intentionally modifying the backend catalogue without regenerating the frontend bindings, opening a pull request, and confirming CI fails with a clear message pointing the contributor at the regeneration command. Conversely, regenerating the bindings makes CI pass again.

**Acceptance Scenarios**:

1. **Given** a pull request that adds a new error code to the backend catalogue without updating the frontend bindings, **When** CI runs, **Then** CI fails and the failure message names the missing/outdated artefact and the command to regenerate it.
2. **Given** a pull request that changes the shape of an existing error's `data` without regenerating frontend bindings, **When** CI runs, **Then** CI fails for the same reason.
3. **Given** a pull request that updates both the catalogue and the regenerated frontend bindings consistently, **When** CI runs, **Then** the sync check passes.
4. **Given** a pull request that touches only the backend catalogue, **When** CI runs, **Then** the SDK submodule is not inspected by this check (its sync is enforced upstream in the SDK repository).

---

### User Story 5 - Public Error Schema for Third-Party Consumers (Priority: P4)

Operators and third-party integrators (outside the Infrahub repository) can obtain a machine-readable description of the error catalogue — every `code` and the shape of its `data` payload — so they can generate their own bindings or validate responses without copying source code from Infrahub.

**Why this priority**: This is explicitly described in the Jira ticket as a "looking ahead" benefit. It is valuable but not on the critical path to fixing internal pain. Doing it as a separate slice avoids coupling community-facing surface to internal binding mechanics.

**Independent Test**: Can be fully tested by fetching/exporting the published schema from a built Infrahub artefact and feeding it into a separate (non-Infrahub) code generator or validator that successfully reproduces typed bindings or validates a captured GraphQL response.

**Acceptance Scenarios**:

1. **Given** a released Infrahub version, **When** an external consumer obtains the error catalogue schema, **Then** the schema lists every supported `code` and the structural definition of its `data` payload.
2. **Given** an updated catalogue in a later Infrahub release, **When** the consumer pulls the new schema, **Then** changes (added, removed, modified codes) are detectable by diffing the schema between versions.

---

### Edge Cases

- **Uncovered errors**: every **GraphQL** error response carries `extensions.code` without exception. When an internal error is raised that has not yet been adopted into the catalogue, the response carries `code = UNDEFINED_ERROR`. `UNDEFINED_ERROR` is a contract-level signal that the backend has a catalogue gap — its occurrence is treated as a bug to be triaged and either classified into a proper code or explicitly accepted as out-of-scope. GraphQL consumers can always rely on `extensions.code` being present, and their typed-fallback branch is the `UNDEFINED_ERROR` case rather than a "code missing" case.
- **Multiple errors per response**: when a single request produces several distinct catalogue errors (e.g. multiple invalid form fields), all of them must appear in the `errors` array independently, each with their own `code` and `data`. Combining them into one error is not acceptable for the form-validation use case.
- **Errors raised from nested resolvers** vs. top-level mutations: structured errors must be produced regardless of where in resolution they originate, and the GraphQL `path` continues to point at the offending field.
- **Backward compatibility for text-based consumers**: existing scripts and dashboards that read `message` must continue to function; the catalogue adds structured information without removing or altering the existing `message` field's intent.
- **Sensitive data in `data` payloads**: structured payloads must not leak information that the requesting user would not otherwise be entitled to see (e.g. existence of objects they have no permission on, internal IDs in security-sensitive contexts).
- **Partial mutation success**: when a mutation that touches multiple records partially fails, the structured errors must allow a caller to identify which record(s) failed without re-querying.
- **Catalogue change without binding regeneration**: see US4 — must fail CI rather than producing a silently broken release.
- **REST API errors raised by the same backend code paths**: the underlying backend exception classes are shared (a single Python catalogue is the source of truth), but REST response bodies under `/api/...` continue to behave as today — the wire-format change in this feature is scoped to GraphQL. REST's discovery surface for consumers is the OpenAPI schema; the long-term direction is for that schema to enumerate the possible error responses per endpoint, referencing catalogue codes by name. Carrying out that OpenAPI enrichment is out of scope for v1 (see Future Direction).
- **Apollo client compatibility**: the chosen `extensions` shape must be consumable by Apollo Client without custom link middleware beyond what is already in use (named out as a verification requirement in the Jira ticket).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST emit, on every GraphQL error that originates from a catalogued condition, an `extensions` object containing a `code` field (a stable string identifier) and a `data` field (a structured object whose shape is defined by the catalogue for that `code`).
- **FR-002**: System MUST preserve the existing GraphQL `message`, `locations`, and `path` fields on every error in the response, so that consumers that have not adopted the catalogue continue to work.
- **FR-003**: System MUST return one entry in the GraphQL `errors` array per distinct catalogued failure within a single request (e.g. multiple invalid fields produce multiple entries, not one combined entry).
- **FR-004**: System MUST maintain a single authoritative definition of each catalogue error inside the Infrahub backend codebase, with the `data` shape declared as a strongly-typed Python structure (i.e. not free-form dictionaries), so the catalogue cannot drift from what the backend actually emits.
- **FR-005**: The v1 catalogue MUST consist of the following nine codes (selected per the "right and useful over many" principle from the discovery analysis in [discovery.md](./discovery.md) §5–§6): `NODE_NOT_FOUND`, `AUTHENTICATION_REQUIRED`, `TOKEN_EXPIRED`, `PERMISSION_DENIED`, `ATTRIBUTE_REQUIRED`, `ATTRIBUTE_INVALID_TYPE`, `ATTRIBUTE_CONSTRAINT_VIOLATION`, `BRANCH_NOT_FOUND`, `SCHEMA_NOT_FOUND`. This set eliminates every existing message-string parse site in the SDK, migrates both integer-code branches in the frontend (`401` → `AUTHENTICATION_REQUIRED`/`TOKEN_EXPIRED`, `403` → `PERMISSION_DENIED`), and delivers the per-field validation payload required by US2. A code MAY ship with an empty `data` object (`{}`) when no useful payload has yet been identified, provided the code itself enables programmatic handling. The canonical `data` shape for each code is defined in [discovery.md](./discovery.md) §8; field names may be refined during planning. Additional codes are explicitly out of scope for v1 (see discovery §5 deferred list) but may be admitted to the catalogue in subsequent releases without breaking the contract.
- **FR-006**: System MUST provide a machine-consumable description of the catalogue (every `code` and the schema of its `data`) suitable for code generation, distinct from the GraphQL schema (which cannot natively represent the dynamic per-code shape of `data`).
- **FR-007**: System MUST generate type-safe frontend bindings from the authoritative catalogue such that frontend code branching on `code` receives a precisely typed `data` payload, with a typed fallback for unknown codes.
- **FR-008**: System MUST generate Python SDK bindings from the same authoritative catalogue, exposing the same identifiers and `data` shapes to SDK consumers without forcing them to parse the GraphQL `message` text.
- **FR-009**: The Infrahub repository's CI MUST include a check that fails when the committed **frontend** bindings do not match what would be regenerated from the current backend catalogue. The failure message MUST point at the regeneration command. SDK bindings live in the `python_sdk/` submodule and are out of scope for the Infrahub repository's CI — keeping the SDK in sync is the responsibility of the SDK repository's own CI, which consumes the catalogue's machine-readable schema (FR-012) as an external input.
- **FR-010**: System MUST clearly state in user-facing documentation which `code` values, and which fields of `data`, are part of the stable contract, and which (if any) are still considered evolving — so integrators know what they can rely on across releases.
- **FR-011**: System MUST place the string error identifier at `extensions.code` (aligning with Apollo / GraphQL ecosystem convention) and MUST move the HTTP status integer — currently carried at `extensions.code` — to a dedicated `extensions.http_status` field, so the two pieces of information no longer collide on the same key.
- **FR-012**: System MUST expose the error catalogue through **both** of the following surfaces: (a) a human-browsable documentation page generated from the catalogue source so developers and integrators can review every code, its `data` shape, its description, and its stability status; and (b) a machine-readable schema file shipped with each build so code generators (internal and third-party) can consume the catalogue without scraping the docs.
- **FR-013**: System MUST not include in `extensions.data` any information about an object that the requesting user is not entitled to see (e.g. confirming a node exists when permission is denied).
- **FR-014**: System MUST keep `code` values stable across releases once published — adding new codes is allowed at any time, removing or renaming a published code constitutes a breaking change and MUST follow Infrahub's existing deprecation policy.
- **FR-015**: System MUST surface uncovered (not-yet-catalogued) errors raised through the **GraphQL** response with `extensions.code = "UNDEFINED_ERROR"` so every GraphQL error response carries a `code` without exception. `UNDEFINED_ERROR` is reserved as the always-present fallback identifier and its occurrence is treated as a bug (the catalogue has a gap that should be filled or explicitly accepted as out-of-scope). The human-readable `message` continues to be populated, and the rollout can be incremental across multiple releases — uncovered errors degrade gracefully into `UNDEFINED_ERROR` rather than breaking the contract.
- **FR-016**: When a single backend operation produces multiple catalogued field-level failures (e.g. a `ValidationError` whose internal `input_value` dict carries N field errors), the GraphQL response MUST emit one entry in the `errors` array per failing field, each with its own `code` and `data`. Combining multiple field failures into one error entry is not acceptable — it would break the US2 form-validation use case.
- **FR-017**: For any catalogued field-level error, the GraphQL `path` field in that error entry MUST point at the offending field within the operation (e.g. `["BuiltinTagCreate", "data", "description", "value"]`), so that consumers can correlate the error with the input field without parsing `message` or relying solely on `data.field_name`. This is a tightening of FR-002, which only requires `path` to be preserved.
- **FR-018**: When a catalogued error is raised, the backend's structured logs and telemetry MUST include the catalogue `code` as a first-class field, so that on-call dashboards and analytics consumers see the same identity as GraphQL API consumers without parsing log messages.
- **FR-019**: Changes to a published `data` payload follow these evolution rules: adding a new optional field is non-breaking and MAY happen at any time; removing a field, renaming a field, changing a field's type, or making an optional field required is a breaking change and MUST follow Infrahub's existing deprecation policy (same as removing or renaming a `code`, per FR-014).

### Key Entities

- **Error Catalogue**: The single authoritative list of error definitions inside the Infrahub backend. Each entry has a stable `code` (string identifier), a structured `data` schema, a human-readable description, and stability metadata (stable vs. evolving).
- **Error Code**: A stable string identifier such as `NODE_NOT_FOUND` or `PERMISSION_DENIED`. Uppercase snake_case, namespaceable if future growth warrants it.
- **Error Data Payload**: The structured object specific to one error code, carrying the contextual information a consumer needs to react (e.g. which attribute name was missing, which kind was searched). Defined alongside the code in the catalogue.
- **Error Binding**: A generated artefact in a consumer codebase (frontend TypeScript types; Python SDK types/exceptions) that mirrors the catalogue and allows that consumer to handle errors in a type-safe way.
- **Catalogue Schema**: The machine-readable description of the whole catalogue (every code + every data shape) used to generate bindings and, in the future, consumed by third parties.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of catalogued errors returned by the backend carry both `extensions.code` and `extensions.data` matching the published schema for that code, verified by an end-to-end test that triggers each catalogued error.
- **SC-002**: Frontend handlers can branch on every catalogue error using `code` alone, with zero string parsing of `message` in product code — measurable by static-analysis count of `message`-string-matching call sites in the frontend (target: 0 net new, and a reduction in pre-existing ones for the catalogued errors).
- **SC-003**: Python SDK callers can match every catalogue error without parsing `message`, demonstrated by removing all existing message-string checks for the catalogued errors from the SDK and replacing them with typed checks.
- **SC-004**: When a user submits a form with N invalid fields, the UI displays an error indicator on every one of the N fields after a single submit (no fix-submit-fix-submit cycle), verified by an end-to-end test.
- **SC-005**: Any pull request to the Infrahub repository that changes the backend catalogue without regenerating the frontend bindings fails CI with a self-explanatory message — verified by an intentional sync-break test in CI. (SDK sync is enforced by the SDK repository's own CI against the catalogue's published schema.)
- **SC-006**: For every catalogued error, a developer (or integrator) reading the catalogue documentation can determine the `code`, the exact shape of `data`, and whether the contract is stable, in under one minute without reading backend source code.
- **SC-007**: Adoption is incrementally measurable: at every release, the count of catalogued error codes is published, so we can track coverage growth over the multi-release rollout described in the Jira ticket.
- **SC-008**: 100% of GraphQL error responses carry `extensions.code` — verified by an integration test that triggers every catalogued error plus a synthetic uncovered exception, asserting `UNDEFINED_ERROR` for the synthetic case and the specific code for each catalogued case. The occurrence rate of `UNDEFINED_ERROR` in production is observable so it can be driven toward zero over successive releases.

## Breaking Changes

This feature includes one intentional breaking change, scoped to the **GraphQL** error contract. REST endpoint response bodies under `/api/...` are not affected by this work. The change is small in scope but must be called out explicitly and surfaced in release notes.

### What changes

In **GraphQL error responses**, the `extensions.code` field is being repurposed:

| Before                                            | After                                                  |
|---------------------------------------------------|--------------------------------------------------------|
| `extensions.code` is an integer HTTP status       | `extensions.code` is a string error identifier         |
| (e.g. `401`, `403`)                               | (e.g. `NODE_NOT_FOUND`, `PERMISSION_DENIED`)           |
| HTTP status is **not** otherwise represented in the error payload | HTTP status moves to a new `extensions.http_status` field (integer) |
| `extensions.data` does not exist                  | `extensions.data` carries a typed payload defined by the catalogue for that `code` |

### Why

`extensions.code` carrying a string error identifier is the GraphQL ecosystem convention (Apollo Server's default; widely expected by GraphQL tooling and third-party integrators). The integer at `extensions.code` is actually emitted today by Infrahub's REST exception handler when a request to the `/graphql` endpoint is short-circuited by FastAPI middleware (e.g. auth rejection before GraphQL execution runs). Aligning the GraphQL wire format with the ecosystem convention now — before the catalogue is published — avoids permanently diverging from how GraphQL consumers expect the field to behave, and prevents Infrahub from needing a second non-standard error-identifier field forever.

### Out of scope for this breaking change

- **REST endpoints under `/api/...`**: response bodies keep their current behaviour. The OpenAPI schema is the discovery surface for REST consumers (see Future Direction).
- **Frontend's other Apollo paths**: unchanged unless they currently read `extensions.code` as an integer.

### Blast radius (verified)

- **Frontend**: two call sites in the Infrahub frontend currently read `extensions.code` as an integer (`graphqlClientApollo.tsx:66`, `pages/login.tsx:27-29`). Both consume GraphQL-bound error responses (auth-short-circuit case). Both must be migrated in the same release that introduces the new contract.
- **Python SDK** (this repo's `python_sdk/` submodule): the SDK's `GraphQLError` exception class bundles the raw `errors` array but does not itself introspect `extensions.code`. No SDK code change is forced by this rename — adopting the new typed `code` is pure addition.
- **External GraphQL integrations**: SA-team integrations (Ansible, Nornir) and any third-party GraphQL consumer that today reads `extensions.code` from a GraphQL response as an integer will need to update. The probability is assessed as low (the prior integer convention is non-standard and lightly used at the GraphQL endpoint) but cannot be guaranteed for code outside this repository.

### Release-notes requirement

The release containing this feature MUST include, in the user-facing release notes, an entry that:

1. Calls out that GraphQL `extensions.code` has changed from integer (HTTP status) to string (error identifier), and that REST `/api/...` response bodies are unaffected.
2. Names the new `extensions.http_status` field on GraphQL responses.
3. Points to the new error catalogue documentation (FR-012).
4. Provides a short migration snippet for the most likely consumer pattern (`if (extensions.code === 401)` → `if (extensions.http_status === 401)` or, preferably, switching on the string identifier).

## Assumptions

- **Transport**: The wire-format contract introduced by this feature is GraphQL-only. The Python error catalogue is a shared source of truth (the same backend exception classes are raised regardless of which transport surfaced them), but the `extensions.code` / `extensions.data` shape is added to GraphQL responses only. REST API response bodies under `/api/...` continue to behave as today. REST consumers discover possible errors per endpoint via the OpenAPI schema (see Future Direction for the long-term plan to enrich that schema).
- **Catalogue location**: The authoritative catalogue lives in the Infrahub backend repository. Frontend and SDK consumers receive generated, checked-in artefacts so that consumers can build without running the backend.
- **CI scope**: The Infrahub repository's CI sync check covers frontend bindings only. The Python SDK is a Git submodule with its own repository and its own CI — Infrahub's CI cannot enforce the SDK's binding freshness, and the SDK's contents are not modified by PRs against this repository. Keeping the SDK bindings in sync is the SDK repository's responsibility, using the catalogue's machine-readable schema (FR-012) as an external input (likely fetched from a tagged Infrahub release artefact). This is a cross-repo workflow, not a within-repo CI check.
- **Rollout shape**: Per the Jira ticket, the catalogue grows over multiple releases. The first release establishes the contract and the tooling (catalogue, bindings, CI), and includes a small initial set of high-value error codes. Subsequent releases adopt additional error sites without breaking the contract.
- **Message stability**: The human-readable `message` field is preserved but is explicitly not part of the stable contract. Consumers that want stability must move to `code` + `data`.
- **Naming convention**: `code` values use uppercase snake_case (e.g. `NODE_NOT_FOUND`) for consistency with the examples in the Jira ticket.
- **Initial-coverage method**: rather than pre-committing a numeric count of error codes for v1, the planning phase produces an analysis of currently-raised errors and selects those whose programmatic handling delivers concrete consumer value (form validation, control flow, permission UX). Codes whose `data` payload is not yet useful are still allowed to ship with `data: {}`. See FR-005.
- **`code` field semantics**: the string error identifier lives at `extensions.code` (Apollo / GraphQL convention). The integer HTTP status that previously occupied `extensions.code` moves to `extensions.http_status`. See Breaking Changes.
- **Catalogue surfaces**: both a generated documentation page and a machine-readable schema file are produced from the same authoritative source.
- **Apollo compatibility**: The chosen extensions shape works with Apollo Client out of the box (no exotic transport configuration on the consumer side). This is called out as a verification item from the Jira ticket.
- **Public schema timing**: User Story 5 (third-party schema export) is "looking ahead" and may land in a follow-up release; it is not blocking for the internal-pain-point fix that motivates this work.

## Future Direction *(out of scope for v1, captured to keep the long-term shape coherent)*

- **REST API error documentation via OpenAPI**: REST endpoints under `/api/...` should eventually have their possible error responses enumerated directly in the OpenAPI schema, per endpoint, referencing catalogue codes by name (e.g. `"This endpoint may raise NODE_NOT_FOUND, PERMISSION_DENIED."`) and ideally including the structured `data` shape for each. This makes the OpenAPI schema the authoritative discovery surface for REST consumers — analogous to what the catalogue documentation does for GraphQL — and removes any need for a duplicated string `code` in REST response bodies. Carrying this out is a separate piece of work; this v1 spec only requires that the catalogue source-of-truth in Python is structured so that the OpenAPI enrichment can be layered on later without rewriting it.
- **Third-party GraphQL schema export**: User Story 5 captures this; the machine-readable catalogue schema can be consumed by external integrators to generate their own bindings.
- **Catalogue coverage growth**: the Jira ticket frames this work as multi-release. Subsequent releases adopt additional backend exception classes into the catalogue, reducing the occurrence rate of `UNDEFINED_ERROR` toward zero.

## Dependencies

- INFP-468 (this work) blocks INFP-393 ("Improve repository synchronization logs"), which expects more granular error reporting.
- Linked Epic IFC-2279 ("[Spike] Enrich GraphQL errors raise by Infrahub") provides the prior discovery context referenced throughout this spec.
- Historical/related items providing context (not blockers): IFC-551, IFC-2026, IHS-98, community GitHub issue #143.
