# Contract: Post-merge follow-up — threaded key, selection, fallbacks

**Plan**: [../plan.md](../plan.md) · **Decisions**: D3, D4, D6, D7, D9

## Threaded parameter

| Site | Change |
|---|---|
| `BranchMergeOrchestrator.merge` (`core/merge/orchestrator.py`) | After changelog collection, before freeze: build summary, `set_merge_diff_summary_cache`, obtain `merge_diff_cache_key = diff_root_uuid`; pass to `run_follow_ups`. On capture failure → `None`. |
| `PostMergeDispatcher.run_follow_ups` (`core/merge/post_merge.py:58-104`) | New param `merge_diff_cache_key: str \| None`; include it in the `BRANCH_MERGE_POST_PROCESS` parameters dict (`:100-104`). |
| `BRANCH_MERGE_POST_PROCESS` params | `{source_branch, target_branch, merge_diff_cache_key}`. |
| `post_process_branch_merge` (`core/branch/tasks.py:434-478`) | New param `merge_diff_cache_key: str \| None = None`. |

Only the string key crosses Prefect. Older in-flight submissions (no key) → `None` → fallback.

## Selection decision in `post_process_branch_merge`

```
if not config.SETTINGS.main.selective_execution_after_merge:
    -> FULL REGENERATION (submit the two TRIGGER_* as today)     # D9 flag off
elif merge_diff_cache_key is None:
    -> FULL REGENERATION                                         # D6 no key / capture failed
else:
    try:    summary = get_merge_diff_summary_cache(merge_diff_cache_key)
    except ResourceNotFoundError:
            -> FULL REGENERATION                                 # D6 cache miss
    else:   run selective_regen(summary, target_branch, is_proposed_change_merge)
```

## `selective_regen` behavior (`core/merge/selective_regen.py`)

**Definition level** (artifacts and generators):

- Select when any of: `_query_changed`, `_definition_changed` (includes fingerprint-attribute
  change), or `MODIFIED_KINDS` (a `query_models` kind is in `get_modified_kinds(summary)`;
  artifacts also apply the `Profile`-strip variant).
- Generators additionally require `execute_after_merge == True`.
- **Repo-code null-fingerprint fallback**: if a definition's `fingerprint` is null **and** the
  summary contains a repository commit change for that definition's repository → select it
  (and all definitions of that repository).
- `dependencies` null or `dependencies_complete != True` → select (over-execution).

**Member level** (per selected definition — reconciled against the live group, D4a). The impact
analysis returns **subscriber** ids, which are never passed to a member filter directly:

1. Fetch the definition's live group members on the **target branch**; build
   `member.id → existing subscriber_id`.
2. `managed_branch` = the definition-level gate result (query/definition/fingerprint/code).
3. `impacted = get_field_level_impacted_subscribers(summary, query_branch=target_branch, ...)`.
4. `render(member)` iff `managed_branch` **or** `subscriber_of(member) is None` (new member)
   **or** `impacted.scope == ALL` **or** `subscriber_of(member) in impacted.ids`.
5. Dispatch with the **member ids** of rendered members
   (`REQUEST_GENERATOR_DEFINITION_RUN(target_members=...)` /
   `REQUEST_ARTIFACT_DEFINITION_GENERATE(members=...)`), or an empty filter when all render.

New members and membership-only additions are covered by step 4's `is None` short-circuit plus
the definition-level group-membership gate — not by the diff (critique E1/E2).

**Direct-merge generator cascade (D7)**: if `is_proposed_change_merge` is `False` **and** ≥1
generator was dispatched, the artifacts that consume generator output must not be left stale.
The cascade coverage depends on a **blocking spike** (critique E4): if the event-driven
machinery regenerates artifacts on generator-produced data mutations, rely on it (no extra
submission); otherwise submit full artifact regeneration **sequenced after** generator
completion (awaited) — never concurrent, which would race generator mutation. Proposed-change
merges keep full selective artifact behavior (generator output is already in the merge diff).

## Invariants

- No path may result in fewer regenerations than the set of artifacts/generators whose inputs
  changed. Every "cannot prove irrelevant" branch selects/regenerates.
- The full-regeneration fallback is byte-for-byte the current behavior (the two `TRIGGER_*`
  submissions), so the flag-off path and every fallback are provably safe.
- No behavior change for any caller outside the merge follow-up.
