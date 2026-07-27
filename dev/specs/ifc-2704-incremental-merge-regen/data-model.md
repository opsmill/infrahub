# Data Model: Incremental generator & artifact execution on merge

**Date**: 2026-07-10 · **Plan**: [plan.md](./plan.md)

This feature introduces **no new persisted (Neo4j) entities** and **no schema fields**. It
reuses existing schema attributes and introduces in-memory / cache-transported data shapes and
two message-model changes. Entities below are the data the selection path reads and writes.

## 1. Merge diff summary (cache-transported)

The authoritative "what changed" record for a merge, serialized into the SDK `NodeDiff` shape
so the existing selection predicates consume it unchanged.

- **Shape**: `list[NodeDiff]` (`python_sdk/infrahub_sdk/diff.py`).
- **Element**: `NodeDiff = {branch: str, kind: str, id: str, action: str, display_label: str, elements: list[NodeDiffElement]}`.
  - `NodeDiffElement = {name: str, element_type: str, action: str, summary: {added,updated,removed}, peers?: list[NodeDiffPeer]}`.
  - `element_type ∈ {"ATTRIBUTE", "RELATIONSHIP_ONE", "RELATIONSHIP_MANY"}`.
  - `action` is the **uppercase** GraphQL enum name (`"ADDED" | "UPDATED" | "REMOVED"`).
- **Source**: `EnrichedDiffRoot.nodes` (`backend/infrahub/core/diff/model/path.py`), filtered
  to `node.action != DiffAction.UNCHANGED`, including relationship/membership changes.
- **Validation rules**:
  - Nodes with `action == UNCHANGED` are excluded.
  - Nodes whose only change was a conflict resolved to the base branch **are retained** (do not
    apply the changelog `_keep_branch_update` narrowing).
  - `id` is the node uuid; must be non-empty.
- **Lifecycle**: produced once per merge in the orchestrator; stored in `InfrahubCache` with
  TTL `KVTTL.TWO_HOURS`; read once by the selection routine in the follow-up; never mutated.

## 2. Merge diff cache entry

- **Key**: `branch_merge:diff_id:{diff_root_uuid}:diff_summary` (parallel to the PC key
  `proposed_change:pipeline:pipeline_id:{pipeline_id}:diff_summary`).
- **`diff_root_uuid`**: `EnrichedDiffRootMetadata.uuid` (`path.py`) — stable across the
  merged/frozen marking, unlike the tracking id.
- **Value**: `json.dumps(list[NodeDiff])`.
- **Cache-miss semantics**: absence (expired / never written / capture failed) → full
  regeneration fallback (Decision 6). Never an error to the merge.

## 3. Threaded parameter — `merge_diff_cache_key`

- **Type**: `str | None`.
- **Flow**: `BranchMergeOrchestrator.merge` → `PostMergeDispatcher.run_follow_ups` →
  `BRANCH_MERGE_POST_PROCESS` parameters → `post_process_branch_merge`.
- **`None`**: capture skipped/failed, or an older in-flight submission → fallback path.
- **Rule**: only this string crosses the Prefect boundary; the payload never does.

## 4. Regeneration definition (reused, in-memory)

Structural `RegenerationDefinition` protocol (`core/regeneration/models.py`), satisfied
by `ProposedChangeArtifactDefinition` and `ProposedChangeGeneratorDefinition`
(`generators/models.py`). Fields read by the gates:

| Field | Type | Used by |
|---|---|---|
| `definition_id` | `str` | `_definition_changed` (incl. fingerprint change) |
| `definition_name` | `str` | diagnostics |
| `query_id` | `str` | `_query_changed` |
| `query_name` | `str` | diagnostics |
| `query_models` | `list[str]` | `MODIFIED_KINDS` intersection |
| `dependencies` | `list[str] \| None` | over-execution fallback (null → regenerate) |
| `dependencies_complete` | `bool \| None` | over-execution fallback (≠ True → regenerate) |
| `fingerprint` | `str \| None` (schema attr) | repo-code signal; null → repo-commit fallback |
| `execute_after_merge` | `bool` (generators only) | merge filter |

