# UI contract — repository branch status

The **client side** of the frozen backend contract. The backend contract itself lives at
`dev/specs/infp-671-cross-branch-repo-status/contracts/graphql-repository-branch-status.md` and its
SDL at `…/graphql-repository-branch-status.graphql`. That contract is **frozen** from increment A;
this document states only what the frontend commits to on top of it.

---

## 1. The gql.tada document

Hand-written with `gql.tada`, **not** a codegen document. The generated type surface lives at
`frontend/app/src/shared/api/graphql/generated/`; the base branch already carries it (IFC-3126
merged both `schema/schema.graphql` and the regenerated types), so **codegen must produce zero drift**
and needs no local schema overlay.

### Variables the document declares

| Variable | Type | Notes |
|---|---|---|
| `id` | `String!` | Repository id (uuid) or name |
| `limit` | `Int` | = page size (default 20) |
| `offset` | `Int` | = `(page - 1) * pageSize` |
| `name__value` | `String` | Branch-name fragment |
| `partial_match` | `Boolean` | **Always `true`** when `name__value` is sent — the filter is a partial match by requirement (FR-012) |
| `status__value` | `BranchStatus` | Wire enum name is `BranchStatus`, *not* `InfrahubBranchStatus` |

### Variables the document deliberately does NOT declare

```
sync_status__value        ✗
internal_status__value    ✗
own_values_only           ✗
```

**This is how FR-016 is enforced — structurally.** A variable that cannot be expressed cannot be
sent. There is no code path to forget to guard, and no reviewer needs to remember the rule.

**What actually happens if one is sent**: the backend **rejects it with a `ValidationError`** while
the stub serves placeholder values — the resolver raises it for any of the three that would narrow the
rows, and the frozen SDL says so in terms. So the failure mode being prevented is a **loud whole-card
failure**, not a silently-wrong row set.

> IFC-3130's Jira description says these are "accepted but ignored", so that a filter "appears to do
> nothing". That contradicts the frozen SDL and the resolver. **The ticket is wrong and needs editing
> by its owner** — tracked as open question Q6 in [plan.md](../plan.md). The contract is what this
> feature is built against.

They are **deferred, not dropped** — once IFC-3127 lifts the restriction they become buildable as
follow-on work outside this spec.

FR-016's component test pins the absence anyway, asserting these arguments appear in no request the
feature makes.

### Selection set

```graphql
InfrahubRepositoryBranchStatus(...) {
  count                    # ← the ONLY source of the stated total
  edges {
    node {
      name          { value }
      status        { value }
      is_default    { value }
      sync_with_git { value }
      branched_from { value }
      commit        { value }
      sync_status   { value label color description }
      internal_status { value label color description }
      ref           { value }      # CoreReadOnlyRepository only; null for CoreRepository
    }
    # node_metadata: NOT SELECTED — see below
  }
}
```

**`node_metadata` is not selected.** It carries `updated_at`, and not asking for it is the cheapest
possible structural guarantee for FR-006: the card cannot render a "Last import" timestamp, or any
substitute drawn from `updated_at`, from data it never requested.

**`sync_status` selects `label` and `color` from the schema** (FR-004, FR-005). The card holds no
label map and no colour map. A value the test invents must render with that invented label and
colour — which is exactly how FR-004 is verified.

**The column header is the schema's `sync_status` label**, whatever it is. The design canvas heads
this column `Import status` (read-write) and `Git state` (read-only); FR-005 forbids rendering either,
because neither is the schema's own. This document names no canvas label as a column name.

---

## 2. The API boundary — the mock point

```
frontend/app/src/entities/repository/api/get-repository-branch-status-from-api.ts
```

**This file is the contract boundary for tests (D2).** Component tests mock **this module** and let
the real use case and react-query run. Mocking the query *hook* instead would hide the request, and
every request assertion would degrade to asserting a mock.

### The pairing rule

> Every request assertion MUST be paired, **in the same test**, with a rendered-output assertion
> drawn from a **different payload**.

A filter change is then observable twice:

```
apiMock.mock.calls[1][0]          → carries the new variables
rendered rows                     → now show a branch absent from the first payload
```

This is what makes the suite non-tautological:

| Bug | Caught by |
|---|---|
| Filtering client-side instead of server-side | rows change, but there is no second call |
| Calling the server and ignoring the response | second call happens, but the old rows remain |

Neither passes. A test that asserts only one half catches neither.

---

## 3. Error contract (D4)

```ts
class RepositoryBranchStatusError extends Error {
  code: "PERMISSION_DENIED" | "UNKNOWN"
}
```

Thrown by the **use case**, derived from the GraphQL `extensions` payload against the frontend error
catalogue, which already declares `ERROR_CODES.PERMISSION_DENIED` with a typed `PermissionDeniedData`.

