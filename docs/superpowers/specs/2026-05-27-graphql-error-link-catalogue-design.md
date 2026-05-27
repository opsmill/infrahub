# GraphQL `errorLink` — catalogue-aware refactor

**Branch:** `pog-infp-468-us1-graphql-error-formatter`
**File primarily affected:** `frontend/app/src/shared/api/graphql/graphqlClientApollo.tsx`
**Related backend commit:** `ee06f2f485` — `feat(graphql): wire enriched error catalogue into GraphQL responses (INFP-468)`

## Background

The backend now attaches a typed catalogue to every GraphQL error's `extensions`:

```json
{
  "code": "NODE_NOT_FOUND",
  "http_status": 404,
  "data": { "node_kind": "CoreAccount", "identifier": "xyz" }
}
```

`code` is a string identifier (e.g. `AUTHENTICATION_REQUIRED`, `TOKEN_EXPIRED`,
`PERMISSION_DENIED`, `NODE_NOT_FOUND`, `ATTRIBUTE_REQUIRED`,
`ATTRIBUTE_INVALID_TYPE`, `ATTRIBUTE_CONSTRAINT_VIOLATION`, `BRANCH_NOT_FOUND`,
`SCHEMA_NOT_FOUND`, `UNDEFINED_ERROR`). The catalogue is not yet exported in the
GraphQL schema, so the frontend must keep its own copy of the codes and payload
shapes until it is.

The minimal frontend wire-up landed in the same commit: the numeric `switch (401 | 403 | default)` became three string-based `if`s. That change preserved behavior but lost the readability of the switch and ignored everything else the catalogue now carries (`http_status`, structured `data`).

## Problems with the current `errorLink`

1. **Untyped strings.** `graphQLError.extensions?.code` is `unknown`. Nothing forces the file to stay in sync with the backend catalogue; a typo would compile.
2. **Lost structure.** The new switch became a chain of `if`s. The intent ("here is the policy for each catalogue code") is harder to read.
3. **Token-refresh on bad credentials.** `AUTHENTICATION_REQUIRED` and `TOKEN_EXPIRED` are both routed through the refresh flow. Develop had the same behavior because it could not distinguish them — both arrived as HTTP `401`. When the refresh fails (which it always does for genuinely-bad credentials), `observer.error(err)` is called and **no toast is shown**, so the user gets a silent failure. The new catalogue makes this distinguishable; the frontend should use that.
4. **Inline `Observable` block.** The token-refresh code sits inside the `for` loop and dominates the file, obscuring the simple policy table the link is really expressing.

## Goals

- Single source of truth for catalogue codes and payload shapes on the frontend, ready to be deleted the day the GraphQL schema exports them.
- A `switch` over a typed `ErrorCode` so every catalogue code is either handled by name or falls into an explicit `default`.
- Fix the silent-failure on `AUTHENTICATION_REQUIRED`: only `TOKEN_EXPIRED` triggers a refresh attempt.
- Preserve every other behavior the link has today (silent `PERMISSION_DENIED`, `processErrorMessage` context override, toast fallback, dev `console.error`).

## Non-goals

- Exposing typed errors to components / forms / pages. No existing consumer asks for this; we'll add the export surface the day a real caller wants it. The new types are organized so that future export is a one-line change, not a refactor.
- Generating friendlier user-facing messages from `extensions.data`. The current behavior of showing `graphQLError.message` is unchanged.
- Changing anything in `login.tsx`. Its flat read of `code` + `message` continues to work; the new union type happens to be assignment-compatible.
- Removing the `processErrorMessage` context callback. It is the existing escape hatch for caller-specific error handling and stays.

## Design

### New module: `frontend/app/src/shared/api/graphql/errors.ts`

A small, self-contained module that mirrors the backend catalogue. A top-of-file comment notes the duplication is intentional until the schema exports the catalogue.

```ts
// Mirrors backend/infrahub/errors/catalogue.py. Delete once the catalogue is
// exported through the GraphQL schema; until then keep this file in sync.

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
 * missing or carries a code the frontend does not know about, so every caller
 * gets a typed value.
 */
export function parseErrorExtensions(extensions: unknown): GraphQLErrorExtensions;
```

**Parsing rules** (implemented inside `parseErrorExtensions`):

- If `extensions` is not an object, return `UNDEFINED_ERROR` with `http_status: 500` and empty `data`.
- If `extensions.code` is one of the known `ERROR_CODES` values, return `{ code, http_status: Number(extensions.http_status) || 500, data: extensions.data ?? {} }` typed to the matching variant.
- Otherwise return the `UNDEFINED_ERROR` variant. The original unknown code is logged by the caller (`errorLink`'s `console.error`).
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

| Catalogue code | Today (this branch) | After this change |
|---|---|---|
| `TOKEN_EXPIRED` | Refresh attempt | Refresh attempt (unchanged) |
| `AUTHENTICATION_REQUIRED` | Refresh attempt → silent failure on bad creds | Toast / `processErrorMessage` (real message visible) |
| `PERMISSION_DENIED` | Silent | Silent (unchanged) |
| All other codes incl. `UNDEFINED_ERROR` and unrecognized codes | Toast / `processErrorMessage` | Toast / `processErrorMessage` (unchanged) |

The only intentional behavior change is the `AUTHENTICATION_REQUIRED` row.

## Testing

A new `errors.test.ts` alongside `errors.ts`, following the GIVEN/WHEN/THEN style of `utils.test.ts`:

- `parseErrorExtensions` returns the matching variant for each known code, with `http_status` and `data` passed through.
- Unknown codes, missing `code`, non-object inputs (`null`, `undefined`, strings) all narrow to `UNDEFINED_ERROR` with `http_status: 500`.
- Missing `data` defaults to `{}`.
- A TypeScript-level check (a `satisfies` assertion or compile-time test) that exhaustively switching on `ErrorCode` is checked by the compiler — guards against catalogue drift.

The `errorLink` itself is not unit-tested today (no existing test file for it). Adding link-level tests is out of scope; the refactor is structured so each behavior change is isolated to a single small helper or switch arm, reviewable by reading.

## Migration / rollout

Single PR. No data migration. No env flags. `login.tsx`'s narrower inline type for `extensions` continues to assign cleanly from `GraphQLErrorExtensions` (it reads only `code` and `message`), so no changes there.

## Open follow-ups (out of scope, captured for later)

- Export the catalogue through the GraphQL schema and delete `errors.ts`.
- Per-code message builders that use `extensions.data` for friendlier UI.
- Expose `parseErrorExtensions` to forms / pages once a concrete consumer needs structured data.
