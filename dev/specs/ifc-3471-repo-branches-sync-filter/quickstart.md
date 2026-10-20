# Quickstart: validate the Sync Status filter

## Prerequisites

- Backend and frontend running from the worktree (`uv run invoke dev.start`, `pnpm dev` in `frontend/app`), logged in as `admin`.
- A read-write repository connected from Integrations, Git Repositories, with at least three branches that have Sync with Git turned on.
- One branch with Sync Status "Import Error", for example by pushing a schema file with an error to its Git branch, or with the SDK as in `tests/e2e/repository/test_repository_sync_status.py`.

## Scenarios

1. **Filter picker** (User Story 1): open the repository's page, open Filter in the Branches section, choose Sync Status. Expect five labelled values. Choose Import Error and apply. Expect only the failing branch, and `1` next to the "Branches" heading.
2. **Tag**: expect the tag `Sync Status contains Import Error`. Add a Status filter Open; expect `Status contains OPEN` next to it.
3. **Column header** (User Story 2): remove the filters, open the Sync Status column header. Expect a Filter action and no sort action. Apply Import Error; expect the same rows, tag and URL as in scenario 1.
4. **Combine, page, share** (User Story 3): with a name search, a Status filter and the Sync Status filter, reload the page; expect all three restored. Change the filter while on page 2; expect page 1.
5. **Invalid URL value**: edit the URL so the stored sync status value is `bogus`; expect the unfiltered list.
6. **Read-only repository**: repeat scenario 1 on a read-only repository's "Infrahub branches" section.
7. **Other tables unchanged**: on any object list with a Dropdown attribute filter, expect the tag to show the stored value as before.

## Automated checks

```bash
cd frontend/app
pnpm vitest run src/entities/repository src/entities/nodes/filters
cd .. && node_modules/.bin/biome ci . && cd app && pnpm knip && pnpm exec betterer ci && pnpm test
cd ../.. && uv run pytest -c tests/e2e/pytest.ini tests/e2e/repository/test_repository_branches_sync_filter.py -s --pdb
```
