# Phase 0 Research: Enriched GraphQL Error Catalogue

**Feature**: INFP-468 | **Created**: 2026-05-19 | **Plan**: [plan.md](./plan.md)

This file resolves the open implementation questions surfaced by [discovery.md](./discovery.md) §9 ("Belongs in the plan"). The spec answers *what* and *why*; this file answers *how* before tasks are generated. Each section has the decision, the rationale, and the alternatives rejected.

---

## R-001 — Catalogue source-of-truth location

**Decision**: New package `backend/infrahub/errors/`, with:
- `catalogue.py` — the registry data (an ordered mapping of `code → CatalogueEntry`).
- `payloads.py` — one Pydantic `BaseModel` per code, defining the `data` shape.
- `exceptions.py` — a small layer that annotates the existing `backend/infrahub/exceptions.py` classes with their catalogue `code` (either via a class attribute `CATALOGUE_CODE: ClassVar[str]` added to the adopted classes, or via a `code_of(exc) -> str | None` mapper if we avoid touching `exceptions.py`).
- `export.py` — renders the catalogue into the machine-readable JSON Schema file.

**Rationale**: Keeps the registry separate from the existing 50+ exception classes in `backend/infrahub/exceptions.py`, which is already large and mixes infrastructure concerns. A dedicated package makes the generator's input trivial to discover and import (`from infrahub.errors.catalogue import CATALOGUE`). Pydantic payload models live with the registry so they are versioned together and cannot drift.

**Alternatives considered**:
- *Inline in `backend/infrahub/exceptions.py`*: rejected — the file is already long and mixes exception classes with HTTP status concerns; collocating catalogue metadata would make both harder to read and would force the catalogue exporter to import the full module graph.
- *Per-domain catalogues (e.g. `backend/infrahub/core/errors/`, `backend/infrahub/auth/errors/`)*: rejected for v1 — premature scaling. Nine codes do not justify a federated catalogue; a single registry is simpler. Can split later without changing the published JSON Schema (which is flat).

---

## R-002 — `data` payload definition: Pydantic vs. frozen dataclass

**Decision**: Pydantic v2 `BaseModel`, one per code. Field declarations use Python types (e.g. `node_kind: str`, `identifier: str`); serialization to the GraphQL `extensions.data` is `model.model_dump(mode="json", by_alias=False)`.

**Rationale**:
- Pydantic 2.10 is already a backend dependency. No new dependency added.
- `BaseModel.model_json_schema()` exports JSON Schema natively — the single primitive that unblocks the entire generator pipeline.
- Forced typing at construction (`PayloadModel(node_kind="BuiltinTag", identifier=node_id)`) catches mismatches at the raise site instead of at the wire. This satisfies FR-004 ("strongly-typed Python structure, not free-form dicts").
- Field aliases (Pydantic feature) are available if we later want the wire field name to differ from the Python attribute name.

**Alternatives considered**:
- *Frozen `@dataclass`*: works for the raise site but lacks built-in JSON Schema export. Would require pairing with `dataclasses-json` or hand-writing a schema emitter — extra moving parts for no gain.
- *TypedDict*: not enforceable at runtime; defeats the FR-004 invariant.

---

## R-003 — Machine-readable schema format

**Decision**: JSON Schema (draft 2020-12), shipped as a single committed file `schema/error-catalogue.json`. Structure:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "infrahub_catalogue_version": "1",
  "codes": {
    "NODE_NOT_FOUND": {
      "description": "...",
      "stability": "stable",
      "http_status": 404,
      "data_schema": { /* JSON Schema for the payload */ }
    },
    "...": "..."
  }
}
```

**Rationale**:
- JSON Schema is the lingua franca for code generators across languages (TypeScript, Python, Go, Rust). Choosing it makes the third-party scenario (US5, deferred) feel free.
- Pydantic produces draft 2020-12 by default; no schema-spec wrangling needed.
- A single file (vs. one per code) keeps the commit diff readable and the consumer logic trivial (one fetch).
- `infrahub_catalogue_version` is a coarse-grained version that future-proofs the wrapper without forcing semver on the codes themselves (codes have their own stability per-entry, per FR-014).

**Alternatives considered**:
- *GraphQL SDL union types*: rejected — GraphQL's type system cannot represent "the `data` shape depends on the value of `code`" without one of (a) a per-code object type returned from a discriminated union, which would require N error-specific GraphQL types and pollutes the API surface, or (b) `JSON` scalar, which throws away typing. Neither is acceptable.
- *OpenAPI fragment*: would tie REST and GraphQL discovery surfaces together prematurely; REST enrichment is a Future Direction in the spec.
- *Custom YAML format*: rejected — every consumer would need a custom parser. JSON Schema is parseable everywhere.

---

## R-004 — Frontend binding generator

**Decision**: `json-schema-to-typescript` (npm), invoked by a small script in `frontend/app/scripts/generate-error-bindings.ts` (or `.mjs`). Output: `frontend/app/src/shared/api/errors/catalogue.generated.ts`.

The hand-written `frontend/app/src/shared/api/errors/index.ts` re-exports the generated types and adds a discriminated-union helper:

```ts
export type CatalogueError =
  | { code: "NODE_NOT_FOUND"; data: NodeNotFoundData; http_status: number }
  | { code: "VALIDATION_ERROR"; data: ValidationErrorData; http_status: number }
  | ...
  | { code: "UNDEFINED_ERROR"; data: Record<string, never>; http_status: number };
