# Frontend `errorLink` — catalogue-aware refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Apollo `errorLink` in `frontend/app/src/shared/api/graphql/graphqlClientApollo.tsx` to consume the new GraphQL error catalogue with typed codes and a switch-based policy, and fix a pre-existing silent failure on `AUTHENTICATION_REQUIRED`.

**Architecture:** Add a small hand-written module `errors.ts` next to `graphqlClientApollo.tsx` that mirrors the backend catalogue (`backend/infrahub/errors/catalogue.py`) — `ERROR_CODES` const, `ErrorCode` union, a `GraphQLErrorExtensions` discriminated union, and a `parseErrorExtensions(unknown)` narrowing helper that falls back to `UNDEFINED_ERROR` for anything unrecognised. Refactor `errorLink` to a `switch (parsed.code)` with two named file-local helpers — `retryWithRefreshedToken` (today's `Observable` block, lifted verbatim) and `notifyUser` (today's `processErrorMessage`/toast fallback, lifted verbatim) — so the per-code policy is a one-screen read. The hand-written module is intentionally temporary and gets deleted when US2's generated bindings (T029) land; the design doc names that fate explicitly.

**Tech Stack:** TypeScript, React 19, Apollo Client (`@apollo/client` + `apollo-upload-client`), vitest, biome (formatter + linter), pnpm workspaces. Tests use the GIVEN/WHEN/THEN style already established in `frontend/app/src/shared/api/graphql/utils.test.ts`.

**Spec:** `dev/specs/infp-468-graphql-error-catalogue/frontend-errorlink-refactor.md`. Cross-references: `dev/specs/infp-468-graphql-error-catalogue/data-model.md` for the authoritative payload shapes, `dev/specs/infp-468-graphql-error-catalogue/tasks.md` T031a–T031d for the parent task IDs.

---

## File Structure

| Path | Status | Responsibility |
|---|---|---|
| `frontend/app/src/shared/api/graphql/errors.ts` | **create** | Hand-written catalogue mirror: `ERROR_CODES`, `ErrorCode`, `GraphQLErrorExtensions` discriminated union, `parseErrorExtensions` narrowing helper. Single source of truth on the frontend until T029 lands. |
| `frontend/app/src/shared/api/graphql/errors.test.ts` | **create** | Vitest tests for `parseErrorExtensions`: per-code narrowing, fallback to `UNDEFINED_ERROR`, malformed inputs, and a compile-time exhaustiveness check that fails to build if `ErrorCode` gains a value without a corresponding switch arm. |
| `frontend/app/src/shared/api/graphql/graphqlClientApollo.tsx` | **modify** | Replace the `if`-chain `errorLink` body with a `switch (parsed.code)` over `parseErrorExtensions(graphQLError.extensions)`; extract `retryWithRefreshedToken` and `notifyUser` as file-local helpers; add `code` to the `console.error` log line. No other change to the file. |

No source or test files outside `frontend/app/src/shared/api/graphql/` are touched. The only other file the plan edits is `dev/specs/infp-468-graphql-error-catalogue/tasks.md`, where Task 4 flips the T031a–T031d task checkboxes to `[X]` (no code or content changes). `login.tsx`'s inline `extensions: { code: string; http_status?: number }` type remains assignment-compatible with `GraphQLErrorExtensions` (it only reads `code` and `message`).

---

## Pre-flight

- [ ] **Step 0.1: Verify you're on the right branch and tree is clean**

Run:
```bash
cd /Users/paul/Projects/infrahub
git status
git rev-parse --abbrev-ref HEAD
```
Expected: clean working tree, branch is `pog-infp-468-us1-graphql-error-formatter`. If the branch differs, stop and confirm with the user before continuing.

- [ ] **Step 0.2: Confirm the spec exists and is committed**

Run:
```bash
ls -la dev/specs/infp-468-graphql-error-catalogue/frontend-errorlink-refactor.md
git log --oneline -1 -- dev/specs/infp-468-graphql-error-catalogue/frontend-errorlink-refactor.md
```
Expected: file exists, last commit references "frontend errorLink catalogue-aware refactor". This is the source of truth referenced throughout the plan.

- [ ] **Step 0.3: Establish the test/lint baseline**

