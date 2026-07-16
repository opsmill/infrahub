# Phase 0 Research: Selective Recompute of Transform-Based Computed Attributes

The spec is precise about behaviour but leaves the mechanism ("recompute
automation is an implementation detail confirmed in planning") open. This document
records the resolved decisions and the exact codebase facts they rest on. Every
decision is checked against the real code; where the epic's framing and the code
disagree, the code wins and the disagreement is called out.

## Decision 1 - Static kind-scoped lifecycle triggers, not per-transform gathered automations

**Decision**: Replace `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT` with **three
static `BuiltinTriggerDefinition`s**, one per transform lifecycle
(created / updated / deleted), each matching on `infrahub.node.kind ==
CoreTransformPython`. The fired workflow resolves the transform node from the event
payload to the computed attribute(s) it feeds and recomputes only those. The triggers
are not per-transform and not per-attribute; there is exactly one create trigger, one
update trigger, one delete trigger for the whole system.

**Why the alternative was rejected.** The data-path triggers in
`computed_attribute/models.py` (`ComputedAttrPythonTriggerDefinition`,
`ComputedAttrPythonQueryTriggerDefinition`) are gathered per (branch, attribute) by
`gather_trigger_computed_attribute_python` (`gather.py:147`) and reconciled by
`setup_triggers` (`trigger/setup.py:66`). That model gives free teardown: when a
definition drops out of the gathered set, `to_delete = set(automation_names) -
set(trigger_names)` (`trigger/setup.py:107`) deletes its automation. It is the right
shape for triggers keyed on schema content that must be regenerated whenever the schema
changes.

A per-transform gathered model for the *lifecycle* triggers would be circular. To
gather "one update automation per transform" you must first enumerate the transforms,
which requires a database read on every relevant change and a setup flow to run. But
the whole point of this feature is to stop running a branch-wide setup on every commit.
A gathered per-transform trigger set would need something to trigger its own
re-gathering on transform create/delete, which is exactly the lifecycle event we are
already reacting to. That is a setup flow chasing its own tail.

The static model breaks the cycle. Three fixed automations, registered once at startup
in `builtin_triggers` (`trigger/catalogue.py:15`), match every transform of the kind.
The transform-to-attributes resolution happens at *task* time from live schema state,
not at *gather* time from a snapshot. There is nothing per-transform to create or tear
down, so:

- **Create/delete need no per-transform automation lifecycle.** The delete trigger does
  not remove an automation (there is none per transform); it recomputes nothing and
  simply lets the now-absent transform stop producing fingerprint-update events. See
  Decision 5 for how FR-005 ("tear down the per-attribute recompute automation") is
  satisfied under this model.
- **No setup flow runs on every commit.** The static triggers exist for the process
  lifetime; only the recompute workflow runs, and only when a fingerprint actually
  changes.

**Trade-off accepted.** The static trigger must resolve transform -> attributes at task
time (a schema-branch lookup, see Decision 2), where the gathered model would have
baked that mapping into the automation's parameters. This is a cheap in-memory lookup
against `registry.schema` and is already how `process_transform` (`tasks.py:155`)
resolves the transform for a node. The cost is trivial and the resolution is always
against current schema, which is strictly more correct than a snapshot.

**Codebase facts.**

- `BuiltinTriggerDefinition` (`trigger/models.py:301`) has `type = TriggerType.BUILTIN`
  and `generate_name()` -> `f"{type}::{name}"` (`trigger/models.py:285`). Builtin
  automations are reconciled together as one set; they are not branch-specific
  (`TriggerType.is_branch_specific` at `trigger/models.py:119` does not include BUILTIN).
- The existing `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` (`triggers.py:29`) is already a
  `BuiltinTriggerDefinition` that resolves scope inside its workflow rather than baking
  it into per-attribute automations. The new lifecycle triggers follow that same shape.
- `NodeMutatedEvent.get_resource()` (`node_action.py:146`) carries
  `infrahub.node.kind`, `infrahub.node.id`, `infrahub.branch.name`, and
  `NODE_ORIGIN_LABEL`. `get_related()` (`node_action.py:29`) emits one related resource
  per changed attribute with role `infrahub.node.attribute_update` and
  `infrahub.field.name`. Both are exactly what the match/match_related need.

## Decision 2 - Resolve transform -> attributes via `python_attributes_by_transform`, fan out with the existing `trigger_update_python_computed_attributes`

**Decision**: The lifecycle workflow reads the fired transform's **name** and **branch**
from the event, then looks up the attributes it feeds through
`schema_branch.computed_attributes.python_attributes_by_transform`
(`facade.py:56`), which returns `dict[transform_name -> list[PythonDefinition{kind,
attribute}]]` (`python_transform.py:91`). For each `PythonDefinition` it submits the
existing `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` workflow
(`catalogue.py:414` / `tasks.py:221`), one submission per (attribute kind,
attribute name).

**Why reuse `trigger_update_python_computed_attributes`.** That flow already does
exactly the required fan-out: `nodes = await get_client().all(kind=computed_attribute_kind,
branch=branch_name)` then chunks the ids and submits `COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM`
per chunk (`tasks.py:229-248`). It recomputes the attribute across **all** nodes of the
attribute's kind, which is FR-004 ("recompute across all nodes of that attribute's
kind"). It takes exactly `(branch_name, computed_attribute_name, computed_attribute_kind,
context)` - the four values the resolution produces. No change to it is needed.

**Why this is narrower than today.** Today `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT`
(`triggers.py:10`) fires `computed_attribute_setup_python` (`tasks.py:519`) on every
commit with `changed_elements = None`. In `computed_attribute_setup_python` the scoper
sees `changed_elements is None` and returns `fallback_full_recompute=True`, selecting
**every** candidate attribute (`scoping.py:132`). It then submits
`TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` for each selected ref (`tasks.py:586`). So a
commit recomputes every transform-based attribute on the branch. The new path submits
`TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` only for the attributes fed by the **one**
transform whose fingerprint changed. The narrowing is entirely in *which* attributes get
the fan-out; the fan-out itself is unchanged (FR-008, SC-002, SC-003).

**Decision: new flow entry, not parameterize the existing setup flow.** Add one new
Prefect flow (e.g. `process_transform_lifecycle`) in `computed_attribute/tasks.py`, not a
new parameter on `computed_attribute_setup_python`. Justification:

- `computed_attribute_setup_python` also reconciles the data-path automations via
  `setup_triggers` (`tasks.py:597-612`) - the `ComputedAttrPythonTriggerDefinition` /
  `ComputedAttrPythonQueryTriggerDefinition` sets that react to *node* changes feeding a
  transform's query. That reconciliation must still run on schema change (it is
  driven by `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA`, which stays). Overloading it with a
  per-transform-event mode would tangle two responsibilities in one flow: single-transform
  recompute vs. branch-wide automation reconciliation. That violates single responsibility
  (`.agents/rules/backend-component-design.md`).
- The new flow's job is pure resolution + fan-out with no `setup_triggers` call and no
  scoper. It is small and independently testable.

**Codebase facts.**

- `python_attributes_by_transform` is keyed by transform *name* (`python_transform.py:96`),
  and the fingerprint event carries the transform's node id and kind, not its name. The
  new flow must look the transform up by id to get its name, or key the resolution by id.
  `process_transform` already fetches a transform by id via `ComputedAttributeTransformQuery`
  (`tasks.py:182`); the same query resolves id -> name. See the contract for the exact shape.
- `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` required params are `branch_name`,
  `computed_attribute_name`, `computed_attribute_kind`, `context` (`tasks.py:221`).

## Decision 3 - The update trigger filters to origin=LIVE and field=fingerprint; loop and merge/rebase safety fall out

**Decision**: The **update** trigger sets:

- `match = {"infrahub.node.kind": InfrahubKind.TRANSFORMPYTHON, NODE_ORIGIN_LABEL:
  NodeMutationOrigin.LIVE.value}`
- `match_related = {"prefect.resource.role": ["infrahub.node.attribute_update"],
  "infrahub.field.name": ["fingerprint"]}`

This mirrors the data-path shape in `models.py:165-175` exactly (kind on `match`,
origin=LIVE on `match`, role+field on `match_related`), narrowed to the single
`fingerprint` field.

**Merge/rebase replay safety (FR-010).** `origin=LIVE` on the match excludes replays.
Rebase stamps `meta.origin = NodeMutationOrigin.REBASE` (`core/branch/tasks.py:280`);
merge stamps `meta.origin = NodeMutationOrigin.MERGE` (`core/merge/post_merge.py:148`).
The event default is `NodeMutationOrigin.LIVE` (`events/models.py:78`). A merge/rebase
that replays a fingerprint change carries MERGE/REBASE origin, so it does not match, so
it does not fire this trigger. The dedicated coalesced merge/rebase recompute path
(`core/merge/recompute_coalescing`, driven from `post_merge.py` and `branch/tasks.py`)
handles those, unchanged (SC-006).

**Recompute-write loop safety (FR-011).** This is the one place the epic's framing is
inaccurate and must be corrected. There is **no `RECOMPUTE` value** in
`NodeMutationOrigin`; the enum is `LIVE / MERGE / REBASE` only (`events/constants.py:8`).
The recompute write itself
(`UpdateComputedAttribute.mutate`, `graphql/mutations/computed_attribute.py:111`) emits a
`NodeUpdatedEvent` stamped `origin=NodeMutationOrigin.LIVE` (line 122). So origin does
**not** distinguish a recompute write from a live edit. The loop is prevented by a
different, stronger property: the recompute write targets the **computed attribute's own
node kind** (e.g. `TestingCar`), not `CoreTransformPython`, and touches the computed
attribute field, not `fingerprint`. Our trigger matches only
`kind == CoreTransformPython` AND `field == fingerprint`. A recompute write can never
satisfy both, so it can never re-fire the trigger. No origin filter is needed for loop
safety; the kind+field match is sufficient and is the real guarantee.

**Why keep origin=LIVE on the match anyway.** Even though loop safety comes from
kind+field, merge/rebase *do* replay changes to the transform node's own `fingerprint`
attribute (fingerprint is a branch-aware attribute that participates in merge/rebase).
Those replays are `kind==CoreTransformPython` and `field==fingerprint` - they WOULD match
without the origin filter. So origin=LIVE is load-bearing for FR-010 (merge/rebase), not
for FR-011 (loop). Both requirements are satisfied, by two different mechanisms.

**Codebase facts.**

- `NodeMutationOrigin(StrEnum)`: `LIVE`, `MERGE`, `REBASE` (`events/constants.py:8-13`).
  No RECOMPUTE.
- Override sites: `core/branch/tasks.py:280` (REBASE), `core/merge/post_merge.py:148`
  (MERGE), default `events/models.py:78` (LIVE).
- `UpdateComputedAttribute.mutate` writes with `origin=NodeMutationOrigin.LIVE`
  (`graphql/mutations/computed_attribute.py:122`) and the event kind is the target
  node's kind (`node_schema.kind`, line 112), never `CoreTransformPython`.
- The importer writes the transform through `self.sdk.create(...)` / `obj.save()` and
  `existing_transform.save()` (`git/integrator.py:1772`, `1806`), the standard SDK-over-
  GraphQL path from the git worker, which produces node events with the default
  `origin=LIVE`. So the import write DOES match our LIVE trigger (this is required, not a
  bug).

## Decision 4 - Create trigger: initial compute; fires only when the transform node is created

**Decision**: The **create** trigger sets:

- `match = {"infrahub.node.kind": InfrahubKind.TRANSFORMPYTHON, NODE_ORIGIN_LABEL:
  NodeMutationOrigin.LIVE.value}`
- `match_related` omitted (or role-only). A newly created transform node's changelog
  reports its attributes; there is no need to filter on `fingerprint` because the create
  is itself the signal that a brand-new transform arrived (its attribute(s) must be
  computed for the first time regardless of the fingerprint value, per FR-002).

The create workflow does the same resolution + fan-out as update (Decision 2): resolve
transform -> attributes, submit `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` for each. For
a create, this is the "initial setup and first computation" of the attribute(s) the new
transform feeds (FR-002, edge case "New transform on import").

**Why create is distinct from update.** A brand-new transform's import is a
`NodeCreatedEvent`, not a `NodeUpdatedEvent` - the changelog has no "previous" and the
event name differs (`node_action.py:161` vs `:169`). If only an update trigger existed,
a brand-new transform whose fingerprint goes null->value on first import would still fire
(it is an attribute change), but the cleaner and explicit contract is a dedicated create
trigger so first-import population never depends on the fingerprint field being present in
the create changelog. Both the create path (brand-new transform) and the update path
(null->value on a pre-existing transform) lead to exactly one recompute (FR-013, US6).

## Decision 5 - Delete trigger: no per-transform automation to remove under the static model

**Decision**: The **delete** trigger sets:

- `match = {"infrahub.node.kind": InfrahubKind.TRANSFORMPYTHON}` (origin filter optional;
  a delete replayed by merge/rebase is handled by the coalesced path, so origin=LIVE is
  applied for consistency with create/update).

Under the static-trigger model there is **no per-transform recompute automation to tear
down** - the three lifecycle automations are kind-scoped and shared by all transforms, so
deleting one transform never leaves a dangling automation. This satisfies FR-005 and US5
("no automation survives for a transform that no longer exists") by construction: nothing
per-transform ever exists.

**What the delete trigger still must do.** Two real cleanups are per-transform and must
be reconciled on delete:

1. The **data-path automations** (`ComputedAttrPythonTriggerDefinition` /
   `ComputedAttrPythonQueryTriggerDefinition`) that react to node changes feeding the
   deleted transform's query. These are gathered from the schema
   (`gather.py:147`); when the computed attribute is removed from the schema, a
   `setup_triggers` run deletes them via `to_delete` (`trigger/setup.py:107`). This
   reconciliation is already driven by `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` on schema
   change, which stays in place. Deleting the *transform node* does not by itself remove
   the computed-attribute *schema* definition; the schema-change path handles the
   automation teardown when the attribute is removed. The transform-delete trigger's job
   is therefore to stop recompute, not to reconcile data-path automations.
2. There is nothing else to remove. The delete trigger's workflow may simply log and
   return, or be omitted entirely if we accept that a deleted transform stops emitting
   fingerprint events on its own. **Recommendation:** register the delete trigger for
   symmetry and observability, with a no-op/log workflow, so US5's "the automation is
   gone" assertion is testable as "no lifecycle recompute fires for the deleted
   transform" rather than requiring per-transform automation enumeration.

**Consequence for testing US5.** The test asserts that after deleting a transform,
subsequent commits produce zero recompute for the attribute it fed. Under the static
model this holds because (a) no fingerprint-update event is emitted for a node that no
longer exists, and (b) the resolution `python_attributes_by_transform` no longer contains
the deleted transform, so even a stray event resolves to zero attributes.

## Decision 6 - Null-fingerprint self-heal needs no special code

**Decision**: Rely on the ordinary create/update triggers. No null-specific branch is
added.

- **Brand-new transform (first-ever import):** a `NodeCreatedEvent` -> create trigger ->
  one recompute (FR-002).
- **Pre-feature transform, first post-upgrade import (null -> value):** the importer's
  `existing_transform.save()` writes the new fingerprint. `fingerprint` transitions from
  null to a value, which is an attribute change, so `get_related()` emits an
  `infrahub.node.attribute_update` related resource with `infrahub.field.name ==
  "fingerprint"` (`node_action.py:35-50`). The update trigger matches -> one recompute
  (FR-013).
- **Subsequent no-op import (watch-declared):** `existing_transform.fingerprint.value ==
  fingerprint`, so `update_python_transform` does not change it (`git/integrator.py:1782`)
  and the compare-and-skip in the apply loop (`integrator.py:536`) avoids a write.
  No fingerprint change -> no event -> no recompute (SC-008).

The invariant "null means unknown means recompute" holds automatically: a null
fingerprint only ever becomes non-null through an import write, and that write is exactly
the change event the trigger reacts to. There is no code path where a null fingerprint is
read and a skip decision is made, because this feature does not read the fingerprint value
at all - it reacts to the *event of it changing*. This is a key simplification versus
IFC-2844's consumer framing.

## Decision 7 - No-watch transforms: unchanged behaviour, now scoped

**Decision**: No special handling. A no-watch transform folds the commit id into its
fingerprint (IFC-2844 behaviour), so its fingerprint changes on every commit. Each such
change is an update event -> the update trigger fires -> only that transform's attributes
recompute (FR-014, US4). The scoping to "only this transform's attributes" is inherent in
the resolution (Decision 2): the event names one transform, resolution yields only its
attributes. A no-watch transform is never starved (it recomputes every commit) and never
fans out to unrelated attributes.

## Removed and confirmed-separate paths (FR-009)

**Removed:** `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT` (`triggers.py:10`) and its
entry in `builtin_triggers` (`trigger/catalogue.py:19`). This is the only trigger that
maps `CommitUpdatedEvent` -> `COMPUTED_ATTRIBUTE_SETUP_PYTHON` for the full-sweep Python
recompute.

**Must remain (grep-confirmed separate):**

- `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` (`triggers.py:29`) reacts to
  `SchemaUpdatedEvent` / `BranchDeletedEvent` and drives both Jinja2 and Python setup with
  `changed_elements` forwarded. This is the schema path; it is orthogonal and stays.
- The coalesced merge/rebase recompute (`core/merge/recompute_coalescing`, invoked from
  `post_merge.py` and `branch/tasks.py`) stays.
- `CommitUpdatedEvent` still exists and is still emitted by the importer
  (`git/integrator.py:399`); other consumers (if any) are unaffected. Only the
  computed-attribute-python subscription to it is removed.

**Grep evidence.** `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT` is referenced only in
`computed_attribute/triggers.py` (definition) and `trigger/catalogue.py` (registration).
No test references it. `computed_attribute_setup_python` remains reachable only via
`TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` after removal, so its `changed_elements`-driven
scoping still runs for schema changes.

## Open items for reviewer confirmation (non-blocking)

1. **Delete-trigger workflow.** Register a no-op/log delete trigger (Decision 5) vs. omit
   the delete trigger entirely. Recommendation: register it for testability and symmetry.
2. **Resolution keyed by id vs. name.** The event carries the transform id; resolution is
   keyed by name. Recommendation: resolve id -> name via the existing transform query,
   then look up `python_attributes_by_transform[name]`. Keeps one source of truth.
3. **Branch scoping of the static triggers.** Builtin triggers are not branch-specific;
   the fired workflow receives `branch_name` from the event resource and resolves against
   that branch's schema. Confirm this matches the branch-aware fan-out already done by
   `trigger_update_python_computed_attributes` (it takes `branch_name` explicitly).
