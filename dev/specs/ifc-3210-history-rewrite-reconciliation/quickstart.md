# Quickstart: validating Git history-rewrite reconciliation

**Feature**: `dev/specs/ifc-3210-history-rewrite-reconciliation`
**Date**: 2026-09-29

How to run the validation for this feature, and what each run must show. Every test here uses
testcontainers. No test uses an external or locally-running Neo4j.

---

## Prerequisites

1. A running Docker daemon. The component, integration and live-remote tests start their services
   through testcontainers.
2. A worktree with the submodules initialised and the SDK reinstalled in editable mode.
3. **Unset every `INFRAHUB_*` variable in the shell before running tests.** A dev-shell
   `INFRAHUB_USE_TEST_CONTAINERS=false`, or leftover credentials, makes the suite hit an external
   Neo4j or fail the SDK login.

```bash
env | grep '^INFRAHUB_' | cut -d= -f1 | while read -r v; do unset "$v"; done
export INFRAHUB_USE_TEST_CONTAINERS=1
```

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
| Classifier, rewrite | Not an ancestor and the target did not change, so the result is `REWRITE`. |
| Classifier, re-target | Not an ancestor and the target changed, so the result is `RETARGET`. |
| Classifier, missing object | The ancestry question cannot be answered, so the result is `REWRITE`. |
| Classifier, never imported | No imported commit, so the result is never `REWRITE` or `RETARGET`. |
| Recorder, last-write-wins | A second rewrite overwrites the first record. |
| Recorder, increment | The count goes from absent to 1, then 1 to 2. |
| Recorder, precondition | A `RETARGET` writes nothing. A present suppression marker turns a `REWRITE` into a skip and consumes the marker. |
| Recorder, signal | A rewrite of the configured default branch emits exactly one event. Any other branch emits none. |
| Handler fan-out | N branch-and-commit pairs are reset inside one lock acquisition and one fetch. |

The negative cases carry as much weight as the positive ones. A fast-forward and a deliberate
re-target must both come out clean.

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

These use the Gogs harness of PR #10465. They need the new force-push helper.

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
| A rewritten trunk | US4, SC-002 | The same reconciliation happens. Across several cycles, exactly one record is written and exactly one event is emitted. |
| A worker that received no broadcast | US2, SC-004 | It converges on first contact. It writes no commit to the graph and emits no report. |
| One rewritten branch beside a healthy one | US3, SC-005 | The healthy branch still converges. The broadcast for it was sent before the failed branch raised. |
| A read-only repository | US5 | The record is written. No reset is performed. |
| A deliberate ref change | US6, SC-007 | Nothing is recorded. |
| A webhook on the trunk event | FR-014 | Exactly one delivery per rewrite. |

---

## 4. End-to-end scenario

The developer journey, end to end.

```bash
uv run pytest -c tests/e2e/pytest.ini tests/e2e/<node_id> -q
```

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
cd frontend/app && pnpm codegen
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
- [ ] SC-002: a rewritten default branch is healthy again, with exactly one record and exactly one
      signal across several cycles.
- [ ] SC-003: no message describing a rewritten history uses the word "conflict".
- [ ] SC-004: every worker's view matches the remote, including one that heard no broadcast and one
      added afterwards.
- [ ] SC-005: a rewritten branch never blocks another branch of the same repository.
- [ ] SC-006: the repository view alone explains why content at an earlier commit cannot be
      re-derived.
- [ ] SC-007: a deliberate re-point produces no rewrite report.
- [ ] The three stale statements in `dev/knowledge/backend/` are corrected.
- [ ] A changelog fragment exists. This is a user-visible change.
