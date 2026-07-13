# Contract: Merge diff summary — converter & cache

**Plan**: [../plan.md](../plan.md) · **Decisions**: D1, D2

## Converter: `EnrichedDiffNode → NodeDiff`

New function (proposed home: `backend/infrahub/core/merge/diff_summary.py`).

**Input**: an `EnrichedDiffRoot` (`core/diff/model/path.py:497`) and its `diff_branch_name`.

**Output**: `list[NodeDiff]` (SDK TypedDict, `python_sdk/infrahub_sdk/diff.py:11-36`).

**Mapping**:

```
for node in root.nodes:
    if node.action == DiffAction.UNCHANGED: skip
    NodeDiff.id            = node.uuid
    NodeDiff.kind          = node.kind
    NodeDiff.branch        = target_branch_name        # the merge target_branch — NOT root.diff_branch_name — see below
    NodeDiff.display_label = node.label
    NodeDiff.action        = node.action.name        # UPPERCASE
    NodeDiff.elements       =
        for attr in node.attributes:  {name: attr.name, element_type: "ATTRIBUTE",
                                        action: attr.action.name,
                                        summary: {added: attr.num_added, updated: attr.num_updated, removed: attr.num_removed}}
        for rel in node.relationships (include_in_response only):
            element_type = "RELATIONSHIP_ONE" if rel.cardinality == ONE else "RELATIONSHIP_MANY"
            {name: rel.name, element_type, action: rel.action.name,
             summary: {...}, peers: [ {action: p.action.name, summary: {...}} for p in rel.relationships ]}
```

**Guarantees**:

- `action` is emitted as the **uppercase** GraphQL enum name so `_is_triggering_action`
  (`.lower()` compare) and the predicates read it identically to the PC path.
- `branch` is tagged with the **target (destination) branch name** — the merge's `target_branch`
  (i.e. `self.destination_branch`), not the source `diff_branch_name` and not a fresh
  `registry.default_branch` lookup: post-merge the changed data lives on the target branch, and
  the selection runs its live lookups there, so the summary tag and the query branch match and
  the source branch may be deleted without affecting selection (research D2, critique E3).
- Nodes changed only via a conflict resolved to the base branch are **retained** (the
  changelog narrowing is not applied here).
- A definition whose `fingerprint` attribute changed appears as an `UPDATED` node with an
  `ATTRIBUTE` element named `fingerprint` — `_definition_changed` fires on it with no special
  casing.

**Capture timing (hard requirement)**: serialization and the cache write are split around the
merge's point of no return:

- **Serialize** the already-loaded in-memory `branch_diff` (no re-load) into `list[NodeDiff]`
  before the freeze — the in-memory object is unaffected by `freeze_diffs_for_branch`.
- **`set_merge_diff_summary_cache` runs only after the merge commits** (after the
  `BranchStatus.MERGED` transition and write-block lift), immediately before the follow-up is
  submitted. A merge that rolls back therefore writes nothing — no orphan entry.

**Failure mode (hard requirement, critique E7)**: both the serialization and the cache write
MUST be wrapped in their own try/except. On any failure they log and yield
`merge_diff_cache_key = None` (→ full-regeneration fallback) and MUST NOT re-raise — a
serialization bug must never roll back a committed merge.

## Cache functions

Parallel to `set/get_diff_summary_cache` (`proposed_change/branch_diff.py:133-151`).

```
set_merge_diff_summary_cache(diff_id: str, diff_summary: list[NodeDiff], cache: InfrahubCache) -> None
    key   = f"branch_merge:diff_id:{diff_id}:diff_summary"
    value = json.dumps(diff_summary)
    expires = KVTTL.TWO_HOURS

get_merge_diff_summary_cache(diff_id: str) -> list[NodeDiff]      # raises ResourceNotFoundError on miss
```

- `diff_id` = the diff-root uuid (stable across the freeze).
- On `ResourceNotFoundError`, the caller falls back to full regeneration (never propagates the
  error to the merge).

## Consumers unchanged

`get_modified_kinds` (`branch_diff.py:122-130`), `_query_changed`, `_definition_changed`
(`tasks.py:1407-1477`) operate on `list[NodeDiff]` and require no change beyond receiving the
merge summary instead of the PC summary.