Run:
```bash
cd /Users/paul/Projects/infrahub/frontend/app
pnpm test -- --run src/shared/api/graphql/utils.test.ts
```
Expected: PASS (this is the neighbouring file; we want to confirm vitest works in the workspace before adding our own tests). If pnpm or vitest are missing, run `pnpm setup` per `frontend/app/AGENTS.md` and retry.

---

## Task 1: Hand-written catalogue mirror — `errors.ts`

Implements T031a from `tasks.md`. Creates the typed catalogue surface that the refactored `errorLink` (Task 3) will consume.

**Files:**
- Create: `frontend/app/src/shared/api/graphql/errors.ts`

- [ ] **Step 1.1: Create the file with codes, payload types, discriminated union, and parser**

Write `frontend/app/src/shared/api/graphql/errors.ts`:

```ts
// Hand-written mirror of backend/infrahub/errors/catalogue.py. Delete this
// file once US2's generated bindings (tasks T027–T030) land and re-export
// the catalogue from frontend/app/src/shared/api/errors/. Until then, keep
// this file in sync with the backend catalogue — both columns belong to
// the same release.

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
  | {
      code: typeof ERROR_CODES.AUTHENTICATION_REQUIRED;
      http_status: number;
      data: AuthenticationRequiredData;
    }
  | { code: typeof ERROR_CODES.TOKEN_EXPIRED; http_status: number; data: TokenExpiredData }
  | {
      code: typeof ERROR_CODES.PERMISSION_DENIED;
      http_status: number;
      data: PermissionDeniedData;
    }
  | {
      code: typeof ERROR_CODES.ATTRIBUTE_REQUIRED;
      http_status: number;
      data: AttributeRequiredData;
    }
  | {
      code: typeof ERROR_CODES.ATTRIBUTE_INVALID_TYPE;
      http_status: number;
      data: AttributeInvalidTypeData;
    }
  | {
      code: typeof ERROR_CODES.ATTRIBUTE_CONSTRAINT_VIOLATION;
      http_status: number;
      data: AttributeConstraintViolationData;
    }
  | { code: typeof ERROR_CODES.BRANCH_NOT_FOUND; http_status: number; data: BranchNotFoundData }
  | { code: typeof ERROR_CODES.SCHEMA_NOT_FOUND; http_status: number; data: SchemaNotFoundData }
  | {
      code: typeof ERROR_CODES.UNDEFINED_ERROR;
      http_status: number;
      data: UndefinedErrorData;
    };

const KNOWN_CODES = new Set<string>(Object.values(ERROR_CODES));

const UNDEFINED_FALLBACK: GraphQLErrorExtensions = {
  code: ERROR_CODES.UNDEFINED_ERROR,
  http_status: 500,
  data: {},
};

/**
 * Parse the raw `extensions` blob from an Apollo `GraphQLError` into a
 * discriminated union. Falls back to `UNDEFINED_ERROR` (http_status 500,
 * empty data) when the payload is missing or carries a code the frontend
 * does not know about, so every caller gets a typed value.
 */
export function parseErrorExtensions(extensions: unknown): GraphQLErrorExtensions {
  if (extensions === null || typeof extensions !== "object") {
    return UNDEFINED_FALLBACK;
  }

  const record = extensions as Record<string, unknown>;
  const rawCode = record.code;

  if (typeof rawCode !== "string" || !KNOWN_CODES.has(rawCode)) {
    return UNDEFINED_FALLBACK;
  }

  const code = rawCode as ErrorCode;
  const httpStatus = Number(record.http_status);
  const data =
    record.data !== null && typeof record.data === "object" ? (record.data as object) : {};

  return {
    code,
    http_status: Number.isFinite(httpStatus) && httpStatus > 0 ? httpStatus : 500,
    // Cast is safe: the discriminated union is gated by `code`, and we do
    // not validate the inner shape at runtime by design (see spec
    // §"Parsing rules" — narrowing is for ergonomics, not runtime trust).
    data: data as never,
  } as GraphQLErrorExtensions;
}
```

- [ ] **Step 1.2: Verify the file compiles standalone**

Run:
```bash
cd /Users/paul/Projects/infrahub/frontend/app
pnpm tsc --noEmit -p tsconfig.json 2>&1 | grep -E "errors\.ts" || echo "no errors"
```
Expected: `no errors`. If tsc reports issues inside `errors.ts`, fix them before moving on (most likely: a missing `as const` or a typo in the discriminated union).

