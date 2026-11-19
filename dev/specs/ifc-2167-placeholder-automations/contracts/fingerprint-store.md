# Contract: `TemplateFingerprintRepository` and carry-over

Internal contract. Nothing here is exposed through GraphQL, REST or the web interface. See [data-model.md](../data-model.md) for the record and [research.md](../research.md) Decisions 2, 3, 8, 9 and 10.

## Repository

`TemplateFingerprintRepository(db: InfrahubDatabase)`. Each method runs one Query class. Every query names the `TemplateFingerprint` label and uses parameters only (Principles V and VI).

| Method | Query shape | Notes |
|---|---|---|
| `get_by_family(family) -> list[RecordedFingerprint]` | `MATCH (f:TemplateFingerprint {family: $family}) RETURN f.branch, f.kind, f.fingerprint` | Returns only the three properties. Result read through a frozen dataclass `get_data()` |
| `upsert(records: list[RecordedFingerprint]) -> None` | `UNWIND $records AS r MERGE (f:TemplateFingerprint {family: r.family, branch: r.branch, kind: r.kind}) ON CREATE SET f.uuid = r.uuid SET f.fingerprint = r.fingerprint` | One query for all records. No-op on an empty list |
| `insert_missing(records: list[RecordedFingerprint]) -> int` | Same `MERGE`, with `ON CREATE SET f.uuid = r.uuid, f.fingerprint = r.fingerprint` only | Used by the carry-over and the first-start seed; never overwrites. Returns the number created |
| `delete(keys: list[FingerprintKey]) -> None` | `UNWIND $keys AS k MATCH (f:TemplateFingerprint {family: k.family, branch: k.branch, kind: k.kind}) DETACH DELETE f` | One query |
| `delete_branch(branch: str) -> None` | `MATCH (f:TemplateFingerprint {branch: $branch}) DETACH DELETE f` | Called by `BranchDataDeleter` |

Callers that write hold the lock `configure-action-rules-<trigger type>` for the family, except `delete_branch` (the branch is being deleted and no flow writes its records once it is out of scope) and `insert_missing` (idempotent).

## Collector

`collect_schema_fingerprints(family) -> SchemaFingerprints` reads `registry.default_branch` and `registry.get_altered_schema_branches()`, and for each branch in scope reads `get_template_nodes()` of the family from `registry.schema.get_schema_branch(name=branch)` and takes `get_hash()` of each entry. No database or task manager access.

## Carry-over

`carry_over_placeholder_fingerprints(deleted: list[Automation], schema: SchemaFingerprints per family, repository) -> int`

Input: the Prefect `Automation` objects in `TriggerSetupReport.deleted`.

An automation is carried over when all of these hold:

1. Its name starts with `display_label_jinja2::` or `human_friendly_id::`.
2. Its trigger matches only the field `TRIGGER_PLACEHOLDER_FIELD`.
3. Its name, without the family prefix and split from the right on `::` three times, gives `<branch>`, `<kind>`, `by`, `<kind>` with the same kind twice.
4. Its description ends with `| hash:<value>` and `<value>` is not empty.
5. `<branch>` is in scope for the family.

Each matching automation becomes one record passed to `insert_missing`. An automation that fails a check is skipped and logged at debug level. The function is idempotent: running it twice creates no extra record and overwrites none.

Callers:

| Caller | When |
|---|---|
| `trigger/tasks.py::trigger_configure_all` | `infrahub upgrade` step 5, and the `TRIGGER_CONFIGURE_ALL` workflow |
| Display label and HFID setup flows | Step 2 of [recompute-decision.md](./recompute-decision.md) |

## First-start seed

`workflows/initialization.py::setup_task_manager_identifiers` calls `insert_missing` with the collector output of both families for every branch in scope. No recompute is submitted (research Decision 9).
