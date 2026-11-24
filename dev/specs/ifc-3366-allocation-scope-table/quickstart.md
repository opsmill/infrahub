# Quickstart: validate the allocation scope table

## Prerequisites

- A running Infrahub with the backend from `stable` at or after the commit that serves the number pool queries from the database (#11056)
- The frontend dev server: `cd frontend/app && pnpm dev`
- A schema with a node that has a Number attribute and a required, cardinality-one relationship. The base schema's `InfraInterfaceL3.speed` and its `device` relationship work.

## Set up data

1. In the web interface, create a number pool:
   - **Allocates to**: `InfraInterfaceL3`, attribute `speed`
   - **Scoped by**: `Device`
   - **Ranges**: 100–199 with weight 10, and 300–399
2. Create three L3 interfaces on device A and one on device B, each taking `speed` from that pool.

## Scenarios

| # | Do | Expect | Covers |
|---|---|---|---|
| 1 | Open the pool | The header ends with "scoped by Device". The table lists two allocation scopes: device A first with 3 used, device B second with 1 used. | FR-001, FR-002, FR-003, FR-006, FR-011, SC-001, SC-002 |
| 2 | Type part of device B's name in the search field | Only device B's row remains. The URL contains `allocation_scope_search`. | FR-005 |
| 3 | Clear the search and sort by Device | The rows are in name order. | FR-006 |
| 4 | Select device A's row | The URL contains `allocation_scope=[…]`. The summary shows "Device: <device A>". The ranges card shows 3 used in 100–199. The allocations card lists the 3 numbers. | FR-007, FR-008, FR-009, FR-010, SC-004 |
| 5 | Select range 100–199, then filter allocations by source | The URL keeps `allocation_scope`. The list stays within device A. | FR-009 |
| 6 | Copy the URL and open it in a new tab | The same page appears. | FR-007 |
| 7 | From the table with a search typed, open a row, then press the browser's Back button | The table shows the same search and sort. Then open the row again and select "All allocation scopes": the table appears. | FR-010, R6 |
| 8 | Replace the URL value with `[]`, then with `nonsense` | Both show "This link does not match the pool's allocation scope (Device)" and the link back. | Edge case: URL does not match |
| 9 | Delete device B's interface, then open device B's old URL | The page shows 0 used and no allocations. The summary shows the raw value. | Edge case: all numbers released |
| 10 | Create a second scoped pool with no allocations and open it | "No numbers allocated yet. An allocation scope appears here once an object in it holds a number from this pool." | Edge case: empty pool |
| 11 | Open an unscoped pool | The page looks and behaves as before. | FR-013 |

## Width check (FR-014)

Create a pool scoped by four or more fields, or narrow the browser window. Check that:

- the table scrolls horizontally
- the usage column stays on the right edge while it scrolls
- the header stays at the top while the table scrolls down

## Volume check (SC-003)

Run the component test for the allocation scopes card with 1,000 generated allocation scopes (`tests/fake/number-pool.ts`). Check that:

- the first rows are visible
- a search narrows the list
- the last row is reachable by scrolling

The table draws every row. Pools much larger than 1,000 allocation scopes are slow until virtualization is added (spec, Out of Scope).

## Automated checks

```bash
cd frontend/app && pnpm test -- src/entities/resource-manager src/pages/resource-manager
cd frontend && pnpm exec biome ci .
cd frontend/app && pnpm knip && pnpm exec betterer ci
uv run pytest -c tests/e2e/pytest.ini tests/e2e/resource-manager/test_number_pool.py -s --pdb
uv run invoke docs.lint
```
