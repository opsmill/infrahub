# Quickstart: validate the number pool field tabs

## Prerequisites

- Branch `ple-number-pool-field-ifc-3371` (based on `feature-number-pools-1.12`, which carries the
  backend attach and detach behaviour).
- A running instance: `uv run invoke dev.start`, then `cd frontend/app && pnpm dev`.
- A number pool for a kind with a Number attribute, for example `InfraInterfaceL3.l3_mtu`, or the
  pools created by `tests/e2e/resource-manager/test_number_pool.py`.

## Automated checks

```bash
cd frontend/app && pnpm vitest run src/shared/components/form
uv run pytest -c tests/e2e/pytest.ini tests/e2e/resource-manager/test_number_pool.py -s --pdb
```

## Manual scenarios

Walk the rows of [contracts/form-submission.md](contracts/form-submission.md). For each row, open
the browser network panel and compare the mutation payload with the "Sent" column, then open the
pool's details page and check that the number is listed (or not) as expected.

Minimum walk:

1. C2 — create with a pool and no number: the node gets the next free number.
2. C3 — create with a pool and a number: the node holds it, and the pool lists it.
3. E4 — reopen that node: the pool tab is active, with the pool and the number shown. Save: no
   mutation is sent for the field.
4. E9 — switch to the Value tab, type a number, save: the pool no longer lists the node.
5. C1 — create with a number in the Value tab: no pool lists it.
