# Contract: `graphqlClient` transport interface (UI contract)

This is the internal contract the entire app depends on. The migration MUST preserve it byte-for-byte at the type and runtime level. It is the acceptance surface for FR-008.

## Module

`src/shared/api/graphql/graphqlClient.ts` (default export). The current file `graphqlClientApollo.tsx` is replaced; the import path used by callers is kept stable (either keep the filename or update the 33 import sites — see tasks).

## Type contract

```ts
import type { DocumentNode } from "graphql";
import type { TypedDocumentNode } from "@urql/core";

type RequestPriority = "high" | "low";

interface OperationContext {
  branch?: string | null;
  date?: Date | null;
  priority?: RequestPriority;
  processErrorMessage?: (message?: string) => void;
}

interface GraphQLResult<TData> {
  data?: TData;
  /** undefined on success — NEVER an empty array */
  errors?: Array<{ message: string }>;
}

interface GraphQLClient {
  query<TData = any, TVars = Record<string, unknown>>(opts: {
    query: DocumentNode | TypedDocumentNode<TData, TVars> | string;
    variables?: TVars;
    context?: OperationContext;
    fetchPolicy?: "no-cache"; // accepted, ignored (already the default)
  }): Promise<GraphQLResult<TData>>;

  mutate<TData = any, TVars = Record<string, unknown>>(opts: {
    mutation: DocumentNode | TypedDocumentNode<TData, TVars> | string;
    variables?: TVars;
    context?: OperationContext;
  }): Promise<GraphQLResult<TData>>;
}
```

## Behavioral contract (verifiable assertions)

1. **Headers**: every request carries `Authorization: Bearer <token>` iff a token exists (else absent), and `X-Priority` = `high` by default or `low` when `context.priority === "low"`.
2. **Endpoint**: request URL = `CONFIG.GRAPHQL_URL(context.branch, context.date)` per operation; `?at=<ISO>` appended iff `date` present; branch defaults to `main`.
3. **Success**: resolves `{ data: <payload>, errors: undefined }`.
4. **GraphQL error + partial data**: resolves `{ data: <partial>, errors: [{ message }, ...] }` — data retained.
5. **Error routing** by catalogue code: `TOKEN_EXPIRED` → single refresh+replay; `AUTHENTICATION_REQUIRED` → redirect to login; `PERMISSION_DENIED` → silent; `UNDEFINED_ERROR` → toast (+ dev console warning); otherwise `context.processErrorMessage(message)` if provided, else default toast.
6. **Token refresh (FR-006)**: at most one refresh+replay per operation; concurrent operations trigger exactly one shared refresh; persistent `TOKEN_EXPIRED` after replay, a refresh returning no token, or a throwing refresh all → `redirectToLogin()` + surfaced error, never a hung promise.
7. **File upload**: a `File`/`Blob` in `variables` produces a multipart request accepted by the existing backend upload mutations.
8. **No cache**: identical sequential queries each hit the network (no cached result served).

## Known deviation (must be resolved before ship)

- **In-flight dedup**: urql dedups concurrent identical `query+variables` at the Client level with no off-switch; the key ignores `context`. Cross-branch concurrent identical operations are the exposed case. See `research.md` Decision 3 — a spike must confirm non-reproducibility or apply a mitigation before this contract is considered fully met (assertion 8's concurrent-cross-branch variant).
