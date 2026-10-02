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
3. For the e2e scenario, build a local image under a tag of its own:

   ```bash
   INFRAHUB_IMAGE_VER=e2e-writeback uv run invoke dev.build
   ```

## Automated scenarios

| # | Scenario | Spec | Command | Must show |
|---|---|---|---|---|
| 1 | Classifier, queue model, service, barrier, retry condition | FR-004, FR-005, FR-012, FR-013, FR-020, FR-022 | `uv run pytest backend/tests/unit/git/writeback backend/tests/unit/core/merge/test_regeneration_barrier.py` | All pass with no database. |
| 2 | Store transitions and branch safety | FR-009, FR-019, FR-025, FR-026 | `uv run pytest backend/tests/component/git/writeback` | No delivery attribute in a diff or a merge. The update input has none of them. A new branch reads a copy, and the store never does. No node event is emitted. |
| 3 | Rejected push is visible | US1 | `uv run pytest backend/tests/integration/git/test_git_live_remote.py -k delivery_visible` | One entry, `action-required`, cause `permission`, the hook's `remote:` line verbatim, commit unchanged. |
| 4 | Two merges, one retry | US2 | `... -k one_retry_delivers_both` | The remote holds both merges after one push. Commit equals the remote head. Status `none`. |
| 5 | Remote advanced during the outage | US2 #3, FR-023 | `... -k remote_advanced_is_imported` | The direct push is imported before the record. The synchronisation skipped the default branch while pending. |
| 6 | Recorded-but-not-recorded | FR-012 | `... -k observed_after_record_failure` | No second push. The queue clears by observation. |
| 7 | Transient fault | US4, FR-004 | `... -k transient_fault_heals` | The Gogs container is paused for the first attempt. The second automatic attempt delivers. No user action. |
| 8 | Conflict, then abandon | US5 | `... -k conflict_then_abandon` | Cause `replay-conflict`, nothing pushed. After the abandonment: the record names the entries, the account and the time; the repository objects match the recorded commit; the held work released once. |
| 9 | Source discarded | US7 #1, FR-020, SC-007 | `... -k source_discarded` | Cause `source-discarded`. The remote never receives the discarded commit. |
| 10 | Remote branch kept | US6, FR-011 | `... -k remote_branch_kept_while_pending` | With `delete_git_branch_after_merge`, the remote source branch still exists. After the queue clears, a new deletion works. |
| 11 | Regeneration held and released once | US3 | `uv run pytest backend/tests/component/core/merge/test_held_regeneration.py` | Repository Y dispatched at once, X held. One release for X after the delivery, against the delivered commit. A deleted held definition widens. |
| 12 | Operator journey in the UI | PRD E2E, Principle IV | see below | The page shows the cause and the message, "Retry push" works, the status returns to "Nothing pending". |

The `...` stands for `uv run pytest backend/tests/integration/git/test_git_live_remote.py`.

### Scenario 12, e2e

```bash
sleep infinity | INFRAHUB_TESTING_IMAGE_VER=e2e-writeback INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e/repository/test_repository_delivery.py -s --pdb \
  2>&1 | tee /tmp/pdb.log
```

The test writes a rejecting `pre-receive` hook into the bare repository that the SDK `GitRepo`
helper serves, merges a branch, opens the repository page on another branch, and checks that the
"Push to remote" section shows the default branch's state. It removes the hook, clicks "Retry push",
and waits for "Nothing pending".

## Manual check on the development stack

1. Start the stack and load a repository whose credential can read but not push:

   ```bash
   uv run invoke dev.start
   ```

2. Create a branch with `sync_with_git`, change a file in the repository on that branch, and merge
   the branch.
3. Open the repository. The "Push to remote" section shows "Action required", the cause "Push
   refused by the remote", the remote's own message and one pending merge.
4. Switch to another branch. The section still shows the same state, read from the default branch.
5. Grant push permission on the remote. Use "Retry push". Follow the task link. The section returns
   to "Nothing pending", and the remote holds the merge.
6. Repeat step 2 twice with permission removed, then use "Abandon pending push". The confirmation
   lists both merges. After the run, `delivery_last_abandonment` names them, your account and the
   time.

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
