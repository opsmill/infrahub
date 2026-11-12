# Quickstart: validate owner and source metadata (Community side), storage option E

This guide lists the checks that prove the feature works. The data model is in [data-model.md](data-model.md). The API is in [contracts/](contracts/).

## Prerequisites

- A running Docker daemon. The component tests start Neo4j through testcontainers.
- `uv sync --all-groups`
- The `python_sdk` submodule checked out, for the object file checks.

## Backend tests

```bash
uv run pytest backend/tests/unit/core/ownership backend/tests/unit/permissions -q
```

```bash
uv run pytest backend/tests/component/core/ownership backend/tests/component/core/diff/merge backend/tests/component/core/migrations backend/tests/component/graphql/metadata backend/tests/component/permissions -q
```

Expected: all tests pass. The existing permission tests pass without changes (SC-007).

## Integration Docker test

```bash
uv run pytest backend/tests/integration_docker/test_schema_migration.py -q
```

Expected: the owners follow a kind change and a field rename on the full stack (FR-040, FR-041).

## E2E tests

```bash
uv run pytest -c tests/e2e/pytest.ini tests/e2e/ownership -s --pdb
```

Expected: all tests pass. They run user stories 1 to 6 through the API on the full stack, and they open no page.

## Query benchmarks

```bash
uv run pytest backend/tests/query_benchmark -q
```

Expected: SC-001, SC-002, SC-004, SC-005, SC-006 and SC-008 are within their limits on the reference data set. SC-003 is the open point of the spike ([research.md](research.md), R-6).

## Scenarios through GraphQL on a local stack

```bash
uv run invoke dev.build
```

```bash
uv run invoke dev.start
```

Run each scenario as an administrator in the GraphQL sandbox, unless the step names another user.

### 1. Node owners and inheritance (user story 1)

1. Create the account groups `dc-emea` and `dc-security`.
2. Update a device with `node_metadata: {owners: [{hfid: ["dc-emea"], kind: "CoreAccountGroup"}]}`.
3. Read `node_metadata { ownership { state origin origin_node { display_label } owners { display_label } } }` on an interface of the device.
   - Expected: `state: INHERIT`, `origin: PARENT`, the device as origin node, the owner `dc-emea`.
4. Filter interfaces with `node_metadata__owners__ids` and the ID of `dc-emea`.
   - Expected: the interfaces of the device, with the correct `count`.
5. Set the interface to `owners: []`, then to `owners: null`.
   - Expected: `NO_OWNER`, then `INHERIT` with the owner of the device again.
6. Give a repository as owner.
   - Expected: Infrahub refuses the whole mutation.

### 2. Branch, diff and merge (FR-029, FR-030)

1. On a branch, set two owners on a device.
   - Expected: the default branch shows no owner for the device.
2. Read the diff of the branch.
   - Expected: one changed node, with the display labels of the owners added.
3. Merge the branch.
   - Expected: the default branch shows both owners, and the interfaces of the device show them as inherited.

### 3. Profiles and object templates (user story 2)

1. Create a profile with `node_metadata: {target_owners: [...]}` and attach it to a device.
   - Expected: `origin: PROFILE` and the profile as origin node.
2. Change `target_owners` on the profile.
   - Expected: the next read of the device shows the new owners. The diff of a branch lists the profile only.
3. Create a device from an object template that gives owners.
   - Expected: `origin: TEMPLATE`. A later change of the template does not change the device.

### 4. Field owners and the deprecated `owner` field (user story 3)

1. Set `field_owners` on a relationship without peers.
   - Expected: the relationship returns its `ownership` block with `origin: SELF`. The other fields return `origin: OBJECT`.
2. Read `owner` on an attribute with one own owner, then with two.
   - Expected: that owner, then null.

### 5. Node sources (user story 4)

1. Create a device with `node_metadata: {sources: [...]}`.
2. Filter devices with `node_metadata__sources__ids`.
   - Expected: the device, with the correct `count`.

### 6. Upgrade (user story 5)

1. On a database of the release before, run `infrahub db ownership-report`.
   - Expected: the report lists the repository owners, the relationships whose links have owners, and the values with `is_protected` set.
2. Run `infrahub upgrade`.
3. Read `owner` on an attribute that an account group owned.
   - Expected: the same account group, and `ownership { state }` is `OWNERS`.

### 7. Change check and "applies to" (user story 6)

1. As a user with update permission on devices, update a device that another group owns.
   - Expected: Infrahub Community stores the change.
2. Save an object permission with `applies_to: owned_objects`.
   - Expected: Infrahub refuses it, and the message says that the value needs Infrahub Enterprise.
3. Read `node_metadata { permissions { update delete } }` on a list of devices.
   - Expected: each node reports the decision for the kind.

The refusal of a change is covered by the component tests, with a test implementation of the change check.

### 8. Account group tree (user story 7)

1. Create `dc-emea-fra` as a subgroup of `dc-emea`, and give a role to `dc-emea`.
2. Run `infrahub db account-group-tree-report`.
   - Expected: the report lists the members of `dc-emea-fra` and the roles that they gain.
3. Turn the group tree setting on and restart.
   - Expected: a member of `dc-emea-fra` can use the permissions of the role.

## Object files

Load a file with the keys of [contracts/object-file.md](contracts/object-file.md) through `infrahubctl object load`, then read the owners and sources through GraphQL.

## Checks before a push

```bash
uv run invoke format
```

```bash
uv run invoke lint
```

```bash
uv run invoke docs.validate
```