- [ ] **Step 1.3: Format with biome**

Run:
```bash
cd /Users/paul/Projects/infrahub/frontend/app
pnpm biome format --write src/shared/api/graphql/errors.ts
```
Expected: file is reformatted in place; biome reports it as formatted. No lint errors.

- [ ] **Step 1.4: Commit**

```bash
cd /Users/paul/Projects/infrahub
git add frontend/app/src/shared/api/graphql/errors.ts
git commit -m "feat(frontend): hand-written GraphQL error catalogue mirror (INFP-468 T031a)

Mirrors backend/infrahub/errors/catalogue.py until US2's generated bindings
(T029) land. Adds ERROR_CODES, ErrorCode, GraphQLErrorExtensions
discriminated union, and parseErrorExtensions narrowing helper that falls
back to UNDEFINED_ERROR for unrecognised inputs. See spec at
dev/specs/infp-468-graphql-error-catalogue/frontend-errorlink-refactor.md."
```

---

## Task 2: Unit tests for `parseErrorExtensions` — `errors.test.ts`

Implements T031b from `tasks.md`. Tests are written before consumers in Task 3 — TDD discipline, plus the test file establishes the compile-time exhaustiveness check we want to lock in early.

**Files:**
- Create: `frontend/app/src/shared/api/graphql/errors.test.ts`

- [ ] **Step 2.1: Write the test file**

