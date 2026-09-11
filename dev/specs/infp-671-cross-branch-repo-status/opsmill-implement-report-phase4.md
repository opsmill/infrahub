# Implementation report: Cross-branch Repository Status Query, Phase 4

**Run status: COMPLETE.** Every Phase 4 task is `[X]`, every test added or modified was observed
passing locally, and the final tree passes the locally-executable CI checks. Two review findings
rated HIGH; one was fixed inline with a before/after regression test, the other was recorded on the
repository owner's explicit instruction rather than fixed.

Written as a sibling to `opsmill-implement-report.md` (which covers Phase 3) rather than
overwriting it, following that file's per-phase convention.

| | |
| --- | --- |
| Feature | Cross-branch Repository Status Query, Phase 4 (Increment B, graph read) |
| Jira | [IFC-3127](https://opsmill.atlassian.net/browse/IFC-3127), under epic IFC-3104 |
| Spec dir | `dev/specs/infp-671-cross-branch-repo-status` |
| Branch | `pog-infrahubrepobranch-read-attr-from-graph-IFC-3127` |
| PR base | `cross-branch-repo-status-infp-671` (the integration branch, not `develop`) |
| Base commit | `5a4c0a9a1` |
| Head commit | `b79687077` |
| Commits | 7 |
| Diff | 20+ files, roughly +1700 / -430 |
| Scope | Phase 4 only: T033 to T047, plus T034a added mid-run. Nothing from Phase 5 or 6. |

## 1. Chunk-by-chunk ledger

### Chunk 1: Core primitive (T033, T034, T035, T036)

4 tasks, 4 done. Commit `c09543957`.

Added `RepositoryBranchAttributesQuery` and the frozen `RepositoryBranchAttributeValue` to
`backend/infrahub/core/query/repository.py`, and `RepositoryBranchAttributesReader` to
`backend/infrahub/core/repository_branch_status/reader.py`.

Flagged upward:

- **T034's `Branch.name` criterion FAILED.** No `Branch` entry existed in
  `backend/infrahub/core/graph/index.py`, so the opening `UNWIND ... MATCH (br:Branch {name:
  branch_name})` compiled to `NodeByLabelScan` under an `Apply`. Escalated to the owner, measured,
  and resolved as T034a below.
- `self.limit` is set even though `insert_limit = False`, because `Query.execute()` treats a READ
  with neither `limit` nor `offset` as unpaginated and would loop forever on a statement that
  cannot have SKIP/LIMIT appended. Deliberate, per `dev/knowledge/backend/query-pattern.md`.
- `default_window` uses `CASE WHEN br.is_isolated THEN br.branched_from ELSE $at END`
  unconditionally, whereas `get_branches_and_times_to_query_global` applies `branched_from` only
  when `at > branched_from`. Implemented as the spec dictated; recorded as review finding 7.
- The graph stores an unset attribute value as the string `"NULL"`; `get_data()` maps it to `None`.

### Chunk 2: Resolver swap (T037, T038, T039)

3 tasks, 3 done. Commit `10f2eda66`. 94 tests passing at that point.

Swapped `build_attribute_source` to the real reader, deleted `stub.py`, removed the
`unsupported_filters` guard, wired `apply_value_filters`, restored the `own_values_only` widening
in `_attribute_names`.

Flagged upward:

- Work beyond the three task IDs, unavoidably: three increment-A component assertions pinned
  fabricated values and had to be re-pointed at the graph.
- **The fixture ordering trap:** `repository_branch_status_branches` saves its branches before the
  repositories are created. Passed forward to every later chunk.
- Regenerated `schema/schema.graphql` and the frontend `types.ts` for the description change.

### Chunk 2b: `Branch(name)` index (T034a, added mid-run)

1 task, 1 done. Commit `f85248486`.

Not in the original `tasks.md`. Added after the owner approved it on measured evidence, and
recorded as a ticked T034a so the deviation is visible to a reviewer rather than silent. All four
T034 EXPLAIN criteria pass with it in place.

### Chunk 3: Tests for increment B (T040, T041, T042, T043)

4 tasks, 4 done. Commit `7ea524766`. 114 tests passing.

Flagged upward, and this is the most valuable finding of the run:

- **The fixture trap as briefed was too broad, and the correction matters.** Node creation writes
  attributes on the global branch when `Node.get_branch_based_on_support_type` returns global for
  the AGNOSTIC repository kinds, and global edges are visible on every branch regardless of fork
  point. So a repository created after the branches still resolves its *creation* value everywhere;
  only subsequent imports are windowed by the fork point. This made
  `contracts/core-primitive.md`'s `own_value is False` on `main` correct, and it meant the
  differential test would have been vacuous without a post-creation import on `main`, which the
  agent added rather than letting it pass hollowly. (Chunk 6 later narrowed this again: it holds
  for `LOCAL` attributes on an AGNOSTIC node, not for `AWARE` ones.)
- FR-011's obvious test would have measured the wrong thing: comparing `ROWS_QUERY` to
  `NAMES_ONLY_QUERY` measures the attribute selection, not `count`. Replaced with two documents
  differing only in `count`.
- B4/B5 needed four extra branches, added via a module-scoped autouse fixture, with row-count
  constants moved 212 to 216 and 213 to 217.

### Chunk 4: Documentation and hygiene (T044, T045, T045a, T045b, T045c, T045d)

6 tasks, 6 done (T045c with a substituted mechanism). Commit `9c61a8f5f`. 118 tests passing.

Flagged upward:

- **T045c did not ship the approved snippet.** `prepare_graphql_params` ends with
  `at=Timestamp(at)` and `Timestamp(None)` is now, so `graphql_context.at` is never `None` and
  `if graphql_context.at is not None: raise` would have rejected 100% of requests. Substituted
  `request.query_params.get("at")`, independently verified against `graphql/app.py:206` as the sole
  source of `at` for the GraphQL endpoint. The decision (reject) is intact; only the detection
  changed.
- **Two changelog fragments, not one.** The `Branch(name)` index is not covered by the
  unreleased-feature exception: no such index existed before, and about ten existing call sites do
  `MATCH (b:Branch {name: ...})`.
- `docs.validate` is `git diff --exit-code docs`, so it only reads clean post-commit.

### Chunk 5: Error-path review and gate (T046, T047)

2 tasks, 2 done. Commit `55f093138` (tasks.md only; no source change was required).

`/pre-ci` fully green on first run. T046's `except` criterion holds: the only `except` clause in
the slice is `permissions.py:61` catching `InitializationError`. All nine raise sites have a named
provoking test.

One deliberate deviation, recorded for the owner: `models.py:38` raises a plain `ValueError`, not
an Infrahub `Error` subclass, on the duplicate-triple guard. The reasoning is that the Cypher makes
the duplicate impossible, so reaching it is a server-side integrity bug that should surface as a
500 rather than as a clean client-facing message with `data: null`. T046's text says "every raised
error is an Infrahub `Error` subclass", so this is a knowing deviation.

### Chunk 6: Review fixes

Commit `b79687077`. 119 tests passing.

Fixed review findings 1 (HIGH), 5, 6, 9, 10 and the finding-12 nits. Details in section 5.

## 2. Tasks not completed

Every Phase 4 task is `[X]`. Two acceptance clauses inside completed tasks could not be met:

| Task | Unmet clause | Reason |
| --- | --- | --- |
| T047 | "Jira subtask from T032 closed" | **No such issue exists.** Epic IFC-3104's children are IFC-3125 through IFC-3132, verified against Jira. T032 asked for a "Remove InfrahubRepositoryBranchStatus stub" task that was never created. Per instruction, not created. The stub is nonetheless deleted, so the clause is moot in substance. Owner to decide whether IFC-3127 subsumes it. |
| T047 | "open the increment B pull request" | Deliberately not done. The owner opens the PR; the PR body is handed over instead. |

Housekeeping: T031 and T032 were ticked as instructed. Only those two were actually unticked at or
below T032; T001 to T030 were already `[X]`, and T007, T009, T009a, T009b, T010 and T030a are
struck through as dropped, so they carry no checkbox.

## 3. Local-pass evidence

Environment for every row: worktree
`/Users/patrick/Code/.worktrees/infrahub/pog-infrahubrepobranch-read-attr-from-graph-IFC-3127`,
darwin 25.5.0, Python 3.14.7, pytest 9.0.3, Neo4j via testcontainers (Docker running).
Component runs used `-p no:randomly --no-cov`.

| Test id | Type | Run command | Passed at (ISO 8601) | Environment | Verbatim pass line |
| --- | --- | --- | --- | --- | --- |
| `component/core/query/test_repository_branch_attributes.py` (10 tests: the 9 reader tests plus the differential test) | component | `uv run pytest backend/tests/component/core/query/test_repository_branch_attributes.py -q -p no:randomly --no-cov` | 2026-09-10T14:06:51Z | testcontainers Neo4j | `10 passed, 16 warnings in 9.38s` |
| `component/graphql/queries/test_repository_branch_status.py` (82 tests: 67 pre-existing, 10 from T042/T043, 2 from T045c, 3 from the review fix) | component | `uv run pytest backend/tests/component/graphql/queries/test_repository_branch_status.py -q -p no:randomly --no-cov` | 2026-09-10T14:06:25Z | testcontainers Neo4j | `82 passed, 16 warnings` |
| `unit/graphql/queries/test_repository_branch_status.py` (27 tests) | unit | `uv run pytest backend/tests/unit/graphql/queries/test_repository_branch_status.py -q -p no:randomly --no-cov` | 2026-09-10T14:07:11Z | none | `27 passed, 16 warnings in 0.13s` |
| All three files together, post-commit at `b79687077` | mixed | `uv run pytest <all three> -q -p no:randomly --no-cov` | 2026-09-10T14:10:26Z | testcontainers Neo4j | `119 passed` |
| `query_benchmark/test_repository_branch_attributes.py::test_repository_branch_attributes[benchmark_config0]` and `[benchmark_config1]` | benchmark (opt-in) | `uv run pytest backend/tests/query_benchmark/test_repository_branch_attributes.py -q -p no:randomly --no-cov` | 2026-09-10T13:21:04Z | testcontainers Neo4j | `2 passed, 16 warnings in 30.12s` |
| `component/conftest.py::repository_branch_status_branches` teardown (T045d), cross-module proof | component | `uv run pytest <status file> <primitive file> test_order.py test_hfid.py test_relationship.py test_status.py -q -p no:randomly --no-cov` | 2026-09-10T13:27:01Z | testcontainers Neo4j | `94 passed, 16 warnings in 24.62s` |
| Whole backend unit suite, final tree | unit | `uv run invoke backend.test-unit` | 2026-09-10T14:2xZ | none | `2523 passed, 18 warnings in 57.20s` |

No `MISSING` rows. `backend/tests/query_benchmark/` is opt-in and not part of the default suite
(`testpaths = ["tests"]`, no CI job references it, mypy-excluded); it was nonetheless run locally,
so it is a normal row rather than a deferral.

**FIX 1 regression proof** (the one test that must fail before the fix):

Before, with the resolver change stashed:

```
E   assert 0 == 3
E   assert 0 == 4
E   AssertionError: assert frozenset() == {'sync_status'}
FAILED ...::test_the_sync_status_filter_applies_when_the_document_does_not_select_it
FAILED ...::test_the_internal_status_filter_applies_when_the_document_does_not_select_it
FAILED ...::test_a_value_filter_widens_the_read_by_the_attribute_it_compares
3 failed, 79 deselected, 16 warnings in 11.12s
```

After: `3 passed, 79 deselected, 16 warnings in 8.07s`.

**T045d teardown proof.** With the teardown stashed, a probe module run after the fixture's own
module failed with `assert [...218 more items...] == []`. With it restored, `80 passed`.

## 4. Review findings

Full pass over `5a4c0a9a1..HEAD`.

| Sev | File | Finding | Disposition |
| --- | --- | --- | --- |
| HIGH | `resolver.py:210-217` with `paging.py:44-47` | `sync_status__value` / `internal_status__value` silently returned zero rows unless the caller also selected that attribute in the document. `_attribute_names` widened by `commit` for `own_values_only` but not by the filtered attribute, so `_value_of` read `None` and dropped every row, returning `count: 0` with no error. | **Fixed inline** (`b79687077`), with a test that fails before and passes after. |
| HIGH | `resolver.py:55-57` | The `at` rejection is bypassable: `api/query.py:64` and `api/transformation.py:67,136` call `prepare_graphql_params(at=branch_params.at, ...)` with no `request=`, so `context.request is None`, the guard no-ops, and a saved `CoreGraphQLQuery` fetched via `GET /api/query/<name>?at=<past>` returns current branches with historical values and a 200. | **Code not fixed, on the owner's explicit instruction:** that path is not an expected way to run this query, and it becomes a new issue if it ever comes up. Cubic raised the same point against the *contract wording* after PR review, which was a fair hit: `contracts/graphql-repository-branch-status.md` claimed the rejection unconditionally. The contract now states the boundary, so the document no longer overclaims what the code guarantees. |
| MEDIUM | test files | Read-only repository kind (`CoreReadOnlyRepository`) takes a different edge-placement path (`commit` and `ref` are `AWARE`, so they land on the current branch at creation) and has no value coverage. `own_values_only` is true on the default branch without any import, contradicting the docs. | Deferred; docs corrected in `b79687077`. Chunk 6 flags this as the most likely place for a surprise. |
| MEDIUM | `test_repository_branch_attributes.py:303-357` | The differential test is substantive, not vacuous, but every fixture timestamp is strictly ordered, so a strict/non-strict boundary flip (`from <=` to `from <`) is undetectable. Copying those operators verbatim is the single stated correctness requirement for this Cypher. | Deferred. One test passing an explicit `at` equal to an edge timestamp would close it. |
| MEDIUM | `test_repository_branch_status.py:1998-2010` | The injection harness hand-rolled a replica of the production `Field` omitting six arguments, which is the structural reason finding 1 had no test. | **Fixed inline**; all six added. |
| MEDIUM | `test_repository_branch_status.py:1569-1611` | Two `DOCUMENT_SHAPES` exercising the broken filter asserted only "no error, truthy data, no bus message", so they passed on a zero-row answer. | **Fixed inline**; they now assert exact rows. A third shape (`own-values-only`) still has the same weakness. |
| MEDIUM | `repository.py:85` | `default_window` omits the `at > branched_from` guard that `branch/models.py:314` applies, so a historical read at a time before a branch was created gets a too-permissive default-branch window. | **Fixed after PR review** (cubic raised it independently). Now `CASE WHEN br.is_isolated AND br.branched_from < $at THEN ...`. No-op for current reads; pinned by `test_a_read_before_a_branch_forked_uses_the_requested_time_not_the_fork_point`, verified failing before the change. |
| MEDIUM | `repository.py:66` | Setting `self.limit` steers into the single-shot branch, so `query_with_size_limit`'s chunking never applies and no `LIMIT` is emitted. At 3000 branches a read-only repository fetches 12,000 rows to render 40. | Deferred. The trade-off is real (server-side `count` needs every row) but deserves an explicit ceiling. |
| MEDIUM | `dev/knowledge/backend/query-pattern.md` | Stated the AGNOSTIC rule too broadly (`attribute.py:684-689` has no `AWARE` arm), making its worked conclusion false for `CoreReadOnlyRepository`. | **Fixed inline.** |
| MEDIUM | `branch-synchronization.mdx:285,288` | Stated the inheritance rule unconditionally; wrong for non-isolated branches and for repositories created after a fork, and `own_values_only` described wrongly for the read-only kind. | **Fixed inline.** |
| MEDIUM | `repository.py:106,120` | No coverage for a soft-deleted value or repository (`WHERE r.status = "active"` and the `r.status ASC` tie-break). | Deferred. |
| LOW | various | Code cross-references in a source comment, an inaccurate docstring, a missing `Raises:` on the protocol, a changelog overclaim about `ref`, a tautological assert, British spellings, spec vocabulary in a test docstring, an over-long inline comment. | **All fixed inline.** |

### Post-PR review (cubic, PR #10606)

Cubic raised three issues against the opened PR. All three were checked against the code and all
three were valid; two were items this report had already recorded and deferred, which is a fair
signal they were under-called.

| Sev | Finding | Disposition |
| --- | --- | --- |
| P2 | `contracts/graphql-repository-branch-status.md` documented `at` as unconditionally rejected, which the code does not guarantee. | Fixed: the contract now names `/graphql` and states the saved-query and transformation boundary. |
| P2 | `repository.py` `default_window` moved the window forward to `branched_from` even when `at` predates the fork. | Fixed, with a regression test proven to fail before the change. |
| P3 | The fixture teardown emptied the database but restored a pre-setup registry snapshot, leaving registry and database mutually inconsistent. | Fixed: `registry.delete_all()` runs after the wipe, then the snapshot's registered types are restored while `branch`, `_schema` and `_default_ipnamespace` stay cleared. |

A second cubic pass on the fix commit found two more, both valid:

| Sev | Finding | Disposition |
| --- | --- | --- |
| P3 | This report marked the `default_window` divergence fixed in the findings table while section 7 still listed it for triage. | Fixed: section 7 no longer lists it. |
| P3 | The first teardown fix only *skipped restoring* the database-backed registry fields, so the values this module built stayed in place and still described deleted rows - the docstring asserted the opposite of what the code did. | Fixed: `registry.delete_all()` now actually clears them, which makes the docstring true rather than the docstring being softened to match. |

The teardown fix was verified with a throwaway probe module run after the fixture's own module,
asserting `registry.branch == {}` and `registry._schema is None`: it FAILED against the previous
teardown and passed against the fixed one. The probe was then deleted rather than committed,
because a test asserting what a *previous* module left behind depends on module execution order and
worker assignment, and would be flaky under the xdist configuration component tests run with. The
teardown therefore has no permanent regression guard; that is a deliberate trade and the reason
this behaviour has now been got wrong twice.

Explicitly checked and cleared by the reviewer, not merely unexamined:

- **The visibility predicate is correct.** Non-strict `from <=` with strict `to >`, matching
  `Branch.get_query_filter_path`'s branch loop verbatim, not the `branch_agnostic` shortcut's
  strict `from <`. This was the single highest-risk item in the Cypher.
- The missing global-branch-at-fork-point clause was traced case by case: the extra candidate the
  upstream helper admits is always the older edge and always loses the `from DESC` tie-break, so
  the elected winner is identical.
- No em dash or en dash anywhere in the diff. No Jira, GitHub or spec IDs in source.
- `.agents/rules/testing-python.md` clean: no `unittest.mock`, no `MagicMock`, no `patch`, no
  `monkeypatch`; the recording source and fixed factory are the prescribed injected-double pattern.
- The conftest fixture restore is sound: `Registry` is a dataclass so `dict(vars(registry))`
  captures every field, and `registry.delete_all()` rebinds rather than clearing in place.
- `count_for` / `rows_for` assert absolute values, so a read that silently returned nothing fails.

## 5. `/pre-ci` result

Run at chunk 5 (commit `55f093138`), fully green across every applicable check: whole-repo ruff,
`ty`, mypy on 1670 files, 2523 backend unit tests, 1270 frontend tests, both lockfiles, all four
generated-file validations, markdownlint and Vale. Nothing failed and no source file needed
changing.

Re-verified after the review fixes at `b79687077`, because source changed after that run:

| Check | Result |
| --- | --- |
| `uv run ruff check . --exclude python_sdk --no-cache` | All checks passed |
| `uv run invoke backend.validate-generated` | no drift; `git status` empty afterwards |
| `uv run invoke docs.validate` | no drift; `git status` empty afterwards |
| `uv run invoke backend.test-unit` | `2523 passed, 18 warnings in 57.20s` |
| `uv run invoke docs.lint` | 0 markdownlint issues; Vale 0 errors, 5 warnings, all in untouched files |
| `uv run mypy` on changed files | Success, no issues |

Vale's 5 warnings are in `learn/labs/overview.mdx`, `transformations/python.mdx` and three
release-notes pages, none of which this branch touches.

## 6. Autonomous decisions

Decisions the owner may want to revisit:

1. **Chunking.** Phase 4 was split into five chunks along the `tasks.md` sub-headings, plus a sixth
   for review fixes and an unplanned chunk 2b for the index. Chunks ran strictly sequentially
   because they share files.
2. **Worktree repair before any work.** The worktree had uninitialised submodules and an editable
   install mapping only `backend` and `python_testcontainers`, so `import infrahub_sdk` failed.
   Fixed with `git submodule update --init --recursive` and
   `uv sync --all-groups --reinstall-package infrahub-server`. Not committed; environment only.
3. **T034a invented.** The `Branch(name)` index is not in `tasks.md`. Added as a ticked T034a after
   escalation and measurement, so the deviation is auditable.
4. **Measurement before the index decision**, at the owner's request, rather than acting on planner
   estimates. This corrected an argument of mine: I claimed the index would also fix the
   pre-existing `Branch.get_by_name` scan, and measurement showed it does not (db-hits 428 to 24,
   wall-clock unmoved, because that lookup is round-trip-bound). The index is justified by the new
   query alone.
5. **T045c's mechanism substituted** without re-asking, because the approved snippet was provably
   unusable. Escalated immediately after.
6. **Finding 2 recorded rather than fixed**, on the owner's explicit instruction.
7. **The `ValueError` deviation in `models.py:38` left standing**, flagged rather than converted.
8. **Report written as a sibling file** rather than overwriting the Phase 3 report.

## 7. Suggested next steps

1. **Open the PR.** Base `cross-branch-repo-status-infp-671`, not `develop`. The body, carrying the
   T034 EXPLAIN plan and the T046 error-path checklist, was handed over in the session.
2. **Decide the two open questions**: whether IFC-3127 subsumes the never-created "Remove
   InfrahubRepositoryBranchStatus stub" task, and whether the `ValueError` in `models.py:38` should
   become an Infrahub `Error` subclass.
3. **Triage the deferred MEDIUM findings.** In rough order of risk: read-only repository value
   coverage (the review's own pick for most likely surprise), an explicit ceiling on the result
   set, and soft-delete coverage. The `default_window` divergence is no longer on this list: it was
   fixed after the PR review. The differential test's boundary-timestamp gap is partly closed by
   the regression test that fix carried, which reads at an exact edge timestamp and so pins the
   non-strict `from <=`; a case for the `to >` arm would finish it.
4. **Sweep the contract docs in Phase 6.** `contracts/graphql-repository-branch-status.{md,graphql}`
   and `plan.md` still describe the stub window; T057 owns that.
5. Phase 5 (T048 onward, IFC-3128, the periodic sync) is untouched and ready.