```

The union is also generated (driven off the schema's `codes` map) so the typed-fallback branch on `UNDEFINED_ERROR` is checked by the TS compiler.

**Rationale**:
- `json-schema-to-typescript` is widely-used, has no transitive bloat, and produces idiomatic TS with proper discriminated unions when fed schema with a `const` for the discriminator.
- A single small script (rather than a generator package) keeps the codegen visible inside `frontend/app/`; matches the existing pattern of `pnpm codegen` for GraphQL types.
- The CI sync check is `regenerate && git diff --exit-code` — same pattern as the existing GraphQL codegen freshness check.

**Alternatives considered**:
- *quicktype*: heavier dependency surface, supports many target languages we don't need; YAGNI for v1.
- *Hand-written TS emitter in Python*: rejected — bespoke generator code is a maintenance burden Principle VII says to avoid. Use the existing tool.
- *Generated GraphQL types via codegen*: rejected — the catalogue is not expressible in GraphQL's type system (see R-003).

---

## R-005 — GraphQL custom error formatter

**Decision**: New file `backend/infrahub/graphql/error_formatter.py` exporting `catalogue_error_formatter(error: GraphQLError) -> GraphQLFormattedError`. Wired in at `backend/infrahub/graphql/initialization.py` (where `InfrahubGraphQLApp` is constructed) via the existing `error_formatter` constructor argument.

Formatter behavior:
1. Call graphql-core's `format_error(error)` for the baseline shape (preserves `message`, `locations`, `path` — satisfies FR-002).
2. Inspect `error.original_error`. If it's a catalogued exception type, look up the `code` from the catalogue and build the `data` payload from the exception's typed attributes.
3. Populate `extensions = {"code": <string>, "http_status": <int>, "data": <dict from model_dump>}`.
4. If no catalogued mapping exists, set `extensions = {"code": "UNDEFINED_ERROR", "http_status": 500, "data": {}}` (satisfies FR-015).
5. Emit a structured log entry with the catalogue `code` as a first-class field via `structlog` (satisfies FR-018).

For multi-field validation errors (one `ValidationError` carrying N field errors via `input_value: dict[str, str]`), the formatter cannot fan out one entry into N — that has to happen in the resolver. We add a small helper (`raise_validation_errors_per_field(input_value: dict, ...)`) that raises one `GraphQLError(original_error=AttributeRequiredError(...))` per field, attached to its `path`. This satisfies FR-016 and FR-017.

**Rationale**:
- `InfrahubGraphQLApp.__init__` already accepts `error_formatter` (line 99) — no infrastructure change needed.
- Wrapping `format_error` (rather than reimplementing it) preserves the `locations`/`path` mechanics graphql-core has handled for years.
- Doing the per-field fan-out at the resolver (not the formatter) is the only correct place — the formatter sees one `GraphQLError` at a time and cannot synthesize new `path` values out of thin air.

**Alternatives considered**:
- *Single per-validation-error formatter that splits one error into N at the formatter layer*: rejected — would have to reconstruct GraphQL `path` from `data.field_name`, but `path` carries operation-level context (mutation name, argument names) that only the resolver knows. Doing it in the formatter is fragile.
- *Use Graphene's `format_error` hook*: Graphene delegates to graphql-core's `format_error`. Same hook, indirect; using graphql-core's directly is cleaner.

---

## R-006 — REST/GraphQL exception handler split

**Decision**: Modify `backend/infrahub/api/exception_handlers.py:generic_api_exception_handler` so that if `request.url.path.startswith("/graphql")` (auth-short-circuit case), the response body uses the GraphQL-shaped error envelope:

```json
{
  "data": null,
  "errors": [{
    "message": "<existing message>",
    "extensions": {
      "code": "<catalogue code or UNDEFINED_ERROR>",
      "http_status": <int>,
      "data": <model dump or {}>
    }
  }]
}
```

For `/api/...` routes, the existing shape (`extensions.code = <int>`) is preserved exactly. This is the smallest change consistent with the spec's REST-unchanged scope.

**Rationale**:
- The same FastAPI handler serves both routes today. The only delta is response shape based on the route. A single `if` branch is cheaper than two handlers and is easy to test.
- Route-prefix matching is reliable (the GraphQL route is well-known and stable; not a runtime-registered route).

**Alternatives considered**:
- *Two separate exception handlers, registered with different `prefix`*: rejected — FastAPI exception handlers are not prefix-scoped; we'd still need a route-aware dispatch.
- *Always emit string code on both routes*: rejected — the spec explicitly carves REST out of the breaking change; doing both would force REST consumers (potentially external) to migrate too.

---

## R-007 — Backward-compatibility shim for the integer→string `extensions.code`

**Decision**: **No shim.** Ship the rename in a single release with the frontend migration in the same PR. Release notes carry the migration guidance per the spec's Breaking Changes section.

**Rationale**:
- Verified blast radius inside this repo: exactly 2 frontend files (`graphqlClientApollo.tsx:66`, `pages/login.tsx:27-29`), both migrated as part of the same task list — zero downtime within the repo.
- Verified blast radius in the SDK submodule: 0 sites (SDK does not introspect `extensions.code` today).
- External GraphQL consumers reading the integer code: probability low (the integer-at-`extensions.code` was non-standard for GraphQL; Apollo and most GraphQL tooling expect a string), and any consumer that does is already broken from a tooling-compatibility standpoint.
- A shim (`extensions.legacy_code = <int>`) would be a forever liability: once shipped, removing it is itself a breaking change, just kicked one release down the road. The clean break now is cheaper over a 5-year horizon.
- Release notes (spec.md §Breaking Changes) carry the migration snippet for the most likely external consumer pattern.

**Alternatives considered**:
- *Emit both `extensions.code` (string) and `extensions.legacy_code` (int) for one release*: rejected for the reasons above. Logged here so future readers know it was considered.
- *Two-release migration with feature flag*: rejected — the feature is not toggleable per consumer; the wire format is global. A feature flag adds runtime branching for no real audience.

---

## R-008 — Docs generation for the catalogue

**Decision**: A new Invoke task `docs.generate-error-catalogue` reads `schema/error-catalogue.json` and renders a Docusaurus page at `docs/docs/reference/error-catalogue/index.md`. The page lists every code with: description, stability badge, HTTP status, `data` shape (as a table), and a worked-example response (one for `NODE_NOT_FOUND`, one for the `VALIDATION_ERROR` family — pulled from discovery §8). The task runs as part of `docs.build`.

**Rationale**:
- Single source of truth: the catalogue JSON file. Docs cannot drift from the bindings because both are generated from it.
- Docusaurus is already the docs pipeline; no new infrastructure.
- Markdown generation from a flat JSON is trivial; no template engine needed beyond f-strings.

**Alternatives considered**:
- *Hand-written docs page kept in sync by convention*: rejected — drifts the first time someone adds a code without updating docs. FR-010 + FR-012 require the docs to be authoritative.
- *Auto-render at runtime from a `/api/errors/catalogue` endpoint*: rejected — the docs site is static; runtime rendering adds a backend dependency to the docs build for no real-world benefit.

---

## R-009 — CI sync check

**Decision**: A new Invoke task `frontend.check-error-bindings` runs:

```bash
uv run invoke backend.export-error-catalogue          # writes schema/error-catalogue.json
cd frontend/app && pnpm generate:error-bindings        # regenerates catalogue.generated.ts
git diff --exit-code schema/error-catalogue.json frontend/app/src/shared/api/errors/catalogue.generated.ts
```

Failure message: `Catalogue bindings are out of date. Run: uv run invoke frontend.regenerate-error-bindings`. Wired into the existing GitHub Actions workflow that already runs codegen freshness checks.

**Rationale**:
- Same idiom as the existing GraphQL/REST codegen freshness checks (per the pattern in spec FR-009).
- The diff is over the *committed* generated artefacts, so the check is deterministic and cache-free.

**Alternatives considered**:
- *Skip the JSON in the diff and only check the TS file*: rejected — drift between Python catalogue and the JSON would slip through. Both must match.
- *Run codegen during CI and fail on stale*: same as decision; this *is* the codegen, just expressed as an Invoke task.

---

## R-010 — Telemetry / structured-logging integration (FR-018)

**Decision**: The catalogue formatter calls `structlog.get_logger().info("graphql.error", code=<code>, http_status=<int>, ...)` (or equivalent) for every error it formats. The `code` field becomes a first-class log key, queryable by dashboards.

The catalogue `code` is also threaded through `log_forwarding`'s `ForwardableError` path (existing module). Where an adopted exception class is `ForwardableError`-derived, its catalogue code is included in the forwarded log payload.

**Rationale**:
- `structlog` is already used throughout the backend.
- One central log emission point (the formatter) means we don't have to instrument every raise site.

**Alternatives considered**:
- *Emit logs at each raise site*: rejected — error sites already log; the formatter is the single point where the catalogue mapping is resolved.

---

## R-011 — Per-field fan-out for `ValidationError`

**Decision**: The existing `ValidationError` class carries `input_value: dict[str, str]` (one entry per failing field). The resolver layer (specifically the GraphQL mutation handlers in `backend/infrahub/graphql/mutations/`) inspects this dict and raises one catalogued exception per entry, classifying by reason:

- Reason matches "mandatory" → `AttributeRequiredError(node_kind=..., field_name=...)` → code `ATTRIBUTE_REQUIRED`.
- Reason matches "not a valid <type>" → `AttributeInvalidTypeError(node_kind=..., field_name=..., expected_type=..., received_type=...)` → code `ATTRIBUTE_INVALID_TYPE`.
- Otherwise → `AttributeConstraintViolationError(node_kind=..., field_name=..., constraint=..., detail=...)` → code `ATTRIBUTE_CONSTRAINT_VIOLATION`.

Each raised exception is attached to its `path` via `GraphQLError(original_error=exc, path=[...])`, satisfying FR-017.

The classification logic lives in `backend/infrahub/errors/validation.py` (or similar) so the resolver call site stays small (`raise_classified_validation_errors(input_value, node_kind, path)`).

**Rationale**:
- The existing backend already computes both `expected_type` and `received_type` at the attribute type-check (verified in discovery §8b against `backend/infrahub/core/attribute.py:762`). No new type plumbing needed.
- Classifying at the resolver (not in `ValidationError.__init__`) avoids touching the 194 existing raise sites in this release. The dict-based contract on `ValidationError` is preserved; only the GraphQL-facing code path classifies.

**Alternatives considered**:
- *Change `ValidationError.__init__` to take a structured kind*: rejected — touches 194 call sites for v1. Defer to a follow-up if the backend ever benefits from carrying the classification end-to-end.
- *Classify in the formatter*: rejected — see R-005, the formatter cannot synthesize per-field `path` values.

---

## R-012 — SDK binding generation (informational; out of scope for this repo)

**Decision (informational)**: The SDK repository's CI consumes `schema/error-catalogue.json` from a tagged Infrahub release (e.g. via a pinned URL like `https://github.com/opsmill/infrahub/releases/download/v<X.Y.Z>/error-catalogue.json` or by following the submodule head). The SDK repo's binding generator (Pydantic models + typed exception classes) runs there. This work is tracked separately in the SDK repository.

**Rationale**:
- This plan cannot modify SDK code (submodule contents belong to the SDK repo). The contract that crosses the repo boundary is the JSON Schema file, which this plan publishes.

**Action for this plan**: ensure `schema/error-catalogue.json` is included in release artefacts (release pipeline change is a one-line addition to whatever publishes the existing `schema/schema.graphql`).

---

## Resolved → ready for Phase 1

All NEEDS CLARIFICATION items from the discovery doc are now resolved. Phase 1 generates `data-model.md`, `contracts/`, and `quickstart.md` against these decisions.
