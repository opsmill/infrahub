# Quickstart: validate the branch details repositories and tasks

**Feature**: [spec.md](./spec.md) | Contracts: [graphql-queries.md](./contracts/graphql-queries.md), [ui-components.md](./contracts/ui-components.md)

## Prerequisites

- Worktree on `ple-branch-details-repos-infp-671`. Frontend deps installed (`cd frontend/app && pnpm install`; don't run `pnpm setup` in this worktree, the submodules aren't initialised).
- A running Infrahub with the task manager (`uv run invoke dev.start` or the demo stack), and at least one read-write and one read-only repository connected.
- `cd frontend/app && pnpm dev`, then open `http://localhost:8080`.

## Seed

1. Create branch `bdr-demo` with Sync with Git on.
2. Break an import on it: push a commit to the read-write repository's `bdr-demo` Git branch with an invalid `.infrahub.yml` (for example a duplicated transform name), then wait for the periodic sync, or run "Import current commit" from the repository page on `bdr-demo`.
3. Point a second repository at an unreachable location or wrong credentials so its `operational_status` becomes `error-cred`/`error-connection`.
4. Run Validate on the branch (creates a branch task).

## Scenarios

| # | Do | Expect | Spec |
|---|---|---|---|
| 1 | Open `/branches/bdr-demo` | Header: name, copy (screen reader: "Copy branch name"), metadata, status badge, description, Refresh at the right. Notice above it. Tabs, then the body card. | FR-001–005 |
| 2 | Look at the Details tab | Details card → Git repositories → the five buttons → Tasks. | FR-005 |
| 3 | Git repositories card | Rows in name order (2026-10-02: failing ones no longer first; their bands are); the broken repository has the schema's "Import Error" pill; the unreachable one a warning icon; the read-only one has its tag; commits in monospace. | FR-010–013 |
| 4 | Bands | Red band "<repo> — import failed" with the raw error line; "View task log" opens `/tasks/<id>` for that import. Amber band for the unreachable one with "Open repository". | FR-021–023 |
| 5 | Click Merge | Merges as today; nothing on the button changes because of the failures. | FR-030–031 |
| 6 | Tasks card | Validate and import tasks, newest first; count and "N failed" in the header; a title opens its task page. | FR-040–042 |
| 7 | Refresh | Button busy; repositories, bands and tasks refetch (network tab: Q1–Q4). | FR-004 |
| 8 | Theme switch to dark | Bands, pills, tables readable; no light-only colours. | FR-050 |
| 9 | Remove view permission on repositories for a test user, log in as them | Card shows the no-access message; tasks still list. | FR-018 |
| 10 | Create `bdr-nosync` with Sync with Git off | Only read-only repositories, or "Not synchronised with Git". | FR-010, FR-019 |
| 11 | Open the default branch | Details card only, no tabs, no actions, no tasks. | FR-005 |

Pagination (10/11 boundaries, fixed height, URL `repositories_page`/`tasks_page`, invalid page values) and the "3 bands + Show all" rule are covered by component tests with fixtures; to see them live, connect 11+ repositories or use the fixtures in Storybook-less mode via the component tests.

## Automated checks (before pushing)

```bash
cd frontend/app && pnpm exec biome ci .
cd frontend/app && pnpm knip
cd frontend/app && pnpm exec betterer ci
cd frontend/app && pnpm test
uv run pytest -c tests/e2e/pytest.ini tests/e2e/branches/test_branch_details.py   # with the e2e stack up, see dev/guides/frontend/writing-e2e-tests.md
```

## R2 verification (import task lookup)

For each import path (initial add, "Import current commit" = `git-repository-import-object`, periodic sync, read-only pull), put the repository in Import Error on `bdr-demo` and record whether the band shows the error line or the not-found fallback. Record the result in the PR description and on the follow-up backend ticket.
