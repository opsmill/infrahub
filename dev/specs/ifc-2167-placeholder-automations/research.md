# Research: Record template fingerprints in the database instead of placeholder automations

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-11-19

This file records the decisions taken before design. Each decision cites the code it was derived from as `module::symbol`. The sources for the current behavior are the code on branch `claude/friendly-goodall-b7a3eu` (based on `stable`) and the knowledge docs [display-labels-and-hfid.md](../../knowledge/backend/display-labels-and-hfid.md), [computed-attributes.md](../../knowledge/backend/computed-attributes.md) and [events.md](../../knowledge/backend/events.md).

## How the placeholder automations work today

| Family | Placeholder created by | Fingerprint held in | Used to decide a recompute |
|---|---|---|---|
| Display label | `display_labels/models.py::DisplayLabelTriggerDefinition.from_schema_display_labels` (fields `[TRIGGER_PLACEHOLDER_FIELD]`, `target_kind == node_kind`) | automation description, `get_description()` suffix `\| hash:<template_hash>` | Yes. `display_labels/tasks.py::display_labels_setup_jinja2` submits `TRIGGER_UPDATE_DISPLAY_LABELS` for each placeholder in `report.modified_triggers_with_type(...)` (created or updated) |
| HFID | `hfid/models.py::HFIDTriggerDefinition.from_schema_hfids` (same shape) | automation description, suffix `\| hash:<hfid_hash>` | Yes. `hfid/tasks.py::hfid_setup` follows the same pattern and submits `TRIGGER_UPDATE_HFID` |
| Jinja2 computed attribute | `computed_attribute/gather.py::gather_trigger_computed_attribute_jinja2` replaces the fields of each `targets_self` trigger node with `TRIGGER_PLACEHOLDER_FIELD` | automation description, suffix `\| hash:<template_hash>` | No. `computed_attribute/tasks.py::computed_attribute_setup_jinja2` selects candidates from every self-targeting trigger on the branch, narrowed by the `changed_elements` of the event through `RecomputeScoper`. The hash is read only to skip a branch whose template matches the default branch |

Shared facts:

- `trigger/setup.py::compare_automations` returns `UPDATE` for a branch-specific trigger type when the description differs, and `REFRESH` when only the branch filter differs. A placeholder therefore lands in `report.updated` when its hash changes, and in `report.created` when it did not exist.
- The base description contains the Infrahub version (`trigger/models.py::TriggerDefinition.get_description`). `infrahub upgrade` calls `trigger/tasks.py::trigger_configure_all`, which runs `setup_triggers(..., force_update=True)` and submits no recompute, so the descriptions are rewritten with the new version and the current hash during the upgrade.
- The setup flows run on `SchemaUpdatedEvent` and `BranchDeletedEvent` (`display_labels/triggers.py`, `hfid/triggers.py`, `computed_attribute/triggers.py::TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA`). On `BranchDeletedEvent` they submit nothing; the setup deletes the automations of branches that are no longer returned by `core/registry.py::Registry.get_altered_schema_branches`.
- On first start (`is_initial_setup`), `workflows/initialization.py::setup_task_manager_identifiers` creates the display label and HFID automations with `force_update=True` and submits no recompute.
- `setup_triggers_specific` holds the distributed lock `configure-action-rules-<trigger type>` (namespace `trigger-rules`) only around gather, compare, create, update and delete. The default-branch comparison and `submit_workflow` run after the lock is released.

## Decision 1: Jinja2 computed attributes need no recorded fingerprint

- **Decision**: Stop creating the self-targeting Jinja2 computed attribute automations, and build the setup flow's candidate list directly from `schema_branch.computed_attributes.get_jinja2_trigger_nodes()` (the trigger nodes with `targets_self`). Keep the `changed_elements` scoping and the default-branch skip, and read the default-branch template hash from the default branch schema instead of from the automation list. No fingerprint is recorded for this family.
- **Rationale**: The current flow does not compare a stored hash with the schema hash to decide a recompute (see the table above). Every input it reads is available from the schema registry. Recording a fingerprint and using it would change which recomputes are submitted, which FR-012 and SC-002 forbid. Recording one without using it adds writes that nothing reads (Principle VII).
- **Alternatives considered**: Record the fingerprint and recompute only when it changes, as for display labels. Rejected: when an event carries no `changed_elements`, the current flow recomputes every computed attribute on the branch, and a fingerprint gate would suppress those recomputes.
- **Effect on the spec**: FR-002, FR-003, FR-009 and the Key Entity list Jinja2 computed attributes among the recorded families, and the Background says the fingerprint decides the recompute for all three families. This plan keeps FR-001, FR-010, FR-012 and SC-001 for computed attributes and records fingerprints for display labels and HFIDs only. The spec needs amending (see plan.md, "Differences from the spec").

