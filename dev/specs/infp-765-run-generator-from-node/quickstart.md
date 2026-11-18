# Quickstart: Validate Running a Generator from a Node's Page

Runnable checks that prove the feature works end to end. The expected behavior is in [contracts/generators-menu-section.md](contracts/generators-menu-section.md).

## Prerequisites

- Python dependencies: `uv sync --all-groups`.
- Frontend dependencies: `cd frontend/app && pnpm install`.
- Docker running, for the E2E suite.

## 1. Frontend unit and component tests

```bash
cd frontend/app && pnpm test src/entities/generators src/entities/permission
```

Expected: the tests for `select-node-generator-definitions`, `can-run-generators` and `node-generators-menu-section` pass. They cover:

- no definition
- a definition for another kind
- a member, enabled
- a non-member of the targeted kind, disabled, with the tooltip text
- several definitions sharing one group
- each visibility row of the contract
- one toast per outcome

## 2. Generated types are current

```bash
cd frontend/app && pnpm codegen:graphql && git diff --exit-code -- src/shared/api/graphql/generated/
```

Expected: after committing the updated `graphql-cache.d.ts`, no difference remains.

## 3. E2E test

```bash
uv run pytest -c tests/e2e/pytest.ini tests/e2e/objects/test_object_details_generators.py -s --pdb
```

Expected, on a throwaway branch with the demo-edge repository loaded:

1. **atl1-edge1 Ethernet5** (member of `upstream_interfaces`, signed in as admin): Actions > Generators > "Run update_upstream_interfaces_description" is enabled. Selecting it shows "Generator update_upstream_interfaces_description started for Ethernet5." with a "View task" link. The task reaches `COMPLETED`, and exactly one generator instance for that definition on the branch points at Ethernet5.
2. **atl1-edge1 Ethernet7**: the item is disabled, and its tooltip reads "Ethernet7 is not a member of the target group upstream_interfaces". After Ethernet7 is added to `upstream_interfaces` on the branch, reopening the menu shows the item enabled.
3. **atl1 site page, and an `InfraCircuit` page** (its target groups are empty): no Generators section.
4. **jbauer** (`read_only_page`): no section on Ethernet5 on the default branch; section shown on the throwaway branch.
5. **Signed out** (`page`): no section.

## 4. Manual check with solution-ai-dc (optional)

Load `opsmill/infrahub-solution-ai-dc` into a local Infrahub started with `invoke dev.*`. On a new branch:

1. Fabric-A's Actions menu shows "Run generate-fabric", enabled. Selecting it starts the run, and the pod and rack generators follow through the trigger rules.
2. A new fabric outside the `fabrics` group shows the item disabled, with the tooltip naming `fabrics`.
3. A pod's page lists `generate-pod` only.

## 5. CI gate before pushing

```bash
cd frontend && pnpm exec biome ci .
cd frontend/app && pnpm knip && pnpm exec betterer ci && pnpm test
```

Then run `/pre-ci` from the repository root.