Write `frontend/app/src/shared/api/graphql/errors.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import {
  ERROR_CODES,
  type ErrorCode,
  type GraphQLErrorExtensions,
  parseErrorExtensions,
} from "./errors";

describe("parseErrorExtensions", () => {
  it("narrows NODE_NOT_FOUND with its typed data", () => {
    // GIVEN
    const extensions = {
      code: "NODE_NOT_FOUND",
      http_status: 404,
      data: { node_kind: "CoreAccount", identifier: "abc-123" },
    };

    // WHEN
    const parsed = parseErrorExtensions(extensions);

    // THEN
    expect(parsed).toEqual({
      code: ERROR_CODES.NODE_NOT_FOUND,
      http_status: 404,
      data: { node_kind: "CoreAccount", identifier: "abc-123" },
    });
  });

  it("narrows AUTHENTICATION_REQUIRED with empty data", () => {
    // GIVEN
    const extensions = { code: "AUTHENTICATION_REQUIRED", http_status: 401, data: {} };

    // WHEN
    const parsed = parseErrorExtensions(extensions);

    // THEN
    expect(parsed.code).toBe(ERROR_CODES.AUTHENTICATION_REQUIRED);
    expect(parsed.http_status).toBe(401);
    expect(parsed.data).toEqual({});
  });

  it("narrows TOKEN_EXPIRED and preserves expired_at", () => {
    // GIVEN
    const extensions = {
      code: "TOKEN_EXPIRED",
      http_status: 401,
      data: { expired_at: "2026-05-27T10:00:00Z" },
    };

    // WHEN
    const parsed = parseErrorExtensions(extensions);

    // THEN
    expect(parsed).toEqual({
      code: ERROR_CODES.TOKEN_EXPIRED,
      http_status: 401,
      data: { expired_at: "2026-05-27T10:00:00Z" },
    });
  });

  it("narrows PERMISSION_DENIED with nullable action/resource_kind", () => {
    // GIVEN
    const extensions = {
      code: "PERMISSION_DENIED",
      http_status: 403,
      data: { action: "update", resource_kind: "CoreAccount" },
    };

    // WHEN
    const parsed = parseErrorExtensions(extensions);

    // THEN
    expect(parsed.code).toBe(ERROR_CODES.PERMISSION_DENIED);
    expect(parsed.data).toEqual({ action: "update", resource_kind: "CoreAccount" });
  });

  it.each([
    ["ATTRIBUTE_REQUIRED", { node_kind: "CoreAccount", field_name: "name" }, 422],
    [
      "ATTRIBUTE_INVALID_TYPE",
      {
        node_kind: "CoreAccount",
        field_name: "name",
        expected_type: "String",
        received_type: "Number",
      },
      422,
    ],
    [
      "ATTRIBUTE_CONSTRAINT_VIOLATION",
      {
        node_kind: "CoreAccount",
        field_name: "name",
        constraint: "regex",
        detail: "must match ^[a-z]+$",
      },
      422,
    ],
    ["BRANCH_NOT_FOUND", { branch_name: "feature-x" }, 400],
    ["SCHEMA_NOT_FOUND", { kind: "CoreAccount" }, 422],
  ])("narrows %s passing through http_status and data", (code, data, httpStatus) => {
    // GIVEN
    const extensions = { code, http_status: httpStatus, data };

    // WHEN
    const parsed = parseErrorExtensions(extensions);

    // THEN
    expect(parsed.code).toBe(code);
    expect(parsed.http_status).toBe(httpStatus);
    expect(parsed.data).toEqual(data);
  });

  it("returns UNDEFINED_ERROR for an unknown code", () => {
    // GIVEN
    const extensions = { code: "SOMETHING_NEW", http_status: 500, data: {} };

    // WHEN
    const parsed = parseErrorExtensions(extensions);

    // THEN
    expect(parsed).toEqual({
      code: ERROR_CODES.UNDEFINED_ERROR,
      http_status: 500,
      data: {},
    });
  });

  it.each([
    ["null", null],
    ["undefined", undefined],
    ["a string", "AUTHENTICATION_REQUIRED"],
    ["a number", 401],
    ["a boolean", true],
  ])("returns UNDEFINED_ERROR when extensions is %s", (_label, input) => {
    // WHEN
    const parsed = parseErrorExtensions(input);

    // THEN
    expect(parsed).toEqual({
      code: ERROR_CODES.UNDEFINED_ERROR,
      http_status: 500,
      data: {},
    });
  });

  it("returns UNDEFINED_ERROR when code is missing", () => {
    // GIVEN
    const extensions = { http_status: 401, data: {} };

    // WHEN
    const parsed = parseErrorExtensions(extensions);

    // THEN
    expect(parsed.code).toBe(ERROR_CODES.UNDEFINED_ERROR);
  });

  it("defaults http_status to 500 when missing or non-numeric", () => {
    // GIVEN
    const missing = parseErrorExtensions({ code: "AUTHENTICATION_REQUIRED", data: {} });
    const garbage = parseErrorExtensions({
      code: "AUTHENTICATION_REQUIRED",
      http_status: "not-a-number",
      data: {},
    });

    // THEN
    expect(missing.http_status).toBe(500);
    expect(garbage.http_status).toBe(500);
  });

  it("defaults data to {} when missing or non-object", () => {
    // GIVEN
    const missing = parseErrorExtensions({
      code: "AUTHENTICATION_REQUIRED",
      http_status: 401,
    });
    const garbage = parseErrorExtensions({
      code: "AUTHENTICATION_REQUIRED",
      http_status: 401,
      data: "not-an-object",
    });

    // THEN
    expect(missing.data).toEqual({});
    expect(garbage.data).toEqual({});
  });
});

/**
 * Compile-time exhaustiveness guard. If a new code is added to ERROR_CODES
 * without a corresponding case here, the assertion below will fail to
 * compile because `unhandled` will not narrow to `never`. This is a
 * type-level test — it runs at `tsc`, not at vitest.
 */
describe("ErrorCode exhaustiveness", () => {
  it("forces every ErrorCode to have a switch arm in this file", () => {
    const assertExhaustive = (code: ErrorCode): string => {
      switch (code) {
        case ERROR_CODES.NODE_NOT_FOUND:
        case ERROR_CODES.AUTHENTICATION_REQUIRED:
        case ERROR_CODES.TOKEN_EXPIRED:
        case ERROR_CODES.PERMISSION_DENIED:
        case ERROR_CODES.ATTRIBUTE_REQUIRED:
        case ERROR_CODES.ATTRIBUTE_INVALID_TYPE:
        case ERROR_CODES.ATTRIBUTE_CONSTRAINT_VIOLATION:
        case ERROR_CODES.BRANCH_NOT_FOUND:
        case ERROR_CODES.SCHEMA_NOT_FOUND:
        case ERROR_CODES.UNDEFINED_ERROR:
          return code;
        default: {
          const unhandled: never = code;
          return unhandled;
        }
      }
    };

    expect(assertExhaustive(ERROR_CODES.NODE_NOT_FOUND)).toBe("NODE_NOT_FOUND");
  });

  it("locks the GraphQLErrorExtensions union to ErrorCode values", () => {
    // Compile-time check: any GraphQLErrorExtensions.code must be an ErrorCode.
    const variant: GraphQLErrorExtensions = {
      code: ERROR_CODES.UNDEFINED_ERROR,
      http_status: 500,
      data: {},
    };
    const code: ErrorCode = variant.code;
    expect(code).toBe(ERROR_CODES.UNDEFINED_ERROR);
  });
});
```

