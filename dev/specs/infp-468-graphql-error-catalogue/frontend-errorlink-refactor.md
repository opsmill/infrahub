# Frontend `errorLink` — catalogue-aware refactor (follow-up to T031)

**Status**: Design — ready for tasking
**Created**: 2026-05-27
**Scope**: Phase 4 (US2), follow-up to the minimal migration in T031
**Files primarily affected**:

- `frontend/app/src/shared/api/graphql/graphqlClientApollo.tsx`
- New: `frontend/app/src/shared/api/graphql/errors.ts` (+ its `errors.test.ts`)

## Why this exists

T031 in [tasks.md](./tasks.md) shipped the minimal frontend migration required by the breaking change in US1: the numeric `switch (401 | 403 | default)` in `graphqlClientApollo.tsx` was translated into three string-based `if`s on `extensions.code`. That unblocked the release but is not the end state. Specifically:

1. **Untyped strings.** `graphQLError.extensions?.code` is `unknown` at the call site. Nothing forces the file to stay in sync with the backend catalogue; a typo would compile.
2. **Lost structure.** Replacing the switch with a chain of `if`s obscured the policy table the link is really expressing.
3. **`AUTHENTICATION_REQUIRED` silently fails.** Both `TOKEN_EXPIRED` and `AUTHENTICATION_REQUIRED` are routed through the refresh flow. Develop had the same behavior because it could not distinguish them — both arrived as HTTP `401`. When the refresh fails (which it always does for genuinely-bad credentials), `observer.error(err)` is called and **no toast is shown**, so the user sees no message. The split introduced by US1 (R-005, [data-model.md §`AUTHENTICATION_REQUIRED` / `TOKEN_EXPIRED`](./data-model.md)) finally makes this fixable; the frontend has not yet taken advantage.
4. **Inline `Observable` block.** The token-refresh body sits inside the `for` loop and dominates the file, making the simple per-code policy hard to read.

These are deeper consumer-side concerns and were out of scope for T031's minimal swap; they belong to a follow-up that lands while US2's full bindings pipeline (T027–T030) is still pending.

## Relationship to T027–T030 (generated bindings)

T027–T030 will introduce auto-generated discriminated-union types under `frontend/app/src/shared/api/errors/`, driven by `schema/error-catalogue.json` through `json-schema-to-typescript`. That is the long-term home for catalogue types on the frontend.

This refactor intentionally **does not block on** T027–T030. The catalogue is not yet exported in the GraphQL schema and the generator/CI plumbing has not landed. Until it does, the frontend keeps a small hand-written mirror of the catalogue at `frontend/app/src/shared/api/graphql/errors.ts`. The day T029 lands, this file is deleted in a one-line change and `errorLink` imports from the generated module instead — no behaviour change.

A top-of-file comment in `errors.ts` names this fate so the next reader does not wonder why the catalogue is duplicated.

## Goals

- Single source of truth for catalogue codes and payload shapes on the frontend right now, ready to be deleted when T029 lands.
- A `switch` over a typed `ErrorCode` in `errorLink` — every catalogue code either handled by name or in an explicit `default`.
- Fix the silent-failure on `AUTHENTICATION_REQUIRED`: only `TOKEN_EXPIRED` triggers a refresh attempt.
- Preserve every other behavior the link has today (silent `PERMISSION_DENIED`, `processErrorMessage` context override, toast fallback, dev `console.error`).

## Non-goals

- Anticipating T027–T030. This module ships as hand-written and is deleted when the generator lands. No partial generator scaffolding.
- Exposing typed errors to forms / pages. No existing consumer asks for this; the types are organised so future export is a one-line change, not a refactor.
- Generating friendlier user-facing messages from `extensions.data`. Showing `graphQLError.message` continues unchanged.
- Touching `login.tsx`. Its flat read of `code` + `message` continues to work; the new union type is assignment-compatible.
- Removing the `processErrorMessage` context callback. It is the existing escape hatch for caller-specific error handling and stays.

## Design

### New module: `frontend/app/src/shared/api/graphql/errors.ts`

A small, self-contained module that mirrors the backend catalogue. The data shapes are the JSON-mode renderings of the Pydantic payload models in [data-model.md §Payload models](./data-model.md), one-to-one.

