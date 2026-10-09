# Quickstart: validate the number pool header

## Automated checks

From `frontend/app`:

```bash
pnpm test src/entities/resource-manager/api/number-pool.mappers.test.ts
pnpm test src/entities/resource-manager/domain/use-cases/get-number-pool.test.ts
pnpm test src/entities/resource-manager/ui/number-pool
pnpm test src/pages/resource-manager/number-pool-details.test.tsx
```

After adding `GET_NUMBER_POOL`, regenerate the gql.tada cache and commit it:

```bash
cd frontend/app && pnpm codegen:graphql
```

Before pushing, run the full frontend gate described in `frontend/app/AGENTS.md`:

```bash
cd frontend && pnpm exec biome ci .
cd frontend/app && pnpm knip && pnpm exec betterer ci && pnpm test
```

End-to-end test, from the repository root, after `uv run invoke dev.build`:

```bash
INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e/resource-manager/test_number_pool.py -s --pdb
```

Expected result: every test in `TestNumberPool` passes, including the new header assertions for:

- the schema-created pool `InfraService.service_identifier`
- the user-created pool "number pool test for generic"

Regression checks: `tests/e2e/resource-manager/test_resource_pool.py` and `tests/e2e/test_breadcrumb.py` pass unchanged (SC-004).

## Manual check

Prerequisite: a running Infrahub with the `models/base` schema loaded, so the schema-created pool for `InfraService.service_identifier` exists.

1. **Schema-created pool**: open `/resource-manager`, then open `InfraService.service_identifier [...]`.
   - The header shows the name cut with an ellipsis and a "Managed by schema" tag. Selecting the tag opens the schema viewer on the `service_identifier` attribute of `InfraService`.
   - The header shows "Allocates to InfraService attribute `service_identifier` with no scope".
   - In Actions, Edit, Groups and Delete are disabled. Their tooltip reads "Defined by the schema attribute InfraService.service_identifier".
   - Go to → View schema opens the `CoreNumberPool` schema.
2. **User-created pool**: create a number pool for `InfraInterface.speed` with range 1 to 10, then open it.
   - The header shows no managed-by tag, and "Allocates to InfraInterface attribute `speed` with no scope".
   - Edit, Groups and Delete are enabled.
3. **Scoped pool**: set `allocation_scope` to `["device", "name"]` on the user-created pool through the GraphQL sandbox, then reload.
   - The header shows "scoped by" followed by the two field labels from the `InfraInterface` schema, separated by "+".
   - The kind, the attribute and the two scope fields look the same. Each has a dotted underline, and selecting it opens the schema viewer in a modal on that field, and the page stays where it is.
4. **Edit**: Actions → Edit, change the description, save. The new description appears in the header without a page reload.
5. **Reload**: allocate a number from the pool in another tab, then press the reload button. The utilization in the page body updates.
6. **Delete**: Actions → Delete on the user-created pool. The app opens the resource manager list.
7. **Other pool kinds**: open an IP prefix pool. Its header is unchanged.

See [contracts/number-pool-header.md](contracts/number-pool-header.md) for each state and [data-model.md](data-model.md) for the fallbacks.
