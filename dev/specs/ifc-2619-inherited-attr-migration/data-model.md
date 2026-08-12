# Data Model: Inherited-Attribute Migration Fix and Healing Migration

**Date**: 2026-07-31 | **Plan**: [plan.md](plan.md)

No Infrahub schema-model changes and no new persisted entity types. The feature operates on the existing graph data model; this document records the structures it reads and writes and the invariant it restores.

## Core Invariant (restored by this feature)

> Every **active** node vertex has, for every attribute its schema defines (local or inherited), an **active** attribute row on the branch where the node is visible.

- "Active" means the branch/time-resolved edge status per the priority ordering `branch_level DESC, from DESC, status ASC`.
- Deleted (tombstoned) nodes are exempt — only nodes active at evaluation time are examined.
- A node whose only row for an attribute is tombstoned counts as **violating** (the tombstone marks a deliberate delete of a *previous* row, not permission for the attribute to be absent under a schema that defines it).
- **Healing audit scope**: the healing migration audits only the attributes a kind inherits from its generics — the only rows the pre-fix damage shape can affect. Kinds and attributes are discovered from the persisted schema graph (SchemaNode `inherit_from` values → SchemaGeneric → SchemaAttribute linkage), never by loading a `SchemaBranch`; attribute properties are hydrated from the SchemaAttribute vertices with only the in-memory internal schema and core models registered.
- An attribute whose schema linkage is no longer active (removed from the generic) is dropped from the audit: its tombstoned rows are final and never re-added.

## Graph Structures Read/Written

### Attribute row (the repaired artifact)

Full structure per attribute (all created by the forward path and by healing):

```text
(node:Node:{Kind})-[:HAS_ATTRIBUTE {branch, branch_level, from, to, status}]->(attr:Attribute {name, uuid})
(attr)-[:HAS_VALUE {branch, ...}]->(av:AttributeValue {value, is_default})
(attr)-[:IS_PROTECTED {branch, ...}]->(:Boolean)
(attr)-[:IS_VISIBLE {branch, ...}]->(:Boolean)
```

- **Forward fix**: rows created by `AttributeAddQuery` at migration time on the target branch, guarded by `WHERE has_attr_e IS NULL OR has_attr_e.status = "deleted"` (idempotent).
- **Healing**: same row shape; `from` timestamps are **run-time** for every attribute. Retroactive timestamps were designed and then dropped — see "Schema-graph vertices" below.

### Node kinds targeted

- `Node:{Kind}` — concrete instances.
- `Node:Profile{Kind}` — profile instances; gain the attribute only when `check_if_attr_supports_profiles` passes (not `unique`, not `read_only`, not excluded kinds).
- `Node:Template{Kind}` — template instances; gain the attribute only when the attribute's `support_templates` predicate passes.
- `Template{Generic}` schema is a `GenericSchema` with no instances — never targeted.

### Schema-graph vertices (read-only, historical)

The schema's own graph representation records when schema elements changed. Inherited attributes are never persisted under the inheriting kind's schema vertex, so two owner-side timelines together bound the damage window: the generic's linkage to the `SchemaAttribute` vertex (when the generic gained the attribute) and the inheriting kind's `inherit_from` value edge (when the kind began inheriting the generic).

> **Superseded.** The retroactive-timestamp design below was implemented and then dropped:
> healed rows are created at run time, and branches receive their repairs when they rebase.
> `AttributeAddQuery` no longer accepts a `write_at` argument. Kept for the derivation
> rationale, which still documents why the damage window is bounded by two owner-side
> timelines.

**Retroactive timestamp rule (FR-006, superseded)** per (node kind, attribute):

```text
heal_from = `from` time of the latest active IS_RELATED edge pair linking the generic's
            schema vertex to the SchemaAttribute vertex, branch-resolved across the full
            same-UUID schema-vertex set (schema updates duplicate schema vertices while
            keeping the UUID)
heal_from = max(heal_from, heal_floor)   # heal_floor = `from` of the kind's latest active
                                         # inherit_from value edge (inheritance began)
heal_from = tombstone_time(node, attribute) + ε  if tombstone_time >= heal_from
                                                 # never predate (or equal) a tombstone
```

A pair whose latest schema linkage is **not** active carries no derivable timestamp: it is reported as damaged-but-unrepairable and fails the migration loudly rather than being silently healed at a guessed time.

### NumberPool entities (existing, reused)

- `CoreNumberPool` registered against the **generic's** kind — exactly one pool per (kind, attribute) identifier. Healing looks the pool up by (generic kind, attribute name, schema pool type) and **fails the migration loudly when it is missing** (the schema change that introduced the attribute provisions it); healing never creates a pool.
- Allocations via `CoreNumberPool.get_resource` — reservation-aware; returns an existing reservation for the same identifier (no duplicate allocation on repeat runs).
- Healed NumberPool rows are created at **run time**, not retroactively, so allocation uniqueness checks see all current reservations. The healed row matches the runtime allocation shape: the value lives on an `is_default: false` value vertex and the row carries a `HAS_SOURCE` edge to the pool node.
- **Branch-level pool damage is deferred**: allocations cannot be backdated and must follow the default branch's, so a branch's pool-backed pairs are repaired during the branch's post-upgrade rebase (`execute_against_branch`), not at upgrade time. Upgrade-time validation excludes this deferred scope; the rebase-time pass re-validates it before returning.

### Branch (existing, read/iterated)

- Default branch: repaired at upgrade time, defaults and pools alike. Rows carry run-time timestamps, so they are not visible to a branch until that branch rebases.
- Non-default branches: repaired by each branch's post-upgrade rebase, not during the upgrade. Discovery is **branch-scoped** — only kinds whose inherited attributes go beyond the default branch's schema are audited — so the pass touches branch-origin damage only, and the default branch's rows are already visible post-rebase.
- The upgrade marks stale branches `NEED_UPGRADE_REBASE`, which is what schedules that pass.

## Migration Records (existing framework)

- **Schema migrations** (PR 1): no new migration names; `node.inherit_from.update` / `node.name.update` / `node.namespace.update` (backed by `NodeKindUpdateMigration`) gain sub-migration behavior; `node.attribute.add` gains the `force_inherited` field (in-memory model only — not persisted).
- **Graph migration** (PR 2): `m076_heal_missing_attribute_rows`, a `MigrationRequiringRebase` with `minimum_version: 74`; `execute()` runs at upgrade time (default branch + branch-scoped default-backed passes), `execute_against_branch()` runs during each branch's rebase (deferred pool-backed damage). `GRAPH_VERSION` bumps 74 → 75 on the `Root` vertex after successful upgrade, which is what makes the healing one-shot.

## State Transitions

```text
Damaged install (missing rows)
  --[upgrade: m076 pass 1]--> default branch satisfies invariant (defaults + pools)
  --[upgrade: m076 pass 2]--> each branch satisfies invariant for branch-changed
                              default-backed data; pool pairs deferred to rebase
  --[m076 self-validation]--> PASS: GRAPH_VERSION=75 recorded | FAIL: upgrade aborts with per-kind errors
  --[branch rebase: m076 execute_against_branch]--> branch pool pairs allocated + re-validated
Healthy install
  --[upgrade: m076]--> zero writes, validation passes trivially
Post-fix schema load (kind gains generic)
  --[phase 1: kind-update + forced attribute-adds]--> invariant holds for new inheritance
  --[phase 2: remaining migrations]--> unchanged semantics, now race-free
```