```ts
// Hand-written mirror of backend/infrahub/errors/catalogue.py. Delete this
// file once US2's generated bindings (tasks T027–T030) land and re-export
// the catalogue from frontend/app/src/shared/api/errors/. Until then, keep
// this file in sync with the backend catalogue — both columns belong to the
// same release.

export const ERROR_CODES = {
  NODE_NOT_FOUND: "NODE_NOT_FOUND",
  AUTHENTICATION_REQUIRED: "AUTHENTICATION_REQUIRED",
  TOKEN_EXPIRED: "TOKEN_EXPIRED",
  PERMISSION_DENIED: "PERMISSION_DENIED",
  ATTRIBUTE_REQUIRED: "ATTRIBUTE_REQUIRED",
  ATTRIBUTE_INVALID_TYPE: "ATTRIBUTE_INVALID_TYPE",
  ATTRIBUTE_CONSTRAINT_VIOLATION: "ATTRIBUTE_CONSTRAINT_VIOLATION",
  BRANCH_NOT_FOUND: "BRANCH_NOT_FOUND",
  SCHEMA_NOT_FOUND: "SCHEMA_NOT_FOUND",
  UNDEFINED_ERROR: "UNDEFINED_ERROR",
} as const;

export type ErrorCode = (typeof ERROR_CODES)[keyof typeof ERROR_CODES];

// Payload shapes — one per code. Match backend/infrahub/errors/payloads.py.
type NodeNotFoundData = { node_kind: string; identifier: string };
type AuthenticationRequiredData = Record<string, never>;
type TokenExpiredData = { expired_at: string | null };
type PermissionDeniedData = {
  action: string | null;
  resource_kind: string | null;
};
type AttributeRequiredData = { node_kind: string; field_name: string };
type AttributeInvalidTypeData = {
  node_kind: string;
  field_name: string;
  expected_type: string;
  received_type: string;
};
type AttributeConstraintViolationData = {
  node_kind: string;
  field_name: string;
  constraint: string;
  detail: string | null;
};
type BranchNotFoundData = { branch_name: string };
type SchemaNotFoundData = { kind: string };
type UndefinedErrorData = Record<string, never>;

// Discriminated union — `code` narrows `data` automatically.
export type GraphQLErrorExtensions =
  | { code: typeof ERROR_CODES.NODE_NOT_FOUND; http_status: number; data: NodeNotFoundData }
  | { code: typeof ERROR_CODES.AUTHENTICATION_REQUIRED; http_status: number; data: AuthenticationRequiredData }
  | { code: typeof ERROR_CODES.TOKEN_EXPIRED; http_status: number; data: TokenExpiredData }
  | { code: typeof ERROR_CODES.PERMISSION_DENIED; http_status: number; data: PermissionDeniedData }
  | { code: typeof ERROR_CODES.ATTRIBUTE_REQUIRED; http_status: number; data: AttributeRequiredData }
  | { code: typeof ERROR_CODES.ATTRIBUTE_INVALID_TYPE; http_status: number; data: AttributeInvalidTypeData }
  | { code: typeof ERROR_CODES.ATTRIBUTE_CONSTRAINT_VIOLATION; http_status: number; data: AttributeConstraintViolationData }
  | { code: typeof ERROR_CODES.BRANCH_NOT_FOUND; http_status: number; data: BranchNotFoundData }
  | { code: typeof ERROR_CODES.SCHEMA_NOT_FOUND; http_status: number; data: SchemaNotFoundData }
  | { code: typeof ERROR_CODES.UNDEFINED_ERROR; http_status: number; data: UndefinedErrorData };

/**
 * Parse the raw `extensions` blob from an Apollo `GraphQLError` into a
 * discriminated union. Falls back to `UNDEFINED_ERROR` when the payload is
 * missing or carries a code the frontend does not know about, so every
 * caller gets a typed value.
 */
export function parseErrorExtensions(extensions: unknown): GraphQLErrorExtensions;
```

**Parsing rules** (implemented inside `parseErrorExtensions`):