- [ ] **Step 2.2: Run the tests — they should all pass**

Run:
```bash
cd /Users/paul/Projects/infrahub/frontend/app
pnpm test -- --run src/shared/api/graphql/errors.test.ts
```
Expected: PASS — all assertions green (this is not classic red-then-green TDD because the parser landed in Task 1; the tests are written here as a confirmation pass for the parser plus a compile-time guard for the catalogue surface).

If any test fails, the parser in Task 1 is wrong — fix `errors.ts`, not the tests. The most likely culprits: `parseErrorExtensions` mishandling `null` for `data` (must default to `{}`), or returning the wrong fallback for non-object inputs.

- [ ] **Step 2.3: Confirm the compile-time exhaustiveness guard works by mutating it**

Temporarily comment out one `case` line in `assertExhaustive` (e.g. `case ERROR_CODES.TOKEN_EXPIRED:`). Then run:
```bash
cd /Users/paul/Projects/infrahub/frontend/app
pnpm tsc --noEmit -p tsconfig.json 2>&1 | grep -E "errors\.test\.ts.*never" | head -5
```
Expected: a TypeScript error along the lines of `Type 'ErrorCode' is not assignable to type 'never'` referencing `errors.test.ts`. **Restore the commented line** and re-run `pnpm tsc --noEmit` to confirm zero errors before moving on. This confirms catalogue drift is caught at build time.

- [ ] **Step 2.4: Format with biome**

Run:
```bash
cd /Users/paul/Projects/infrahub/frontend/app
pnpm biome format --write src/shared/api/graphql/errors.test.ts
```
Expected: file is reformatted in place; no lint errors.

- [ ] **Step 2.5: Commit**

```bash
cd /Users/paul/Projects/infrahub
git add frontend/app/src/shared/api/graphql/errors.test.ts
git commit -m "test(frontend): unit tests for parseErrorExtensions (INFP-468 T031b)

Covers per-code narrowing, http_status/data passthrough, UNDEFINED_ERROR
fallback for unknown codes and malformed inputs, and a compile-time
exhaustiveness guard that fails the build if ErrorCode gains a value
without a corresponding switch arm."
```

---

## Task 3: Refactor `errorLink` to a typed switch with named helpers

Implements T031c and T031d from `tasks.md`. T031d's `AUTHENTICATION_REQUIRED` fix falls out naturally as soon as the switch only routes `TOKEN_EXPIRED` through the refresh path.

**Files:**
- Modify: `frontend/app/src/shared/api/graphql/graphqlClientApollo.tsx`

- [ ] **Step 3.1: Read the current file to anchor the edit**

Read `frontend/app/src/shared/api/graphql/graphqlClientApollo.tsx`. Confirm:

- Lines 1–12 are imports.
- Lines 14–23 export `defaultOptions`.
- Lines 26–32 define `httpLink`.
- Lines 35–53 export `authLink`.
- Lines 55–114 export `errorLink` (the `for` loop with the three `if`s).
- Lines 116–122 build and export the `graphqlClient`.

Only the `errorLink` body and the imports change. The other exports are not touched.

- [ ] **Step 3.2: Add the import for the new module and refactor `errorLink`**

Replace the entire `errorLink` block (lines ~55–114) with the new implementation, and add `parseErrorExtensions` + `ERROR_CODES` to the imports.

First, edit the imports. Above the existing `import { ACCESS_TOKEN_KEY } ...` line, add:

```ts
import { ERROR_CODES, parseErrorExtensions } from "@/shared/api/graphql/errors";
```

