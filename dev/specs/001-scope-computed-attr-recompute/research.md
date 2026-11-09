# Phase 0 Research: Scope Computed-Attribute Recompute to Actual Schema Changes

**Date**: 2026-06-03 (regenerated to fold in Session 2026-06-03 clarifications)
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

This document records the decisions that resolve the open questions for scoping computed-attribute recompute. All findings are grounded in the current backend code. The 2026-06-03 clarifications are reflected in Decisions 2, 3, 5, and 6.

## Current behavior (the defect)

The fan-out chain, end to end:

1. A schema change is applied to a branch. Emission sites:
   - Interactive edit: `backend/infrahub/graphql/mutations/schema.py` — calls `registry.schema.update_schema_branch(...)`, then constructs and sends `SchemaUpdatedEvent`.
   - Schema load: `backend/infrahub/api/schema.py` — computes `branch_schema.diff(other=candidate_schema)`, applies it, then sends `SchemaUpdatedEvent`.
   - Branch merge: `backend/infrahub/core/merge/branch_merger.py` — builds the 3-way diff via `SchemaUpdateValidationResult.init(...)`.
   - Branch deletion: `backend/infrahub/core/branch/tasks.py` — sends `BranchDeletedEvent` (no diff).
2. `SchemaUpdatedEvent` (`backend/infrahub/events/schema_action.py`) carries only `branch_name` + `schema_hash`. Its own inline NOTE already proposes adding "List of nodes and generics that have been modified" / "Diff of the change".
3. `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` (`backend/infrahub/computed_attribute/triggers.py`) matches `SchemaUpdatedEvent` (and `BranchDeletedEvent`) and runs `COMPUTED_ATTRIBUTE_SETUP_JINJA2` + `COMPUTED_ATTRIBUTE_SETUP_PYTHON`.
4. `computed_attribute_setup_jinja2` / `computed_attribute_setup_python` (`backend/infrahub/computed_attribute/tasks.py`) gather **all** computed-attribute triggers for the branch and, per attribute, submit `TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES` / `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES`.
5. `trigger_update_jinja2_computed_attributes` / `trigger_update_python_computed_attributes` call `client.all(kind=...)` and submit one `process_jinja2` / `process_transform` job **per object**.

The decision point that selects attributes for recompute (step 4) has no knowledge of *what* changed, so it selects everything. This is the root cause.

## Decision 1 — Source of the changed-element set

**Decision**: Extend `SchemaUpdatedEvent` with an optional changed-element set (added/changed/removed object-type kinds, plus per-kind changed attribute/relationship names), populated from `SchemaBranch.diff()` at the emission sites that already compute it. When absent (`None`), the recompute setup flows fall back to full recompute.

**Rationale**:
- `SchemaBranch.diff()` already produces `SchemaDiff` with `.added` / `.changed` / `.removed`, keyed by kind, with per-node attribute/relationship-level detail. The API-load and merge paths already compute it; the interactive-edit path computes a diff inside `update_schema_branch`.
- The event is the existing seam between "schema changed" and "recompute decided". Threading data through the event (then through the Prefect workflow parameters in `triggers.py`) keeps the trigger model intact and is exactly what the event's own NOTE anticipates.
- Optionality gives a clean, explicit fallback: paths that cannot cheaply surface a diff send `None` and behavior is identical to today (FR-008, SC-005).

**Granularity of "changed" (Session 2026-06-03, Q-D)**: The changed-element set carries **every** element `SchemaBranch.diff()` reports as added/changed/removed. There is no "value-affecting vs cosmetic" classifier — a change to a read element's label, description, or ordering counts as a change and will select dependent attributes. Rationale: a reliable per-element "could this affect the stored value?" classifier is error-prone, cosmetic-only edits are rare, and the over-recompute cost is bounded; avoiding the classifier removes a whole class of correctness bugs (FR-004).