- If `extensions` is not an object, return `UNDEFINED_ERROR` with `http_status: 500` and empty `data`.
- If `extensions.code` is one of the known `ERROR_CODES` values, return `{ code, http_status: Number(extensions.http_status) || 500, data: extensions.data ?? {} }` typed to the matching variant.
- Otherwise return the `UNDEFINED_ERROR` variant. The original unknown code is logged at the call site (`errorLink`'s `console.error`) so catalogue drift is observable in dev.
- No deep schema validation of `data`. The discriminated-union narrowing is for ergonomics, not runtime trust. A backend with a stale schema can ship a malformed payload; we accept it as-is rather than throwing inside the link.

### Refactored `errorLink`

The link becomes a small switch over the parsed code, with two named helpers for the long-running operations.

```ts
export const errorLink = onError(({ graphQLErrors, operation, forward }) => {
  if (!graphQLErrors) return;

  for (const graphQLError of graphQLErrors) {
    const parsed = parseErrorExtensions(graphQLError.extensions);

    console.error(
      `[GraphQL error]: Code: ${parsed.code}, Message: ${graphQLError.message}, ` +
        `Location: ${JSON.stringify(graphQLError.locations)}, Path: ${graphQLError.path}`
    );

    switch (parsed.code) {
      case ERROR_CODES.TOKEN_EXPIRED:
        return retryWithRefreshedToken(operation, forward);

      case ERROR_CODES.PERMISSION_DENIED:
        // Silent — 403s are handled by route-level guards, not toasts.
        return;

      default:
        notifyUser(graphQLError.message, operation);
    }
  }
});
```

Helpers (file-local, not exported):

- `retryWithRefreshedToken(operation, forward)` — the existing `new Observable(...)` block, lifted verbatim. Behavior unchanged: fetch a fresh access token via `refreshAccessTokenQueryOptions()`, replace the `authorization` header, retry the operation; on refresh failure, propagate to `observer.error`.
- `notifyUser(message, operation)` — the existing `processErrorMessage`-vs-toast fallback, lifted verbatim. If `operation.getContext().processErrorMessage` is set, call it with the message; otherwise toast with `toastId: "alert-error"`.

### Behavior matrix

| Catalogue code | Today (post-T031) | After this refactor |
|---|---|---|
| `TOKEN_EXPIRED` | Refresh attempt | Refresh attempt (unchanged) |
| `AUTHENTICATION_REQUIRED` | Refresh attempt → silent failure on bad creds | Toast / `processErrorMessage` (real message visible) |
| `PERMISSION_DENIED` | Silent | Silent (unchanged) |
| All other codes incl. `UNDEFINED_ERROR` and unrecognized codes | Toast / `processErrorMessage` | Toast / `processErrorMessage` (unchanged) |

The only intentional behavior change is the `AUTHENTICATION_REQUIRED` row — a fix for the pre-existing silent failure called out in §Why this exists.

## Testing

A new `frontend/app/src/shared/api/graphql/errors.test.ts` alongside `errors.ts`, following the GIVEN/WHEN/THEN style of the neighbouring `utils.test.ts`:

- `parseErrorExtensions` returns the matching variant for each known code, with `http_status` and `data` passed through.
- Unknown codes, missing `code`, non-object inputs (`null`, `undefined`, strings) all narrow to `UNDEFINED_ERROR` with `http_status: 500`.
- Missing `data` defaults to `{}`.
- A compile-time exhaustiveness check (a `satisfies`-style assertion or a `never`-narrowing helper inside the test file) that exhaustively switching on `ErrorCode` is enforced by the compiler — guards against catalogue drift.

The `errorLink` itself is not unit-tested today (no existing test file for it). Adding link-level tests is out of scope; the refactor is structured so each behavior change is isolated to a single small helper or switch arm, reviewable by reading. The Playwright E2E test for `TOKEN_EXPIRED` silent refresh (T053) covers the only behavior that is hard to verify by inspection.

## Migration / rollout

Single PR. No data migration. No env flags. `login.tsx`'s narrower inline type for `extensions` continues to assign cleanly from `GraphQLErrorExtensions` (it reads only `code` and `message`), so no changes there. No towncrier fragment — this is a frontend-internal refactor; the user-visible change (`AUTHENTICATION_REQUIRED` now toasts) is a bug fix, not a behaviour change worth a release note on its own.

## Removal step (when T029 lands)

When the generator from T029 produces `frontend/app/src/shared/api/errors/catalogue.generated.ts`:

1. Delete `frontend/app/src/shared/api/graphql/errors.ts` and `errors.test.ts`.
2. Replace the import in `graphqlClientApollo.tsx` with the generated module (per T030's hand-written `index.ts` shim).
3. Reconcile naming: `parseErrorExtensions` becomes a thin wrapper around T030's `isCatalogueError` guard.

No behaviour change is expected from that swap. This section exists so the future reader knows the deletion is intentional and how to do it cleanly.