(Place it in the import group that uses the `@/shared/api/...` alias, alphabetised among siblings — biome will reorder it on format if needed.)

Then replace the existing `// Error link to refresh token or display error` block (the entire `export const errorLink = onError(...)` declaration) with:

```ts
// Error link: route each catalogue code to its policy. The catalogue is
// mirrored in @/shared/api/graphql/errors until US2's generated bindings
// (T029) land — see dev/specs/infp-468-graphql-error-catalogue/.
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

// Helper: refresh the access token and replay the operation. Lifted from
// the previous inline Observable block in errorLink — behaviour unchanged.
function retryWithRefreshedToken(
  operation: Parameters<Parameters<typeof onError>[0]>[0]["operation"],
  forward: Parameters<Parameters<typeof onError>[0]>[0]["forward"]
) {
  return new Observable((observer) => {
    const oldHeaders = operation.getContext().headers;

    queryClient
      .fetchQuery(refreshAccessTokenQueryOptions())
      .then((newToken) => {
        if (newToken?.access_token) {
          operation.setContext({
            headers: {
              ...oldHeaders,
              authorization: newToken?.access_token,
            },
          });

          // Retry the failed request.
          const subscriber = {
            next: observer.next.bind(observer),
            error: observer.error.bind(observer),
            complete: observer.complete.bind(observer),
          };

          forward(operation).subscribe(subscriber);
        }
      })
      .catch((err) => observer.error(err));

    forward(operation);
  });
}

// Helper: surface an error to the user. Calls operation.context's
// processErrorMessage if present (caller-specific override), else toasts.
function notifyUser(
  message: string | undefined,
  operation: Parameters<Parameters<typeof onError>[0]>[0]["operation"]
) {
  if (!message) return;

  const { processErrorMessage } = operation.getContext();

  if (processErrorMessage) {
    processErrorMessage(message);
    return;
  }

  toast(<Alert type={ALERT_TYPES.ERROR} message={message} />, {
    toastId: "alert-error",
  });
}
```

Notes for the engineer:

- The helper type for `operation` / `forward` uses `Parameters<...>` rather than importing internal Apollo types, because `@apollo/client/link/error` does not re-export the callback's first-argument type as a named export. This keeps the helpers honest about their contract without leaning on private types. If a future Apollo upgrade exports a named type, swap to it.
- `Observable`, `queryClient`, `refreshAccessTokenQueryOptions`, `toast`, `Alert`, `ALERT_TYPES` are all already imported at the top of the file — do not re-import them.
- The `console.error` is preserved verbatim except for the added `Code: ${parsed.code}, ` prefix.

- [ ] **Step 3.3: Verify the file compiles**

Run:
```bash
cd /Users/paul/Projects/infrahub/frontend/app
pnpm tsc --noEmit -p tsconfig.json 2>&1 | grep -E "graphqlClientApollo\.tsx" || echo "no errors"
```
Expected: `no errors`. Most likely failure: the `Parameters<...>` helper type doesn't extract correctly because `onError`'s callback signature in the installed `@apollo/client` version differs. If so, fall back to declaring local type aliases for the operation/forward params by reading `node_modules/@apollo/client/link/error/index.d.ts` and copying the relevant types into local `type` declarations at the top of the helpers — do **not** import internal modules.

- [ ] **Step 3.4: Run the full unit-test suite for the workspace**

Run:
```bash
cd /Users/paul/Projects/infrahub/frontend/app
pnpm test -- --run
```
Expected: PASS — no behaviour change should regress any existing test. If a snapshot or integration test relied on the old error-message format (e.g. asserting the exact `console.error` string without `Code: ...`), update the assertion to match the new format and call it out in the commit message.

- [ ] **Step 3.5: Format and lint**

Run:
```bash
cd /Users/paul/Projects/infrahub/frontend/app
pnpm biome:fix
```
Expected: biome reports the changed files as fixed; no lint errors. If lint reports unused imports or an unused parameter on `notifyUser`, fix locally — do **not** remove `processErrorMessage` or the operation parameter.

- [ ] **Step 3.6: Manually verify the AUTHENTICATION_REQUIRED fix path by inspection**

