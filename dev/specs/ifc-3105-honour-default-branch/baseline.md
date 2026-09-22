# Pre-change test baseline

Recorded so the warm-clone reproduction added in T005 is provably a **new** failure rather than one
of the suite's pre-existing ones.

**Base commit**: `0a9cf432a` (`docs(specs): correct infp-546 Story 6, superseded by IFC-3105`), the
commit PR 2 is built on. A baseline taken against any other base proves nothing about T005.

**Date**: 2026-09-08.

## Results

| Command | Result |
|---|---|
| `uv run pytest backend/tests/unit/git backend/tests/functional/git` | **201 passed**, 0 failed |
| `PYTHONPATH=backend uv run pytest backend/tests/component/git/test_git_repository.py backend/tests/component/git/test_sync_repository.py` | **68 passed, 1 xfailed**, 0 failed |

No test named `test_repository_default_branch.py::*warm*` exists at this commit; the file
`backend/tests/functional/git/test_repository_default_branch.py` covers the cold-clone path only.
Any failure in it after T005 lands is therefore the new reproduction.

The single `xfailed` in the component tier is
`test_git_repository.py::test_has_conflicting_changes` (pre-existing, unrelated to this feature: its
marker states it cannot reproduce conflicts without remote branches). It must still be `xfailed`
after the change, not `xpassed`.

## Two local-environment prerequisites

Both were discovered while taking this baseline. Neither is a code defect, but a run that skips them
reports failures that look like regressions.

1. **`PYTHONPATH=backend` is required for the component tier.** The Prefect test harness launches its
   server as `python -m tests.helpers.prefect_test_server` in a subprocess. The parent pytest process
   can import `tests.*` because pytest inserts the rootdir; the subprocess inherits only
   `os.environ`, so without `backend` on `PYTHONPATH` it dies with
   `No module named tests.helpers.prefect_test_server` and every component test in the module errors
   with `Timed out while attempting to connect to ephemeral Prefect API server`. The failure gives no
   hint of the cause: the harness discards the subprocess's stdout and stderr, and the real message
   is only in `<pytest tmpdir>/prefect-test-server-<port>.log`.
2. **`INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES` must be unset.** A dev shell that exports it (e.g.
   `["infrahub-.*","sync-.*"]`) makes `test_compare_remote_local_new_branches` and
   `test_get_filtered_remote_branches__no_import_sync_branch_names` fail, because both assert the
   unfiltered branch set. Run the component tier with `env -u INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES`.

The numbers above were taken with both applied. CI has neither problem: it sets no such env var and
runs the suite through `uv run invoke backend.test-component`.
