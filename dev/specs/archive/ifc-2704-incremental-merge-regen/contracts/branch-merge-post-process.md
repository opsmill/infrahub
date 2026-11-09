# Contract: Post-merge follow-up — threaded key, selection, fallbacks

**Plan**: [../plan.md](../plan.md) · **Decisions**: D3, D4, D6, D7, D9

## Threaded parameter

| Site | Change |
|---|---|
| `BranchMergeOrchestrator.merge` (`core/merge/orchestrator.py`) | Serialize the in-memory `branch_diff` into `list[NodeDiff]` before the freeze; then, **only after the point of no return** (post `MERGED` transition / write-block lift, just before the follow-up), `set_merge_diff_summary_cache` and obtain `merge_diff_cache_key = diff_root_uuid`; pass to `run_follow_ups`, along with the caller-supplied `proposed_change_id` (the PC id, or `None` for a direct merge). On any capture/write failure → `None` (never re-raise). A rolled-back merge writes nothing. |
| `PostMergeDispatcher.run_follow_ups` (`core/merge/post_merge.py:58-104`) | New params `merge_diff_cache_key: str \| None` and `proposed_change_id: str \| None`; include both in the `BRANCH_MERGE_POST_PROCESS` parameters dict (`:100-104`). |
| `BRANCH_MERGE_POST_PROCESS` params | `{source_branch, target_branch, merge_diff_cache_key, proposed_change_id}`. |
| `post_process_branch_merge` (`core/branch/tasks.py:434-478`) | New params `merge_diff_cache_key: str \| None = None` and `proposed_change_id: str \| None = None`; derive `is_proposed_change_merge = proposed_change_id is not None`. |

Only the string key and PC id cross Prefect. Older in-flight submissions (no key) → `None` → fallback; older submissions with no `proposed_change_id` → treated as a direct merge (the conservative branch that applies the cascade).

## Selection decision in `post_process_branch_merge`

```
if not config.SETTINGS.main.selective_execution_after_merge:
    -> FULL REGENERATION (submit the two TRIGGER_* as today)     # D9 flag off
elif merge_diff_cache_key is None:
    -> FULL REGENERATION                                         # D6 no key / capture failed
else:
    try:    summary = get_merge_diff_summary_cache(merge_diff_cache_key)
    except ResourceNotFoundError:                                # miss OR unreadable/malformed
            -> FULL REGENERATION                                 # D6 any summary-load failure
    else:   run selective_regen(summary, target_branch, is_proposed_change_merge)
                                                                 # is_proposed_change_merge = proposed_change_id is not None
```

## `selective_regen` behavior (`core/merge/selective_regen.py`)

**Definition level** (artifacts and generators):

- Select when any of: `_query_changed`, `_definition_changed` (includes fingerprint-attribute
  change), or `MODIFIED_KINDS` (a `query_models` kind is in `get_modified_kinds(summary)`;
  artifacts also apply the `Profile`-strip variant).
- **Group-membership gate**: select when the definition's target group — or that group's
  `members` relationship — appears in the summary. A membership-only change (a member added to
  or removed from the group, with no data change) matches none of the gates above, so without
  this gate reconciliation never runs and the added member is skipped (critique E2). The gate
  makes the definition eligible so member-level reconciliation can pick up the new member.
- Generators additionally require `execute_after_merge == True`.
- **Repo-code null-fingerprint fallback**: if a definition's `fingerprint` is null **and** the
  summary contains a repository commit change for that definition's repository → select it
  (and all definitions of that repository). If the `fingerprint` is null **and** no repository
  commit change can be confirmed for its repository, **escalate**: select all definitions of
  that repository (repository-wide full regeneration) rather than skipping — a null fingerprint
  means the diff signal is untrustworthy for that node, and an unverified repo-code signal must
  over-execute (research D6/E6). Null-fingerprint state is transient and self-heals on the next
  re-import, so this coarse escalation is bounded.
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
