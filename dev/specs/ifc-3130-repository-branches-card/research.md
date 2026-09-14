# Research: codebase and toolchain facts

Verified by reading the source in this worktree, not inferred. Every claim carries a path, and
where a line number is given it was read at the commit this branch was cut from — treat the path as
stable and the line as a hint.

Companion documents: [spec.md](spec.md) (what we build and why), [design.md](design.md) (the canvas,
transcribed verbatim).

---

## 1. Where repositories live in the frontend today

**There is no dedicated repository page.** Repositories render through the generic object-detail
route `/objects/:objectKind/:objectId`.

| Concern | File |
|---|---|
| Page shell | `src/pages/objects/object-details-page.tsx` |
| Tabs + `Card`-wrapped `<Outlet>` | `src/entities/nodes/object/ui/object-details/object-details-body.tsx` |
| Index tab, the card grid to extend | `src/entities/nodes/object/ui/object-details/object-details.tsx` |
| The "Details" attribute card | `src/entities/nodes/object/ui/object-details/object-details-card.tsx` |
| Tab injection (`isRepository`) | `src/entities/nodes/object/ui/object-details/object-details-tabs.tsx` |
| Repo menu + connectivity modal | `src/entities/nodes/object/ui/object-details/object-details-menu.tsx` |
| Kind constants | `src/entities/repository/domain/model/repository.ts` |

The index tab lays out `DetailsLayout.Main` / `.Aside` (`src/shared/components/layout/details-layout.tsx`,
a 2/3–1/3 grid): Main is `ObjectDetailsCard`, Aside is `ObjectProfilesGroupsCard` +
`ObjectActivitiesCard`. **That grid is what the two-card split extends.**

Existing repository entity code covers connectivity checks, the repository group, and commit
import/reimport — `src/entities/repository/{api,domain/use-cases,ui}/`. Notably: **`internal_status`
and `commit` appear only in generated GraphQL types. There is no app code for them.**

**Exemplars to copy for a tabbed detail page**: `src/pages/branches/details.tsx` plus
`src/entities/branches/` (the most complete entity folder, including `ui/routing/`), and the
proposed-changes equivalent. Entity-layer convention is documented in
`dev/knowledge/frontend/entities-structure.md`.

**Card primitives**: `frontend/packages/ui/src/components/card/card.tsx` exports only `Card`,
`CardHeader`, `CardContent` — no Title or Footer. The header-with-action pattern is
`object-details-card.tsx` (`<CardHeader className="flex justify-between">` + a ghost `Button`).

---

## 2. Tables, and why `RelationshipTable` cannot be reused

`src/entities/nodes/relationships/ui/relationship-table/relationship-table.tsx` takes only
`{relationshipSchema, parentId, parentKind, relationshipName}` and **owns its own query**
(`useObjectRelationships` + `useGetRelationshipCount`). It cannot be pointed at a hand-written
query. Reuse stops at the layer beneath it.

**What is reusable**: `src/shared/components/table/data-table.tsx` (TanStack, CSS-grid) with props
`{columns, count, data, isLoading, renderEmpty, toolbarActions, enableRowSelection, gridTemplateColumns, columnOrder}`.

Two constraints it imposes:

- `DataTable<T extends NodeCore>` with `getRowId: (row) => row.id`. **Branch-status rows carry no
  `id`** in the contract — branch `name` is unique and is the natural row identity, so this is a
  mapper concern.
- The default `gridTemplateColumns` assumes a trailing actions column:
  `repeat(count-2, fit-content(MAX)) 1fr 2.5rem`. A table without one must pass its own function.

**Cell renderers to reuse** (`src/entities/nodes/object/ui/object-table/cells/`):
`dropdown-cell.tsx` renders `{value, label, color}` as a chip using `label ?? value` — an exact
match for the contract's `Dropdown` payload, which is why no new mapping is needed. Also
`table-attribute-cell.tsx` (kind switch), `src/shared/components/display/date-display.tsx`,
`src/shared/components/ui/badge.tsx`, `src/shared/components/buttons/copy-to-clipboard*.tsx`.
Branch-specific cells live in `src/entities/branches/ui/branches-table/cells/`.
**There is no commit-hash cell yet.**

