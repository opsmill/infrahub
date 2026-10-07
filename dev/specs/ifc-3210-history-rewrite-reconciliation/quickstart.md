# Quickstart: validating Git history-rewrite reconciliation

**Feature**: `dev/specs/ifc-3210-history-rewrite-reconciliation`
**Date**: 2026-09-29

How to run the validation for this feature, and what each run must show. Every component,
integration and end-to-end test here uses testcontainers. No test uses an external or
locally-running Neo4j. The unit tests need no database at all.

---

## Prerequisites

1. A running Docker daemon. The component, integration and live-remote tests start their services
   through testcontainers.
2. A worktree with the submodules initialised and the SDK reinstalled in editable mode through the
   root package: `uv sync --all-groups --reinstall-package infrahub-server`. Do not install
   `python_sdk` on its own with `uv pip install -e`. Its `tests` package then hides `backend/tests`
   from the Prefect test server process, and every component test that needs Prefect fails at
   setup with "Timed out while attempting to connect to ephemeral Prefect API server".
3. **Unset every `INFRAHUB_*` variable in the shell before running tests.** A dev-shell
   `INFRAHUB_USE_TEST_CONTAINERS=false`, or leftover credentials, makes the suite hit an external
   Neo4j or fail the SDK login.

```bash
unset $(env | grep -o '^INFRAHUB_[^=]*')
export INFRAHUB_USE_TEST_CONTAINERS=1
```

Do not pipe into `while read ... unset`. In bash every stage of a pipeline runs in a subshell, so
the `unset` would affect the subshell only and the calling shell would keep its variables. zsh runs
the last stage in the current shell, which hides the bug on a zsh machine and lets it through to CI.

4. Run one `backend/tests/component/` package per pytest session. Errors in the last package of a
   long run are contention, not the code.

---

## 1. Unit tests, no database

These cover the classifier, the recorder and the broadcast handler's fan-out. They must run in
seconds.

```bash
uv run pytest backend/tests/unit/git/divergence/ backend/tests/unit/message_bus/ -q
```

**What must pass**

| Test group | Assertion |
|---|---|
| Classifier, unchanged | The remote head equals the imported commit, so the result is `UNCHANGED`. |
| Classifier, fast-forward | The imported commit is an ancestor, so the result is `FAST_FORWARD` and nothing is recorded. |
| Classifier, rewound remote | The remote head is an ancestor of the imported commit, so the result is `REWRITE`. With the target changed it is `RETARGET`. |
| Classifier, remote absent | The remote carries no such ref, so the result is `REMOTE_ABSENT`. |
| Classifier, rewrite | Neither is an ancestor and the target did not change, so the result is `REWRITE`. |
| Classifier, re-target | Neither is an ancestor and the target changed, so the result is `RETARGET`. |
| Classifier, missing object | The imported commit is gone from the object database and the target did not change, so the result is `REWRITE`. With the target changed it is `RETARGET`. |
| Classifier, missing remote head | The remote head is gone from the object database, so the classification raises a `RepositoryError` instead of reporting a rewrite. |
| Classifier, never imported | No imported commit, so the result is never `REWRITE` or `RETARGET`. |
| Suppression, present | A present marker makes `target_changed` true and is gone afterwards. |
| Suppression, absent | An absent marker makes `target_changed` false. |
| Suppression, consumed once | A second classification after the same marker is not suppressed. |
| Recorder, last-write-wins | A second rewrite overwrites the first record. |
| Recorder, increment | The count goes from absent to 1, then 1 to 2. |
| Recorder, precondition | Every classification other than `REWRITE` writes nothing. The recorder never reads the cache. |
| Recorder, signal | A rewrite of the configured default branch emits the event once and never twice. Any other branch emits none. |
| Handler fan-out | N branch-and-commit pairs are reset inside one lock acquisition and one fetch. |

The negative cases carry as much weight as the positive ones. A fast-forward, a deliberate
re-target and an absent remote ref must all come out clean. The re-target is the one that would
report an ordinary configuration change as a rewrite if it were wrong.

---

## 2. Component tests

```bash
uv run pytest backend/tests/component/git/ -q
```

**What must pass**

