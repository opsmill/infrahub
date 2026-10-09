# Quickstart: validate the number pool body

**Spec**: [spec.md](./spec.md) | **Contracts**: [contracts/](./contracts/) | **Data model**: [data-model.md](./data-model.md)

## Prerequisites

- Branch `number-pool-body-ifc-3362`, with the branch of [PR #10932](https://github.com/opsmill/infrahub/pull/10932) merged in and the frontend types regenerated:

  ```bash
  cd frontend/app && pnpm codegen
  ```

  Check: `grep -c InfrahubNumberPoolAllocations ../../schema/schema.graphql` prints at least 1.
- Frontend dependencies installed (`cd frontend/app && pnpm install`).

## 1. Automated checks (the gate for this PR)

```bash
cd frontend/app && pnpm test -- resource-manager                   # unit and component tests of the body
cd frontend && pnpm exec biome ci .
cd frontend/app && pnpm knip
cd frontend/app && pnpm exec betterer ci
```

Expected: every test passes, and the three checks report no new problems.

What the component tests prove, mapped to the spec:

| Scenario (spec) | Test | Expected |
|---|---|---|
| Story 1, scenario 1 | Ranges card with two ranges, weights 0 and 10 | Options in order "All ranges", "1 – 50", "51 – 100"; "All ranges" is `aria-selected` |
| Story 1, scenario 2 | Page at `/ranges/<id of 1–50>` | That option is selected; the table has no Range column; the hook is called with that `rangeId` |
| Story 1, scenario 3 | Row on branch `b1` | Holder link `href` contains `branch=b1` |
| Default-branch row | Row on the default branch | Holder link has no `branch` parameter; no branch icon |
| Story 1, scenario 4 | "All ranges", two ranges | Range column shows "1 – 50" for a row in that range |
| Story 2, scenario 2 | Page at `/ranges/unknown` | "This range is not part of the pool" and a link "All ranges"; no option selected; allocations hook not enabled |
| Story 3, scenario 1 | Focus the listbox, press ArrowDown, then Enter | Address changes to the next range |
| FR-012 | 250 fake rows, scroll to the end | `fetchNextPage` is called; the rows of the next page render |
| Edge: no ranges | `ranges: []`, `pool_type` User, then Schema | "No ranges", followed by "Edit the pool to add one", then by "Add one in the schema" |
| Edge: no numbers | `count: 0`, all ranges, then one range | "No allocations yet", then "No allocations in 1 – 50" |
| FR-005 rule | `sortRangesByFillOrder` unit test | Weight first, then start, then end; input unchanged |
| FR-006 | Usage bar with `used 30`, `size 50` | Percentage "60%"; tooltip "30 of 50" |

## 2. Manual check of the queries (fake data from #10932)

The full page cannot load the fake pool, because the header reads the pool from the database (research R1). Check the two documents in the GraphQL sandbox (`/graphql`) instead:

1. Run `GET_NUMBER_POOL_UTILIZATION` (in [contracts/graphql-queries.md](./contracts/graphql-queries.md)) with `poolId: "mock-unscoped"`.
   - **Expected:** two ranges, 1–50 with weight 10 and 51–100 with weight 0. The pool reports 3 used, and the excluded value 40 is not counted in `size`.
2. Run `GET_NUMBER_POOL_ALLOCATIONS` with `poolId: "mock-unscoped"`, `offset: 0`, `limit: 100`.
   - **Expected:** 3 rows: 1 on `main`, 7 on `branch1`, 51 on `main`.
3. Run the same query with `rangeId` set to the ID of 1–50.
   - **Expected:** 2 rows, 1 and 7.

## 3. Manual check of the page on a real pool (before the database reads)

1. `uv run invoke dev.start`, then open any number pool at `/resource-manager/<id>`.
2. **Expected:** the header renders unchanged. The body shows the backend's refusal for a scoped pool, because #10932 answers every real pool ID with the scoped fake pool. The old properties card, the Resources card and the "View" links are gone.
3. Open an IP prefix pool. **Expected:** its page is unchanged, including the `resources/<id>` view.

## 4. After IFC-3347 reads the database (tracked separately)

The end-to-end test for the body, written in its own ticket, goes in `tests/e2e/resource-manager/test_number_pool.py`. It covers:

- a pool with two ranges
- selecting a range and checking the address and the rows
- opening a holder node

It must pass before `feature-number-pools-1.12` merges into `stable`. Run it with:

```bash
uv run pytest -c tests/e2e/pytest.ini tests/e2e/resource-manager/test_number_pool.py -s --pdb
```
