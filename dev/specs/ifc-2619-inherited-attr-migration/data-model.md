# Data Model: Inherited-Attribute Migration Fix and Healing Migration

**Date**: 2026-07-31 | **Plan**: [plan.md](plan.md)

No Infrahub schema-model changes and no new persisted entity types. The feature operates on the existing graph data model; this document records the structures it reads and writes and the invariant it restores.

## Core Invariant (restored by this feature)

> Every **active** node vertex has, for every attribute its schema defines (local or inherited), an **active** attribute row on the branch where the node is visible.

- "Active" means the branch/time-resolved edge status per the priority ordering `branch_level DESC, from DESC, status ASC`.
- Deleted (tombstoned) nodes are exempt — only nodes active at evaluation time are examined.
- A node whose only row for an attribute is tombstoned counts as **violating** (the tombstone marks a deliberate delete of a *previous* row, not permission for the attribute to be absent under a schema that defines it).

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
- **Healing**: same row shape; `from` timestamps are **retroactive** (see below) for default-backed attributes, run-time for NumberPool attributes.

### Node kinds targeted

- `Node:{Kind}` — concrete instances.
- `Node:Profile{Kind}` — profile instances; gain the attribute only when `check_if_attr_supports_profiles` passes (not `unique`, not `read_only`, not excluded kinds).
- `Node:Template{Kind}` — template instances; gain the attribute only when the attribute's `support_templates` predicate passes.
- `Template{Generic}` schema is a `GenericSchema` with no instances — never targeted.

### Schema-graph vertices (read-only source for retroactive timestamps)

The schema's own graph representation records when schema elements changed:

- The **kind's schema node** and its `inherit_from` state → when the kind began inheriting the generic.
- The **generic's schema node** and its attribute vertices → when the generic gained each attribute.

**Retroactive timestamp rule (FR-006)** per (node kind, attribute):

```text
heal_from = max(inherit_began_at(kind, generic), attribute_added_at(generic, attribute))
heal_from = max(heal_from, tombstone_time(node, attribute) + ε)   # never predate a tombstone
```

### NumberPool entities (existing, reused)

- `CoreNumberPool` registered against the **generic's** kind (`SchemaNumberPoolUpserter._get_pool_kind`) — exactly one pool per (kind, attribute) identifier; healing/forward-fix must not create duplicates.
- Allocations via `CoreNumberPool.get_resource` — reservation-aware; returns an existing reservation for the same identifier (no duplicate allocation on repeat runs).
- Healed NumberPool rows are created at **run time**, not retroactively, so allocation uniqueness checks see all current reservations.

### Branch (existing, read/iterated)

- Default branch: pass 1 target; retroactive timestamps < `branched_from` of pre-existing branches make repairs visible on those branches without rebase.
- Non-default branches: pass 2 iterates all existing (non-deleted) branches; detection is **branch-scoped** — only data changed on the branch is considered (branch-level edges), so branch-originated damage is repaired at branch level.

## Migration Records (existing framework)

- **Schema migrations** (PR 1): no new migration names; `node.inherit_from.update` / `node.name.update` / `node.namespace.update` (backed by `NodeKindUpdateMigration`) gain sub-migration behavior; `node.attribute.add` gains the `force_inherited` field (in-memory model only — not persisted).
- **Graph migration** (PR 2): `m075_heal_missing_attribute_rows`, `minimum_version: 74`; `GRAPH_VERSION` bumps 74 → 75 on the `Root` vertex after successful upgrade, which is what makes the healing one-shot.

## State Transitions

```text
Damaged install (missing rows)
  --[upgrade: m075 pass 1]--> default branch satisfies invariant
  --[upgrade: m075 pass 2]--> each branch satisfies invariant for branch-changed data
  --[m075 self-validation]--> PASS: GRAPH_VERSION=75 recorded | FAIL: upgrade aborts with per-kind errors
Healthy install
  --[upgrade: m075]--> zero writes, validation passes trivially
Post-fix schema load (kind gains generic)
  --[phase 1: kind-update + forced attribute-adds]--> invariant holds for new inheritance
  --[phase 2: remaining migrations]--> unchanged semantics, now race-free
```