| Backend | Wire | Frontend `code` | Rendered |
|---|---|---|---|
| `PermissionDeniedError` (a `ForwardableError`, HTTP 403) | `extensions.code = PERMISSION_DENIED` | `"PERMISSION_DENIED"` | `UnauthorizedScreen` |
| anything else (network, 5xx, malformed) | — | `"UNKNOWN"` | `ErrorScreen` |

The query requires view permission on the repository's kind covering **both** the default and
non-default branches (`ALLOW_ALL`, or `ALLOW_DEFAULT` plus `ALLOW_OTHER`). A denial is **outright** —
the server does not return fewer rows.

Which is why the denied state must never look like the empty state (FR-023, SC-007): "you may not see
this" and "this repository has no branches" are different facts, and conflating them tells the user
something false. They differ by **component**, not by a hand-written string.

---

## 4. Card states (FR-023)

Four distinguishable states — loading, populated, empty and failed — each with exactly one component,
so no two can render the same text. Empty and failed each split in two by cause.

| State | Component | Copy | Distinguishing fact |
|---|---|---|---|
| Loading | `ObjectTableSkeleton`, `rowCount` = the current page size | — | Occupies its space; **no layout jump** when rows arrive |
| Populated | `DataTable` + `TablePagination` | — | Rows, the count pill, and the window statement |
| Empty — no match | `NoDataFound` | `No branch matches these filters` | Follows a filter the user set |
| Empty — none in scope, `CoreRepository` | `NoDataFound` | `No branch of this repository synchronises with Git` | The row set *is* the `sync_with_git` branches, so an empty set means none of them syncs |
| Empty — none in scope, `CoreReadOnlyRepository` | `NoDataFound` | `This repository has no branches` | The row set is **every** branch (§5), so an empty set means there are no branches at all — the Git-sync wording would state something false |
| Failed — denied | `UnauthorizedScreen` (with a `className` override; its default is page-shaped `flex-1 p-8`) | `You do not have permission to view this repository's branches` | The user is told they cannot see the list |
| Failed — other | `ErrorScreen` (same override) | `The branches could not be loaded` | A failure distinct from both empty and loading |

**The strings are pinned here deliberately.** The canvas draws none of these states, so left
unspecified the components' defaults would silently become the user-facing copy — including the
none-in-scope case, which is specific enough that a generic default would be actively misleading.
Pinning them here lets copy be reviewed without reading code.

**The none-in-scope string is per kind**, because the row-set rule is (§5). A single Git-sync string
is correct on `CoreRepository` and false on `CoreReadOnlyRepository`. Every other string is shared.

**A failure here must not blank the rest of the page** (FR-024) — both details cards continue to
render while the branches query is failed. This holds for query failures by construction (the throw
lands in react-query's `isError` and renders in place). It holds for **render-time** failures — a
mapper crash, a null reaching `DropdownCell` — only because of the **card-scoped `ErrorBoundary`**;
without it such a failure propagates to `error-boundary-router` and blanks the whole route.

> **A fifth, column-scoped state will be needed** when IFC-3101's drift column lands: that column
> arrives as a *second* query with independent failure states. Build the **column slot**, not the
> machinery — the fifth state is IFC-3101's to specify.

---

## 5. Per-kind differences

| | `CoreRepository` | `CoreReadOnlyRepository` |
|---|---|---|
| Card title (FR-007) | `Branches` | `Infrahub branches` |
| Row set | branches with `sync_with_git` true | **every** branch, including those with Git sync disabled |
| `ref` column | absent (`ref` is null) | present — the ref that branch tracks |
| Columns | Branch · *`sync_status`'s schema label* · Commit | Branch · *`sync_status`'s schema label* · Commit · Ref |
| None-in-scope empty copy (§4) | `No branch of this repository synchronises with Git` | `This repository has no branches` |
| E2E coverage | yes (FR-026) | **no — deliberately** (FR-027) |

**FR-027 is a recorded gap, not an oversight.** The e2e data set contains no `CoreReadOnlyRepository`;
adding that fixture is shared with IFC-3153 and is not budgeted here. Read-only behaviour is covered
by component tests instead — the row set, the ref column and the card title. The absence of e2e
coverage is recorded rather than silent.

---

## 6. What this contract does not carry

Named here so a later reader does not go looking for them:

- **Upstream / remote commit, any "N behind" indicator, any last-import timestamp** — FR-006. They
  belong to epic IFC-3101, arrive on their own data path (`InfrahubRepositoryBranchDrift`), and have
  their own failure states. **The rows here must render whether or not they ever appear.**
- **A row-action menu** — FR-003a. The design shows a 40px `mdi:dots-vertical` column but does not
  specify its contents, so it is not invented.
- **Any order control.** Ordering is the server's default (default branch first, then name ascending)
  and this feature neither imposes nor exposes an order.
- **The `tag` / `branch` ref-kind pill** from the design canvas. No field in the contract carries that
  distinction, and deriving it from the ref string would be guesswork.
