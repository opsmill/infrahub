# Contract: Recompute decision for display labels and HFIDs

Internal contract between the display label and HFID setup flows and the pure decision component. See [data-model.md](../data-model.md) for the value types and [research.md](../research.md) Decisions 4 to 7.

## Inputs

| Input | Description |
|---|---|
| `family` | `display_label_jinja2` or `human_friendly_id` |
| `event_branch` | Branch of the event that started the setup flow. `None` when the flow did not come from an event |
| `branch_deleted` | `True` when the event is `BranchDeletedEvent` |
| `default_branch` | Name of the default branch |
| `schema` | `SchemaFingerprints` for the default branch and every branch in scope (`Registry.get_altered_schema_branches()`) |
| `recorded` | Every `RecordedFingerprint` of the family, all branches |

## Rules

Let `S[b][k]` be the schema fingerprint of kind `k` on branch `b`, and `R[b][k]` the recorded one. `in_scope` is the set of branches in `schema`.

**Deletions** (apply to every branch):

| Condition | Result |
|---|---|
| `R[b][k]` exists and `b` is not in `in_scope` | delete `(b, k)` |
| `R[b][k]` exists, `b` is in scope, and `S[b][k]` does not exist (kind or template removed) | delete `(b, k)` |

**Recompute and recording** (event branch `E` only). Nothing is recomputed or recorded when `branch_deleted` is true, when `E` is `None`, or when `E` is not in scope.

For each kind `k` in `S[E]`:

| `R[E][k]` | `E` is the default branch | `S[E][k] == S[default][k]` | Result |
|---|---|---|---|
| equal to `S[E][k]` | any | any | nothing |
| missing or different | yes | n/a | recompute `k`, then record `S[E][k]` |
| missing or different | no | yes | skip (identical to the default branch), record `S[E][k]` |
| missing or different | no | no, or `k` missing on the default branch | recompute `k`, then record `S[E][k]` |

Records of branches other than `E` are never written (research Decision 5).

## Order of execution in the setup flow

All steps run inside the distributed lock `configure-action-rules-<trigger type>` (namespace `trigger-rules`):

1. Configure the remaining (peer) automations of the family with `setup_triggers` and keep the report.
2. Carry over the fingerprints of the placeholder automations listed in `report.deleted` (see [fingerprint-store.md](./fingerprint-store.md), "Carry-over").
3. Read the records of the family.
4. Compute the decision.
5. Delete the records in `to_delete`.
6. Submit one recompute workflow per kind in `to_recompute`.
7. Write the records in `to_record` in one query. If step 6 raised, this step does not run (FR-006).

## Guarantees

- A template change on `E` is recomputed at least once: until a submission succeeds, the record keeps the old fingerprint or stays missing.
- A second flow for the same family waits on the lock and reads the fingerprints written by the first, so a change is not recomputed twice and not lost (FR-007).
- The number of recompute submissions for a given event equals the number the current release submits for the same event (SC-002), except after a failed submission (one extra submission) and for a branch whose records are out of date (research Decision 5).