**Selection outcome**: `DefinitionSelect` (`IntFlag`) accumulating `MODIFIED_KINDS |
FILE_CHANGES | QUERY_CHANGED | DEFINITION_CHANGED`; truthy → the definition is dispatched.

## 5. Impacted subscribers (reused, in-memory)

`TargetSelection` (`core/regeneration/models.py`):

- `ids: list[str]` — the **existing** subscriber (artifact/generator-instance) ids to process.
  Always complete and authoritative, so a caller needs nothing else to act on it.
- `widened: bool` — whether narrowing had to be abandoned. Diagnostic only; it carries no meaning
  of its own and exists so a caller can report the lost precision.

The caller passes the set to fall back to (`every_target`), so "process everything" is resolved
before the result is returned rather than described by it. An empty `ids` therefore means *nothing
to process*, unambiguously — it can never stand for *everything*.

**Member-selection rule** (merge path — reconciled against the live group, research D4a).
`ids` are **subscriber** (artifact/instance) ids and are never placed in a member filter
directly. Per selected definition, fetch live group members on the **target branch**, build the
`member.id → subscriber_id` map, and decide render per member:

```
render(member) = managed_branch                       # query/definition/fingerprint/code change
              or subscriber_of(member) is None        # new member (no existing subscriber)
              or subscriber_of(member) in selection.ids
```

A widened selection needs no clause of its own: its `ids` already hold every existing subscriber,
so the membership test admits every member that has one.

The dispatch filter (`target_members` / `members`) is then the **member ids** of the rendered
members, or an empty list when every member renders (= all).

| Selection | Result (after reconciliation) |
|---|---|
| widened | all live members render (empty filter) |
| empty `ids` | only new members render; if none, definition dispatches nothing |
| narrowed | members whose subscriber ∈ `ids`, **plus** all new members, **plus** all when `managed_branch` |

New members are covered by the `subscriber_of(member) is None` short-circuit, not by the diff
(Decision 4a / critique E1, E2). A definition is additionally selected at the definition level
when its target group appears in the merge summary (group-membership gate), so a membership-only
addition still reaches this reconciliation.

## 6. Dispatch payloads (message models)

- **`RequestGeneratorDefinitionRun`** (`generators/models.py`) — unchanged. `target_members:
  list[str]` filters on member node id (`generators/tasks.py`); safe for new members.
- **`RequestArtifactDefinitionGenerate`** (`git/models.py`) — **add** `members: list[str]
  = Field(default_factory=list)` (member node ids). Consumed in
  `generate_request_artifact_definition` (`git/tasks.py`) by filtering on `member.id`,
  mirroring `target_members`. Existing `limit` (keyed on existing artifact ids) is retained for
  current callers and unused by the merge path.

## 7. Config setting

`MainSettings.selective_execution_after_merge: bool = True` (`backend/infrahub/config.py`). Env var
`INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE`. Read at follow-up time via
`config.SETTINGS.main.selective_execution_after_merge`.

## Reused schema attributes (no change)

| Attribute | Kind(s) | Origin |
|---|---|---|
| `fingerprint` (Text, branch-aware, nullable) | `CoreGraphQLQuery`, `CoreTransformation`, `CoreArtifactDefinition`, `CoreGeneratorDefinition` | IFC-2844 |
| `dependencies` (List, nullable) | `CoreTransformation`, `CoreGeneratorDefinition` | INFP-409 / IFC-2738 |
| `dependencies_complete` (Boolean, nullable) | `CoreTransformation`, `CoreGeneratorDefinition` | INFP-409 / IFC-2738 |
| `execute_after_merge` (Boolean, default True) | `CoreGeneratorDefinition` | existing |
