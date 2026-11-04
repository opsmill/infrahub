# Quickstart: validate schema-defined field sections

Commands run from the repository root unless a `cd` is written. Each block names the outcome that
shows the step passed.

## Prerequisites

- Branch `ple-field-sections-ifc-2729` checked out, `uv sync --all-groups` and
  `cd frontend/app && pnpm install` done.
- Docker running, for the component tests and the end-to-end test.
- The `python_sdk` submodule at the SDK commit that carries the regenerated models (the SDK PR
  branch while it is open, the merged commit once the pointer is bumped). Until then the schema
  API tests fail by design.

## Backend unit tests

```bash
uv run pytest backend/tests/unit/core/schema backend/tests/unit/api/test_schema_load_contract.py
```

Expected: every test passes, including the container validator cases (the three exact messages
and the accepted cases), the inheritance merge cases, the "no migration, no constraint" cases and
the load contract cases.

## Backend component tests

```bash
uv run pytest backend/tests/component/core/schema/schema_branch/test_process_idempotency.py \
  backend/tests/component/core/schema_manager/test_manager_schema.py -k "container or profile or template or idempotency or reload"
uv run pytest backend/tests/component/api/test_40_schema.py
uv run pytest backend/tests/component/core/schema/test_schema_documentation.py
```

Expected: the idempotency and round-trip tests pass with containers in the fixture schema; the
reload cases append, update, keep and remove containers as the reload merge section of
[data-model.md](data-model.md#reload-merge) states; the profile and template tests find the copied
containers; the schema API tests return
`containers` and `container` on the default branch and on `branch1`, and a 422 with the exact
message for the undeclared-container fixture; the documentation test finds a description on all
three properties.

## Generated files

```bash
uv run invoke backend.generate
uv run invoke schema.generate-jsonschema
uv run invoke docs.generate
cd frontend/app && pnpm codegen:openapi && cd ../..
uv run invoke backend.validate-generated
uv run invoke schema.validate-jsonschema
uv run invoke schema.validate-graphqlschema
uv run invoke docs.validate
git diff --exit-code frontend/app/src/shared/api/rest/types.generated.ts
```

Expected: the generate tasks rewrite `backend/infrahub/core/schema/generated/`,
`python_sdk/infrahub_sdk/schema/generated/`, `schema/openapi.json`,
`docs/docs/reference/schema/` and the REST types; every validate task reports no difference;
`schema.validate-graphqlschema` reports no difference because the GraphQL schema does not change;
the final `git diff` exits 0 once the regenerated REST types are committed.

## SDK tests (inside the submodule)

```bash
cd python_sdk && uv run pytest tests/unit/ctl/test_schema_format.py
```

Expected: the key-order tests pass with `containers` after `uniqueness_constraints`, `container`
right before the trailing `order_weight`, and the container item keys in the order `name`,
`label`, `description`, `order_weight`, `collapsed`.

## Frontend tests and gates

```bash
cd frontend && pnpm biome:fix && cd app
pnpm exec tsc --noEmit
pnpm test src/entities/nodes/object/domain src/entities/nodes/object/ui/object-details \
  src/shared/components/form src/entities/schema
pnpm knip
pnpm exec betterer ci
pnpm test
```

Expected: Biome rewrites nothing on a clean tree; `tsc` reports no error; the partition rule, the
card, the detail view, the form and the schema viewer tests pass; `knip` reports no unused export;
`betterer` reports no TypeScript regression; the full suite passes.

## Demo schema in a running instance

```bash
uv run invoke dev.start
uv run invoke dev.load-infra-schema
uv run infrahubctl schema check models/base/dcim.yml
uv run invoke dev.load-infra-data
```

Expected: the schema loads without error; `schema check` reports the file as valid; the demo data
loads. Then, in the web UI:

1. Open the list of `InfraLagInterfaceL2` objects and open `port-channel1` of `atl1-leaf1`.
2. View, in this order: a Details card (name, device, description, status, role, MTU, tags, and
   the other ungrouped fields; `members` stays in its tab), an LACP card (LACP, minimum links,
   MLAG), a Layer 2 card with its description under the title (Layer 2 mode, untagged VLAN, tagged
   VLANs), and a collapsed Advanced card (max bundle). No Layer 3 card is shown, because this node
   has no Layer 3 field.
3. Select the Layer 2 header: the card collapses; select it again: it expands.
4. Select Edit: the form shows a Details panel, then LACP, Layer 2 and Advanced panels, all
   expanded. Change the minimum links inside the LACP panel and save: the toast confirms the
   update and the LACP card shows the new value.
5. Open `Schema` in the sidebar, select `InfraLagInterface`: the Containers block lists `lacp`,
   `layer2` and `layer3`; the `lacp` attribute shows `Container: lacp`.
6. Open any object of a kind without containers (for example an `InfraDevice`): the detail page
   shows the single Details card and the edit form is the flat list, as before the change.

## End-to-end test

Build the image from the branch with the bumped `python_sdk` pointer, then:

```bash
INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e/objects/test_object_containers.py -s --pdb
```

Expected: the test opens the L2 LAG interface on its own branch, finds the Details, LACP and
Layer 2 regions and the Advanced header, finds no Layer 3 region, edits the minimum links inside
the LACP panel, saves, and reads the new value in the LACP card. The existing object detail and
object update tests keep passing because their kinds declare no container.

## Documentation

```bash
uv run invoke docs.lint
cd docs && npm run build
```

Expected: no Vale or markdownlint error; the site builds with the new `schema/field-sections` page
in the "Display & presentation" sidebar group and the regenerated reference pages listing
`containers` and `container`.

## Repository gates before pushing

```bash
uv run invoke format
uv run invoke lint
uv run ruff check . --exclude python_sdk
uv run ruff format --check --exclude python_sdk .
```

Expected: no change from `format`, no lint error, no ruff finding. Then ask the user to run
`/pre-ci`.
