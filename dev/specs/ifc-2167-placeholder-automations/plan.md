# Implementation Plan: Record template fingerprints in the database instead of placeholder automations

**Branch**: `claude/friendly-goodall-b7a3eu` | **Date**: 2026-11-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `dev/specs/ifc-2167-placeholder-automations/spec.md`

## Summary

Infrahub stops creating the task manager automations that never run and only hold a template fingerprint: one per kind for display labels and HFIDs, and one per self-targeting Jinja2 computed attribute, on the default branch and on every branch that owns its schema.

- **Display labels and HFIDs**: the fingerprint last applied is recorded in Neo4j as an internal `TemplateFingerprint` vertex keyed by family, branch and kind. The setup flows compare the schema fingerprints with the records, submit the same recomputes as today, and record a fingerprint only after its recompute is submitted, all under the existing per-family lock.
- **Jinja2 computed attributes**: the setup flow already decides from the schema and the `changed_elements` of the event, and reads the automation hash only to compare a branch with the default branch. It now reads that hash from the default branch schema, so no record is needed.
- **Upgrade**: the fingerprints held by the placeholder automations are copied into records at the point where those automations are deleted (`infrahub upgrade` step 5, and the first setup run on the new release), so an unchanged schema triggers no recompute after the upgrade.
- **Branch lifecycle**: branch deletion removes the branch's records; each setup run removes the records of branches that no longer own their schema and of removed kinds or templates.

