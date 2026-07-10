# Data Model: Incremental generator & artifact execution on merge

**Date**: 2026-07-10 · **Plan**: [plan.md](./plan.md)

This feature introduces **no new persisted (Neo4j) entities** and **no schema fields**. It
reuses existing schema attributes and introduces in-memory / cache-transported data shapes and
two message-model changes. Entities below are the data the selection path reads and writes.

## 1. Merge diff summary (cache-transported)

The authoritative "what changed" record for a merge, serialized into the SDK `NodeDiff` shape
so the existing selection predicates consume it unchanged.

- **Shape**: `list[NodeDiff]` (`python_sdk/infrahub_sdk/diff.py:11-36`).
- **Element**: `NodeDiff = {branch: str, kind: str, id: str, action: str, display_label: str, elements: list[NodeDiffElement]}`.
  - `NodeDiffElement = {name: str, element_type: str, action: str, summary: {added,updated,removed}, peers?: list[NodeDiffPeer]}`.
  - `element_type ∈ {"ATTRIBUTE", "RELATIONSHIP_ONE", "RELATIONSHIP_MANY"}`.
  - `action` is the **uppercase** GraphQL enum name (`"ADDED" | "UPDATED" | "REMOVED"`).
- **Source**: `EnrichedDiffRoot.nodes` (`backend/infrahub/core/diff/model/path.py:497`), filtered
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
- **`diff_root_uuid`**: `EnrichedDiffRootMetadata.uuid` (`path.py:463`) — stable across the
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

Structural `RegenerationDefinition` protocol (`proposed_change/tasks.py:1383-1404`), satisfied
by `ProposedChangeArtifactDefinition` and `ProposedChangeGeneratorDefinition`
(`generators/models.py:75`). Fields read by the gates:

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

`ImpactedSubscribers` (`proposed_change/tasks.py:753-764`):

- `scope: ImpactScope` — `ALL` | `NONE` | `SPECIFIC`.
- `ids: list[str]` — for `SPECIFIC`, the **existing** subscriber (artifact/generator-instance)
  ids whose read fields intersect the changed elements.

**Member-selection rule** (merge path):

| `scope` | Generators (`target_members`) | Artifacts (`members`) |
|---|---|---|
| `ALL` | empty list → all members | empty list → all members |
| `NONE` | definition skipped | definition skipped |
| `SPECIFIC` | member ids of `ids` **+ new members** | member ids of `ids` **+ new members** |

New members (group members with no existing artifact/instance) MUST be added explicitly for
`SPECIFIC` — the impact analysis returns only existing subscriber ids (Decision 5).

## 6. Dispatch payloads (message models)

- **`RequestGeneratorDefinitionRun`** (`generators/models.py:31-38`) — unchanged. `target_members:
  list[str]` filters on member node id (`generators/tasks.py:224-228`); safe for new members.
- **`RequestArtifactDefinitionGenerate`** (`git/models.py:19-28`) — **add** `members: list[str]
  = Field(default_factory=list)` (member node ids). Consumed in
  `generate_request_artifact_definition` (`git/tasks.py:594-598`) by filtering on `member.id`,
  mirroring `target_members`. Existing `limit` (keyed on existing artifact ids) is retained for
  current callers and unused by the merge path.

## 7. Config setting

`MainSettings.selective_execution_after_merge: bool = True` (`config.py:183`). Env var
`INFRAHUB_SELECTIVE_EXECUTION_AFTER_MERGE`. Read at follow-up time via
`config.SETTINGS.main.selective_execution_after_merge`.

## Reused schema attributes (no change)

| Attribute | Kind(s) | Origin |
|---|---|---|
| `fingerprint` (Text, branch-aware, nullable) | `CoreGraphQLQuery`, `CoreTransformation`, `CoreArtifactDefinition`, `CoreGeneratorDefinition` | IFC-2844 |
| `dependencies` (List, nullable) | `CoreTransformation`, `CoreGeneratorDefinition` | INFP-409 / IFC-2738 |
| `dependencies_complete` (Boolean, nullable) | `CoreTransformation`, `CoreGeneratorDefinition` | INFP-409 / IFC-2738 |
| `execute_after_merge` (Boolean, default True) | `CoreGeneratorDefinition` | existing |
