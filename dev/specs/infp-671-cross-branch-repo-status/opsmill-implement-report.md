# Implementation report: Cross-branch Repository Status Query, Phase 3

**Run status: COMPLETE**, with one caveat that is not a blocker: the frontend app test suite is
flaky on this machine and never came back clean. It produced zero assertion failures across two
full runs, this branch changed no runtime frontend source, and every backend test this run added was
observed passing locally. Details in section 6.

| | |
| --- | --- |
| Feature | Cross-branch Repository Status Query, Phase 3 (Increment A, contract stub) |
| Spec directory | `dev/specs/infp-671-cross-branch-repo-status` |
| Jira | [IFC-3126](https://opsmill.atlassian.net/browse/IFC-3126) (PR 2 of 5), epic [IFC-3104](https://opsmill.atlassian.net/browse/IFC-3104) |
| Branch | `pog-InfrahubRepositoryBranchStatus-IFC-3126` |
| Base commit | `5d76c2b50cdff5008701e55470576ff3f19367ec` |
| Head commit | `6350181bd9` |
| Diff | 22 files changed, 2979 insertions, 89 deletions |
| Scope run | T012 to T030, excluding the dropped T030a and the excluded T031 and T032 |
| Wall clock | Approximately 1h55m from preflight to report |

Phases 1 and 2 landed previously on the integration branch and were not touched. Phases 4, 5 and 6
were not started.

## 1. Chunk-by-chunk ledger

### Chunk 1: shapes shared by stub and reader (T014 to T016)

| | |
| --- | --- |
| Tasks | 3 |
| Outcome | 3 done, 0 partial, 0 blocked |
| Commit | `d80d9fd31e` |

New modules: `backend/infrahub/core/query/repository.py` (frozen
`RepositoryBranchAttributeValue`), `backend/infrahub/core/repository_branch_status/models.py`
(frozen `RepositoryBranchAttributes`), `.../interface.py`
(`RepositoryBranchAttributesSource(Protocol)`).

Flagged upward:

- `RepositoryBranchAttributes` is built through a `from_values(values=...)` classmethod, because a
  frozen dataclass cannot derive its own field in `__init__`. It groups by
  `(repository_id, branch_name)` internally rather than by the flat triple, so `for_branch` is an
  O(1) lookup instead of a scan per assembled row. The `get` and `for_branch` contract is
  unchanged, but `data-model.md`'s "holds a `Mapping` keyed by the triple" line is now imprecise
  and was left untouched. The Phase 4 reader (T033, T035) must construct through `from_values`.
- The Protocol keeps `Sequence[str]` and `Collection[str]` as the task text and
  `contracts/core-primitive.md` specify, which sits against `dev/guidelines/backend/python.md`'s
  preference for a concrete container. Kept as specified because the Phase 5 caller passes
  `batched()` tuples and a set of attribute names.

### Chunk 2: GraphQL types and pure helpers (T017 to T022)

| | |
| --- | --- |
| Tasks | 6 |
| Outcome | 6 done, 0 partial, 0 blocked |
| Commit | `16490337d1` |

New modules: `backend/infrahub/graphql/types/repository_branch_status.py` (three graphene types,
exported from `types/__init__.py`), and `paging.py`, `stub.py`, `payload.py`, `kind_dispatch.py`,
`permissions.py` under `backend/infrahub/graphql/queries/repository_branch_status/`.

Flagged upward:

- The generated SDL block for all three types came out byte-identical to the frozen contract, so no
  contract change was needed.
- `kind_dispatch.py` also exports `REPOSITORY_KIND_POLICIES` (a `MappingProxyType`) so
  `permissions.py` derives the two permission names from the policies instead of hardcoding them a
  second time. `policy_for_kind` remains the dispatch entry point. See the deferred findings, where
  a reviewer argues this second door should be closed.
- `ensure_any_kind_viewable` denies through `raise_for_permission` on the first policy's permission,
  so the message names one permission and never a kind list.
- Environment: this worktree had uninitialised submodules and a stale editable install, so
  `import infrahub_sdk` failed. Fixed with `git submodule update --init --recursive` and
  `uv sync --all-groups --reinstall-package infrahub-server`. No repo file changed.

### Chunk 3: resolver, wiring, registration and generated files (T023 to T026)

| | |
| --- | --- |
| Tasks | 4 |
| Outcome | 4 done, 0 partial, 0 blocked |
| Commit | `24df8012c7` |

New modules `resolver.py` and `field.py` (the composition root); the field registered on
`InfrahubBaseQuery` in `backend/infrahub/graphql/schema.py` by direct import;
`schema/schema.graphql` and `frontend/app/src/shared/api/graphql/generated/types.ts` regenerated.

Flagged upward:

- Zero divergence from the frozen contract: field name, type, all eleven arguments, every default
  (`limit: Int = 40`, `offset: Int = 0`, `partial_match: Boolean = false`,
  `own_values_only: Boolean = false`) and every description match. The SDL printer sorts arguments
  alphabetically while the contract lists them in declaration order, which is presentation only.
- `raise_on_error=True` does not exist on `NodeManager.get_one_by_id_or_default_filter`. It always
  delegates to `get_one_by_default_filter(raise_on_error=True)`, so a miss raises
  `NodeNotFoundError` as required, but T023's task text names a parameter that is not there.
- `branch=None` resolves to the default branch inside both the lookup and `db.schema.get`, so
  `field.py` stays the only module that reads `registry`.
- `at=graphql_context.at` was added to the repository lookup and to the source `read`, which T023's
  literal call list omits. Without it a time-travel request would resolve the node at now and the
  attributes at `at`.
- Process note from the subagent: it flipped the four tasks.md checkboxes with a `uv run python`
  heredoc, against the global instruction to mutate files only through the edit tools. The
  resulting diff was verified to be exactly the four checkbox flips and nothing else.

### Chunk 4: fixtures and tests (T012, T013, T027 to T030)

| | |
| --- | --- |
| Tasks | 6 |
| Outcome | 6 done, 0 partial, 0 blocked |
| Commit | `dd1a0ac63d` |

`repository_branch_status_branches` (module-scoped, 214 branches with explicit increasing
`created_at`) and `make_repository_pair` in `backend/tests/component/conftest.py`; 32 unit tests;
51 component tests across three classes.

Flagged upward:

- **T028's `TestInfrahubApp` instruction does not hold with the T012 fixture.** Module scope sets up
  before class scope, so `TestInfrahub.default_branch` (class-scoped, `delete_all_nodes`) would wipe
  the fixture's branches, and `initialize_registry` calls `initialization()`, which loads a schema
  per branch: unusable at 214 branches. The module therefore uses plain classes with
  `prepare_graphql_params` plus `tests.helpers.graphql.graphql`, the pattern of the sibling
  `test_event_account_permissions.py`. The test reviewer assessed this substitution and found it
  costs no coverage in scope: `prepare_graphql_params` produces the same `GraphqlContext` the API
  route builds, and the contract to pin is a `PermissionDeniedError` in `errors` with `data` null,
  not an HTTP status. Only HTTP-layer concerns go unpinned, none of which this PR changes.
- `tests/helpers/permissions.py::define_permissions` now takes `role_name` and `group_name`, with
  the previous values as defaults. `CoreAccountRole.name` and the group name are unique, so the
  permission matrix could not otherwise grant several accounts in one database. Its existing
  consumers were regression-tested.
- Test-environment contention: `INFRAHUB_USE_TEST_CONTAINERS=false` is preset on this machine, and a
  concurrent session in the sibling worktree `pog-publish-git-state-resolver-IFC-3146` was running
  component tests against the same shared `infrahub-database-1` and wiping it mid-run. Every green
  run reported below therefore used `INFRAHUB_USE_TEST_CONTAINERS=true` for isolation.

### Review fix pass (Phase 6 output)

| | |
| --- | --- |
| Fixes applied | 11 of 11 |
| Commit | `2b127d2aaa` |

Two high-severity findings and nine mediums and lows, listed in section 5. No fix required an SDL
change, and `git diff --exit-code schema/schema.graphql` was confirmed clean afterwards.

### Orchestrator fixup

| | |
| --- | --- |
| Commit | `6350181bd9` |

`/pre-ci` Phase 3D caught two generated files the task list never named. `pnpm codegen` runs
`graphql-codegen`, which writes `types.ts` only; the gql.tada artifacts
`graphql-env.d.ts` and `graphql-cache.d.ts` come from `pnpm codegen:graphql`. T026 names only the
first, so the new root field was missing from the introspection output and all 65 cached document
hashes were stale. CI's `frontend-validate-graphql-types` job checks both files and would have
failed. See section 6.

## 2. Tasks not completed

No task in the run's scope is still `[ ]`. Every one of T012, T013, T014 to T030 is `[X]`.

Deliberately out of scope, unchanged and still `[ ]`:

- **T031** (run `/pre-ci`, open the pull request) and **T032** (frontend handoff, stub-removal Jira
  task) were excluded from the chunk plan at your instruction; you are doing both. The `/pre-ci`
  half of T031 was nevertheless run and is recorded in section 6.
- **T030a, T007, T009, T009a, T009b, T010** are dropped in tasks.md and were not implemented.
- **T033 to T060** are Phases 4, 5 and 6 and were not started.

## 3. Local-pass evidence

Environment for every row: macOS Darwin 25.5.0, Docker 29.7.2 build a7dcaa6, Python 3.14,
component runs under `INFRAHUB_USE_TEST_CONTAINERS=true` (testcontainers, isolated throwaway Neo4j
per run, `testcontainers-ryuk:0.8.1` observed) rather than the machine's preset `false`, because a
concurrent session was mutating the shared dev database. No compose project involved. Unit runs
need no services.

| Test id | Type | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
| --- | --- | --- | --- | --- | --- |
| `backend/tests/unit/graphql/queries/test_repository_branch_status.py` (34 tests, final) | unit | `INFRAHUB_USE_TEST_CONTAINERS=true uv run pytest backend/tests/unit/graphql/queries/test_repository_branch_status.py -v` | 2026-09-08T14:16:40Z | no services required | `======================= 34 passed, 16 warnings in 0.16s ========================` |
| `backend/tests/component/graphql/queries/test_repository_branch_status.py` (64 tests, final) | component | `INFRAHUB_USE_TEST_CONTAINERS=true uv run pytest backend/tests/component/graphql/queries/test_repository_branch_status.py -v` | 2026-09-08T14:18:04Z | testcontainers, Docker 29.7.2 | `======================= 64 passed, 16 warnings in 26.49s =======================` |
| both files together (98 tests) | unit + component | `INFRAHUB_USE_TEST_CONTAINERS=true uv run pytest backend/tests/unit/graphql/queries/test_repository_branch_status.py backend/tests/component/graphql/queries/test_repository_branch_status.py -q --no-header` | 2026-09-08T14:19:44Z | testcontainers, Docker 29.7.2 | `======================= 98 passed, 16 warnings in 25.69s =======================` |
| pre-fix baseline, both files (83 tests) | unit + component | `INFRAHUB_USE_TEST_CONTAINERS=true uv run pytest backend/tests/unit/graphql/queries/test_repository_branch_status.py backend/tests/component/graphql/queries/test_repository_branch_status.py -q --no-header` | 2026-09-08T13:52:30Z | testcontainers, Docker 29.7.2 | `======================= 83 passed, 16 warnings in 32.57s =======================` |
| `test_branch.py` + `test_mutation_context.py` regression (26 tests) | component | `INFRAHUB_USE_TEST_CONTAINERS=true uv run pytest backend/tests/component/graphql/queries/test_branch.py backend/tests/component/graphql/mutations/test_mutation_context.py -q --no-header` | 2026-09-08T13:53:47Z | testcontainers; consumers of the widened `define_permissions` and the shared conftest | `================== 26 passed, 16 warnings in 85.52s (0:01:25) ==================` |
| `backend/tests/unit/graphql` registration guard (147 tests) | unit | `uv run pytest backend/tests/unit/graphql -q -p no:randomly` | 2026-09-08T13:29:10+02:00 | no services required | `======================= 147 passed, 16 warnings in 0.34s =======================` |
| full backend unit suite (2528 tests) | unit | `uv run invoke backend.test-unit` | 2026-09-08T14:31Z | no services required; `/pre-ci` Phase 5.1 | `====================== 2528 passed, 18 warnings in 50.77s ======================` |
| `@infrahub/graph` suite (23 tests) | frontend unit | `pnpm --dir frontend/packages/graph run test` | 2026-09-08T14:36:39Z | vitest 4.1.10 | `Test Files  5 passed (5)` / `Tests  23 passed (23)` |
| `src/shared/components/inputs/list.test.tsx` (12 tests, flake demonstration) | frontend unit | `pnpm --dir frontend/app exec vitest run src/shared/components/inputs/list.test.tsx` | 2026-09-09T07:52:43Z | vitest 4.1.10 browser mode, chromium, warm Vite dep cache; fails on a cold cache | `Test Files  1 passed (1)` / `Tests  12 passed (12)` |

The frontend app suite as a whole is **not** clean locally and is recorded as such in section 6,
with both runs' counts. This branch added no frontend test and changed no runtime frontend source,
so no row here is owed for it.

Per-test `PASSED` lines for the 15 tests added or modified by the review fix pass, from
`INFRAHUB_USE_TEST_CONTAINERS=true uv run pytest <file> -v`:

```text
backend/tests/unit/graphql/queries/test_repository_branch_status.py::TestBuildAttributePayload::test_updated_at_is_a_datetime_the_graphql_type_accepts PASSED [ 47%]
backend/tests/unit/graphql/queries/test_repository_branch_status.py::TestBuildAttributePayload::test_absent_updated_at_yields_none PASSED [ 50%]
...::TestRepositoryBranchStatusRows::test_an_order_argument_expressing_no_ordering_keeps_the_default_order PASSED [  9%]
...::TestRepositoryBranchStatusRows::test_contradictory_order_is_rejected PASSED [ 10%]
...::TestRepositoryBranchStatusRows::test_invalid_paging_arguments_are_rejected[explicit-null-limit] PASSED [ 21%]
...::TestRepositoryBranchStatusRows::test_invalid_paging_arguments_are_rejected[explicit-null-offset] PASSED [ 23%]
...::TestRepositoryBranchStatusRows::test_updated_at_is_returned_as_a_timestamp PASSED [ 28%]
...::TestRepositoryBranchStatusRows::test_name_filter_exact_and_partial PASSED [ 12%]
...::TestRepositoryBranchStatusPermissions::test_a_grant_on_one_kind_does_not_cover_the_other_kind[default-branch-read-write-grant-on-read-write-repository] PASSED [ 48%]
...::TestRepositoryBranchStatusPermissions::test_a_grant_on_one_kind_does_not_cover_the_other_kind[default-branch-read-write-grant-on-read-only-repository] PASSED [ 50%]
...::TestRepositoryBranchStatusPermissions::test_a_grant_on_one_kind_does_not_cover_the_other_kind[default-branch-read-only-grant-on-read-only-repository] PASSED [ 51%]
...::TestRepositoryBranchStatusPermissions::test_a_grant_on_one_kind_does_not_cover_the_other_kind[default-branch-read-only-grant-on-read-write-repository] PASSED [ 53%]
...::TestRepositoryBranchStatusPermissions::test_a_grant_on_one_kind_does_not_cover_the_other_kind[user-branch-read-write-grant-on-read-write-repository] PASSED [ 54%]
...::TestRepositoryBranchStatusPermissions::test_a_grant_on_one_kind_does_not_cover_the_other_kind[user-branch-read-write-grant-on-read-only-repository] PASSED [ 56%]
...::TestRepositoryBranchStatusPermissions::test_a_grant_on_one_kind_does_not_cover_the_other_kind[user-branch-read-only-grant-on-read-only-repository] PASSED [ 57%]
...::TestRepositoryBranchStatusPermissions::test_a_grant_on_one_kind_does_not_cover_the_other_kind[user-branch-read-only-grant-on-read-write-repository] PASSED [ 59%]
...::TestRepositoryBranchStatusPermissions::test_denial_runs_no_database_query[default-branch] PASSED [ 60%]
...::TestRepositoryBranchStatusPermissions::test_denial_runs_no_database_query[user-branch] PASSED [ 62%]
```

No row is `MISSING`, and no row is deferred: every test this run added was observed passing locally,
component tests included. No E2E test was added; the user-facing Branches card and its
pytest-playwright test are tracked separately on IFC-3130 and deferred by design, which tasks.md
records at T059.

### Mutation check on the permission fix

The fix for the untested permission guard was verified by deliberate mutation, not by assertion
alone. With `guard.ensure_kind_viewable(policy=policy)` commented out of `resolver.py`, exactly the
four cross-kind denial cases failed and both positive controls passed: `4 failed, 22 passed`. With
the guard restored, all 26 pass. The gap is closed by a test that demonstrably bites.

## 4. Invariant checks over the whole diff

Verified by the orchestrator against `5d76c2b50..HEAD`, independently of the subagents' reports:

| Invariant | Result |
| --- | --- |
| Frozen SDL `contracts/graphql-repository-branch-status.graphql` unchanged | No diff |
| `schema/schema.graphql` matches a fresh `schema.generate-graphqlschema` | `git diff --exit-code` clean |
| `InfrahubBranch` unchanged everywhere, no `sync_with_git` argument added | 0 diff lines in any code or generated file; the identifier appears only inside the T026 task text in tasks.md |
| Only `except` in new production code is the single `InitializationError` catch | 1 match, `permissions.py:60` |
| Composition root is `field.py`, both feature `__init__.py` files empty | Both 0 bytes |
| No em dashes or en dashes in added lines | 0 matches |
| No ticket, task, FR, SC or increment ids in source or test names | 0 matches (reviewer-confirmed) |
| `sync_status` wire values hyphenated, taken from `RepositorySyncStatus.<MEMBER>.value` | Confirmed in chunk 2 and chunk 4 |

## 5. Review findings

Six reviewers ran over `5d76c2b50..dd1a0ac63`: code quality, error handling, test coverage, type
design, comments and simplification. All six agents are enabled in the extension defaults; none was
skipped. The extension's `detect-changed-files.sh` was not used, because it diffs against `stable`
and would have pulled in several hundred unrelated files; the explicit two-commit range was used
instead.

**Totals: 0 critical, 2 high, 8 medium, 13 low.** Both highs and nine of the mediums and lows were
fixed inline in `2b127d2aaa`.

### Fixed inline

| Severity | File | Finding | Reviewer |
| --- | --- | --- | --- |
| HIGH | `payload.py` | `updated_at` was emitted as an ISO string into graphene's `DateTime` field, which refuses to serialize it. A document selecting `commit { updated_at }` returned `updated_at: null` plus an error entry and the value was silently lost. Repro: `DateTime.serialize("2026-01-01T00:00:00.000000Z")` raises `GraphQLError`. No test selected the field. Now converted to a real `datetime`; wire value is `2026-01-01T00:00:00+00:00` | code |
| HIGH | `resolver.py`, component tests | The post-lookup `guard.ensure_kind_viewable(policy=policy)` could be deleted with all 83 tests still green: every grant in the matrix named `Core:Repository`, so the pre-lookup gate always decided. A caller granted view on one repository kind could read the other kind's per-branch status. Fixed with eight single-kind grant cases plus positive controls, mutation-verified | tests, errors |
| MEDIUM | `resolver.py` | An explicit `limit: null` or `offset: null` overrode the argument default and reached the resolver as `None`, producing `TypeError: '<' not supported between instances of 'NoneType' and 'int'` as a raw Python message instead of a clean `ValidationError` | code |
| MEDIUM | `resolver.py` | `order: {}` and `order: {node_metadata: {}}` are valid documents that are not `None`, so the Python default ordering was skipped while the resolved ordering was still the default: rows came back in insertion order instead of default-branch-first then name. Now gated on the effective ordering, verified exact because no real `order` input can produce the default | code |
| MEDIUM | component tests | Exact versus `partial_match` was not distinguished: the exact case filtered on `rbs-five-03`, not a substring of any other branch name, so hard-wiring `partial_match=True` changed no assertion. A strict-prefix case with `count == 0` was added, keeping the original | tests |
| MEDIUM | component tests | `test_denial_runs_no_database_query` had no positive control, so it could not distinguish "no query ran" from "the counter never saw the resolver". An allow-all run through the same counting database now asserts a non-zero count | tests |
| MEDIUM | `permissions.py` | The `InitializationError` to `PermissionDeniedError` conversion logged nothing, and the app logs `PermissionDeniedError` only at `debug`, so a server that failed to load permissions was indistinguishable from a routine denial at default log level. One `log.warning` added at the catch site; the catch stays as narrow and still chains `from exc` | errors |
| MEDIUM | `interface.py` | The Protocol's `read` had a `...` body and no `@abstractmethod`, so an explicit subclass missing or misspelling the method instantiated fine and its inherited `read` returned `None`, failing at request time instead of at the definition. That is precisely the guarantee the explicit-Protocol shape is chosen for. Now abstract, verified: `TypeError: Can't instantiate abstract class MissingRead without an implementation for abstract method 'read'` | types |
| LOW | component tests | The resolver docstring promised `ValidationError` for a contradictory `order` and nothing tested it, against the phase's own rule that every raise has a test that provokes it. Case added | errors |
| MEDIUM | `stub.py` | The module docstring carried a truncated sentence with a dangling preposition and used present tense for work not yet done | comments |
| LOW | `backend/tests/component/conftest.py` | Three inaccurate fixture docstrings: a purpose clause claiming a consumer that does not exist yet, "names of the branches" for a field holding a `Branch` object, and "the only branch the fixture creates data on" where the fixture creates no repository data at all | comments |

### Deferred, not blocking

**Frozen-SDL descriptions, flagged upward for your decision.** Two reviewers independently observed
that four API-facing descriptions describe post-Phase-4 behaviour while the behaviour is inert:
`sync_status__value` and `internal_status__value` both end "(server-side)", `own_values_only` says
it keeps only branches holding their own commit value, and `count` says "after all filters". The
resolver accepts all three arguments without applying them and computes `count` before any value
filter. A third finding is that the field description says "Resolved entirely from the graph" two
sentences before "(preview: attribute values are placeholders, not yet read from the graph)".

These were **not** changed, deliberately. They are the frozen contract text, and the contract's
whole purpose is that the frontend team codegens once against the final shape; rewording now and
again at T037 would churn the artifact they build against. Implementation did not force the change,
so the contract-update-and-flag clause was not triggered. If you would rather the stub window be
announced per argument, that is an SDL edit to the contract, `schema/schema.graphql` and the
frontend types, and it belongs in the same PR as the decision.

Type-design hardening, all low or medium, none reachable through current callers:

- `RepositoryBranchAttributes`' generated `__init__` is public, so the key-to-value agreement that
  `from_values` establishes is bypassable. This becomes live in Phase 4, where the reader is a
  second producer of the lookup and can build the nested mapping directly. Worth a `__post_init__`
  validation or a private field when T035 lands.
- `RepositoryBranchStatusRow` pairs a `Branch` with a values mapping and nothing ties the values to
  that branch; a one-token slip in the resolver comprehension would type-check and report another
  branch's commit. A `build` classmethod or a `__post_init__` check would make it unrepresentable.
- `page_rows(rows, offset: int, limit: int)` re-admits the illegal pairs the resolver just rejected;
  a frozen `Page` validating in `__post_init__` would carry the guarantee in the type.
- `RepositoryKindPolicy.kind` duplicates the mapping key in `REPOSITORY_KIND_POLICIES`, so a
  mismatched entry would hand the resolver a policy guarding the other kind's permission. Building
  the mapping from the policies makes disagreement unrepresentable.
- `REPOSITORY_KIND_POLICIES` being public alongside `policy_for_kind` gives two doors to one lookup,
  and only one produces the mandated `ValidationError`; direct subscription raises a bare
  `KeyError`. The guard's genuine need is enumeration, not lookup.
- `_attribute_names(node_fields: dict[str, Any], ...)` types the selection as a bare dict identical
  to the `fields` dict one line above, so passing the wrong one type-checks and silently renders
  every attribute null. `Collection[str]` plus `node_fields.keys()` would close it.
- `attribute_names.add("commit")` bypasses the policy set; both current policies include `commit`,
  so nothing fails today.
- `frozen=True` on the two dataclasses advertises hashability their `Mapping` and `Branch` fields do
  not have, so a plausible `set(rows)` dedupe type-checks and raises at runtime.
- `Sequence[str]` and `Collection[str]` also accept a bare `str`, which would iterate characters.
- `root: dict` on the resolver is inaccurate; every call site passes `root_value=None`.

Coverage and hygiene, all low:

- The stub's warning firing once at import rather than per call is unpinned; moving it into `read`
  would pass every test.
- The component first-page ordering assertion cannot fail on a name-only sort, because the default
  branch is `main` and every other branch is `rbs-*`. The unit test does have that power.
- `RepositoryBranchAttributes.get` has no production caller yet; only `for_branch` is used. It is
  specified by T015 and intended for the Phase 4 reader.
- The bootstrap fixture mutates `registry`, `registry.schema` and `registry.branch` and never
  restores them at module teardown. The existing `default_branch` fixture has the same shape, so
  this is pre-existing in kind, but a later module in the same xdist worker inherits 215 branches.
- `ValueError` from `from_values` is the only raise in the feature that is not an Infrahub `Error`
  subclass. It is spec-sanctioned by T015 and T027 as a programming-error guard, and unreachable
  through the stub.

Simplification, advisory, eight suggestions, none applied: a `read_rows` fixture to collapse roughly
200 lines of repeated plumbing across 14 component tests, `default_permission_backend` as a module
`pytestmark` instead of 20 unused parameters, splitting the repository-pair tuple fixture into two
named fixtures, collapsing four repetitions of the same `choice is None` question in `payload.py`,
a `BranchSpec` dataclass in place of a positionally-commented 4-tuple in the fixture, iterating the
values that exist in `_build_node`, `any()` in the guard, and `monkeypatch.setattr` for the two
config-mutating fixtures. The reviewer's pick if only one is taken is the `read_rows` fixture.

## 6. `/pre-ci` result

Run before this report, per your instruction. Detected areas: **backend**, **python**, **frontend**
(the generated GraphQL types only), **docs** (a spec markdown), **schema**. Skipped: yaml
(nothing matching changed) and testcontainers (unchanged).

| Check | CI job | Status |
| --- | --- | --- |
| Frontend format/lint (`biome ci`) | frontend-lint | Pass, 1460 files, no fixes |
| Frontend unused exports (`knip`) | frontend-lint | Pass, exit 0 (one configuration hint, not a failure) |
| Frontend TS regressions (`betterer ci`) | frontend-lint | Pass, stayed the same at 186 issues |
| Frontend unit tests (`test:coverage`) | frontend-tests | **Flaky locally, not clean.** Two full runs, 0 assertion failures in either; see the note below |
| `@infrahub/graph` unit tests | frontend-tests | Pass, 5 files, 23 tests |
| OpenAPI types | frontend-validate-openapi-types | Skipped, trigger paths unchanged |
| Frontend GraphQL types | frontend-validate-graphql-types | **Failed on first run, fixed and committed as `6350181bd9`; clean on re-run** |
| Error catalogue bindings | frontend-validate-error-catalogue | Skipped, trigger paths unchanged |
| Python format (`ruff format --check`) | python-lint | Pass, 2425 files already formatted |
| Main Python lint | python-lint | Pass |
| Ruff (CI parity, repo-wide) | python-lint | Pass |
| Lockfiles (root + testcontainers) | infrahub-uv-check, infrahub-testcontainers-uv-check | Pass, 233 and 87 packages resolved |
| YAML lint | yaml-lint | Skipped, no yaml changes |
| Type check (`ty check .`) | python-lint | Pass |
| Backend lint (mypy) | backend-tests-integration, backend-tests-functional | Pass, no issues in 1670 source files |
| Generated files | backend-validate-generated | Pass, exit 0 |
| GraphQL schema validation | graphql-schema | Pass, exit 0 |
| JSON schema validation | json-schema | Pass, exit 0 |
| Docs lint (markdownlint + vale) | markdown-lint, validate-documentation-style | Pass, 0 errors in 421 files (5 warnings, all in release-notes files this branch never touched) |
| Generated docs validation | validate-generated-documentation | Pass, exit 0 |
| Backend unit tests | backend-tests-unit | Pass, 2528 passed |
| Testcontainers unit tests | backend-testcontainers-unit | Skipped, unchanged |

**The frontend app suite did not come back clean locally, and I could not make it clean.** It is
reported honestly here rather than as a pass. Two full runs of `pnpm --dir frontend/app run
test:coverage`:

| Run | Conditions | Result |
| --- | --- | --- |
| 1 | concurrent with other heavy local work | `Test Files  36 failed \| 144 passed (187)` / `Tests  27 failed \| 891 passed (918)` |
| 2 | run in isolation, nothing else competing | `Test Files  6 failed \| 181 passed (187)` / `Tests  6 failed \| 1264 passed (1270)` |

**Neither run contained a single assertion failure.** Every failure was browser-runner or bundler
infrastructure: `[birpc] rpc is closed, cannot call "createTesters"` with WebSocket close stacks in
run 1, and Vite dep-optimizer reloads in run 2 (`[vitest] Vite unexpectedly reloaded a test. This
may cause tests to fail, lead to flaky behaviour or duplicated test runs`). The one failing test
name that survived the captured output, `src/shared/components/inputs/list.test.tsx`, failed with
`TypeError: Failed to fetch dynamically imported module` on a cold dependency cache and then
**passed 12 of 12 when re-run with the cache warm**, which is the flake demonstrated rather than
argued.

This branch's entire frontend diff is two generated TypeScript declaration files under
`src/shared/api/graphql/generated/`. Declaration files are erased at runtime and the browser suite
does not typecheck, so they cannot reach an input-component test. Treat CI's `frontend-tests` job as
the arbiter: it runs on a clean machine with a cold, uncontended cache. If it fails there, the
failure is environmental in the same way and predates this branch, because no runtime frontend
source changed.

**The one genuine failure this run found and fixed was `frontend-validate-graphql-types`**, a
task-list gap rather
than a coding mistake. T026 says to run `pnpm codegen`, which is `graphql-codegen` and writes
`types.ts` only. The gql.tada artifacts `graphql-env.d.ts` and `graphql-cache.d.ts` come from a
different script, `pnpm codegen:graphql`, which no task names. `graphql-env.d.ts` was missing the
three new types and the new Query field, and all 65 cached document hashes in `graphql-cache.d.ts`
were stale, because gql.tada hashes include the schema. Both were regenerated and committed, and
Phase 3D then passed clean. **T026's command list is wrong and should be corrected before Phase 4
regenerates these files again**, since T037 changes the field description and will invalidate the
same artifacts.

A cosmetic observation, no action taken: the stub's deliberate import-time warning now appears in
the output of `schema.validate-graphqlschema`, `schema.validate-jsonschema` and any other task that
imports the GraphQL schema. That is the warning doing its job, and it disappears when the stub is
deleted at T038.

## 7. Autonomous decisions

Judgement calls made by the orchestrator that you may want to revisit:

1. **Chunk plan taken verbatim from your instruction**, four chunks in the order you gave, rather
   than the phase headings the skill would otherwise use. Implementation chunks ran strictly
   sequentially; only the six read-only reviewers ran in parallel.
2. **Frozen-SDL descriptions left unchanged** despite two reviewers rating four of them HIGH.
   Reasoning in section 5. This is the decision most worth your review, because it is the one place
   where a reviewer's severity rating and the phase's stated constraint disagree.
3. **Applied nine mediums and lows alongside the two highs**, where the skill only requires fixing
   high and above. All nine were single-site, grounded in a concrete failure the reviewer
   reproduced, and several were mandated by the phase's own cross-cutting rules ("every raise has a
   test", "mypy checks the contract at the definition"). Two are behaviour changes to argument
   validation and default ordering rather than pure hygiene: an explicit `limit: null` now raises
   `ValidationError` instead of `TypeError`, and `order: {}` now receives the documented default
   ordering instead of insertion order.
4. **All simplification suggestions deferred.** They are advisory by design, and the largest touches
   roughly 200 lines of test plumbing that Phase 4 will extend anyway. Better taken as one pass then
   than half-taken now.
5. **`detect-changed-files.sh` deliberately bypassed** for the review scope, because it diffs
   against `stable` and this branch's base is the integration branch.
6. **The frontend area was treated as changed** for `/pre-ci` purposes on the strength of a single
   generated file under `frontend/app/**`, which is what CI's own path filter does, so Phase 3B ran
   in full.
7. **The two gql.tada artifacts were committed by the orchestrator**, not by a subagent, as a fixup
   after `/pre-ci` caught them. No subagent commit was amended.
8. **The flaky frontend suite was reported rather than retried into a green run.** After the second
   run still showed 6 failures, I stopped re-running the full suite and instead isolated the one
   named failing file to demonstrate the flake (cold cache fails, warm cache passes 12 of 12). A
   third and fourth full run at 27 minutes each would have been rerolling dice, and a green roll
   would have been weaker evidence than the cold-versus-warm demonstration. If you want a clean
   local run on the record before merging, that is a re-run to ask for, not a code change.
9. **No changelog fragment was added.** The feature's fragment is T044 in Phase 4, the dropped T030a
   was PR 1's, and the query stays unlogged while its values are fabricated. This matches tasks.md.

## 8. Suggested next steps

1. **Open the pull request against `cross-branch-repo-status-infp-671`, not `develop`** (T031).
   Every PR in this epic targets the integration branch. The PR wants GraphQL schema sign-off (one
   new root field, three new types, `InfrahubBranch` verifiably unchanged) and authorization
   sign-off (the permission check lives in the resolver because the checker pipeline cannot see a
   hand-written root field, and this is the first read needing a decision covering both the default
   branch and other branches). State the release rule in the description: **no release may be cut
   while `stub.py` exists.** The `/pre-ci` half of T031 is already done and recorded in section 6.
2. **Frontend handoff and the stub-removal Jira task** (T032), both yours. Worth passing on: the
   contract is `contracts/graphql-repository-branch-status.md`; the codegen instruction the team
   needs is `pnpm codegen` **and** `pnpm codegen:graphql`, per section 6.
3. **Correct T026's command list in tasks.md** to include `pnpm codegen:graphql`, before Phase 4's
   T037 changes the field description and invalidates the same two artifacts.
4. **Reconcile `data-model.md`** with the `from_values` classmethod and the pair-keyed internal
   mapping, so T033 and T035 are written against what actually exists.
5. **Decide the frozen-SDL description question** in section 5 before the frontend team builds
   against those argument descriptions.
6. When Phase 4 starts, pick up the deferred type-design items that become live there: the
   `RepositoryBranchAttributes` constructor invariant (a second producer arrives with T035) and the
   `RepositoryBranchStatusRow` pairing.