## Decision 2: Storage as an internal `StandardNode` keyed by branch name

- **Decision**: Add a `StandardNode` subclass `TemplateFingerprint` (Neo4j label `TemplateFingerprint`) with the properties `family`, `branch`, `kind` and `fingerprint`. Access it only through a `TemplateFingerprintRepository` that takes `db` and runs dedicated Query classes for bulk reads, bulk upserts and deletes by condition.
- **Rationale**: INFP-441 asks for `StandardNode` objects. `core/preferences/models.py::Preference` with `core/preferences/repository.py::PreferenceRepository` and `core/query/preference.py` is the most recent precedent of a global record keyed by a string and written through a repository. `DiffRoot` (`core/diff/repository/repository.py::DiffRepository`) is the precedent of an internal vertex that stores a branch name as a plain property. The backend component rule (`.agents/rules/backend-component-design.md`) requires new persistence behind a repository with Query classes.
- **Alternatives considered**:
  - Branch-aware nodes in the user schema (a `CoreTemplateFingerprint` kind). Rejected: it would be visible in GraphQL (FR-011), would need generated-file changes, and branch awareness does not fit: a record belongs to the branch that owns its own definitions, which is a property of the schema hash, not of the branch graph.
  - Per-record `StandardNode.save()`. Rejected for writes of more than one record: one query per record (N+1). Bulk `UNWIND ... MERGE` queries are used instead.
  - A property on the `Branch` vertex holding a JSON map. Rejected: every write rewrites the whole map, concurrent updates of two families would overwrite each other, and the default branch map would grow with every kind.

## Decision 3: No uniqueness constraint and no new index

- **Decision**: Writes use `MERGE` on `(family, branch, kind)` and run under the per-family distributed lock. Do not add a uniqueness constraint or an index.
- **Rationale**: The number of records is bounded by the number of kinds with a display label or an HFID multiplied by the number of branches that own their own schema plus one, the scale the spec quotes for automations. The records are read once per schema update. A label scan over this many small vertices does not need an index, and `backend/AGENTS.md` lists new indexes under "Ask First". `Preference` follows the same approach (no index on `owner_id`, writes under a lock).
- **Alternatives considered**: A RANGE index on `TemplateFingerprint.branch`. Kept as a fallback if `EXPLAIN` or a benchmark on a large schema shows the read is slow (Principle V); it needs maintainer approval.

## Decision 4: The recompute decision is a pure function of the schema and the records

- **Decision**: A pure component computes, for one event, three sets from the schema fingerprints of the branches in scope and the recorded fingerprints:
  1. the kinds to recompute on the event branch,
  2. the records to write after submission,
  3. the records to delete.
  The rules are in [contracts/recompute-decision.md](./contracts/recompute-decision.md). The display label and HFID setup flows call it with their family.
- **Rationale**: The rules (new, changed, identical to default branch, branch deleted, branch no longer owning its schema, kind removed) are the part the spec tests most (User Stories 2 and 4). A pure function is unit-testable without Prefect or Neo4j (Principle IV) and is shared by both families, so it has two callers (Principle VII).
- **Alternatives considered**: Keep the logic inline in each setup flow as today. Rejected: the two flows already duplicate the default-branch skip, and the new record handling would double that duplication.

## Decision 5: Only the event branch is recomputed and recorded

