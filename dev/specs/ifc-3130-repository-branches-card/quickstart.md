# Quickstart — validating the repository branches card

How to run and validate IFC-3130 locally. A validation guide, not an implementation guide:
implementation detail lives in [plan.md](plan.md) and [tasks.md](tasks.md).

---

## Prerequisites

This branch sits on **`cross-branch-repo-status-infp-671`**, not on `develop` or `stable`. IFC-3126
is already merged into that base, so the schema and the regenerated frontend types are present.

```bash
cd frontend/app && pnpm setup    # init submodules + install (first time only)
cd frontend/app && pnpm install  # dependencies only, submodules already initialised
```

**Codegen must produce zero drift.** The base branch committed both `schema/schema.graphql` and the
regenerated frontend types, so this must leave the tree clean:

```bash
cd frontend/app && pnpm codegen && git diff --exit-code src/shared/api/graphql/generated/
```

A non-empty diff means the base moved under you — rebase before going further, do not commit the
regenerated output as though it were this feature's.

---

## The preview window — what you will actually see

IFC-3127 has not merged. The backend serves **real** rows, paging, ordering and permission denials,
but the four attribute values are **fabricated from the branch name**.

They are stable across reloads and every dropdown value appears, so the card is fully buildable and
screenshottable. What you must **not** do is let anything depend on the values being real (SC-008) —
when IFC-3127 lands, the values become real with no contract change and no code change here.

Three arguments — `sync_status__value`, `internal_status__value`, `own_values_only` — are **rejected
with a `ValidationError`** today. IFC-3130's Jira description says the opposite, "accepted but
ignored"; the ticket is wrong and needs editing by its owner (plan.md open question Q6). This feature
never sends them: they are not declared in the gql.tada document at all. See
[the UI contract](contracts/repository-branch-status-ui.md).

**Who sees the fabricated values**: you do, running the card locally, which is exactly what makes it
buildable and screenshottable today. **No end user does**, as long as this stays on the
`cross-branch-repo-status-infp-671` epic branch, where IFC-3127 also lands — which is why there is no
preview banner. If the epic branch is ever released with IFC-3127 outstanding, revisit it — see open
question Q2 in [plan.md](plan.md).

---

## Run it

```bash
cd frontend/app && pnpm dev
```

Then open a repository:

| What | Where |
|---|---|
| Read-write repository | Git Repositories → any `CoreRepository` (the demo set has `infrastructure-templates`) |
| Read-only repository | Read-Only Repositories → any `CoreReadOnlyRepository` |

---

## Manual validation scenarios

Each maps to a user story in [spec.md](spec.md). These are the checks a reviewer can run by hand;
the automated equivalents are in the test suites below.

### US1 — See every branch's status without switching branch

1. Open a repository with more branches than one page holds.
2. **Expect** a `Branches` card listing one row per in-scope branch, each with its own sync status
   and imported commit — the failing branch showing *its own* status, not the default branch's.
3. **Expect** the count pill beside the title to state the total across **all** branches, not the
   number of rows on screen.
4. Move to page 2. **Expect** different rows, and the previous page's rows gone (replaced, not
   accumulated).
5. Reload. **Expect** to land on the same page — the position is in the URL.
6. Copy the URL into a new tab. **Expect** the same page.

**What would be wrong**: a count equal to the row count; rows accumulating as you page; the position
lost on reload.

### US2 — Tell repository-wide values from branch-scoped ones

1. On the same page, look above the branches card.
2. **Expect two** details cards: repository-wide attributes first, then `On this branch` with the
   branch name as a caption beneath the title, then the branches card (FR-018a — that document order
   exactly).
3. Switch branch with the branch picker. **Expect** only the second card's values and its stated
   branch to change. The first card must not move.
4. Open any **non-repository** object's detail page. **Expect** exactly one details card, unchanged
   from today (FR-020).

**What would be wrong**: the split leaking onto a non-repository kind; the repository-wide card's
values changing with the branch; an empty titled box where a partition has no attributes (FR-022).

### US3 — Isolate a branch in a large repository

1. Type a fragment of a known branch name into the card's search.
2. **Expect** only matching branches listed, **and the stated total to narrow with them** — that is
   the tell that the filter was applied server-side, before the page boundary.
3. With a filter matching more rows than one page, go to page 2. **Expect** the filter still applied.
4. Change the filter. **Expect** to be returned to page 1 (FR-014).
5. Filter to something matching nothing. **Expect** an explicit "nothing matched", not a spinner and
   not a blank frame.
6. Open the filter button and pick **Status**. **Expect** the five statuses a repository's branches
   can actually carry, and neither `MERGED` nor `DELETING`.
7. Open the order button. **Expect** exactly two fields — created and updated — and no branch name,
   sync status, commit or ref, because the contract cannot order by them (FR-012a).
8. Order by updated, descending, from page 2. **Expect** to land on page 1 of the reordered set, and
   **no** timestamp column to appear (FR-006).

**What would be wrong**: rows narrowing while the total stays put — that means the filtering happened
client-side, on rows already received, which FR-015 forbids.

### States

| To see | Do |
|---|---|
| Loading | Throttle the network. The card must occupy a full page of space. On a repository with **at least one full page** of branches, nothing may jump when the rows arrive; on a smaller set the card shrinks to the rows returned, which is expected (FR-023) |
| Empty | A `CoreRepository` all of whose branches have Git sync disabled. The message is per kind: a `CoreReadOnlyRepository` with no branches must **not** mention Git synchronisation, because its row set is every branch |
| Denied | A user without view permission covering non-default branches — **must not** read as "no branches" |
| Failed | Stop the backend; **the rest of the page, both details cards included, must still render** (FR-024) |

