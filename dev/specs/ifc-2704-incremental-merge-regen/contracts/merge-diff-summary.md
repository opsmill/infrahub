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
    NodeDiff.branch        = root.diff_branch_name
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
- Nodes changed only via a conflict resolved to the base branch are **retained** (the
  changelog narrowing is not applied here).
- A definition whose `fingerprint` attribute changed appears as an `UPDATED` node with an
  `ATTRIBUTE` element named `fingerprint` — `_definition_changed` fires on it with no special
  casing.

**Failure mode**: any exception during conversion is caught by the caller; the merge proceeds
and the follow-up takes the full-regeneration fallback (`merge_diff_cache_key = None`).

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