- **Decision**: Records are written only for the event branch. For other branches the flow only deletes records (branch no longer in scope, kind or template removed). The default branch records apply to every branch that does not own its schema.
- **Rationale**: Today submissions are limited to `display_report.branch == branch_name`, while `setup_triggers` rewrites the descriptions of every branch. Copying that would record fingerprints on other branches without a recompute, which FR-006 forbids. A branch whose records are out of date is reconciled at its next schema update; the result can be an extra recompute, never a missing one.
- **Alternatives considered**: Write the records of every branch in scope on each event (exact copy of today's description rewrite). Rejected because of FR-006.

## Decision 6: Lock held from comparison to recording

- **Decision**: The display label and HFID setup flows take the `configure-action-rules-<trigger type>` lock themselves and hold it across: configuring the remaining (peer) automations, carrying over placeholders, reading the records, deciding, submitting, and writing the records. They call the unlocked `setup_triggers` inside the lock instead of `setup_triggers_specific`.
- **Rationale**: FR-007 requires that two concurrent schema updates do not lose a change. With the comparison and the write in one critical section, the second flow reads the fingerprint the first one wrote after its submission. Submitting a workflow only creates a flow run, so the lock is held for a short time.
- **Alternatives considered**: Compare-and-set in Cypher without a lock. Rejected: the submission to the task manager sits between the read and the write and cannot be part of a database transaction.

## Decision 7: Record after submission, all at once

- **Decision**: The flow submits every recompute, then writes all records for the event branch (the recomputed kinds and the kinds skipped because they match the default branch) in one query. If a submission raises, no record is written.
- **Rationale**: FR-006. A failure part-way leads to the already-submitted kinds being submitted again at the next schema update. This is an extra recompute, which is acceptable; a missing one is not.
- **Alternatives considered**: Write one record after each submission. Rejected: one query per kind (N+1) for no gain in correctness.

## Decision 8: Fingerprints carried over from deleted placeholder automations

- **Decision**: When a setup deletes an automation, a carry-over component reads the deleted placeholder automations from `TriggerSetupReport.deleted`, keeps those of the display label and HFID families whose trigger matches only `TRIGGER_PLACEHOLDER_FIELD`, parses the branch and kind from the name (`<type>::<branch>::<kind>::by::<kind>`) and the fingerprint from the description suffix `| hash:<value>`, and inserts a record for every `(family, branch, kind)` that has none and whose branch is in scope. It runs:
  - in `trigger/tasks.py::trigger_configure_all` (called by `infrahub upgrade`, step 5), and
  - in the display label and HFID setup flows, inside the lock, before the decision.
- **Rationale**: FR-009 and User Story 3. Graph migrations have no task manager client (`core/migrations/shared.py::MigrationInput` holds `db`, `at`, `user_id`, `console`), and the upgrade only reaches the task manager in step 5, after the migrations. Placeholders disappear as soon as any setup runs with the new gatherers, so the carry-over has to happen where they are deleted. Running it in the setup flows as well covers a worker that processes a schema update before `infrahub upgrade` reaches step 5. Branch names cannot contain `:` (`core/branch/models.py::Branch.validate_branch_name`), so splitting the name from the right is unambiguous. Matching on the placeholder field avoids the HFID case where a peer trigger has the same `X::by::X` name.
- **Alternatives considered**:
  - A graph migration. Rejected: no access to the task manager.
  - A separate upgrade step before `trigger_configure_all` that reads all automations. Rejected: it reads the automations a second time, and it does not cover the setup flows.
  - No carry-over (recompute everything once after the upgrade). Rejected by User Story 3.
- **Kinds without a placeholder** (US3 scenario 4) get no record and are recomputed at the next schema update.

## Decision 9: First start records the current fingerprints without a recompute

- **Decision**: `workflows/initialization.py::setup_task_manager_identifiers` records the schema fingerprints of every branch in scope for both families, inserting only missing records, and submits nothing.
- **Rationale**: Today this path creates the placeholder automations with the current hashes and submits no recompute, so the first schema update afterwards submits nothing for unchanged templates. Without the seed, that first update would recompute every kind with a display label or an HFID (SC-002).

## Decision 10: Branch deletion removes the records directly

- **Decision**: `core/branch/data_deleter.py::BranchDataDeleter` deletes the records of the branch together with its other data, before it deletes the `Branch` vertex. The setup flows also delete the records of branches that are no longer in scope.
- **Rationale**: SC-004 asks for zero records after deletion. The setup flows depend on the worker's branch registry (`Registry.get_altered_schema_branches` reads the in-memory registry), which may still hold the deleted branch when the `BranchDeletedEvent` flow runs. Deleting in the branch deleter does not depend on that. A deletion that fails part-way is retried with the rest of the branch data.
- **Alternatives considered**: Rely only on the setup flows, as the automations do today. Rejected because of the registry timing described above.

## Decision 11: Same fingerprint values as today

- **Decision**: The recorded value is the value placed in the automation description today: `get_hash()` of each entry of `schema_branch.display_labels.get_template_nodes()`, and `core/schema/schema_branch_hfid.py::HFIDDefinition.get_hash` of each entry of `schema_branch.hfids.get_template_nodes()`.
- **Rationale**: The carried-over values and the newly computed values must be comparable, otherwise the first schema update after the upgrade recomputes everything (SC-003).

## Points left as they are (out of scope)

- Peer automations of display labels and HFIDs still carry the target hash in their description; a template change updates them in the task manager as today. Removing the hash from them is not required by the spec.
- `core/schema/schema_branch_computed/jinja2.py::get_trigger_nodes` merges the fields of a peer of the same kind into the self-targeting trigger node; those peer changes do not trigger a recompute today. This plan removes the self-targeting automation and does not change this behavior. It exists on `stable` before this change.
- Python transform computed attributes and profile refresh automations run and stay unchanged.
