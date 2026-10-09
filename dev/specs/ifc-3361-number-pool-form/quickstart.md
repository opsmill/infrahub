# Quickstart: validate the number pool forms

## Prerequisites

- A running Infrahub stack on this branch (`uv run invoke dev.start`), with the demo schema loaded.
- Frontend dev server: `cd frontend/app && pnpm dev`.

## Automated checks

```bash
cd frontend/app && pnpm vitest run src/entities/resource-manager
cd frontend && node_modules/.bin/biome ci .
cd frontend/app && pnpm knip && pnpm exec betterer ci
uv run pytest -c tests/e2e/pytest.ini tests/e2e/resource-manager/test_number_pool.py tests/e2e/object-template/test_template_with_number_pool.py tests/e2e/tutorial/guides/test_resource_manager_guide.py
```

## Manual scenarios (spec references)

1. **Create with several ranges** (Story 1): Resource manager → add a Number Pool; choose a node kind and number attribute, add 100–199 weight 10 and 300–399 with no weight; save. Expected: the pool lists both ranges.
2. **Row validation** (FR-003): enter 200–100, then 100–199 and 150–250. Expected: errors on the rows after leaving the field; save disabled.
3. **Clip hint** (FR-004): for an attribute limited to 1–4094, enter 0–5000. Expected: hint "Clipped to 1 – 4,094 …"; save allowed.
4. **Scope** (Story 3): open the scope picker; required fields selectable, optional/List/JSON/cardinality-many fields and the pool's attribute disabled with a reason; change the node kind and check the scope clears.
5. **Edit** (Story 2): open the pool's edit form; node kind, attribute and scope shown as text and badges in the same layout as create; remove a range, add one, change a weight; save.
6. **Refused swap** (FR-009): on a pool with 1–10 and 11–20, edit to 11–20 and 1–10 and save. Expected: one inline message, form open, rows as typed; save again applies only what remains.
7. **Schema pool** (Story 4): open the pool created for `service_identifier` (InfraService); ranges shown as text with the note; name and description editable.