Open `graphqlClientApollo.tsx` and confirm by reading:
1. The `switch` has exactly two named arms (`TOKEN_EXPIRED`, `PERMISSION_DENIED`) plus `default`.
2. `AUTHENTICATION_REQUIRED` is **not** mentioned in the switch — it falls into `default` and routes through `notifyUser`.
3. The `console.error` template includes `Code: ${parsed.code}`.

This is the only behaviour change in the refactor and the visible review surface for it. No new unit test is added — the existing login E2E (and manual QA per T031d) covers the user-facing assertion.

- [ ] **Step 3.7: Commit**

```bash
cd /Users/paul/Projects/infrahub
git add frontend/app/src/shared/api/graphql/graphqlClientApollo.tsx
git commit -m "refactor(frontend): catalogue-typed switch in errorLink (INFP-468 T031c, T031d)

Replaces the if-chain in errorLink with switch (parsed.code) over the
typed GraphQLErrorExtensions returned by parseErrorExtensions. Extracts
retryWithRefreshedToken and notifyUser as file-local helpers so the per-
code policy is a one-screen read.

Fixes a long-standing silent failure (shared with develop) where
AUTHENTICATION_REQUIRED was routed through the refresh flow and produced
no toast when refresh inevitably failed for bad credentials. With the
catalogue split landed in US1, only TOKEN_EXPIRED triggers a refresh
attempt; AUTHENTICATION_REQUIRED now surfaces via the default
toast / processErrorMessage path.

Design: dev/specs/infp-468-graphql-error-catalogue/frontend-errorlink-refactor.md"
```

---

## Task 4: Final verification

- [ ] **Step 4.1: Run the workspace tests one more time, from a clean state**

Run:
```bash
cd /Users/paul/Projects/infrahub/frontend/app
pnpm test -- --run
```
Expected: all tests green.

- [ ] **Step 4.2: Run typecheck and biome over the whole workspace**

Run:
```bash
cd /Users/paul/Projects/infrahub/frontend/app
pnpm tsc --noEmit -p tsconfig.json
pnpm biome check src/
```
Expected: zero errors from both.

- [ ] **Step 4.3: Verify the three new commits are present and the tree is clean**

Run:
```bash
cd /Users/paul/Projects/infrahub
git log --oneline -5
git status
```
Expected: three new commits on top of `471b2424e1` (the "touchups" commit) — one for `errors.ts`, one for `errors.test.ts`, one for the `errorLink` refactor. Clean working tree.

- [ ] **Step 4.4: Update tasks.md to mark T031a–T031d as `[X]`**

Edit `dev/specs/infp-468-graphql-error-catalogue/tasks.md` and flip the `- [ ]` markers on T031a, T031b, T031c, T031d to `- [X]`. Do not modify any other task or text.

- [ ] **Step 4.5: Commit the tasks update**

```bash
cd /Users/paul/Projects/infrahub
git add dev/specs/infp-468-graphql-error-catalogue/tasks.md
git commit -m "chore(spec): mark T031a–T031d complete (INFP-468)"
```

- [ ] **Step 4.6: Manual smoke (optional — only if a dev backend is available locally)**

Per `frontend/app/AGENTS.md`:
```bash
cd /Users/paul/Projects/infrahub/frontend/app
pnpm dev
```
With a backend running, try to log in with intentionally bad credentials. Expected: a red toast appears showing the backend's error message. This was previously silent on `develop` and on this branch pre-refactor — its visibility is the user-facing fix shipped by T031d. If the toast does not appear, re-read Step 3.6 and check the `switch` arms.

---

## Out of scope (do not do)

- **Generated bindings (T027–T030).** The hand-written `errors.ts` is the bridge state; do not scaffold the json-schema-to-typescript generator or its CI here.
- **Form-field error wiring (T033) and permission dialog routing (T034).** These are separate US2 tasks with their own E2E coverage.
- **Touching `login.tsx`.** Its inline type for `extensions` is already assignment-compatible with `GraphQLErrorExtensions`; no edit is needed.
- **Friendlier user-facing messages from `extensions.data`.** Out of scope per spec §Non-goals — the toast continues to show `graphQLError.message`.
- **Adding link-level unit tests for `errorLink`.** None exist today; the refactor's behaviour is one switch + two helpers, reviewable by reading. The `TOKEN_EXPIRED` silent refresh is covered by Phase 8's T053 Playwright test.
