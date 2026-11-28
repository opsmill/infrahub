# Quickstart: Validate the removal of placeholder automations

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

These scenarios prove the feature end to end. The rules they check are in [contracts/recompute-decision.md](./contracts/recompute-decision.md) and [contracts/fingerprint-store.md](./contracts/fingerprint-store.md).

## Prerequisites

- Docker running (component and integration tests start Neo4j and the task manager through testcontainers).
- `uv sync --all-groups`.
- For the live scenarios: a local stack on this branch's code, `INFRAHUB_IMAGE_VER=local`, started with `uv run invoke dev.start`. For scenario 4, a second stack on the current release with the same database volume.

## Automated checks

```bash
uv run pytest backend/tests/unit/core/template_fingerprint/            # decision rules, carry-over parsing
uv run pytest backend/tests/component/core/template_fingerprint/       # repository queries on Neo4j
uv run pytest backend/tests/component/display_labels/ backend/tests/component/hfid/ \
              backend/tests/component/computed_attribute/              # setup flows, submissions recorded
uv run pytest backend/tests/functional/computed_attributes/test_local_computation.py
uv run pytest backend/tests/integration_docker/test_computed_attributes.py  # regression, full stack
```

Expected: all pass. The component setup-flow tests record the submitted workflows and assert the exact list for each case of the decision table.

## Live scenarios

Use a schema with display label templates and HFIDs on several kinds, a Jinja2 computed attribute that reads only its own node, and a display label that reads a peer attribute (for example a device label that reads the name of its role).

### 1. No placeholder automation (User Story 1, SC-001)

1. Load the schema on `main`. Create two branches and load a schema change on each.
2. List the automations in the task manager (UI or `POST /api/automations/filter` on the task manager).

Expected: no automation whose trigger matches the field `_trigger_placeholder`. The automation count does not change when a new kind with a display label template is loaded. The automation for the peer-driven display label exists.

### 2. Recompute only on a template change (User Story 2, SC-002)

1. Load a second schema version that changes only the display label template of one kind on `main`.
2. List the flow runs created after the load.

Expected: one `trigger-update-display-labels` run for that kind on `main`, and no other display label, HFID or computed attribute recompute run. The nodes of that kind show the new label.

3. Load the same schema again.

Expected: no recompute run.

4. On a branch, change a template to the same value as on `main`, then to a different value.

Expected: no run for the first load; one run on that branch for the second, and none on `main`.

### 3. Branch lifecycle (User Story 4, SC-004)

1. On a branch with a schema change on a kind with a display label, check that `MATCH (f:TemplateFingerprint {branch: $branch}) RETURN count(f)` is greater than zero.
2. Delete the branch.

Expected: the same query returns 0.

3. Create a branch with the same name and the same change.

Expected: one recompute run for that kind on the new branch.

### 4. Upgrade from the current release (User Story 3, SC-003)

1. On the current release, load the schema on `main` and on two branches. Count the automations whose names start with `display_label_jinja2::` and `human_friendly_id::` and whose trigger matches `_trigger_placeholder`.
2. Delete one of these automations by hand to simulate a failed setup.
3. Switch the stack to this branch's code and run `infrahub upgrade`.

Expected: no placeholder automation remains; one `TemplateFingerprint` per carried-over automation exists.

4. Load the unchanged schema.

Expected: no recompute run, except one for the kind whose automation was deleted in step 2.

## Performance check (SC-005)

Load an unchanged schema with at least 50 kinds with display labels and HFIDs and 3 diverging branches, on the current release and on this branch, and compare the duration of the `display-labels-setup-jinja2` and `hfid-setup` flow runs. Expected: not longer on this branch.
