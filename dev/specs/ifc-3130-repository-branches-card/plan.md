# Implementation Plan: Repository branches card and branch-scoped details

**Branch**: `ple-branches-card-ifc-3130` | **Date**: 2026-09-16 | **Spec**: [spec.md](spec.md)

**Base branch**: `cross-branch-repo-status-infp-671` — a feature branch, not `develop` or `stable`.
IFC-3126 is already merged into it, so the schema and the regenerated frontend types are present
and codegen regenerates to zero drift.

**Input**: [spec.md](spec.md) (33 requirement statements),
[plan-synthesis.md](plan-synthesis.md) (the merged output of three parallel plan framings —
minimal-change, refactor-friendly, test-first), [design.md](design.md), [research.md](research.md).

> **Precedence.** `plan-synthesis.md` outranks `research.md` wherever they disagree; it corrected
> four of research.md's claims against source. Those corrections are restated in
> [Corrections carried forward](#corrections-carried-forward) and are authoritative here.

## Delivery status

This document describes the **design as delivered** on `ple-branches-card-ifc-3130`, at the paths
named below. [tasks.md](tasks.md) is the only place that tracks work still to do — a ticked box there
means the file exists on this branch.

| Work unit | Status |
|---|---|
| 1 Pagination utils + hook + component | Delivered |
| 2 Query, model, mapper, use case | Delivered |
| 3 Partition rule | Delivered |
| 4 Test factories, pairing helper, lint guard | Delivered |
| 5a Columns, cells | Delivered |
| 5b Filters (`use-repository-branch-filters.ts`) | **Outstanding** |
| 6 The branches card + its ErrorBoundary | Delivered |
| 7 The details split | Delivered |
| 8 E2E | **Outstanding** |
| 9 Knowledge note, `shared-components.md`, changelog fragment | **Outstanding** |

---

## Summary

The repository page reports the default branch's Git state as though it were the repository's. This
feature adds a **Branches card** listing one row per in-scope branch with that branch's sync status
and imported commit, fed by the frozen `InfrahubRepositoryBranchStatus` query with server-side
paging, counting and filtering; and it **splits the repository details card in two** — repository-wide
attributes above, branch-scoped attributes below — with the division derived from each attribute's
schema branch-support declaration rather than from a field-name list.

The technical approach is **reuse-first**. A verified sweep against source found existing components
for every element but one; the single justified new primitive is `CommitHash`. The one substantial
new piece of machinery is a **three-layer table pagination** (pure utils / URL-scoped hook /
controlled component), built new because the legacy `Pagination` is hard-wired to a single global
`QSP.PAGINATION` key and to a page-level scroll area, and is shared by three unrelated pages.

Nothing in this feature writes. It is a read-only presentation over one GraphQL query.

## Technical Context

**Language/Version**: TypeScript 5.x (strict), React 19 with the React Compiler enabled

**Primary Dependencies**: Vite · Tailwind CSS + CVA · `@infrahub/ui` design system · TanStack Query
(react-query) · `nuqs` for URL state · `gql.tada` for typed hand-written GraphQL documents ·
jotai · React Router

**Storage**: N/A — read-only over GraphQL; no client-side cache shape beyond react-query's

**Testing**: Vitest in **browser mode** for unit and component tests; pytest-playwright for E2E at
repo-root `tests/e2e/`

**Target Platform**: Browser (the Infrahub web app at `frontend/app`)

**Project Type**: Web application frontend, Feature-Sliced architecture (`entities/` · `shared/` ·
`pages/`)

**Performance Goals**: One request per page view regardless of branch count (SC-003); rows
transferred bounded by the fixed page size (10), not by branch count

**Constraints**: Server-side paging, counting, filtering and ordering only — no client-side
narrowing of any kind (FR-015). The card must not blank the rest of the page on failure (FR-024).

**Scale/Scope**: Repositories with up to ~200 branches; 2 repository kinds (`CoreRepository`,
`CoreReadOnlyRepository`); 33 requirement statements; 9 work units.

### The IFC-3127 preview window

IFC-3126 ships the query with **real** rows, paging, ordering and permission denials, but the four
attribute values are **fabricated from the branch name**. They are stable across reloads and every
dropdown value appears, so the card is fully buildable and screenshottable against them.

Two consequences this plan must honour:

- `sync_status__value`, `internal_status__value` and `own_values_only` are **rejected with a
  `ValidationError`** while the stub serves placeholder values. The resolver raises it for any of the
  three that would narrow the rows, and the frozen SDL's own field description says "rejected" in
  those terms. IFC-3130's Jira description says the opposite — "accepted but ignored", so a filter
  "appears to do nothing". **The ticket is wrong and needs editing by its owner**; see Q6 in
  [Open questions](#open-questions--carried-not-invented). Nothing here is built against the ticket's
  wording.

  **FR-016 is enforced structurally**: the gql.tada document does not declare those three variables,
  and a variable that cannot be expressed cannot be sent. The failure mode prevented is a **loud
  whole-card failure**, not silently-wrong data.
- Nothing in this feature may depend on the values being real (SC-008). When IFC-3127 merges, the
  values become real **with no contract change and no code change here**.

### Who sees the fabricated values

This branch targets **`cross-branch-repo-status-infp-671`**, the epic branch, and IFC-3127 lands on
that same branch. So the fabricated values reach a user only if the epic branch merges to `develop`
while IFC-3127 is still outstanding — which is the epic owner's release decision, not this card's.

That is the honest position, and it is why this feature carries **no preview banner**: adding one
would be chrome that must then be removed, for a window that by construction has no users in it.
**If the epic branch is ever released without IFC-3127, this decision must be revisited** — plausible
fake commit hashes with nothing marking them are worse than showing nothing. Recorded as an open
question for the epic owner rather than settled here.

## Constitution Check

*GATE: evaluated before Phase 0, re-evaluated after Phase 1 design, and revised after critique.
Result: **PASS**, with four justified complexity entries.*

> **Git Workflow deviation, stated once so a reviewer does not flag it late**: the constitution says
> feature branches come from `develop`. This one comes from `cross-branch-repo-status-infp-671`,
> the INFP-671 epic branch, because it depends on IFC-3126 which has merged there and not to
> `develop`. Deliberate, and the PR targets that branch.

| Principle | Applies? | How this plan satisfies it |
|---|---|---|
| **I. Schema-Driven Integrity** | Yes — **conditional** | The card division is derived from each field's `branch` support declaration (FR-019), and every label and column header comes from the schema (FR-005) — never from a field-name list held in the frontend. This is what makes SC-005 free. Generated files under `src/shared/api/graphql/generated/` are **regenerated, never hand-edited**; the base branch already carries them, so codegen must produce zero drift. **The condition**: this is schema-*shaped* until the rule names all three `BranchSupportType` values. `local` is the one that matters — see [data-model.md](data-model.md) §2. Reads PASS only once that mapping and its per-value tests exist. |
| **II. Branch-Safe by Default** | Yes | Read-only; writes nothing, so no merge behaviour to specify. The one branch-semantics risk — a branch showing a value inherited from its **origin** branch at its fork point — is correct behaviour, pinned by acceptance scenario US1-4 and US1-7, and rendered as an ordinary value rather than as an error or an empty cell. This feature computes no inheritance itself. |
| **III. Type Safety & Explicit Contracts** | Yes | The query is typed end-to-end through gql.tada against the frozen contract. No `any`; `unknown` + type guards where a boundary is loose. The nullable contract fields ([data-model.md](data-model.md) §1) are guarded **in the mapper**, not at the call site. The page window and filter set are explicit inputs, never ambient state. Errors are typed (`RepositoryBranchStatusError` with a `code` union) rather than bare `Error`. |
| **IV. Test Discipline** | Yes — **with one recorded deviation** | Unit tests for the pure pagination arithmetic and the partition rule (one case per `BranchSupportType` value); component tests (Vitest browser mode) for every FR carrying a component-test verification; E2E at `tests/e2e/repository/` with the `shard_branches_repo` marker against `demo_edge_repo` (FR-026). The backend slice deferred the epic's E2E requirement to this card, so it lands here. Test files mirror source structure. **Two requirements are honestly recorded as verified by review rather than by test** — see [below](#verified-by-review-not-by-test). **The deviation**: the constitution says E2E "MUST be included for all user-facing features"; FR-027 knowingly ships `CoreReadOnlyRepository` without it. Defensible, but Governance requires a deviation be recorded in Complexity Tracking — it now is. |
| **V. Query Performance & Efficiency** | Yes | One request per page (SC-003). Server-side count, filters and ordering; no client-side narrowing (FR-015). `node_metadata` is **not selected at all** — the cheapest possible guarantee for FR-006. Row transfer bounded by page size. |
| **VI. Security & Input Boundaries** | Partial (N/A by shape) | No user input reaches a query language here — the filter values are bound as typed GraphQL variables. Authorization is the server's: the resolver raises `PermissionDeniedError` (a `ForwardableError`, HTTP 403) and the card renders `UnauthorizedScreen` for it (FR-023), distinct from the empty state, so a denial is never mistaken for "no branches" (SC-007). No error message exposes internal detail. |
| **VII. Simplicity & Maintainability** | Yes, with one justified entry | Reuses the existing `ObjectDetailsCard`, `DataTable` and `DropdownCell` rather than adding parallel ones. D1 was decided **against** the more elegant refactor precisely to avoid touching a file every object-detail page depends on. One new shared primitive (`CommitHash`) and one new pagination trio — both justified in [Complexity Tracking](#complexity-tracking). |

**Documentation requirement** (Governance → Documentation Requirements): frontend architecture
changes must update `dev/knowledge/frontend/`. FR-028 requires a note on the new pagination
component; the repo's own anti-pattern rule additionally requires a new shared primitive to be
justified in the PR description **and** added to `dev/knowledge/frontend/shared-components.md`.
Both are folded into work unit 9.

**Changelog** (Code Quality Gates → 5): this is a user-facing change, so it needs a Towncrier
fragment in `changelog/`.

### Post-Phase-1 re-evaluation

Re-checked after the data model and contracts below were settled. **No new violations.** The
design work made two constitution positions *stronger* rather than weaker:

- Principle I: choosing derived `ModelSchema` objects (D1) over a `fieldFilter` prop means the
  schema stays the single source of the division, with no second mechanism inside `ObjectDataDisplay`.
- Principle V: deciding not to pass `count` to `DataTable` (correction 2) removes a second,
  conflicting count from the DOM — the stated total has exactly one source, the server's.

## Corrections carried forward

All three plan framings verified source rather than trusting `research.md`. These four corrections
are authoritative and override `research.md` wherever it disagrees:

1. **`renderAt` is not exported** from `frontend/app/tests/components/render.tsx`. It is a private
   helper in `src/shared/components/ui/link-tab.test.tsx` and it **overrides the whole wrapper**,
   dropping `NuqsAdapter`, jotai, `QueryClient` and `BranchContext`. `research.md` §7 is wrong.
   URL-driven tests MUST instead drive `window.history` under the default `BrowserRouter` and reset
   it in `afterEach` — the only shape that keeps the nuqs adapter wired.
2. **`DataTable` renders its own count footer** whenever `count !== undefined` (rendering "N counts"),
   which would collide with FR-010a's window statement. **Do not pass `count`.**
3. **Generated gql.tada files live at** `frontend/app/src/shared/api/graphql/generated/`, and the
   **E2E suite is at repo-root `tests/e2e/`**, not under `frontend/app/`.
4. **`isOfKind(GENERIC_REPOSITORY_KIND, schema)`** already resolves both concrete repository kinds
   through `inherit_from` — the same predicate `object-details-tabs.tsx` uses for tab injection.
   FR-020's gate needs **no kind list**.

## Architecture decisions

Four decisions where the three framings diverged. Settled; not to be revisited during implementation.

### D1 — Two derived `ModelSchema` objects, rendered through a local `RepositoryDetailsCard`

Two derived `ModelSchema` objects with partitioned fields, each rendered through a **thin local
`RepositoryDetailsCard`** in `entities/repository/ui/` that composes `Card` + `CardHeader` + the
existing **`ObjectDataDisplay`**.

*Rejected*: adding an optional `fieldFilter` predicate to `ObjectDataDisplay` (~8 lines, default =
today's behaviour). Both reach the same place, but the derived-schema route **touches no file that
every object-detail page depends on** — the one change in this feature that could break unrelated
pages, and the refactor framing's own risk register ranked that edit as its highest-blast-radius item.

*Why not `ObjectDetailsCard`*: it **hardcodes the literal `Details`** in its `CardHeader` and
hardcodes `data-testid="object-details"`, exposing no title, caption or test-id prop. It cannot
produce FR-018's "On this branch" card, and two instances would collide on test id.

*Why the local card*: `ObjectDataDisplay` is the genuinely reusable part and is reused unchanged. The
wrapper is ~15 lines. It keeps **zero shared-file edits** — D1's whole point — while freeing both
titles, the caption slot and distinct test ids.

*Cost accepted*: two `ObjectDataDisplay` instances mount two metadata `Sheet`s, both default closed —
a duplicated dialog in the tree, not a behaviour change.

*Consequence for the partition*: `ObjectDataDisplay` renders **relationships as well as attributes**,
so the partition must cover both or every relationship renders twice. See
[data-model.md](data-model.md) §2.

### D2 — Tests mock at the API layer, never the hook

Mock `…/api/get-repository-branch-status-from-api` and let the **real** use case and react-query run.
Mocking the query *hook* hides the request, so every request assertion degrades to asserting a mock.

**The pairing rule — non-negotiable, and the single most important rule in this plan:** every request
assertion MUST be paired, *in the same test*, with a rendered-output assertion drawn from a **different
payload**. A filter change is then observable twice: `apiMock.mock.calls[1][0]` carries the new
variables, *and* the rendered rows change to a second payload containing a branch absent from the first.

This is what makes the suite non-tautological. A client-side filter would change rows without a second
call; a "call the server and ignore the response" bug would keep the old rows. Neither passes.

#### The rule is enforced mechanically, not by prose

A rule this important cannot survive as a paragraph. The first developer under time pressure writes
the request half alone and **nothing fails** — which is exactly how a suite becomes decorative.

Two mechanisms, both delivered in **work unit 4** so that units 5 and 6 had no other path available:

1. **One helper whose signature makes both halves required arguments** —
   `tests/helpers/expect-server-driven-change.ts`:

   ```ts
   expectServerDrivenChange({ apiMock, callIndex, variables, payload, rowVisibleAfter })
   ```

   Omitting either half is a type error, so "did you pair it?" is answered by the type checker
   rather than by a reviewer's memory.

2. **A lint guard** forbidding direct `apiMock.mock.calls[...]` access in the branches-card test
   files — the GritQL plugin `frontend/app/lint/no-direct-api-mock-calls.grit`, attached by a Biome
   override scoped to `src/entities/repository/ui/repository-branches-card/**/*.test.tsx`.

   **The guard is deliberately narrow.** It bans the member access *in those files*, not the
   assertion it is protecting: an absence assertion that no test can express through
   `expectServerDrivenChange` (FR-016, whose `toMatchObject` matching is partial by design) goes
   through a helper in `tests/helpers/` instead, where the guard does not apply.

   **Why it is not repo-wide.** `mock.calls` is a legitimate assertion in tests that are not
   request/response pairs, and `expectServerDrivenChange` only fits a test that renders a card
   against an api mock — so a global ban would fail existing suites it offers no replacement for.
   Widening it is a sweep of the existing call sites, not a config change, and belongs with whoever
   does that sweep.

This is the one decision in the plan that **cannot be retrofitted cheaply**: once twenty unpaired
tests exist, the helper is a migration rather than a default.

### D3 — Pagination in three layers

| Layer | File | Knows about |
|---|---|---|
| Pure functions | `src/shared/utils/table-pagination.ts` | arithmetic only — no React, no URL |
| Hook | `src/shared/hooks/use-table-pagination.ts` | the URL, scoped by a **required** `urlKey` |
| Component | `src/shared/components/table/table-pagination.tsx` | nothing about URLs — controlled via `page` / `onPageChange` |

The controlled component is what makes FR-011a testable with no URL at all, and what makes the three
later migrations mechanical. Building it uncontrolled — the legacy shape — would rebuild the exact
defect that makes the legacy component unmigratable.

`urlKey` is a **required** prop, never defaulted. That is the whole of FR-011's collision guarantee,
pinned by a test rendering two probes with different keys and asserting one is unmoved after the
other pages.

### D4 — A typed error from the use case

The use case throws `RepositoryBranchStatusError` carrying `code: "PERMISSION_DENIED" | "UNKNOWN"`,
derived from the error catalogue. Verified against the merged backend: the resolver raises
`PermissionDeniedError`, a `ForwardableError` with HTTP 403, and the frontend catalogue already
declares `ERROR_CODES.PERMISSION_DENIED` with typed `PermissionDeniedData`.

Without this the distinction dies at `graphqlClient.query`, which rethrows as a bare `Error` with the
detail only on `.cause`. Two independently testable levels result: a use-case unit test over the raw
`extensions` payload, and a card test over the two `code` values.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3130-repository-branches-card/
├── spec.md                       # 33 requirement statements, 3 user stories, success criteria
├── research.md                   # Phase 0 — codebase and toolchain facts (superseded in 4 places)
├── plan-synthesis.md             # Merged output of three parallel plan framings
├── design.md                     # Verbatim transcription of the design canvas
├── plan.md                       # This file
├── data-model.md                 # Phase 1 output
├── quickstart.md                 # Phase 1 output
├── contracts/
│   └── repository-branch-status-ui.md   # Phase 1 output — the UI-side contract
├── checklists/
│   └── requirements.md
└── tasks.md                      # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Everything unmarked is on the branch. `OUTSTANDING` marks what is not yet written — work unit 5b's
filters, and work units 8 and 9. Files marked `edited` already existed; see the shared-file table
above for what each edit is and what it risks.

```text
frontend/app/src/
├── shared/
│   ├── utils/table-pagination.ts                      # pure paging arithmetic
│   ├── hooks/use-table-pagination.ts                  # URL-scoped, required urlKey
│   ├── api/graphql/error-handling.ts                  # edited — hasThrownCatalogueCode
│   └── components/
│       ├── table/
│       │   ├── data-table.tsx                         # edited (do not pass `count`)
│       │   ├── style.tsx                              # edited — CELL_HEIGHT_PX
│       │   └── table-pagination.tsx                   # controlled, card-safe
│       ├── errors/unauthorized-screen.tsx             # edited — defaultOpen
│       └── display/commit-hash.tsx                    # the one justified new primitive
│
└── entities/
    ├── repository/
    │   ├── api/get-repository-branch-status-from-api.ts        # the mock boundary (D2)
    │   ├── domain/
    │   │   ├── model/repository-branch-status.ts               # row model + typed error
    │   │   ├── use-cases/get-repository-branch-status.ts
    │   │   └── rules/partition-fields-by-branch-support.ts     # pure, unit-testable
    │   └── ui/
    │       ├── queries/
    │       │   ├── get-repository-branch-status.query.ts       # react-query queryOptions
    │       │   └── repository.query-keys.ts                    # the slice's query-key factory
    │       ├── repository-branches-card/
    │       │   ├── repository-branches-card.tsx
    │       │   ├── repository-branches-card-boundary.tsx       # card-scoped ErrorBoundary
    │       │   ├── repository-branches-empty.tsx
    │       │   ├── messages.ts                                 # the pinned state copy
    │       │   ├── columns.tsx
    │       │   ├── cells/
    │       │   └── use-repository-branch-filters.ts            # OUTSTANDING — work unit 5b
    │       ├── repository-details-card.tsx                     # Card + CardHeader + ObjectDataDisplay
    │       └── repository-object-details.tsx                   # the two-card split
    │
    └── nodes/object/ui/
        ├── object-details/object-details.tsx           # edited — the isOfKind gate only
        └── object-table/
            ├── object-table-skeleton.tsx               # edited — rowCount, showSelection
            └── cells/
                ├── dropdown-cell.tsx                   # edited — widened prop type
                └── table-column-header-simple.tsx      # edited — optional role

frontend/app/
├── biome.jsonc                                         # edited — the override attaching the guard
├── vitest.config.ts                                    # edited — setupFiles
├── tests/
│   ├── setup.ts                                        # the shared afterEach URL reset
│   ├── fake/repository.ts                              # row factories
│   ├── fake/dropdown.ts
│   └── helpers/expect-server-driven-change.ts          # D2's pairing rule, mechanically enforced
└── lint/
    └── no-direct-api-mock-calls.grit                   # D2's lint guard, scoped by the override

tests/e2e/repository/
└── test_repository_branches_card.py                    # OUTSTANDING — marker: shard_branches_repo

dev/knowledge/frontend/
├── table-pagination.md                                 # OUTSTANDING (FR-028)
└── shared-components.md                                # OUTSTANDING — CommitHash + drift fixes

changelog/                                              # OUTSTANDING — Towncrier fragment
```

**Structure Decision**: Feature-Sliced, following the repository's existing `entities/<slice>/{api,domain,ui}`
layout exactly. The branches card is **inside the repository entity** because it is repository-scoped
presentation; the pagination trio is in **`shared/`** because FR-028 declares it the intended
successor for every future table.

**The gql.tada document lives in `api/get-repository-branch-status-from-api.ts`**, next to the api
boundary — that is where every gql.tada document in this codebase lives. `ui/queries/` is the
react-query `queryOptions` layer and holds none; putting the document there would force an
`api/ → ui/` import, which `dev/knowledge/frontend/entities-structure.md` prohibits.

**Eight shared files are edited, all eight on the branch:**

| File | Edit | Risk |
|---|---|---|
| `object-details.tsx` | the `isOfKind` gate | **Behavioural.** The feature's single entry point, and its entire rollback path |
| `shared/components/table/data-table.tsx` | an opt-in `semanticTable` flag putting `role="table"` on the grid container and `role="row"` on each row wrapper, plus optional `skeletonRowCount` / `skeletonShowSelection` pass-throughs to `ObjectTableSkeleton` | **Additive.** `semanticTable` defaults to `false`, so no existing table gains or loses semantics; only this card opts in. Required by FR-025: the row wrapper lives here, so `within(row)` scoping cannot be reached from the card's own files. Both roles are set together — an orphan `row` is invalid ARIA. Carries one `useFocusableInteractive` suppression, because Biome treats `row` as interactive though that only holds inside a grid/treegrid |
| `object-table/cells/dropdown-cell.tsx` | the `dropdown` prop widened from the full generated `Dropdown` to `Pick<Dropdown, "value" \| "label" \| "color">` | **Type-only.** Strictly more permissive, no runtime change; the component already reads only those three fields |
| `object-table/cells/table-column-header-simple.tsx` | optional `role`, forwarded to the header element | **Additive.** Undefined by default, so an existing header renders exactly as it did. The card passes `columnheader`, which is what completes `semanticTable`'s header row — a `row` of plain `<div>`s is invalid ARIA |
| `object-table/object-table-skeleton.tsx` | optional `rowCount` (default 20) and `showSelection` (default `true`), plus the row and cell roles a table that opted into `semanticTable` needs while it is still loading | **Additive.** Every default reproduces the previous behaviour, so no existing caller changes. The card passes its page size and turns the selection checkbox off, through `DataTable` — without them the skeleton ships a phantom checkbox and a layout jump at this card's page size, which FR-023's loading clause forbids |
| `shared/components/errors/unauthorized-screen.tsx` | optional `defaultOpen`, forwarded to the `Accordion` it already renders | **Additive.** Undefined leaves the accordion at its own default, so existing callers are unchanged. The card opens it, because a collapsed explanation inside a card reads as an empty card |
| `shared/api/graphql/error-handling.ts` | new `hasThrownCatalogueCode`, unwrapping the bare `Error` the transport rethrows before reading its catalogue code | **New export, plus a bundling change.** `CombinedError` moves from a type-only import to a value import — `instanceof` needs the class — so `@urql/core` now reaches the runtime bundle of anything importing this module, where before it was erased at compile time. Harmless while every importer already talks to GraphQL; worth re-checking if this module is ever pulled into one that does not |
| `shared/components/table/style.tsx` | new `CELL_HEIGHT_PX` constant | **Additive.** Nothing reads it unless it imports it. It is the numeric twin of the `h-10` in `cellsStyle` and the pairing is held by hand, so a change to either must carry the other or FR-011b's reservation silently stops matching a row |

The seven additive edits cannot break an existing caller: every new prop is optional and every
default reproduces today's behaviour. Reverting the gate alone still removes the feature.

**The card stays inside the detail route's outlet**, never replacing the page shell — IFC-3150 adds
its Commits tab as a sibling route on the same page.

## Reuse inventory

Verified against source and against `dev/knowledge/frontend/shared-components.md`. The three framings
each assumed more had to be built than actually does.

| Need | Use | Verdict |
|---|---|---|
| Branches card header: title + count pill | **Not `Content.CardTitle`.** `Card` + `CardHeader` with an `<h2 id>` the card's `aria-labelledby` points at, and a sibling `Badge` carrying the count | **LOCAL COMPOSITION** — `Content.CardTitle` is a page-level title component that renders its title as `<h1>`, so several cards on one page would each claim a top-level heading. The count is a sibling badge either way and never part of the heading's accessible name, so it carries its own — poll **the badge's** name, never the heading's |
| Details card header: title + branch-name caption | **Not `Content.CardTitle`.** The local `RepositoryDetailsCard` composes `Card` + `CardHeader` with an `<h2>` title and an optional `caption` paragraph beneath it, both referenced from the card's `aria-labelledby` | **LOCAL WRAPPER (D1)** — `Content.CardTitle` is a page-level title inside a card, and neither of its slots is the caption slot this needs: `end` renders right-aligned *beside* the title, `description` is styled as page-level lede. The `caption` prop puts the branch name beneath the title and inside the card's accessible name, which FR-018 and FR-025 both require |
| `default` row marker | `BranchDefaultBadge` (`entities/branches/ui/branch-list-item/branch-default-badge.tsx`) — already renders the literal `default` | **USE AS-IS** |
| Branch link target | `getBranchDetailsUrl(branchName, tab?, overrideParams?)` (`entities/branches/ui/routing/branch-urls.ts`) | **USE AS-IS** |
| Branch link cell | Compose `Tooltip` + `LinkButton href={getBranchDetailsUrl(name)}`, following `branches-table/cells/branch-name-cell.tsx` | **EXTEND, do not reuse** — that cell hard-depends on `useAuth()`, `StickyLeftCell` and a selection checkbox |
| Search field | `SearchInput` — `{value, onChange, placeholder, onPressReset, …}` (`shared/components/inputs/search-input.tsx`), pure and controlled, plus `useDebounce` (`shared/hooks/useDebounce.ts`) | **USE AS-IS** |
| Branch-status filter | `BranchStatusEnum` — `{value, onChange, defaultOpen?}` (`entities/branches/ui/filters/branch-status-enum.tsx`), fully controlled | **USE WITH PROPS** — it renders **nothing in its trigger when `value === null`**, an empty unnamed button that FR-025 forbids: pass an `aria-label` and a placeholder. It also offers all seven `BranchStatus` values including `MERGED` and `DELETING`, which the contract guarantees are **never returned** — restrict to the five returnable statuses, or selecting either always yields the empty state |
| Empty state | `NoDataFound` — `{message?, icon?}` (`shared/components/errors/no-data-found.tsx`), already `col-span-full py-12`. **Default export** | **USE AS-IS** — card-safe |
| Permission-denied state | `UnauthorizedScreen` — `{className?, message?, icon?, defaultOpen?}` (`shared/components/errors/unauthorized-screen.tsx`). **Default export** | **EXTENDED** — page-shaped `flex-1 p-8`, so it needs a `className` override; and its explanation sits in an `Accordion` that starts closed, which inside a card reads as an empty card. `defaultOpen` is additive and forwarded to that accordion |
| Error state | `ErrorScreen` — `{className?, message?, icon?, hideIcon?}` (`shared/components/errors/error-screen.tsx`) | **USE WITH PROPS** — same override |
| Loading state | `ObjectTableSkeleton` — `{headerCount, rowCount?, showSelection?}` (`entities/nodes/object/ui/object-table/object-table-skeleton.tsx`) | **EXTENDED** — it previously hardcoded 20 rows and a disabled `Checkbox` in column 0 of every row. This card has no selection column and holds 10 rows a page, so as-is it shipped a phantom checkbox **and** a guaranteed layout jump — precisely what FR-023's loading clause forbids. `rowCount` (default 20) and `showSelection` (default `true`) are additive; the card reaches them through `DataTable`'s `skeletonRowCount` / `skeletonShowSelection` |
| Info icon beside a value | `Tooltip` from `@infrahub/ui` with `nonInteractiveTrigger` + `InfoIcon`, per `entities/branches/ui/branch-details/branch-attributes.tsx` | **USE AS-IS** |
| Copy affordance on a full hash | `CopyToClipboardButton` — `{data, …AriaButtonProps}` (`shared/components/buttons/copy-to-clipboard-button.tsx`), already wrapped in a `Copied!`/`Copy` Tooltip | **USE AS-IS** |

**`UnauthorizedScreen` existing is what makes FR-023's denied-vs-empty distinction cheap** — the two
states differ by *component*, not by a hand-written string.

### The one new primitive: `CommitHash`

Nothing in the app renders a monospace, truncating, short-form hash. The only `font-mono` usage is
`entities/path-traversal/ui/infra-node.tsx`, and there is no short-hash helper anywhere.
`src/shared/components/display/commit-hash.tsx` is justified.

It **composes** `CopyToClipboardButton` rather than reimplementing copying, and takes `copyable` as a
prop: the design places copy affordances **only** on full hashes, never in table cells. The details
cards render their attribute values through `ObjectDataDisplay`, which knows nothing of this
primitive, so the card's table cells are its only call site here — see
[Complexity Tracking](#complexity-tracking).

### Reuse traps — do not walk into these

1. **`FilterSearchInput`** (`entities/nodes/object/ui/filters/filter-search-input.tsx`) is the obvious
   grab: it is already used with the exact placeholder `"Search branches"` at `branches-list.tsx`.
   It writes **global `QSP.FILTER`** via `useSearch` → `useFilters`. Use the underlying `SearchInput`.
2. **`useFilters()`** (`entities/nodes/filters/ui/hooks/use-filters.ts`) infects `FilterSearchInput`,
   `BranchesEmpty`, `BranchStatusFilterForm`, `BranchStatusHeader` **and `BranchesTable` itself**.
3. **`BranchesTable` takes zero props** — filters, columns and empty state are all hardcoded, so it
   cannot be reused in a card. `BranchesDataTable` *is* prop-driven but mounts `BranchesToolbar`,
   which renders a **`fixed bottom-10` viewport-anchored** toolbar and needs a Router. **Use
   `DataTable` directly.**
4. **`BranchStatusFilterForm` cannot be reused** — it writes through `useFilters()`'s single global
   `QSP.FILTER` key and would collide exactly as `usePagination` does. Use `BranchStatusEnum` with
   card-scoped state.
5. **Test-provider requirements**: `DataTable` and `BranchesDataTable` call `useAuth()`;
   `useCurrentBranch` needs the jotai provider; any `nuqs` state needs `NuqsAdapter`. All are in
   `tests/components/render.tsx` — which is precisely why copying `link-tab.test.tsx`'s private
   `renderAt` would break them (correction 1).

## Design-to-spec reconciliation

The design canvas shows a **six-column** grid. The spec removes three of those columns. The columns
actually built are:

| Design column | Built? | Why |
|---|---|---|
| `Branch` | ✅ | Row identity; name links to the branch detail page (FR-003a) |
| `Import status` | ✅ | Rendered by `DropdownCell`, label and colour from the schema (FR-004, FR-005) — **not** renamed from `sync_status` |
| `Commit` | ✅ | `CommitHash`, non-copyable in table cells |
| `Ref` (read-only kind only) | ✅ | The ref that branch tracks (FR-002) |
| `Upstream` | ❌ | FR-006 — epic IFC-3101, separate data path |
| `Last import` | ❌ | FR-006, including any `updated_at` substitute |
| Row-menu (40px) | ❌ | FR-003a — the design does not specify its contents, so it is not invented |
| `3 behind` pills | ❌ | FR-006 |
| `Showing 5 of 12 · Load more` footer | ❌ | Replaced by page controls (clarification + FR-011) |

**Custom `gridTemplateColumns` is required**: `DataTable`'s default reserves a trailing 2.5rem
actions column this card must not have.

### Divergence register — all of it, not just paging

**This register is the single record of where this feature departs from the canvas.** Every other
document points here rather than restating a row. **Take the whole of it to T094 in IFC-3101** — the
existing forum for unresolved canvas decisions — as one conversation, not row by row.

| # | Canvas says | This feature does | Why | Needs sign-off? |
|---|---|---|---|---|
| D-a | **ONE `Details` card** split by two internal group headers (`Repository` / `On this branch`). [design.md](design.md)'s "Up front: one card or two?" states in terms that it "does not introduce a second card for branch-local Git values" | **Two separate cards** (FR-018, FR-018a) | The clarification session of 2026-09-10 settled on two cards with "On this branch" as a card title and the branch name as a caption | **Yes — this is the big one.** A designer ruled explicitly against it |
| D-b | `Showing 5 of 12 · Load more` footer | Page controls, position in the URL | "Load more" cannot express a position in a URL, so it is incompatible with FR-011's reload-and-share requirement | Yes |
| D-c | Status column headed `Import status` (read-write) / `Git state` (read-only) | The schema's own `sync_status` label | FR-005 forbids a hardcoded label that differs from the schema's, and renaming the attribute is out of scope per the PRD | Yes — the canvas labels simply cannot be rendered without violating FR-005 |
| D-d | Read-only card has **no search toolbar** and no pagination ([design.md](design.md), the `Infrahub branches` card) | Search and pagination on both kinds | The read-only kind returns *every* branch, so it can exceed one page; asymmetry would be arbitrary | Yes |
| D-e | `tag` / `branch` pill beside the tracked ref | Dropped | No field in the contract carries the distinction; deriving it from the ref string is guesswork | Low risk |
| D-f | Explanatory footer on the read-only card | Kept as designed | The designer flagged it as a question for the team, not a blocker | No |
| D-g | `Internal status` listed in the **`Repository`** group, i.e. repository-wide | Lands in the **branch-scoped** card | `CoreGenericRepository.internal_status` is declared `LOCAL`, and FR-019 derives the division from the schema's branch support, not from a field-name list. The canvas group is where the designer drew it; the schema is what the rule reads. [design.md](design.md) transcribes the canvas and is left as drawn | Low risk — worth naming to the designer so the canvas and the schema agree |

**D-b rests on URL-shareability alone**, which is sufficient. It does *not* rest on serving the
*"jump to the failing branch among 200"* journey, because page controls do not serve that journey
either: FR-013 filters only the **branch lifecycle** `BranchStatus`, FR-016 defers
`sync_status__value` to IFC-3127, and there is no sort control. In this slice, finding the failing
branch among 200 means paging through them looking for a red chip. That is a limitation of the
slice, not an argument for either paging shape, and SC-002 should not be read as claiming otherwise.

**The register is still unraised** (T076). Pagination and the two-card split are both already
built, so a rejection now costs a rebuild rather than a redirection — which is the cost of not
raising it first.

## Accessibility mechanics (FR-025)

`DataTable` emits `data-testid="data-table-row"`, and the path of least resistance is `getByTestId`,
which defeats FR-025. Two changes make the requirement reachable, and both are in place:

- **`DataTable`'s `semanticTable` flag**, which this card sets. It puts `role="table"` on the grid
  container and `role="row"` on each row wrapper, so `getByRole("row", { name: /feat\/bgp-policies/ })`
  works and cells can be scoped with `within(row)`. Otherwise FR-003 can only be written as a
  whole-table text assertion, which passes whenever *any* row carries the default marker. The card's
  own columns complete the tree — every header passes `role="columnheader"` and every cell
  `role="cell"`, because a `row` of plain `<div>`s is invalid ARIA. Everything else the grid emits
  inside the table — the skeleton rows, the empty state, the count footer — follows the same flag,
  so the tree is valid in every card state rather than only once rows have arrived.

  **The flag is opt-in and defaults to `false`**, so a table that does not ask for the roles renders
  exactly as it did. That is what keeps this out of the app-wide-a11y-change class: the roles reach
  one card, and the next table to want them opts in deliberately.
- The default marker is `<Badge aria-label="Default branch">default</Badge>`.

**FR-004 and FR-025 conflict on their face**, and the resolution is written into both tests:
colour may never be used to *locate* an element, but asserting a chip's `backgroundColor` **after**
locating it by accessible name is a data-flow assertion, not a colour dependency. Assert
`backgroundColor` **only** — never the derived text colour, which `DropdownCell` computes with
`lch(from …)` and which serialises inconsistently.

Two mechanics the resolution needs to actually work:

- **Normalise both sides before comparing.** React writes styles through the CSSOM, so
  `element.style.backgroundColor` normalises hex to `rgb(…)` exactly as `getComputedStyle` does —
  asserting against the raw fixture hex fails with `expected 'rgb(76, 29, 149)' to be '#4c1d95'`.
  Push the fixture value through a throwaway element and compare the two normalised strings.
- **`DropdownCell` is a bare `<span>` with no role**, so "locate by accessible name" is in practice
  `within(row).getByText(...)`. The chip tests use that shape. Left unstated, the first implementer
  reaches for `getByRole`, finds nothing, and falls back to `getByTestId` — defeating FR-025.

**The pagination controls carry their own accessible names** — `aria-current` on the active page and
an announced page change. The legacy component has no a11y requirement at all, and three future
migrations inherit whatever this ships.

## Verified by review, not by test

Two requirements cannot be honestly verified by test. Recording them as such is deliberate: a green
test that proves nothing is worse than an honest note.

- **FR-008** ("no row value may depend on data outside the graph read") is unfalsifiable in a test
  that mocks the only source it has. **Verify it against two structural facts instead**: the card
  imports exactly one api module, and the selection set omits `node_metadata` entirely. Both are
  readable from the source in seconds and neither can drift silently.

  *Rejected substitute*: "the api mock is called exactly once per render." It measures render-loop
  stability, not data provenance, and it breaks the first time a legitimate refetch is added — a
  test that fails for the wrong reason teaches people to delete tests.

- **FR-017** (the three legacy paginated pages behave as today) would need three regression files for
  three pages that have **no tests at all** — more cost than the requirement buys, and the resulting
  tests would be the only coverage those files have. The honest guarantee is **zero diff** on
  `frontend/app/src/shared/components/ui/pagination.tsx` and
  `frontend/app/src/shared/hooks/usePagination.ts`, plus the FR-011 key-scoping unit test proving the
  new hook *cannot* collide with `QSP.PAGINATION`.

  > **Note the `ui/` segment**, and put the check in CI. `git diff --exit-code` with a pathspec
  > matching nothing **exits 0 silently**, so a wrong path passes forever. This belongs as a step in
  > the `frontend-lint` job, diffing against the merge base, not in a Definition-of-Done checkbox.

## Work units

Parallel groups separated by `───`. Units within a group share no file and have no sequential
dependency.

> The spec carries **33** requirement statements — FR-001…FR-028 **plus** FR-003a, FR-010a, FR-011a,
> FR-011b and FR-018a. Enumerate them individually; a range like "002–006" silently omits FR-003a.

| # | Unit | Key files | FRs | Status |
|---|---|---|---|---|
| 1 | Pagination utils + hook + component | `shared/utils/table-pagination.ts`, `shared/hooks/use-table-pagination.ts`, `shared/components/table/table-pagination.tsx` | 010, 010a, 011, 017 | Delivered |
| 2 | Query, model, mapper, use case | `entities/repository/{api,domain/model,domain/use-cases,ui/queries}/…` | 001, 008, 009, 016 | Delivered |
| 3 | Partition rule (attributes **and** relationships) | `entities/repository/domain/rules/partition-fields-by-branch-support.ts` | 019, 022 | Delivered |
| 4 | Test factories **+ the pairing helper and its lint guard** | `tests/fake/repository.ts`, `tests/fake/dropdown.ts`, `tests/helpers/expect-server-driven-change.ts`, `lint/no-direct-api-mock-calls.grit` | — (enables 001, 009, 012–015) | Delivered |
| ─── | | | | |
| 5 | Columns, cells, filters | `…/repository-branches-card/columns.tsx`, `cells/`, `…/use-repository-branch-filters.ts` | 002, 003, 003a, 004, 005, 006, 012, 013, 014, 015 | Columns and cells delivered; the filters are not |
| ─── | | | | |
| 6 | The branches card **+ its ErrorBoundary** | `…/repository-branches-card.tsx`, `…/repository-branches-card-boundary.tsx` | 007, 011a, 023, 027 | Delivered |
| 7 | The details split | `…/repository-details-card.tsx`, `…/repository-object-details.tsx` + the kind gate in `object-details.tsx` | 018, 018a, 020, 021, 022, 024, 025 | Delivered |
| ─── | | | | |
| 8 | E2E | `tests/e2e/repository/test_repository_branches_card.py` | 026 | Outstanding |
| 9 | Knowledge note + `shared-components.md` + changelog fragment | `dev/knowledge/frontend/table-pagination.md`, `dev/knowledge/frontend/shared-components.md`, `changelog/` | 028 | Outstanding |

**Dependencies**: 1–4 are fully independent. 5 depends on 2 and 4. 6 depends on 1, 4, 5. **7 depends
on 3 and 6** — FR-018a asserts the document order of *three* cards, and FR-024 and FR-025 are
composition properties of the assembled page, not of the branches card alone. 8 depends on 6 and 7.
9 depends on 1 and 6.

**Unit 4 has no FR behind it and that is correct** — it is fixtures. But it now also owns D2's
pairing helper and lint guard, which must exist *before* any card test is written (see D2).

**FR-011a** ("paging works with the table inside a fixed-height card, with no page-level scroll
container") is listed against unit 6 rather than unit 1: the component is unit 1's, but the
requirement can only be *verified* once there is a card to put it in.

**FR-013** is exercised in both unit 2 (the wire-value mapping) and unit 5 (the filter control). Unit
2 owns the test that the hyphenated wire value is sent.

## Risks, ranked by likelihood of actually biting

1. **Tautological request assertions.** Mitigated by D2, but only if the pairing rule is followed in
   *every* test. This is the failure that would make the whole suite decorative.
2. **URL bleed between tests.** `render.tsx` uses `BrowserRouter`, so nuqs writes to real
   `window.location`. Without an `afterEach` history reset, paging tests become order-dependent — the
   classic "passes alone, fails in a full run". Reset **`window.location.search`**, not just
   `history.state`, and do it in a **shared setup file** so a new test file cannot silently opt out.

   `render.tsx` mounts `NuqsAdapter` **outside** `BrowserRouter`, which reads like a latent crash. It
   is not: `createAdapterProvider` only puts the hook into context; `useNavigate` / `useSearchParams`
   execute in the consuming component, inside the Router. The `afterEach` reset is the right fix.
3. **`DataTable` geometry inside a `Card`.** `min-w-max` plus a sticky first cell inside a rounded
   card will overflow unless an explicit `gridTemplateColumns` is passed and the body scrolls
   horizontally *within* the card.
4. **Nullable contract fields.** Most of the node's fields may be absent entirely, not merely
   `{value: null}` — `is_default` is a `NonRequiredBooleanValueField`, and `sync_status` is a
   nullable `Dropdown` while `DropdownCell` requires non-null. Guard in the mapper; likely to appear
   during the preview window. The full nullability table is in [data-model.md](data-model.md) §1.
5. **Filter/page coupling (FR-014).** With independent URL keys, resetting the page on a filter change
   is a manual call, easy to forget on one of the two filters. Put the reset inside a single
   `setFilters` wrapper.
6. **E2E cost and flake.** Ten `sync_with_git=True` branches each trigger real git-worker branch
   creation; the card can render before all rows exist, so a total assertion races. **Poll the count
   badge by its own accessible name** rather than asserting once — the badge is the card heading's
   sibling, so the total is never part of the heading's name.
7. **FR-006 asserted by absence.** `not.toHaveTextContent("ago")` passes for a card rendering nothing.
   Pair it with a positive assertion in the same test.
8. **Row identity.** The contract guarantees one row per branch, so synthesise `id` from `name.value`
   **in the mapper**. Do **not** relax `DataTable<T extends NodeCore>` or its `getRowId` — that
   touches every table in the app.
9. **Grid style identity.** `DataTable` memoizes its grid `style` on
   `[allHeaders.length, gridTemplateColumns]`. An inline arrow passed from a parent that re-renders on
   every search keystroke changes identity each render. **Define `gridTemplateColumns` at module
   scope.** The React Compiler will usually hoist it — module scope is the fix that does not depend on
   that. (Manual memoization is forbidden in this repo, so this is the available lever.)
10. **Duplicate `urlKey`s.** Making `urlKey` required prevents *accidental* sharing but not two call
    sites passing the same string. Add a dev-mode duplicate-key warning in `use-table-pagination.ts`,
    and state the constraint in the FR-028 knowledge note.

## Deliberately not doing

Each argued and then cut by the refactor-friendly framing:

- Making `RelationshipTable` accept an injected query — the most visible rough edge, the most
  expensive, and no FR needs it.
- Relaxing `DataTable`'s generic or `getRowId`.
- Migrating the three legacy `Pagination` call sites (FR-017 and spec Out of Scope).
- Converting `BranchesTable` off `InfiniteScroll`, or fixing `infinite-scroll.tsx`'s observer-root
  problem — we avoid infinite scroll entirely.
- Building the drift provider or a fifth card state. Build the **column slot**, not the machinery;
  the fifth state is IFC-3101's to specify.
- A dedicated repository route shell — IFC-3150 adds its tab as a sibling route the router already
  supports.
- Renaming `sync_status` to "Import status" (design canvas) — out of scope in the PRD; labels follow
  the schema (FR-005).

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| **A second pagination mechanism** alongside the legacy `Pagination` / `usePagination` | The legacy component is hard-wired to a single global `QSP.PAGINATION` key, so two paginated tables on one route move together — which this card would immediately break (FR-011). It also assumes the table is the page-level scroll area, which is false inside a card (FR-011a). | Generalising the legacy component in place would put this feature's regression risk on **three unrelated pages that have no tests at all**. The duplication is temporary and signposted: FR-028's knowledge note names the new component as the intended successor, and migrating the three call sites is tracked as follow-on work. |
| **A new shared primitive `CommitHash`** | Nothing in the app renders a monospace, truncating, short-form hash; the only `font-mono` usage is unrelated and there is no short-hash helper. | Inlining the mono/truncate/short-form logic would put the hash-shortening rule at the call site, which is the thing that drifts once a second caller appears. It composes `CopyToClipboardButton` rather than reimplementing copying. **Stated honestly**: Principle VII's "two existing callers" bar is **not** met — the card's table cells are the only call site, and the `copyable` branch exists for the full-hash presentation the design places in the details card, which renders through `ObjectDataDisplay` and does not reach this primitive. Accepted as a small, self-contained primitive whose alternative is the rule inlined in a cell renderer. |
| **Two `ObjectDataDisplay` instances** mounting two metadata `Sheet`s, inside a new local `RepositoryDetailsCard` (D1) | The alternative edits a file every object-detail page depends on. `ObjectDetailsCard` itself cannot be reused — it hardcodes its title and test id. | See D1 — the refactor framing's own risk register ranked that edit as its highest-blast-radius item. A duplicated closed dialog in the tree is not a behaviour change, and the local wrapper is ~15 lines of `Card` + `CardHeader` around the genuinely reusable `ObjectDataDisplay`. |
| **A card-scoped `ErrorBoundary`** around the branches card | FR-024 as written holds only for **query** failures: the use case's throw lands in react-query's `isError` and renders in place. A **render-time** failure — a mapper crash on an unexpected preview-window shape, or `DropdownCell` handed a null — propagates to `error-boundary-router` and blanks the whole route. The app has no card-scoped boundary, and the nullable-field risk is the one expected to bite during the preview window. | Relying on the mapper's guards alone makes FR-024 true only for the failure kind that was anticipated. ~15 lines makes it true for all of them. |
| **No E2E for `CoreReadOnlyRepository`** (FR-027) | The e2e data set contains no `CoreReadOnlyRepository`; the fixture is shared with IFC-3153 and is not budgeted here. The kind differs from the read-write one only by title, row set and one column — all presentation over the same query, with the row-set rule enforced server-side. | Adding the fixture here duplicates work IFC-3153 owns. Component tests cover the three differences. Recorded rather than silent, and flagged to IFC-3153 so the fixture owner inherits the gap. |

## Phase 0 — Research

**Status: complete.** [research.md](research.md) covers where repositories live in the frontend, why
`RelationshipTable` cannot be reused, why infinite scroll breaks inside a card, why the existing
pagination is not extended, the gql.tada (not codegen-document) approach, the attribute `branch`
support metadata, the testing patterns a new test must follow, and the backend contract summary.

**Four of its claims are superseded** by [Corrections carried forward](#corrections-carried-forward).
`research.md` is left as written — the corrections are recorded here rather than by rewriting history
in a document three plan framings were run against.

**No `NEEDS CLARIFICATION` remain.** The spec's Clarifications section settled six questions on
2026-09-10 (new paging component; page controls over "load more"; the page size; "On this branch"
title with a branch-name caption; placement below the details card and above the branches card;
branch name links, no row-action menu). The page-size answer was revised on 2026-09-16 to **a single
fixed size of 10 with no page-size selector** — no user story asks for a page-size control, and one
size makes FR-011b's height guarantee unconditional. The Performance Goals line above records the
same figure.

## Phase 1 — Design & Contracts

**Status: complete.** Generated alongside this plan:

- **[data-model.md](data-model.md)** — the three key entities (repository branch status row,
  branch-support declaration, page window), their fields, nullability, and the mapper's guards.
- **[contracts/repository-branch-status-ui.md](contracts/repository-branch-status-ui.md)** — the
  UI-side contract: the exact gql.tada variable set (and the three variables deliberately **not**
  declared), the typed error shape, and the four card states. The backend contract itself is frozen
  and lives at `dev/specs/infp-671-cross-branch-repo-status/contracts/`.
- **[quickstart.md](quickstart.md)** — how to run and validate this feature locally.

**Agent context update: deliberately skipped.** `CLAUDE.md` in this repository is hand-maintained and
delegates to `AGENTS.md`; it carries no `<!-- SPECKIT START -->` / `<!-- SPECKIT END -->` markers, so
there is no managed block to refresh. Running `/speckit-agent-context-update` here would clobber a
hand-written file. This is a standing project decision, not a one-off omission.

## Open questions — carried, not invented

Recorded here and carried into the PR body. None blocks implementation; each has a named owner who is
not the implementer.

| # | Question | Owner | Current working assumption |
|---|---|---|---|
| Q1 | The divergence register above, D-a in particular — two cards where the canvas ruled for one | Designer, via T094 on IFC-3101 | Build two cards per the 2026-09-10 clarification. Raise before work unit 1 starts |
| Q2 | If the epic branch is released before IFC-3127 lands, users see fabricated commit hashes and sync statuses with nothing marking them as placeholders. Gate the card, add a preview banner, or accept? | Epic owner (IFC-3104 / INFP-671) | No banner — the fabricated values reach no user while this lives on the epic branch alongside IFC-3127 |
| Q3 | IFC-3131 is this card's stated manual-validation gate, but its instructions are written by IFC-3132, which has not landed. Is the gate real? | Epic owner | [quickstart.md](quickstart.md)'s validation scenarios serve as the acceptance checklist. They are near-verbatim what IFC-3131 needs, so they can be lifted into it |
| Q4 | Four user-facing state strings (loading, empty, denied, failed) are unpinned, including the "all branches have Git sync disabled" case. The canvas draws none of them | Product + designer | Strings are pinned in the [UI contract](contracts/repository-branch-status-ui.md) §4 so copy can be reviewed without reading code |
| Q5 | Dropping `Last import` makes `Syncing` indistinguishable from stuck, and with no `import_error` and no task-log link a user reaches "branch X is in error" and stops | Epic IFC-3101 | Accepted for this slice. The dead-end is real and closes when the drift column and import-error surface land |
| Q6 | **IFC-3130's Jira description is factually wrong** about the three preview arguments. It says they are "accepted but ignored" so a filter "appears to do nothing"; the frozen SDL and the resolver both **reject** them with a `ValidationError`. The ticket text needs editing — this is not a design choice left open | IFC-3130's ticket owner | Build against the contract: the arguments are rejected, and the gql.tada document declares none of them, so none is ever sent. No code changes when the ticket is corrected |

## Phase 2 — Tasks

**Status: complete.** [tasks.md](tasks.md) derives from the work units, dependency graph and FR
mapping above, and is the single record of what remains to be built.
