# Implementation report: Phase 5 (US2, increment C)

**Status: COMPLETE** for the requested range. T056 was deliberately excluded and handed back to the
user.

| Field | Value |
|-------|-------|
| Feature | Cross-branch repository status query, Phase 5: the periodic sync stops querying per branch |
| Spec dir | `dev/specs/infp-671-cross-branch-repo-status` |
| Jira | [IFC-3128](https://opsmill.atlassian.net/browse/IFC-3128) |
| Branch | `pog-periodic-sync-one-chunk-IFC-3128` |
| PR base | `cross-branch-repo-status-infp-671` (the integration branch, not `develop`) |
| Base commit | `2db4b622f` |
| Head commit | `704e94013` |
| Task range | T048 to T055, including T052a. T056 handed back; Phase 6 (T057 to T060) untouched |

---

## 1. Chunk-by-chunk ledger

### Chunk 1: T048, T049, T050 (core refactor)

- Tasks: 3. Outcome: 3 done, 0 partial, 0 blocked.
- Commit: `dddbe5add0cbcf24419f50a9c430484566c63da5`
- Files: `backend/infrahub/git/constants.py`, `backend/infrahub/git/utils.py`,
  `backend/infrahub/git/models.py`, `backend/infrahub/computed_attribute/models.py`

Flagged upward:

- **T050 finding (paste-ready for the PR description).** Neither caller of
  `get_repositories_commit_per_branch` needs a change. `sync_remote_repositories`
  (`backend/infrahub/git/tasks.py`) reads only `repository_data.repository`,
  `repository_data.branch_info[registry.default_branch].internal_status` and
  `repository_data.get_staging_branch()`; it never indexes `branches` and never references the
  global branch. `gather_trigger_computed_attribute_python`
  (`backend/infrahub/computed_attribute/gather.py`) skips `branch.is_global` before gathering, and
  the per-branch commit reaches it through
  `PythonTransformComputedAttribute.populate_branch_commit`, which iterates
  `RepositoryData.branches` and indexes it by branch name only. A grep for `GLOBAL_BRANCH_NAME` and
  `-global-` across both modules returns nothing.
- The constant's comment runs to two lines rather than one, because a single line would exceed the
  120-character limit.
- The chunk raised a concern that repositories created on a non-default branch would now drop out of
  the result entirely. **The review refuted it** - see section 5.
- This worktree had uninitialised submodules, so pytest could not import `infrahub_sdk`. Fixed with
  `git submodule update --init --recursive` then
  `uv sync --all-groups --reinstall-package infrahub-server`. Nothing in the repository changed.

### Chunk 2: T051, T052, T052a, T053 (tests)

- Tasks: 4. Outcome: 4 done, 0 partial, 0 blocked.
- Commit: `e8c7f68ebe994ba40b22820398b1b54b805eb7be`
- Files: `backend/tests/component/git/test_utils.py`,
  `backend/tests/component/computed_attribute/test_gather.py`,
  `backend/tests/integration_docker/test_computed_attributes.py`

Flagged upward:

- **T051 branch count.** The task's literal bound `ceil(200 / 100) == 2` only holds if the *total*
  branch-name list is 200. `registry.branch` already holds the default branch, so the fixture
  creates 199 branches, giving exactly 200 non-global names. 201 names would need 3 chunks and fail
  the stated bound.
- **T051 provenance is genuinely divergent only for `ref`.** `location` and `default_branch` are
  `BranchSupportType.AGNOSTIC`, so a write from a user branch lands on the global branch and the
  default branch sees it too; they cannot diverge per branch. Only `ref` (AWARE, read-only
  repository) can. The test writes a different `ref` on a user branch and asserts the result carries
  the default branch's value; `location` and `default_branch` are asserted against their
  default-branch values without fabricating an impossible divergence. The review verified this
  claim against the schema definitions independently and confirmed it. Worth a line in the PR, since
  the task text assumed all three could diverge.
- **T052a required a new case.** The existing cases do not cover it:
  `test_transform_based_computed_attribute` and `test_python_scoped_recompute_on_read_field_change`
  exercise the repository-backed Python transform on `main` only;
  `test_branch_isolation_scopes_recompute_to_changed_branch` is the only multi-branch case and it is
  Jinja2, not Python. The landed case is
  `test_python_computed_attribute_renders_on_more_than_one_branch`.
- **Local build workaround, not committed.** `uv run invoke dev.build` fails in this worktree twice
  over: the compose project name derived from the branch name contains uppercase (`IFC3128`), and
  `.vscode` is a symlink into the main checkout that BuildKit cannot resolve. Built with
  `INFRAHUB_BUILD_NAME=infrahub-ifc3128` and the symlink temporarily moved out; the symlink was
  restored and verified intact.

### Chunk 3: T054, T055 (changelog and knowledge doc)

- Tasks: 2. Outcome: 2 done, 0 partial, 0 blocked.
- Commit: `12c57bbf3b1bc9180054102f55b2f5e4d0cfd085`
- Files: `changelog/+repository-sync-single-read.changed.md`, `dev/knowledge/backend/git-sync.md`

Flagged upward:

- `speckit-checkpoint-commit` does not exist in this repository and `speckit-git-commit` is marked
  `disable-model-invocation`, so the chunk committed through the `commit` skill. The same applies to
  every chunk in this run.
- The knowledge-doc section carried two factual errors on landing. The review caught both and they
  were fixed in the review pass - see section 5.

### Review-fix pass (not a task chunk)

- Commit: `704e94013458d3b2ea2350cf37362bfbb0406c47`
- Five review findings fixed: one high, four medium. Detail in section 5.

---

## 2. Tasks not completed

| Task | State | Reason |
|------|-------|--------|
| T056 | `[ ]` not started | **Deliberate.** The user's brief said to stop after T055 and hand T056 (run `/pre-ci`, open the increment C pull request) back to them. No `/pre-ci` run and no PR was opened by this run. |

T057 to T060 (Phase 6) were explicitly out of scope and were not touched.

---

## 3. Local-pass evidence

Common environment for every component run: darwin 25.5.0, Python 3.14.7, pytest 9.0.3, Docker
29.7.2 (Docker Desktop), testcontainers `neo4j:2026.05.0-enterprise` plus
`testcontainers/ryuk:0.8.1`, `INFRAHUB_USE_TEST_CONTAINERS=true`, `-n 0` (no xdist),
`-p no:randomly`, `INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES` unset via `env -u`, worktree
`/Users/patrick/Code/.worktrees/infrahub/pog-periodic-sync-one-chunk-IFC-3128`.

| Test id | Type | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|------|-------------|----------------------|---------------------|--------------------|
| `backend/tests/component/git/test_utils.py` (all 6: 3 modified for `-global-` removal, 3 added, then 2 further modified by the review pass, plus the new `branch_registry_restored` autouse fixture) | component | `env -u INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES INFRAHUB_USE_TEST_CONTAINERS=true uv run pytest backend/tests/component/git/test_utils.py -n 0 -p no:randomly -v` | 2026-09-18T10:23:52Z (final, post review fixes) | testcontainers Neo4j; common environment above | `======================= 6 passed, 16 warnings in 20.37s ========================` |
| `backend/tests/component/computed_attribute/test_gather.py::test_gather_trigger_computed_attribute_python_resolves_every_non_global_branch` | component | `env -u INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES INFRAHUB_USE_TEST_CONTAINERS=true uv run pytest backend/tests/component/computed_attribute/test_gather.py -n 0 -p no:randomly` | 2026-09-18T09:30:36Z | testcontainers Neo4j; common environment above | `backend/tests/component/computed_attribute/test_gather.py::test_gather_trigger_computed_attribute_python_resolves_every_non_global_branch PASSED [ 70%]` (suite: `10 passed, 16 warnings in 31.63s`) |
| `backend/tests/integration_docker/test_computed_attributes.py::TestComputedAttributes::test_python_computed_attribute_renders_on_more_than_one_branch` | integration (distributed stack) | `env -u INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES INFRAHUB_TESTING_DOCKER_PULL=false uv run pytest backend/tests/integration_docker/test_computed_attributes.py -m shard_b -n 0 -p no:randomly -v` | 2026-09-18T09:40:18Z | Full stack via testcontainers, compose project `infrahub-test-56822a29` (database, message-queue, cache, task-manager, task-manager-db, 2x infrahub-server, infrahub-server-lb, 2x task-worker, scraper, cadvisor); image `registry.opsmill.io/opsmill/infrahub:local` rebuilt from this branch | `backend/tests/integration_docker/test_computed_attributes.py::TestComputedAttributes::test_python_computed_attribute_renders_on_more_than_one_branch PASSED [100%]` (whole class: `9 passed, 16 warnings in 168.40s`) |
| `backend/tests/component/git/` (T053 regression run, no test modified) | component | `env -u INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES INFRAHUB_USE_TEST_CONTAINERS=true uv run pytest backend/tests/component/git/ -n 0 -p no:randomly` | 2026-09-18T09:32:42Z | testcontainers Neo4j; common environment above | `=========== 111 passed, 1 xfailed, 26 warnings in 111.16s (0:01:51) ============` |

No `MISSING` rows. No `deferred` rows: the distributed-stack test was run locally against a real
stack, not deferred to CI. Its CI equivalent is
`uv run pytest backend/tests/integration_docker/ -m shard_b` in the `backend-docker-integration`
job.

**Mutation check on the high-severity review fix.** Before committing the review pass,
`backend/infrahub/git/utils.py` was deliberately mutated to look `internal_status` up at
`registry.default_branch` instead of `branch_name`, and
`test_get_repositories_commit_per_branch_branches` was observed to FAIL
(`1 failed, 16 warnings in 16.96s`). The mutation was reverted immediately. The assertion therefore
genuinely pins per-branch resolution rather than passing by coincidence.

**T053 confirmation, paste-ready for the PR description:**

> `uv run pytest backend/tests/component/git/` was run against this branch: **111 passed, 1 xfailed**
> in 1m51s. The sync flow tests bootstrap and sync the same repositories as before the refactor:
> `test_sync_repository.py::test_sync_broadcasts_synced_commit` (all four parametrisations),
> `test_git_rpc.py::TestAddRepository::test_git_rpc_create_successful`,
> `test_git_rpc.py::test_git_rpc_merge` and the read-only import tests in
> `test_git_read_only_repository.py` all pass unchanged. Only the read path differs (C2).

---

## 4. Lint and format status

Run after every chunk and again after the review pass, all clean at head `704e94013`:

- `uv run invoke format` - clean
- `uv run invoke lint` - clean (ruff, ty, mypy: "no issues found in 1672 source files")
- `uv run ruff check . --exclude python_sdk` - "All checks passed!"
- `uv run invoke docs.lint` - 0 errors, 5 pre-existing vale warnings in `docs/docs/release-notes/`,
  untouched by this change

`/pre-ci` itself has **not** been run: it is T056, handed back to the user.

---

## 5. Review findings

Four review agents ran in parallel across `2db4b622f..HEAD` (code quality; tests; errors and types;
comments and simplify). **No critical findings.**

### Fixed inline (commit `704e94013`)

| Severity | File | Finding |
|----------|------|---------|
| High | `backend/tests/component/git/test_utils.py` | Every `internal_status` assertion was `"inactive"`, the schema default, so per-branch status resolution was never exercised. A regression returning the default branch's status for all branches passed the whole suite, while `sync_remote_repositories` branches ACTIVE vs STAGING on exactly this value. Fixed: `test_get_repositories_commit_per_branch_branches` now writes `RepositoryInternalStatus.STAGING` on `branch2` while `main` and `branch3` stay `inactive`, asserted by full `model_dump` equality. Mutation-verified (see section 3). |
| Medium | `backend/tests/component/git/test_utils.py:200` | `count_for(...) <= math.ceil(BRANCH_COUNT / CHUNK_SIZE)` also passes at 0 or 1 queries, so deleting `itertools.batched` would keep it green. Changed to `==`, keeping the `math.ceil(...)` expression. |
| Medium | `backend/tests/component/git/test_utils.py` | 199 branches were inserted into `registry.branch` and never removed, which `.agents/rules/testing-python.md` forbids. Added an autouse `branch_registry_restored` save-and-restore fixture, mirroring the precedent at `backend/tests/component/core/query/test_repository_branch_attributes.py:64-72`. |
| Medium | `backend/infrahub/git/utils.py:109` | The fallback warning used an f-string event, giving every occurrence a distinct event string and defeating grouping in a flow that runs once a minute. Rewritten as a static event with `repository=`, `branch=` and `internal_status=` bound as fields, matching the convention in `lock.py`, `locks/cleaner.py` and `dev/guidelines/backend/exceptions.md`. |
| Medium | `dev/knowledge/backend/git-sync.md` | Two factual errors: (a) `ref` was listed among the branch-agnostic fields, but `CoreReadOnlyRepository.ref` is `BranchSupportType.AWARE` and the read deliberately takes the default branch's value for it; (b) the section called `get_repositories_commit_per_branch` "the entry point of the flow and therefore its composition root. No component further down the call chain builds one", which is wrong on both counts - it is a utility called from flows (`git/tasks.py:383`, `computed_attribute/gather.py:66,153`) and a second reader is built at `graphql/queries/repository_branch_status/field.py:40`. Both corrected. |

### Refuted, no action

| Claim | Resolution |
|-------|------------|
| Repositories created on a non-default branch and not yet merged now drop out of the result, exposing `PythonTransformComputedAttribute.repository_commit` to a `KeyError` (raised by chunk 1) | **Not reachable.** `CoreRepository`, `CoreReadOnlyRepository` and `CoreGenericRepository` are all `branch=BranchSupportType.AGNOSTIC` (`core/schema/definitions/core/repository.py:32,69,107`), so the node is written on `-global-` and stays visible from the default branch whichever branch created it. `repositories.get(name)` in `gather.py:93` cannot be `None` for that reason. Corroborated by the deleted `-global-` test expectations, which only arise for agnostic nodes. |

### Deferred, recorded only

| Severity | File | Finding |
|----------|------|---------|
| Medium | `backend/infrahub/git/models.py:262-267` | `branches` and `branch_info` are parallel dicts that must share a key set, an invariant held only by the producer loop; `branch_info` defaults to `{}` while `branches` is required. One `dict[str, RepositoryBranchState]` would make the pairing structural. Pre-existing shape, beyond the flagged change. |
| Medium | `backend/infrahub/git/models.py:251,271` | `RepositoryBranchInfo.internal_status: str` accepts an unvalidated graph string while `RepositoryInternalStatus` exists; `get_staging_branch` compares to the bare literal `"staging"`. Typing it as the enum would make construction the validation boundary. Pre-existing. |
| Medium | `backend/infrahub/computed_attribute/models.py:97-98` | `repository_commit -> str | None` mismodels its own failure: the absent case is a `KeyError` on `branch_commit[self.branch_name]`, not `None`. Pre-existing, not introduced here. |
| Medium | `backend/infrahub/git/utils.py:108-113` | **Contested.** The errors agent argued the `internal_status is None` warning fires on an expected absence (a branch forked before a repository was added) and would train operators to ignore it. The code agent's analysis contradicts this: for an AGNOSTIC node the creation edges also land on `-global-`, making the fallback effectively dead after repository creation, exactly as the spec assumed. Left as written; worth a reviewer's eye. |
| Medium | `backend/tests/component/git/test_utils.py:166-169` | Two of the three provenance assertions (`default_branch`, `location`) are vacuous, since those fields are AGNOSTIC and cannot diverge. Genuine default-branch provenance is proven only for `ref`. This is a limitation of T051's text, not of the implementation. |
| Low | `backend/infrahub/git/utils.py:84-92` | The chunk size bounds the branch dimension only; `repository_ids` is unbounded, so rows per query scale as repositories x 100 x 2. Query *count* matches the docstring and changelog, but per-query cost is multiplicative once a minute. Suggested as a note in `dev/knowledge/backend/git-sync.md` rather than a code change. |
| Low | `backend/infrahub/git/constants.py:5-6` | The comment narrates the rejected alternative (making it a setting), which `.agents/rules/code-doc-style.md` pushes to the PR description. Kept because T048 explicitly demanded that wording. |
| Low | `backend/infrahub/git/utils.py:81-82` | `if not repositories: return repositories` is dead as an optimisation: the reader already short-circuits on empty `repository_ids` without issuing a query. |
| Low | `backend/infrahub/git/models.py:264` | "None when the branch has no commit" understates it: `None` is also written when the `commit` attribute does not resolve at all on that branch. |
| Low | `backend/tests/component/git/test_utils.py:19` | Hardcodes `"node_get_list"` while the neighbouring import uses `RepositoryBranchAttributesQuery.name`. Using `NodeGetListQuery.name` would fail at import on a rename instead of as a confusing `0 == 1`. |
| Low | `backend/tests/integration_docker/test_computed_attributes.py:493` | Asserts `== ["swe-sth-router-1"]` for all main devices, encoding state left by earlier cases in the class; adding any case that creates a main device breaks it. |
| Low | `backend/tests/component/git/test_utils.py:127-135` | Covers `commit.value is None` but not the other arm (`commit is None`, attribute absent from the reader result). |

---

## 6. Autonomous decisions

1. **Chunking.** Phase 5 was split into three chunks rather than one: T048-T050 (core refactor),
   T051-T053 (tests), T054-T055 (docs). The dependency order in tasks.md
   ("T050 to T052 after T049; T053 after T051; T054 and T055 parallel after T049") permits this, and
   it kept each subagent's blast radius to one concern. Chunks ran strictly sequentially.
2. **T056 excluded from every chunk brief.** Each subagent was told explicitly not to run `/pre-ci`
   and not to open a PR, per the user's instruction.
3. **Review-fix triage.** The skill mandates fixing high-severity findings inline. Four medium
   findings were also fixed because each is a direct violation of a repository rule with an existing
   in-repo precedent, and each was cheap and localised: the inexact count assertion, the
   process-global leak, the f-string log event, and the two factual errors in the knowledge doc.
   Everything else was deferred and recorded above rather than fixed, to keep the fix pass scoped to
   what the review actually flagged.
4. **The type-design cluster was deliberately not acted on.** Restructuring `RepositoryData` into a
   single per-branch dataclass and typing `internal_status` as the enum are real improvements, but
   they touch a shape that predates this change and were not part of any Phase 5 task. They are
   recorded as deferred findings instead.
5. **The contested warning-noise finding was left as written.** Two review agents reached opposite
   conclusions about whether the `internal_status is None` fallback is reachable in practice. The
   code agent's argument (AGNOSTIC node, creation edges on `-global-`) is the better-evidenced one
   and matches the spec's own assumption, so the code was left alone and the disagreement recorded.
6. **`/pre-ci` was not run.** It is part of T056. Lint, format, ruff over the whole repository and
   `docs.lint` were all run and are clean, but the full pre-CI gate has not been exercised.

---

## 7. Suggested next steps

1. **Run `/pre-ci`** at `704e94013`. This is the first half of T056 and has not been run.
2. **Open the increment C pull request** against the integration branch
   `cross-branch-repo-status-infp-671` (not `develop`). Include in the description: the T050
   caller-confirmation paragraph (section 1), the T053 run confirmation (section 3), the query-count
   assertion output that T056 asks for, and the note that only `ref` can genuinely diverge per
   branch so the T051 provenance clause was partly unsatisfiable as written (section 1).
3. **Close the IFC-3128 Jira subtask** once the PR is open.
4. **Decide on the deferred findings** in section 5. The `RepositoryData` restructuring and the
   enum-typed `internal_status` are the two worth a follow-up ticket; the rest are notes.
5. **Phase 6 (T057 to T060)** remains untouched and is the next slice. T057 in particular will want
   to sweep this spec directory for figures the implementation changed.
