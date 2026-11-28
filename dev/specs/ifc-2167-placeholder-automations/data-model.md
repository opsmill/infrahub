# Data Model: Recorded template fingerprints

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

## `TemplateFingerprint` (Neo4j vertex, internal)

One vertex per derived-value family, per kind and per branch that owns its own definitions. It is a `StandardNode` subclass (label = class name), like `Preference` and `Branch`. It is not part of the user schema, has no edges, and is not exposed in GraphQL, REST or the web interface (FR-011).

| Property | Type | Description |
|---|---|---|
| `uuid` | `str` | Set by `StandardNode` on creation. Not used for lookups |
| `family` | `str` (`TemplateFamily` value) | `display_label_jinja2` or `human_friendly_id` |
| `branch` | `str` | Name of the branch the fingerprint belongs to: the default branch, or a branch returned by `Registry.get_altered_schema_branches()` |
| `kind` | `str` | Kind that defines the display label template or the HFID |
| `fingerprint` | `str` | Value of `get_hash()` of the definition that was last applied on that branch (research Decision 11) |

**Identity**: `(family, branch, kind)`. Uniqueness is kept by `MERGE` on these three properties inside the per-family distributed lock (research Decisions 3 and 6). There is no database constraint.

**Branch handling**: The branch is a plain property, as on `DiffRoot.diff_branch`. The vertex is not branch-aware and has no temporal history: an update overwrites `fingerprint`, a deletion removes the vertex (see plan.md, Complexity Tracking).

**Size**: at most (number of kinds with a display label template + number of kinds with an HFID) × (number of branches that own their schema + 1).

## `TemplateFamily` (enum)

| Value | Source of the definitions | Recompute workflow |
|---|---|---|
| `display_label_jinja2` | `schema_branch.display_labels.get_template_nodes()` | `TRIGGER_UPDATE_DISPLAY_LABELS` |
| `human_friendly_id` | `schema_branch.hfids.get_template_nodes()` | `TRIGGER_UPDATE_HFID` |

The values match the `TriggerType` values of the two families so that the carry-over can map an automation name prefix to a family without a lookup table.

## In-memory values (frozen dataclasses)

| Name | Fields | Produced by | Used by |
|---|---|---|---|
| `FingerprintKey` | `family`, `branch`, `kind` | the collector and the repository | the decision and the repository |
| `RecordedFingerprint` | `key: FingerprintKey`, `fingerprint: str` | `TemplateFingerprintRepository` reads (the `get_data()` of the Query result) | the decision |
| `SchemaFingerprints` | `family`, `by_branch: dict[str, dict[str, str]]` (branch → kind → fingerprint) for the default branch and every branch in scope | the collector, from the schema registry | the decision, the first-start seed |
| `FingerprintDecision` | `to_recompute: list[str]` (kinds on the event branch), `to_record: list[RecordedFingerprint]`, `to_delete: list[FingerprintKey]`, `skipped_identical: list[str]` (for logging) | the decision | the setup flows |

## Validation rules

- `family` is one of the `TemplateFamily` values; any other value read from the database is ignored and deleted at the next reconciliation of that branch.
- `branch` must be the default branch or a branch in scope at write time. The carry-over drops placeholders whose branch is not in scope (research Decision 8).
- `fingerprint` is a non-empty string. The carry-over skips an automation whose description has no `| hash:` suffix.

## Lifecycle

```text
                    schema update on branch B (SchemaUpdatedEvent)
  (no record) ───────────────────────────────────────────────▶ recorded
      ▲          after the recompute is submitted, or when B's     │
      │          template equals the default branch template       │
      │                                                            │ template changed on B:
      │                                                            │ recompute submitted, then
      │                                                            ▼ fingerprint overwritten
      │                                                         recorded
      │
      └── deleted when: B is deleted (branch deleter), B no longer owns its schema,
          the kind is removed, or the kind's template is removed
```

Two other ways to create a record, both without a recompute:

- **Carry-over** from a deleted placeholder automation (upgrade, or the first setup run on the new release), only when no record exists.
- **First-start seed** (`setup_task_manager_identifiers` on initial setup), only when no record exists.

## Relationship with the remaining automations

- Display label and HFID automations that react to a peer attribute change stay in the task manager and keep the target hash in their description (research, "Points left as they are").
- Jinja2 computed attributes have no record (research Decision 1). Their self-targeting trigger nodes are no longer turned into automations.
