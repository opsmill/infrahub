# Quickstart: Validate the number pool create and edit form

## Prerequisites

- Python and frontend dependencies installed (`uv sync --all-groups`, then `cd frontend/app && pnpm install`).
- Docker running, for the e2e stack.

## Automated checks

Run from the repository root.

| What | Command | Expected |
|---|---|---|
| Domain rules and form unit and component tests | `cd frontend/app && pnpm test src/entities/resource-manager src/entities/nodes/object` | All pass |
| Frontend CI gate | `cd frontend && pnpm exec biome ci .`, then `cd frontend/app && pnpm knip && pnpm exec betterer ci` | No errors, no unused exports left by the removed prototype |
| Number pool e2e | `uv run pytest -c tests/e2e/pytest.ini tests/e2e/resource-manager/test_number_pool.py -s --pdb` | All pass, including the P1 and P2 scenarios |
| Template e2e that creates a pool | `uv run pytest -c tests/e2e/pytest.ini tests/e2e/object-template/test_template_with_number_pool.py -s --pdb` | All pass |
| Docs | `uv run invoke docs.lint` | No errors |

## Manual walk-through

Start the stack (`uv run invoke dev.start`) and the frontend dev server (`cd frontend/app && pnpm dev`).

### Create a scoped pool (P1)

1. In the object list for Number Pool, choose **Add**.
2. Pick the node `InfraSubinterface`. The Attribute and "Scoped by" rows appear.
3. Pick the attribute `unit_id`. Its limits and "Unique", when it applies, show in the list.
4. In "Scoped by", add `Device`. Optional fields and many-cardinality relationships are not listed.
5. Add ranges 100–199 with weight 10, and 300–399 with no weight. The rows keep that order.
6. Save.

Expected:
- The sheet closes.
- Opening Edit shows both ranges with their weights, and "Scoped by: Device" as read-only text.
- The details page cannot show a scoped pool's ranges yet; it shows the utilization query's refusal.

### Browser checks

| Action | Expected |
|---|---|
| Enter 100–199 and 150–250, then save | Both rows show an overlap error, and nothing is sent |
| Pick a unique attribute, such as `InfraAutonomousSystem.asn` | "Scoped by" is disabled with "asn is unique, so the pool has one sequence", and any picked scope is cleared |
| Remove every range | "No ranges. The pool can't hand out numbers until you add one." shows, and Save still works |

### Backend refusal

Enter a range beyond the attribute's limits, for example 4000–5000 on `vlan_id`, then save.

Expected:
- The sheet stays open with every value kept.
- The backend's message shows once, in the alert above the footer.
- No global toast appears.

### Edit ranges (P2)

1. On a pool's details page, choose **Edit**.
2. Change 100–199 to 100–299, and add 500–599.
3. Save.

Expected:
- Reopening Edit shows 100–299 and 500–599. On an unscoped pool, the details page's ranges card shows them too.
- Numbers already assigned stay assigned.
- A range saved with no weight still has no weight after an edit that leaves it unchanged.