The design decisions and their sources are in [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.14 (backend only)

**Primary Dependencies**: Prefect (setup flows, automations, `TriggerSetupReport`), Neo4j driver through the `Query` class pattern, Pydantic 2 (`StandardNode`). No new dependency.

**Storage**: Neo4j. New internal label `TemplateFingerprint` (no edges, not branch-aware, not in the user schema). No graph migration: the label is new and no existing data changes shape. No index (research Decision 3).

**Testing**: pytest. Unit tests for the decision rules and the carry-over parsing; component tests (testcontainers Neo4j and the Prefect test server) for the repository, the three setup flows with a `WorkflowRecorder`, branch deletion and the carry-over; regression run of `tests/integration_docker/test_computed_attributes.py`. SC-005 is measured on a running instance: the duration of an unchanged schema update before and after the change, on the same schema and branch count, recorded in the PR.

**Target Platform**: Linux server (API server, task workers, `infrahub upgrade` CLI)

**Project Type**: Web application backend (monorepo `backend/` + `frontend/app/`). No frontend change.

**Performance Goals**: An unchanged schema update takes no longer than today (SC-005). The setup flows replace the reading and comparison of K × (B + 1) placeholder automations per family with one Neo4j read and at most one delete and one write per flow run.

**Constraints**: Same recompute submissions as the current release (FR-012, SC-002); record after submission (FR-006); no lost change under concurrent schema updates (FR-007); records invisible to API and UI (FR-011); downgrade not supported (spec Assumptions).

**Scale/Scope**: The instance in INFP-441 reached 11,000 automations. Records are bounded by (kinds with a display label + kinds with an HFID) × (branches owning their schema + 1). Code touched: `display_labels/`, `hfid/`, `computed_attribute/` (gather and setup flow), `trigger/tasks.py`, `workflows/initialization.py`, `core/branch/data_deleter.py`, and a new `core/template_fingerprint/` package.

No item is marked NEEDS CLARIFICATION: each open point is resolved in research.md.

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.0.0 before Phase 0 and again after Phase 1.*

- **I. Schema-Driven Integrity**: PASS with a note. `TemplateFingerprint` is internal bookkeeping, not infrastructure data, and follows the existing internal `StandardNode` labels (`Branch`, `Root`, `Preference`, `TelemetrySnapshot`) that live outside the user schema. No generated file changes.
- **II. Branch-Safe by Default**: PASS with a justified deviation. The records are scoped to a branch by a property, like `DiffRoot.diff_branch`, and every query filters on family and, where relevant, branch. Branch deletion and the loss of a branch's own schema are handled explicitly (FR-008, research Decision 10). The records are hard-deleted and have no temporal history; see Complexity Tracking.
- **III. Type Safety & Explicit Contracts**: PASS. Frozen dataclasses for keys, records and the decision; query results through `get_data()`; typed repository methods ([contracts/fingerprint-store.md](./contracts/fingerprint-store.md)). No GraphQL or REST contract changes.
- **IV. Test Discipline**: PASS. Unit tests for the pure decision and parser; component tests for the repository and the setup flows with recorded submissions; the existing integration Docker suite for computed attributes runs as a regression. No E2E test: there is no user-facing UI change (the only visible effect is the automation count in the task manager, checked in a component test and in [quickstart.md](./quickstart.md)).
- **V. Query Performance & Efficiency**: PASS. Parameterized queries; bulk `UNWIND` writes and deletes by condition (no N+1); reads return three properties. No index, by decision (research Decision 3); `EXPLAIN` is run on the read during development.
- **VI. Security & Input Boundaries**: PASS. No new API surface. Values written come from the schema registry and from automation names and descriptions written by Infrahub; all bound as parameters.
- **VII. Simplicity & Maintainability**: PASS. Follows the `Preference` repository pattern; the decision component serves two callers (display labels and HFIDs); no fingerprint store for computed attributes because nothing would read it; no new dependency.

**Result (before Phase 0)**: PASS, one deviation recorded in Complexity Tracking.

**Re-check after Phase 1**: PASS. The data model and contracts add no API surface, no schema change visible to users, no migration and no index. The deviation in Complexity Tracking is unchanged.

## Notes on the spec

The spec was amended after the critique ([critiques/critique-20261119.md](./critiques/critique-20261119.md)), so it now records fingerprints for display labels and HFIDs only (research Decision 1), and SC-002 lists the cases in which an extra recompute is allowed. One point of timing remains:

| Spec item | Plan | Reason |
|---|---|---|
| User Story 3 scenario 4: a kind without a placeholder is recomputed after the upgrade | Recomputed at the first schema update after the upgrade. Today `infrahub upgrade` recreates a missing automation without a recompute | Research Decision 8 |

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-2167-placeholder-automations/
├── plan.md                         # This file
├── research.md                     # Phase 0: decisions and their sources
├── data-model.md                   # Phase 1: TemplateFingerprint and in-memory values
├── quickstart.md                   # Phase 1: validation scenarios
├── contracts/
│   ├── recompute-decision.md       # Decision rules and order of execution in the setup flows
│   └── fingerprint-store.md        # Repository, collector, carry-over, first-start seed
├── checklists/
│   └── requirements.md             # From /speckit-specify
└── tasks.md                        # Phase 2 (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/template_fingerprint/              # NEW package
│   ├── __init__.py
│   ├── models.py                           # TemplateFingerprint (StandardNode), TemplateFamily, frozen dataclasses
│   ├── repository.py                       # TemplateFingerprintRepository
│   ├── collector.py                        # schema fingerprints per family and branch in scope
│   └── decision.py                         # pure recompute decision (contracts/recompute-decision.md)
├── core/query/template_fingerprint.py      # NEW: get, upsert, insert-missing, delete, delete-branch queries
├── core/branch/data_deleter.py             # BranchDataDeleter: delete the branch's records
├── trigger/
│   ├── placeholder_carry_over.py           # NEW: parse deleted placeholder automations into records
│   ├── constants.py                        # TRIGGER_PLACEHOLDER_FIELD kept: the carry-over matches on it
│   └── tasks.py                            # trigger_configure_all: run the carry-over on report.deleted
├── workflows/initialization.py             # setup_task_manager_identifiers: first-start seed
├── display_labels/
│   ├── models.py                           # stop emitting the self-targeting placeholder definitions
│   └── tasks.py                            # display_labels_setup_jinja2: lock, carry-over, decision, submit, record
├── hfid/
│   ├── models.py                           # same as display_labels/models.py
│   └── tasks.py                            # hfid_setup: same as display_labels/tasks.py
└── computed_attribute/
    ├── gather.py                           # skip targets_self trigger nodes instead of neutralizing them
    └── tasks.py                            # computed_attribute_setup_jinja2: candidates and default-branch hash from the schema

backend/tests/
├── unit/core/template_fingerprint/         # NEW: decision table, collector on schema fixtures
├── unit/trigger/test_placeholder_carry_over.py   # NEW: name and description parsing
├── component/core/template_fingerprint/    # NEW: repository queries on Neo4j
├── component/display_labels/               # update test_gather.py; NEW setup-flow test with WorkflowRecorder
├── component/hfid/                         # NEW: setup-flow test with WorkflowRecorder
├── component/computed_attribute/           # update test_scoped_recompute_jinja2.py and test_gather.py; branch skip test
├── component/trigger/                      # NEW: carry-over through trigger_configure_all on the Prefect test server
├── component/branch/                       # NEW: branch deletion removes the records; no record is written for a deleted branch
└── functional/computed_attributes/test_local_computation.py   # replace the placeholder-field assertions

dev/knowledge/backend/
├── display-labels-and-hfid.md              # "Async Backfill After Schema Changes": records instead of automations
├── computed-attributes.md                  # "Self-Targeting Filter": no automation for self-targeting nodes
└── events.md                               # "Branch scoping of automations": placeholder families removed

changelog/+ifc-2167.changed.md              # NEW: fewer automations in the task manager
```

**Structure Decision**: Backend only. Persistence and the pure decision live in a new `core/template_fingerprint/` package with its queries in `core/query/`, following `core/preferences/` and `core/query/preference.py`, because the branch deleter in `core/branch/` uses the repository. The carry-over lives in `trigger/` because it reads task manager automations. The three setup flows keep their place and delegate to these components; collaborators are built at the top of each flow and passed in (`.agents/rules/backend-component-design.md`).

## Risks

| Risk | Effect | Mitigation |
|---|---|---|
| A worker on the new release runs a setup flow while another worker still runs the old release during a rolling upgrade | The old worker recreates placeholder automations that the new one deletes | Upgrades already require all workers on the same release; the carry-over and the deletion are idempotent, so the state converges at the next setup run |
| The carry-over misparses an automation | A missing record, so one extra recompute for that kind | Parsing is unit-tested on names with `/` and `-` in the branch name; an automation that fails a check is skipped, never recorded with a wrong value |
| The lock is now held during submissions | A second setup flow for the same family waits longer | Submitting creates flow runs only; the number of submissions per event is unchanged |
| A record is left for a deleted branch if the branch deleter fails after the records step | Stale records | The deleter is retried as a whole; the setup flows also delete records of branches out of scope |
| A setup flow whose worker registry still holds a deleted branch writes records for it after the branch deleter ran | A new branch with the same name and the same template skips its recompute (User Story 4 scenario 2) | `upsert` and `insert_missing` write a record only when a `Branch` vertex with that name exists, checked in the same query; covered by a component test |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Principle II: hard delete and no temporal history for `TemplateFingerprint` | A record describes which fingerprint was last applied by a background process; there is no past state that a user or a query needs to read, and the records must disappear with their branch (SC-004) | Branch-aware, soft-deleted nodes would need edges to the branch graph, would appear in diffs and merges, and would need to be in the user schema, which FR-011 forbids. `Preference` and `DiffRoot` use the same hard-delete approach |