**Alternatives considered**:
- *Recompute the diff inside the setup flow by re-comparing schema hashes/branches.* Rejected: the pre-change schema is not reliably available at setup time (the branch already holds the new schema), and re-deriving it duplicates work already done upstream.
- *Classify edits as value-affecting vs cosmetic and skip cosmetic-only changes.* Rejected (Q-D): adds a fragile classifier per element type for a rare, low-cost case.
- *Persist a dependency graph in the database.* Rejected (YAGNI, Principle VII): dependency sets are cheap to derive in-memory from the active `SchemaBranch`.

## Decision 2 — Jinja2 dependency set (full depth, conservative fallback)

**Decision**: Reuse the existing `Jinja2ComputedRegistry` dependency graph (`backend/infrahub/core/schema/schema_branch_computed/jinja2.py`) to answer "given these changed elements, which Jinja2 computed attributes are impacted?" The registry records, per node kind, `local_fields` (field → dependent targets) and `relationship_dependencies` (relationship → {targets, peer attributes}), and exposes `get_impacted_targets(kind, updates)`.

**Full-depth traversal (Session 2026-06-03, Q-B)**: The dependency set must reflect reads at whatever relationship depth the value actually expresses (e.g. `device.site.region.name`). Where the registry exposes the chain, derive it precisely. Where the depth or precise read set cannot be determined for a Jinja2 attribute, mark it "depends on everything" so it is always recomputed — never skip a needed recompute. A computed attribute whose own definition (template) changed is detected directly from the diff on the attribute that owns it (FR-003).

**Rationale**: The data needed to scope Jinja2 recompute already exists and is used for the data-change (`NodeUpdatedEvent`) path. The same graph answers the schema-change question. Conservative marking where the graph is incomplete preserves correctness without abandoning scoping for the branch.

**Alternatives considered**:
- *Re-parse Jinja2 templates at scoping time.* Rejected: redundant; parsing already happens at schema registration and the result is the registry.
- *Bound traversal to a single hop.* Rejected (Q-B): would miss deeper reads and risk stale values, which is worse than over-recomputing.

## Decision 3 — Transform (Python) dependency set + per-attribute fallback

**Decision**: Add a new deriver that, for a transform-based computed attribute, extracts the kinds/attributes/relationships read by the transform's stored GraphQL query and builds its dependency set at full depth. Use the SDK `GraphQLQueryAnalyzer` (already wrapped by `backend/infrahub/graphql/analyzer.py`, whose `GraphQLQueryReport` exposes `requested_read`). Cache the derived set per (branch, transform) keyed by the query's content so it is computed once per schema version.

**Rationale**:
- `PythonTransformRegistry` (`backend/infrahub/core/schema/schema_branch_computed/python_transform.py`) currently maps only kind → attributes; it does **not** know what each transform reads. This is the missing piece. The GraphQL query expresses reads at full depth, so the analyzer yields full-depth dependencies naturally.

**Per-attribute conservative fallback (Session 2026-06-03, Q-C → FR-013)**: When the changed-element set IS known but a single transform's query cannot be statically analyzed (or reads a related object's `display_label`/`hfid`, whose backing fields are imprecise), mark **that one attribute** as "depends on everything" so it recomputes on every schema change. This MUST NOT escalate to a branch-wide full recompute — all other attributes stay normally scoped. This is distinct from FR-008 (whole path has no diff → full recompute).

**Conservative cases (correctness first, FR-005/FR-006/FR-013)**:
- Query text unavailable or unparseable → attribute depends on everything (always recompute).
- Query reads a related object's `display_label` / `hfid` → any change to that related type impacts the attribute.
- An object type read by the query is added or removed → impacts the attribute.

**Alternatives considered**:
- *Run the transform to observe reads.* Rejected: executing arbitrary Python at scoping time is expensive and unsafe; static query analysis suffices.
- *On any unanalyzable query, fall back to full recompute of all attributes.* Rejected (Q-C): one opaque query should not disable scoping for the whole branch.