---

## 3. Why infinite scroll breaks inside a card

`src/shared/components/utils/infinite-scroll.tsx` sets an `IntersectionObserver` whose `root` is the
Radix **ScrollArea viewport**, with a sentinel `div` after the children. Inside a `Card` with no
height constraint that viewport grows to content height, so the sentinel never leaves the root
rect — `onLoadMore` either fires repeatedly or never re-fires.

Today the bound comes from the page level: `src/shared/components/layout/content.tsx` is
`h-full overflow-auto`, under `src/pages/app-layout.tsx`.

A root-less variant exists — `src/shared/components/utils/infinite-trigger.tsx`, viewport-relative,
used by `src/entities/proposed-changes/ui/proposed-change-events.tsx`.

---

## 4. The existing pagination, and why we are not extending it

`src/shared/components/ui/pagination.tsx` — props are **only** `{count?, className?}`:

- It calls `usePagination()` internally and reads/writes a **single global URL key**
  (`QSP.PAGINATION`), so two paginated tables cannot coexist on one route.
- Page sizes are hardcoded `[10, 20, 50]`; `src/shared/hooks/usePagination.ts` hardcodes
  `DEFAULT_LIMIT = 10`, `DEFAULT_OFFSET = 0`, `AVAILABLE_LIMITS = [10, 20, 50]` (nuqs
  `useQueryState` + `parseAsJson`).
- The container is `sticky bottom-0 ... bg-table-cell-pinned p-2` — built for the page-level scroll
  area.
- Copy: `Showing X to Y of N results`. Built on `react-paginate`.

**Three call sites must keep working unchanged**: `src/entities/tasks/ui/task-items.tsx`,
`src/pages/resource-manager/resource-allocation-details.tsx`,
`src/entities/diff/ui/checks/validator-details.tsx`.

Per spec FR-017 the existing component is **not modified**; a new one is built for in-card table
use. See spec Clarifications for the reasoning.

---

## 5. Hand-written GraphQL: gql.tada, not codegen documents

Documents are declared with **gql.tada** — `graphql(...)` re-exported from
`src/shared/api/graphql/client.ts`, executed by a per-call urql client. Types come from
`VariablesOf` / `ResultOf`, not from generated document types. Convention is **one document per
`*/api/*-from-api.ts`**.

Closest prior art: `src/entities/branches/api/get-branches-from-api.ts` (`InfrahubBranch`,
limit/offset + filters, `BRANCHES_PER_PAGE = 40`) and
`src/entities/tasks/api/get-task-list-from-api.ts` (`InfrahubTask`).

**Codegen** — `frontend/app/graphql.config.ts`: schema `../../schema/schema.graphql`, documents
`src/**/*.{ts,tsx}` excluding tests, emitting **types only** to
`src/shared/api/graphql/generated/types.ts`. Scripts: `pnpm codegen`,
`pnpm codegen:graphql` (`gql.tada generate output && gql.tada generate turbo`).

**CI enforces codegen consistency**: `.github/workflows/ci.yml` runs `pnpm codegen:graphql` then
`git diff --exit-code` on `graphql-env.d.ts` and `graphql-cache.d.ts`, failing on drift. Since
IFC-3126 merged into the base branch, the schema and generated types are committed upstream and
this regenerates clean — no local overlay is needed.

---

## 6. The attribute `branch` support metadata — what makes the card split schema-driven

`src/entities/schema/domain/model/schema.ts` types the schema from the OpenAPI document
(`src/shared/api/rest/types.generated.ts`, generated by `pnpm codegen:openapi` from
`schema/openapi.json`).

Every attribute read model carries:

```
branch?: components["schemas"]["BranchSupportType"] | null
// "Type of branch support for the attribute, if not defined it will be inherited from the model"
```

and `BranchSupportType` is `"aware" | "agnostic" | "local"`. `NodeSchema` carries its own `branch`,
which is the fallback when an attribute declares none.

**This already reaches the client** — `src/entities/schema/ui/attribute-display.tsx` renders it in
the schema viewer. **No app code partitions behaviour on it yet; this feature is the first.**

