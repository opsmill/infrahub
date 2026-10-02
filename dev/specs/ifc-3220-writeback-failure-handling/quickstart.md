# Quickstart: validate Git remote writeback failure handling

**Feature**: `dev/specs/ifc-3220-writeback-failure-handling`

This guide proves the feature end to end. It names the scenarios, how to run them, and what each
must show. The contracts are in [contracts/](contracts/), and the attributes in
[data-model.md](data-model.md).

## Prerequisites

1. Initialise the submodules of the worktree, then reinstall the server package:

   ```bash
   git submodule update --init python_sdk frontend/packages/schema-visualizer
   uv sync --all-groups --reinstall-package infrahub-server
   ```

2. Have a running Docker daemon. The component and integration tests start Neo4j, the cache, the
   message bus and a Gogs server through testcontainers.
3. For the e2e scenarios, build a local image under a tag of its own:

   ```bash
   INFRAHUB_IMAGE_VER=e2e-writeback uv run invoke dev.build
   ```

## Automated scenarios

`LIVE` stands for `uv run pytest backend/tests/integration/git/test_git_live_remote.py`.

| # | Scenario | Spec | Command | Must show |
|---|---|---|---|---|
| 1 | Classifier, scrubber, queue model, held set, service, barrier, retry condition | FR-004, FR-005, FR-005b, FR-012, FR-013, FR-015, FR-020, FR-022 | `uv run pytest backend/tests/unit/git/writeback backend/tests/unit/core/merge/test_regeneration_barrier.py` | All pass with no database. A repeated hold survives a release's clear. The obligation is saved before the record. |
| 2 | Store transitions and branch safety | FR-009, FR-019, FR-025, FR-026 | `uv run pytest backend/tests/component/git/writeback` | No delivery attribute in a diff or a merge. The update input has none of them. A new branch reads a copy, and the store never does. No node event is emitted. A 200-entry queue works. |
| 3 | Data-only merge queues nothing | FR-005, US1 #7 | `uv run pytest backend/tests/component/git/writeback -k data_only` | Fork, trunk advances, data-only merge: no entry, no hold. |
| 4 | Mutations off the default branch | FR-008, R7 | `uv run pytest backend/tests/component/graphql/test_repository_delivery_mutations.py` | Both refuse on another branch, and without each of the three permissions. |
| 5 | Rejected push is visible | US1 | `LIVE -k delivery_visible` | One entry, `action-required`, cause `permission`, the hook's `remote:` line verbatim, commit unchanged. |
| 6 | Two merges, one retry | US2 | `LIVE -k one_retry_delivers_both` | The remote holds both merges after one push. Commit equals the remote head. Status `none`. |
| 7 | Remote advanced during the outage | US2 #3, FR-023 | `LIVE -k remote_advanced_is_imported` | The synchronisation skipped the default branch while pending. The delivered commit is recorded, then imported. An artifact definition the import updated renders against the delivered commit. |
| 8 | Pushed but not recorded | FR-012 | `LIVE -k observed_after_record_failure` | No second push. The queue clears by observation. |
| 9 | Transient fault | US4, FR-004 | `LIVE -k transient_fault_heals` | The Gogs port is blocked for the first attempt and opened before the second. Short retry delays. The second automatic attempt delivers. No user action. |
| 10 | Lost attempt | US4 #5, FR-027 | `LIVE -k lost_attempt_recovers` | The flow is killed after the snapshot. Once stale, the next synchronisation cycle submits a new attempt, which delivers. |
| 11 | Conflict resolved by hand | US5 #2 | `LIVE -k conflict_resolved_on_remote` | Cause `replay-conflict`. After a manual merge on the remote and a retry, the entry clears by observation. |
| 12 | Conflict, then abandon | US5 | `LIVE -k conflict_then_abandon` | Cause `replay-conflict`, nothing pushed. After the abandonment: the record names the entries, the account and the time; the edge names the account; the held work released once; the remote is unchanged. |
| 13 | Source discarded | US7 #1, FR-020, SC-007 | `LIVE -k source_discarded` | Cause `source-discarded`. The remote never receives the discarded commit. |
| 14 | Remote branch kept, then deleted | US6, FR-011 | `LIVE -k remote_branch_kept_while_pending` | With `delete_git_branch_after_merge`, the remote source branch still exists, and the next synchronisation does not import it as a new branch. After the retry delivers, the branch is gone. |
| 15 | Regeneration held and released once | US3 | `uv run pytest backend/tests/component/core/merge/test_held_regeneration.py` | Repository Y dispatched at once, X held. One release for X after the delivery, against the delivered commit. Inside the cache window, the release dispatches the narrowed requests. A deleted held definition widens to X only. |
| 16 | Operator journeys in the UI | PRD E2E, Principle IV | see below | Retry: the page shows the cause and the message, "Retry push" works, the status returns to "Nothing pending". Abandon: the modal lists the merges, the record appears. |

### Scenario 16, e2e

```bash
sleep infinity | INFRAHUB_TESTING_IMAGE_VER=e2e-writeback INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e/repository/test_repository_delivery.py -s --pdb \
  2>&1 | tee /tmp/pdb.log
```

The retry test writes a rejecting `pre-receive` hook into the bare repository that the SDK
`GitRepo` helper serves, merges a branch, opens the repository page on another branch, and checks
that the "Push to remote" section shows the default branch's state. It removes the hook, clicks
"Retry push", and waits for "Nothing pending".

The abandonment test makes the push conflict, clicks "Abandon pending push", confirms the modal,
and checks the record and the advice to reimport.

## Manual check on the development stack

1. Start the stack and add a repository with a credential that can push:

   ```bash
   uv run invoke dev.start
   ```

   A read-write repository cannot be added with a read-only credential: the write probe refuses it.
2. On the remote, protect the default branch, or revoke the credential's push right.
3. Create a branch with `sync_with_git`, change a file in the repository on that branch, and merge
   the branch.
4. Open the repository. The "Push to remote" section shows "Action required", the cause "Push
   refused by the remote", the remote's own message, the sentence on paused imports, and one pending
   merge.
5. Switch to another branch. The section still shows the same state, read from the default branch.
   The generic attribute list and its "extra" toggle show none of the delivery attributes.
6. Lift the protection. Use "Retry push". Follow the task link. The section returns to "Nothing
   pending", and the remote holds the merge.
7. Repeat step 3 twice with the protection back, then use "Abandon pending push". The confirmation
   lists both merges. After the run, the section shows the record with your account and the time,
   and advises "Reimport current commit".

## Checks before the PR

```bash
uv run invoke format
uv run invoke lint
uv run invoke backend.generate
uv run invoke schema.generate-graphqlschema
cd frontend/app && pnpm codegen && pnpm codegen:graphql && cd -
uv run invoke docs.validate
```

Then run `/pre-ci`. The SDK protocols change needs its own PR on `opsmill/infrahub-sdk-python`
first (`research.md` R17).
