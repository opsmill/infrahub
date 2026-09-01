# Phase 1 Data Model: Branch-Agnostic Vertex Metadata Correctness

**No new entities, no schema change, no new properties.** This feature corrects the values written
into existing graph properties. The model below records what those properties mean and which
invariants govern them, since the defect is precisely that the meaning was documented incorrectly.

## Vertex properties

| Property | Type | On | Meaning |
|---|---|---|---|
| `created_at` | timestamp? | `:Node`, `:Attribute`, `:Relationship` | When the vertex first became visible on the default branch — the `from` of its earliest `branch_level = 1` edge |
| `created_by` | string? | same | The actor on that edge (`from_user_id`) |
| `updated_at` | timestamp? | same | The latest change visible on the default branch — `max()` over the `from` / `to` of its `branch_level = 1` edges |
| `updated_by` | string? | same | The actor on the edge that supplied `updated_at` |
| `previous_updated_at` | timestamp? | same | Rollback snapshot taken by schema migration / merge before a bump. **Out of scope** — untouched by this feature |
| `previous_updated_by` | string? | same | Rollback snapshot partner. **Out of scope** |
| `branch_support` | string | `:Node`, `:Attribute`, `:Relationship` | `aware` / `local` / `agnostic`. Already persisted on every vertex; the repair migration uses it to scope its sweep without loading a schema |

All six metadata properties are nullable. NULL means "never written" — the state F6 leaves behind
permanently, and the state the repair migration must fill.

## Edge properties consulted

| Property | Meaning for this feature |
|---|---|
| `branch` | `-global-` or a branch name. `-global-` and the default branch are the two that carry level 1 |
| `branch_level` | `1` = visible on the default branch, `2` = user branch only. **The authoritative predicate** |
| `from` / `to` | Open and close times; both are candidate `updated_at` values |
| `from_user_id` / `to_user_id` | Actors; the source of `created_by` / `updated_by` |
| `status` | `active` / `deleted`; soft-delete semantics per Constitution II |

## Branch support lattice

`BranchSupportType` on a field, crossed with `BranchSupportType` on its node, decides the edge level
a field write produces. The pairs where they disagree are exactly the defect surface.

| Node support | Field support | Field edge level (update path) | Node visible on default? |
|---|---|---|---|
| aware | aware | node's branch | yes if node merged |
| aware | local | node's branch | yes if node merged |
| **aware** | **agnostic** | **1 (`-global-`)** | yes if node merged — **mismatch #1, #2** |
| agnostic | agnostic | 1 | always |
| **agnostic** | **aware** | **node's branch** | always — **mismatch #3** |
| **agnostic** | **local** | **node's branch** (update path only; the create path writes level 1) | always — **mismatch #4** |

The update path resolves a field's level through
`core/attribute.py::BaseAttribute.get_branch_based_on_support_type` (and the relationship
equivalent); the create path resolves it through `core/attribute.py::BaseAttribute.get_create_data`.
The two disagree for `local`-on-`agnostic`; see research.md R3. Each gate this feature adds mirrors
the path it guards, so the metadata is correct under either reading.

## State transitions

There are none: the properties are a derived cache, not a state machine. Every value is a pure
function of the vertex's level-1 edges at the time it is read — which is why the repair migration can
recompute it from scratch and why a second run is a no-op (SC-002).