| Scenario | Assertion |
|---|---|
| A diverged branch is pulled | `pull` resets the worktree onto the remote head. It raises nothing. |
| The error text | No message describing a divergent history contains the word "conflict" (FR-003, SC-003). |
| The sync returns its outcome | `RepositorySyncer.sync` returns the reconciled branches and the failures instead of raising. |
| Branch safety | The four attributes appear in no branch diff, on `CoreRepository` and on `CoreReadOnlyRepository`. Merging a branch that carries a record does not carry it to the destination (FR-012, Principle II). |

The branch-safety test is required by the constitution's branch-safe principle. It asserts the
merge behaviour rather than inferring it from the attribute declaration.

---

## 3. Integration tests against a live remote

These use the Gogs harness, which is already on `develop`. They need the new force-push helper.

```bash
uv run pytest backend/tests/integration/git/test_git_live_remote.py -q
```

Use `--pdb` when a failure needs inspecting. A failure then freezes the session with the
testcontainers stack, the SDK clients and every fixture still alive.

```bash
uv run pytest backend/tests/integration/git/test_git_live_remote.py::<node_id> -s --pdb
```

**What must pass**

| Scenario | Maps to | Assertion |
|---|---|---|
| A rewritten non-default branch | US1, SC-001 | It reconciles and re-imports. The branch commit matches the new remote head, the imported objects match the rewritten tree, and the repository reports healthy. |
| A rewritten trunk | US4, SC-002 | The same reconciliation happens. Across several cycles, the record is written once and the event is emitted once, never twice. |
| A worker that received no broadcast | US2, SC-004 | It converges on first contact. It writes no rewrite record and emits no signal. |
| One rewritten branch beside a healthy one | US3, SC-005 | The healthy branch still converges. The broadcast for it was sent before the failed branch raised. |
| A read-only repository | US5 | A force-pushed tracked **branch**, not a moved tag: the read-only fetch omits `--force`, so a moved tag fails the fetch with "would clobber existing tag" instead of showing a lineage break. The record is written. No reset is performed. |
| A deliberate ref change | US6, SC-007 | Nothing is recorded. |
| A webhook on the trunk event | FR-014 | One delivery per rewrite, never two. |

---

## 4. End-to-end scenario

The developer journey, end to end.

```bash
uv run invoke dev.build
INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e/<node_id> -q
```

Without the local image the suite runs against a published one, so it would not exercise this
change at all.

**What must pass**: a developer rebases a branch Infrahub tracks and force-pushes it. The branch
keeps synchronising, its imported objects match the rewritten history, and the repository reports
healthy throughout. No user action is needed at any point.

---

## 5. Regenerate what the schema change makes stale

The four attributes are a schema change, so generated files go stale. Regenerate and commit them in
the same change.

```bash
uv run invoke backend.generate
uv run invoke schema.generate-graphqlschema
uv run invoke schema.generate-jsonschema
uv run invoke docs.generate
cd frontend/app && pnpm codegen:graphql
```

The new event also makes the events reference documentation stale, which `docs.generate` covers.
CI fails when any generated file is not committed.

---

## 6. Before pushing

```bash
uv run invoke format
uv run invoke lint
uv run ruff format --check .
uv run ruff check . --exclude python_sdk
```

`invoke lint` covers only some directories. CI runs `ruff check` over the whole repository, and it
runs `ruff format --check` as well. Run `/pre-ci` for the full local set.

---

## What "done" looks like

Tick each one against `spec.md`.

- [ ] SC-001: a rewritten non-default branch is healthy again with zero user actions.
- [ ] SC-002: a rewritten default branch is healthy again, with at most one record and at most one
      signal across several cycles, and never more than one.
- [ ] SC-003: no message describing a rewritten history uses the word "conflict".
- [ ] SC-004: every worker's view matches the remote, including one that heard no broadcast and one
      added afterwards.
- [ ] SC-005: a rewritten branch never blocks another branch of the same repository.
- [ ] SC-006: the repository's stored state, read through the repository API, explains why content
      at an earlier commit cannot be re-derived. The human-facing view belongs to INFP-671.
- [ ] SC-007: a deliberate re-point produces no rewrite report.
- [ ] The stale statements in `dev/knowledge/backend/` are corrected. The branch-support row is
      already fixed in this change; the rest have tasks.
- [ ] A changelog fragment exists. This is a user-visible change.