Template objects are a separate namespace: `isTemplateSchema` is `schema.namespace === "Template"`
(`src/entities/schema/domain/rules/is-template-schema.ts`). They render through the same generic
object pages and are out of scope.

---

## 7. Testing: what exists, and the patterns a new test must follow

**Coverage in this surface area is thin.** `RelationshipTable` has zero tests. `Pagination` and
`usePagination` have zero tests — only `src/shared/utils/pagination.test.ts` (pure
`calculateDynamicPageSize`). No `src/pages/**` file has a test. Repository tests are limited to
`check-connectivity-modal.test.tsx` and `repository-menu-section.test.tsx`.

**Mocking: no MSW, no `MockedProvider`.** The pattern is `vi.mock("@/entities/<x>/ui/queries/<y>.query")`
at module top, then
`vi.mocked(useX).mockReturnValue({...} as unknown as ReturnType<typeof useX>)`.

**Render** with `render` from `frontend/app/tests/components/render.tsx` — wraps NuqsAdapter →
jotai `Provider` → `QueryClientProvider` → `BrowserRouter` → `ToastContainer` → `BranchContext`.
`renderAt()` swaps `BrowserRouter` for `MemoryRouter`; that is the pattern for URL-driven tests
(see `src/shared/components/ui/link-tab.test.tsx`). Fakes live in `frontend/app/tests/fake/`
(`generateNodeSchema`, `generatePermission`, `generateBranch`). Call `initPointerTracking` from
`tests/components/utils.ts` before hover assertions.

**Exemplars**: `src/entities/preferences/ui/user-preferences-card.test.tsx` is the only card test
(asserts title and `dt`/`dd` rows). `src/entities/user-profile/ui/profile-tabs.test.tsx` and
`link-tab.test.tsx` cover tabs.

**E2E**: `tests/e2e/repository/test_repository_objects.py`, module-level
`pytestmark = pytest.mark.shard_branches_repo` — exactly one marker per file. The repository fixture
is `demo_edge_repo`, which contains **no** `CoreReadOnlyRepository` (stated in IFC-3153). Any new
page under `src/pages/` needs at least one happy path asserting *rendered data*. No
`wait_for_timeout`.

**Binding guide rules** (`dev/guides/frontend/writing-{unit,component,e2e}-tests.md`): colocate
`.test.ts`; factories named `generate*`; exactly one GIVEN / one WHEN / one THEN comment each;
specific assertions, never `toBeTruthy`; component tests must cover error, loading and empty states
and must assert the whole user-visible string, not a static prefix; do not test radix/react-aria
behaviour; restore mutated globals (jotai store, `window.history`).

---

## 8. Backend contract summary

Full contract: `dev/specs/infp-671-cross-branch-repo-status/contracts/graphql-repository-branch-status.{graphql,md}`
(on this branch — IFC-3126 merged). Final from increment A; only the truthfulness of four attribute
values changes afterwards.

Root field `InfrahubRepositoryBranchStatus(id: String!, limit: Int = 40, offset: Int = 0,
name__value: String, partial_match: Boolean = false, status__value: BranchStatus,
order: MetadataOrderInput, sync_status__value: String, internal_status__value: String,
own_values_only: Boolean = false)` returns `{ count: Int!, edges: [{ node, node_metadata }] }`.

Node fields use **`InfrahubBranch`'s value-field wrappers**, not the legacy flat `Branch` shape —
`name.value`, `status.value`, `is_default.value`, `sync_with_git.value`, `branched_from.value`,
plus `commit` / `ref` as `TextAttribute` and `sync_status` / `internal_status` as `Dropdown`.

Row set: read-write → branches with `sync_with_git` true; read-only → all branches. Global, `MERGED`
and `DELETING` branches always excluded. Default order: default branch first, then name ascending.
Permission: view on the concrete kind covering both default and other branches; denial is an error,
never a trimmed row set.

**Traps**: `updated_at` must never be rendered as a last-import time. `sync_status` wire values are
hyphenated (`in-sync`, `error-import`) while labels are title-cased. The status enum is
`BranchStatus` on the wire though the backend symbol is `InfrahubBranchStatus`. While the preview
stub is live, `sync_status__value`, `internal_status__value` and `own_values_only` are **rejected**,
not ignored.