## Decision 4 — Where the scoping decision lives

**Decision**: Introduce `backend/infrahub/computed_attribute/scoping.py` — a single-entry-point component that takes the changed-element set plus the per-kind dependency derivers and returns a report of `selected` (recompute) and `skipped` (with reason) computed attributes. The two derivers (Jinja2, Python transform) sit behind a `Protocol`. The setup flows in `tasks.py` call this component and submit recompute only for `selected`.

**Rationale**: Conforms to `dev/rules/backend-component-design.md` — long-lived collaborators (derivers, schema branch) injected via constructor; the transient work item (the changed-element set) passed to the entry method. A `Protocol` is warranted because two real implementations exist. Keeping the decision out of `tasks.py` makes it unit-testable without Prefect or a database.

**Alternatives considered**:
- *Inline the intersection logic in each setup flow.* Rejected: duplicates logic across the two flows, couples it to Prefect, and is hard to unit-test.

## Decision 5 — Observability (task logs)

**Decision** (Session 2026-06-03, Q-A): Surface the scoping decision through the recompute task logs only. At the end of scoping, log one info-level summary per schema change: count + identities (kind.attribute) selected for recompute. Log the intentionally-skipped set (with reason) at debug level. Use the existing `get_run_logger()` / structlog conventions already present in `computed_attribute/tasks.py`.

**Rationale**: Matches the clarified requirement (FR-012, SC-006): summary signal at normal level, skipped detail at diagnostic level, observable from system output (task logs operators already read) without inspecting source code. Reuses existing logging conventions rather than introducing a metrics subsystem (Principle VII).

**Alternatives considered**:
- *Emit a new structured event / metric, or a persisted task report.* Rejected for now (Q-A): logging satisfies the observability requirement with the least surface; a structured channel can be added later if alerting/automation need it.

## Decision 6 — Fallback & edge-case matrix

| Path / situation | Changed-element set | Behavior | Requirement |
|------------------|---------------------|----------|-------------|
| Interactive schema edit | Available (from `update_schema_branch` diff) | Scoped | FR-001 |
| Schema load (`/api/schema`) | Available (`branch_schema.diff`) | Scoped | FR-001 |
| Branch merge/rebase applying schema | Available only when surfaced on the path | Scoped if present, else full recompute (**must be tested** — Principle II) | FR-008 |
| Branch deletion (`BranchDeletedEvent`) | None (no diff) | Full recompute (current behavior) | FR-008, SC-005 |
| Whole object type added/removed | Present as added/removed kind | Impacts every attribute that reads that type | FR-005 |
| Single transform query unanalyzable | Path diff known; attribute reads opaque | **That attribute only** always recomputed; others scoped (no branch-wide fallback) | FR-013 |
| Display-label / hfid dependency | N/A | Any change to that related type → recompute | FR-006 |
| Cosmetic-only edit to a read element | Present in changed set | Dependent attribute recomputed (no value-affecting filter) | FR-004 |
| Transform source-code change (repo sync) | Out of scope | Unchanged (`CommitUpdatedEvent` path keeps full recompute) | Assumptions |

## Decision 7 — Branch awareness (no regression)

**Decision**: Leave the existing branch-scoping mechanism untouched. `gather.py` already scopes triggers per branch using `registry.get_altered_schema_branches()` and `branches_out_of_scope`. Scoping by changed elements is applied **within** the branch already selected, so a schema change on one branch cannot broaden recompute on another (FR-010). Per Principle II, a test MUST assert this no-cross-branch-broadening property, and the merge/rebase path MUST be tested (see quickstart Scenarios H and J).

## Open items resolved

- All `NEEDS CLARIFICATION` from the spec's Clarifications sessions (2026-06-01 and 2026-06-03) are answered. No outstanding clarifications remain for planning.