### Read-only repository

**Expect** the title `Infrahub branches` (not `Branches`), a `Ref` column, and **every** branch listed
— including those with Git synchronisation disabled, which are excluded only on a read-write
repository.

### Accessibility (FR-025)

Every chip, state and the default-branch marker must be findable **by accessible name alone**, with
colour disregarded. A quick check: tab through the card and confirm the default row announces its
marker, and that each status chip reads its label.

---

## Automated validation

### Unit and component tests

```bash
cd frontend/app && pnpm test
```

Vitest runs in **browser mode**. Coverage to expect:

| Level | What |
|---|---|
| Unit | `table-pagination.ts` arithmetic; `use-table-pagination.ts` key scoping (two probes, different keys, one unmoved after the other pages); `partition-fields-by-branch-support.ts` — **one case per `BranchSupportType` value (`aware`, `agnostic`, `local`) plus the node-level fallback**; the use case's error mapping over a raw `extensions` payload |
| Component | Every FR carrying a component-test verification — both card kinds, the four states, the paging requests, the two details cards, the document order, and **each relationship label appearing exactly once on the page**. The filter requests land with work unit 5b, still outstanding |

**Two rules that make or break this suite:**

1. **Mock at `…/api/get-repository-branch-status-from-api`, never the hook.** Every request assertion
   must be paired *in the same test* with a rendered-output assertion drawn from a **different
   payload**. Use `expectServerDrivenChange(...)` from `tests/helpers/` — every argument is required,
   so omitting the rendered-output half is a type error. Reading `apiMock.mock.calls[...]` directly
   in a card test file compiles and defeats the pairing; keeping it out of those files is on the
   reviewer. See [the UI contract](contracts/repository-branch-status-ui.md).
2. **Reset `window.history` in `afterEach`.** `tests/components/render.tsx` uses `BrowserRouter`, so
   nuqs writes to the real `window.location`; without the reset the paging tests become
   order-dependent — passing alone, failing in a full run. Do **not** reach for `renderAt` from
   `link-tab.test.tsx`: it is private and it overrides the whole wrapper, dropping `NuqsAdapter`,
   jotai, `QueryClient` and `BranchContext`.

### FR-017 — the zero-diff guarantee

The three legacy paginated pages have no tests, so the honest guarantee is that their paging is not
touched at all. Run from the **repository root** — the pathspecs are repo-root relative, and a
pathspec that matches nothing exits 0:

```bash
git diff --exit-code origin/cross-branch-repo-status-infp-671 -- \
  frontend/app/src/shared/components/ui/pagination.tsx \
  frontend/app/src/shared/hooks/usePagination.ts
```

Any output is a failure.

> **Note the `ui/` segment.** `git diff --exit-code` with a pathspec matching **nothing exits 0**, so
> a wrong path passes unconditionally. If you change these paths, verify the command fails when it
> should by touching one of the files deliberately. This belongs in CI (a step in `frontend-lint`,
> diffing against the merge base) rather than in a human checklist.

### End-to-end (FR-026) — pending

> `tests/e2e/repository/test_repository_branches_card.py` is work unit 8, which
> [plan.md](plan.md)'s delivery status still records as outstanding. Until the file lands the command
> below fails on a missing path; it is the invocation to use once it does, and the requirements after
> it are what the test must satisfy.

Run from the **repository root**, not `frontend/app`, and against a **locally built** image — with
`INFRAHUB_TESTING_IMAGE_VER` unset and no `INFRAHUB_ADDRESS`, the suite boots its testcontainers
stack from the published image and exercises released code instead of this branch:

```bash
uv run invoke dev.build                      # once per backend change

INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini \
  tests/e2e/repository/test_repository_branches_card.py -m shard_branches_repo
```

The test must carry a **module-level `pytestmark`** with `shard_branches_repo` — `conftest.py`'s
collection hook fails CI for any file with no shard marker or more than one, and it runs *before* the
`-m` filter, so every shard job validates the full collection.

It runs against the **`demo_edge_repo`** fixture and must assert rendered row data, a page change and
a name filter.

> **Poll the count badge by its own accessible name; never assert the total once.** Ten
> `sync_with_git=True` branches each trigger real git-worker branch creation, and the card can render
> before all rows exist — a single assertion races the worker (risk 6).

### The full CI gate

`pnpm biome:fix` alone is **not** the gate. All four run independently in CI:

```bash
cd frontend/app && pnpm exec biome ci .    # format + lint
cd frontend/app && pnpm knip               # unused exports/files/deps
cd frontend/app && pnpm exec betterer ci   # TypeScript-regression gate (NOT plain tsc)
cd frontend/app && pnpm test               # vitest, browser mode
```

`frontend-lint` has **no path filter** — it runs on every PR, including a markdown-only one. Only
`frontend-tests` is path-gated.

---

## Definition of done

- [ ] All three user stories validate by hand, per kind
- [ ] `pnpm test` green; every request assertion paired with a rendered-output assertion
- [ ] The zero-diff check on `pagination.tsx` and `usePagination.ts` produces no output
- [ ] The e2e test passes in the `shard_branches_repo` shard
- [ ] `pnpm codegen` leaves the generated directory clean
- [ ] All four CI gate commands green
- [ ] `dev/knowledge/frontend/table-pagination.md` exists and names both components (FR-028)
- [ ] `CommitHash` added to `dev/knowledge/frontend/shared-components.md` and justified in the PR body
- [ ] A Towncrier changelog fragment exists in `changelog/`
- [ ] The divergence register in [plan.md](plan.md) is raised in full on **T094 in IFC-3101**
