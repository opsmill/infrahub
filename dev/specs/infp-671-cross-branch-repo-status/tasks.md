# Tasks: Cross-branch Repository Status Query

**Input**: Design documents from `dev/specs/infp-671-cross-branch-repo-status/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md, critiques/critique-2026-09-03.md

**Tests**: Included. The spec attaches a *Verify* clause to every functional requirement and pins
behaviour by test; the constitution (IV. Test Discipline) requires tests alongside implementation.

**Organization**: Tasks follow the plan's three increments. Increment A (Phase 3) is the early
deliverable: a live, typed GraphQL query the frontend team builds against while the graph read
(Phase 4) is written. Increment C (Phase 5) is User Story 2.

## Suggested delivery scope

Each phase heading below carries its pull request number. Work the phases in this order; each row
is one reviewed pull request with one Jira task behind it.

| PR | Phases | Jira | Delivers |
| --- | --- | --- | --- |
| **PR 1** | 1, 2 (T001 to T013) | [IFC-3125](https://opsmill.atlassian.net/browse/IFC-3125) | Branch-list plumbing: `sync_with_git` filter, unpaged `Branch.get_list`, total-ordered standard-node reads, shared fixtures |
| **PR 2** | 3 (T014 to T032, including T030a) | [IFC-3126](https://opsmill.atlassian.net/browse/IFC-3126) | Increment A. Live typed query for the frontend team; fabricated attribute values behind the real contract |
| **PR 3** | 4 (T033 to T047, including T045a and T045b) | [IFC-3127](https://opsmill.atlassian.net/browse/IFC-3127) | Increment B. True values, real attribute filters, stub deleted, changelog, docs, knowledge docs, benchmark |
| **PR 4** | 5 (T048 to T056, including T052a) | [IFC-3128](https://opsmill.atlassian.net/browse/IFC-3128) | Increment C. Periodic sync bounded by `1 + ceil(N / 100)` queries |
| **PR 5** | 6 (T057 to T060) | [IFC-3129](https://opsmill.atlassian.net/browse/IFC-3129) | Spec sweep, Confluence PRD correction, manual check, final validation. Foldable into PR 4 |

Delivery epic: [IFC-3104](https://opsmill.atlassian.net/browse/IFC-3104). Also under it, and not
backend PRs: [IFC-3130](https://opsmill.atlassian.net/browse/IFC-3130) the Branches card and its
end-to-end test, [IFC-3131](https://opsmill.atlassian.net/browse/IFC-3131) the manual validation pass,
and [IFC-3132](https://opsmill.atlassian.net/browse/IFC-3132) writing that pass's instructions.

Phase 2 is its own pull request rather than part of increment A because T009 changes `ORDER BY` for
every standard-node list in the product. That belongs in front of a reviewer looking at ordering, not
buried in a thirty-task repository-query review.

Stop and validate at the end of each scope before starting the next. PR 4 may be opened while PR 3
is in review, but merges after it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story the task belongs to (US1 = repository page rows, US2 = periodic sync)
- File paths are exact. Sites inside a file are named by symbol, never by line number.

## Cross-cutting rules for every task

These come from the user's brief for this task list and from the repository's own rules. Each task
below is written to satisfy them; an implementer who finds a task that cannot is expected to stop and
say so rather than bend the rule.

- **Contract first**: nothing in Phase 3 may change the SDL in
  `contracts/graphql-repository-branch-status.graphql`. If implementation forces a change, the
  contract document is updated in the same commit and the frontend team is told.
- **SOLID and dependency injection** (`.agents/rules/backend-component-design.md`):
  - Cypher lives in a `Query` class; row-to-dataclass mapping lives in the reader component;
    argument validation, permission checks, kind dispatch, paging and payload mapping each live in
    their own small module with one reason to change.
  - The resolver is a composition root. It builds the attribute source through one wiring function
    and codes against the `RepositoryBranchAttributesSource` interface, so the stub (Phase 3) and the
    reader (Phase 4) are two implementations behind one seam and the swap is a wiring change.
  - Every collaborator is a required constructor parameter. `db` is injected in the constructor;
    per-call inputs (repository ids, branch names, attribute names, `at`) go to the entry method.
    Components never read `registry` or settings; the entry point resolves those and passes plain
    values.
  - Prefer frozen dataclasses for results; no untyped dicts across module boundaries except the
    dict graphene consumes at the very edge.
- **Every failure case is caught where it can be handled and reported, never swallowed**
  (`dev/guidelines/backend/exceptions.md`):
  - Bad arguments raise `ValidationError`; an unresolvable repository raises `NodeNotFoundError`
    unchanged from the lookup; a missing grant raises `PermissionDeniedError`; a context without a
    `PermissionManager` is converted to `PermissionDeniedError` by catching only
    `InitializationError` at that one site; a repository whose concrete kind is neither
    `CoreRepository` nor `CoreReadOnlyRepository` raises `ValidationError` naming the kind.
  - No `except Exception`, no bare `except`, no `try` around code that cannot raise. Database errors
    propagate. A lookup miss (`None` from the attribute source) renders a null attribute payload,
    never a crash and never a fabricated value.
  - Every error class above is an Infrahub `Error` subclass so the GraphQL error formatter returns
    a clean message with `data: null` and no internals (constitution VI).
  - Each task that introduces an error path also introduces the test that provokes it.
- **Branch safety and efficiency**: all Cypher parameterised; the primitive returns only the listed
  properties; query count per page independent of branch count; zero message-bus sends.
- **Style**: `dev/guidelines/backend/python.md` (typing, imports, keyword arguments), format and lint
  before each commit, `/pre-ci` before each push. No em dashes anywhere, including comments and docs.

---

## Phase 1: Setup [PR 1]

**Purpose**: Package skeletons and required reading so every later task starts from the same base.

- [ ] T001 Read `dev/knowledge/backend/query-pattern.md`, `dev/knowledge/backend/permissions.md`, `dev/knowledge/backend/graphql-execution.md`, `dev/knowledge/backend/git-sync.md`, `dev/knowledge/backend/package-init-files.md`, `dev/guidelines/backend/python.md`, `dev/guidelines/backend/exceptions.md` and `.agents/rules/backend-component-design.md`; note in the PR description any place the plan contradicts them
- [ ] T002 [P] Create the core package `backend/infrahub/core/repository_branch_status/__init__.py`, empty, per `dev/knowledge/backend/package-init-files.md`; callers import from the owning submodule
- [ ] T003 [P] Create the GraphQL query package `backend/infrahub/graphql/queries/repository_branch_status/__init__.py`. It stays empty for the life of the feature: the wiring function and the field definition live in `field.py` (T024), per `dev/knowledge/backend/package-init-files.md` and the `graphql/queries/diff/` precedent, whose `__init__.py` is empty with the field in `tree.py`
- [ ] T004 [P] Create the test package `backend/tests/component/core/query/__init__.py`. The directory does not exist yet (`backend/tests/component/core/__init__.py` already does) and the existing core query component tests are flat siblings (`test_node_get_list_query.py`, `test_relationship_get_list_query.py`). The new subdirectory mirrors `backend/infrahub/core/query/`, which is what the constitution asks of test layout; note it in the PR so a reviewer does not read it as a stray directory

---

## Phase 2: Foundational (Blocking Prerequisites) [PR 1]

**Purpose**: Changes to existing branch-list plumbing that both user stories and the shared test
fixture depend on. All of these are behaviour-preserving for existing callers.

**CRITICAL**: T005 through T009 must be complete before Phase 3 starts; T010 through T013 must be
complete before any Phase 3 test task starts.

- [ ] T005 Add `sync_with_git: bool | None = None` to `BranchListFilters` in `backend/infrahub/core/branch/filters.py`, documented as "None means no constraint"
- [ ] T006 In `BranchNodeGetListQuery._build_raw_filter` in `backend/infrahub/core/query/branch.py`, emit `n.sync_with_git = $filter_sync_with_git` when the filter is not `None`, binding the parameter through `self._branch_filter_params` like the existing status filter (parameterised, never interpolated)
- [ ] T007 Add a `sync_with_git=Boolean()` argument to `InfrahubBranchQueryList` and pass it through `infrahub_branch_resolver` into `BranchListFilters` in `backend/infrahub/graphql/queries/branch.py`
- [ ] T008 Widen `Branch.get_list` to `limit: int | None = 1000` in `backend/infrahub/core/branch/models.py` so `None` means unpaged: the underlying `BranchNodeGetListQuery` omits its `LIMIT` and is executed through the base `Query.query_with_size_limit` chunked path. Confirm `StandardNodeGetListQuery` in `backend/infrahub/core/query/standard_node.py` tolerates `limit=None` and adjust its `query_init` if it does not
- [ ] T009 In `StandardNodeGetListQuery.query_init` in `backend/infrahub/core/query/standard_node.py`, append the id function (`db.get_id_function_name()` applied to `n`) as a tiebreaker after the `created_at` and `updated_at` `ORDER BY` arms, so the chunked unpaged read in T008 iterates a total order. Today those two arms have no tiebreaker (verified during task generation). Run `backend/tests/component/graphql/queries/test_order.py` to confirm existing ordering tests still pass
- [ ] T010 [P] Component test in `backend/tests/component/graphql/queries/test_branch.py`: `sync_with_git: true` returns only syncing branches, `false` only non-syncing, unset returns both; `count` follows the filter on the paginated `InfrahubBranch` query
- [ ] T011 [P] Component test in `backend/tests/component/core/test_branch.py`: with `config.SETTINGS.database.query_size_limit` lowered to 3 for the test and 10 branches saved, `Branch.get_list(limit=None, node_ordering=<created_at desc>)` returns all 10 exactly once and in a stable order across two calls (pins T008 and T009 together)
- [ ] T012 Shared branch fixture in `backend/tests/component/conftest.py`: a module-scoped async fixture `repository_branch_status_branches` (same scope as the `db` fixture it depends on) that saves branches directly with `Branch(...).save()` rather than the `create_branch` flow, and returns a frozen dataclass exposing: the five-branch name list, the two-hundred-branch name list, one branch with `sync_with_git=False`, one branch for each of the seven `BranchStatus` values so both terminal statuses and all five non-terminal ones (`OPEN`, `NEED_REBASE`, `NEED_UPGRADE_REBASE`, `MERGING`, `MERGE_FAILED`) are represented, and one legacy branch saved with `is_isolated=False`. It creates no repository nodes; tests that write attribute values create their own repositories so writes do not leak between tests sharing the module-scoped database
- [ ] T013 [P] Fixture helper `make_repository_pair(db)` in the same `backend/tests/component/conftest.py` returning one `CoreRepository` and one `CoreReadOnlyRepository` node saved on the default branch, used by Phase 3, 4 and 5 tests

**Checkpoint**: `InfrahubBranch` accepts `sync_with_git`; unpaged branch reads are total-ordered; the
shared fixture exists. `uv run pytest backend/tests/component/graphql/queries/test_branch.py
backend/tests/component/core/test_branch.py` passes.

---

## Phase 3: User Story 1, Increment A: contract stub (Priority: P1) [PR 2]

**Goal**: Ship the complete `InfrahubRepositoryBranchStatus` contract on `develop` so the frontend
team can run `pnpm codegen` and build the Branches card against a live query. Repository lookup,
permission denial, row membership, ordering, paging and `count` are real. Only the four attribute
payloads are fabricated, behind the same interface the graph reader will implement.

**Independent Test**: Against a stack built from this increment, the example document in
`contracts/graphql-repository-branch-status.md` returns one row per in-scope branch for both
repository kinds, `count` and paging are correct, an `ALLOW_DEFAULT`-only caller is denied, and the
generated frontend types match the SDL. Quickstart scenarios A1 through A7.

**Release rule**: no release may be cut while `stub.py` exists (research.md, Decision 1).

### Shapes shared by stub and reader (pulled forward from increment B so the resolver has one shape)

- [ ] T014 [P] [US1] Add the frozen dataclass `RepositoryBranchAttributeValue(repository_id, branch_name, attribute_name, attribute_id, value: str | None, own_value: bool, updated_at: str | None)` in the new module `backend/infrahub/core/query/repository.py`, which does not exist yet (the Query class that yields it arrives in T033)
- [ ] T015 [P] [US1] Add the frozen lookup `RepositoryBranchAttributes` to `backend/infrahub/core/repository_branch_status/models.py` per data-model.md: built from a sequence of `RepositoryBranchAttributeValue`, `get(repository_id, branch_name, attribute_name)` returns `None` for a triple with no row, `for_branch(repository_id, branch_name)` returns the attribute-name map for row assembly; a duplicate triple in the input raises `ValueError` naming the triple (the primitive's `WITH DISTINCT` makes this impossible, so a duplicate means a query bug and must not be silently overwritten)
- [ ] T016 [P] [US1] Define the explicit interface `RepositoryBranchAttributesSource(Protocol)` in `backend/infrahub/core/repository_branch_status/interface.py` with one method `async def read(self, repository_ids: Sequence[str], branch_names: Sequence[str], attribute_names: Collection[str], at: Timestamp | None = None) -> RepositoryBranchAttributes`. Both the stub (T019) and the reader (T033) subclass it so mypy checks the contract at the definition (the "explicit" shape in `.agents/rules/backend-component-design.md`)

### GraphQL types and pure helpers

- [ ] T017 [P] [US1] Create `backend/infrahub/graphql/types/repository_branch_status.py` with graphene types matching the SDL in `contracts/graphql-repository-branch-status.graphql`: `InfrahubRepositoryBranchStatusNode` (`name`, `status` using the existing `InfrahubBranchStatus` enum from `backend/infrahub/graphql/types/enums.py`, whose SDL name is `BranchStatus` because graphene derives it from the Python enum class rather than the variable, `is_default`, `sync_with_git`, `branched_from`, `commit: TextAttributeType`, `sync_status: DropdownType`, `internal_status: DropdownType`, `ref: TextAttributeType`), `InfrahubRepositoryBranchStatusEdge`, `InfrahubRepositoryBranchStatusType` (`count: Int!`, `edges`); each field carries the SDL description; export the three from `backend/infrahub/graphql/types/__init__.py`. The row type carries `class Meta: name = "InfrahubRepositoryBranchStatus"` so the SDL name is unchanged while the Python symbol keeps the `Node` suffix, because the unsuffixed name is also the `Field` registered on `InfrahubBaseQuery` (T024) and two objects under one name in one feature is a trap
- [ ] T018 [P] [US1] Create `backend/infrahub/graphql/queries/repository_branch_status/paging.py` with the frozen dataclass `RepositoryBranchStatusRow(branch: Branch, values: Mapping[str, RepositoryBranchAttributeValue])` and three pure functions with no database or registry imports: `apply_value_filters(rows, sync_status, internal_status, own_values_only)` (FR-013 and FR-014: `own_values_only` keeps a row only when its `commit` value has `own_value` true, independent of the caller's selection), `order_rows(rows)` (default branch first, then `name` ascending; called only when no `order` argument was given), `page_rows(rows, offset, limit)`
- [ ] T019 [P] [US1] Create `backend/infrahub/graphql/queries/repository_branch_status/stub.py`: `StubRepositoryBranchAttributesSource(RepositoryBranchAttributesSource)` whose `read` builds `RepositoryBranchAttributeValue`s from the pure function `fabricate_attribute_values(repository_id, branch_name, attribute_names, is_default_branch)` per research.md Decision 8 (`commit` = SHA-1 hex of the name, `sync_status` cycles the four schema choice values by name hash, `internal_status` `active` on the default branch else `inactive`, `ref` `main`, `own_value` true on the default branch and odd hashes, fixed `updated_at`, `attribute_id` derived deterministically). The constructor takes `default_branch_name: str` (required). A module-level `log.warning` fires once at import, naming the module and saying the attribute values it serves are placeholders; it carries no ticket id (`.agents/rules/code-doc-style.md`). `read` logs at `debug`. The module docstring says the module is temporary and what replaces it, in those terms rather than by increment letter
- [ ] T020 [P] [US1] Create `backend/infrahub/graphql/queries/repository_branch_status/payload.py` with `build_attribute_payload(value: RepositoryBranchAttributeValue | None, attribute_schema: AttributeSchema) -> dict[str, Any] | None`: `None` in yields `None` out (null payload, never a crash); otherwise `id`, `value`, `updated_at`, and for dropdown schemas `label`, `color`, `description` looked up in `attribute_schema.choices` (the same source `infrahub.core.attribute.Dropdown.color` reads); a value absent from the choices yields `label`, `color`, `description` as `None` with one `log.debug` naming attribute and value, never a `KeyError`; the inherited fields the spec accepts as null (`is_default`, `is_protected`, `is_from_profile`, `permissions`, `source`, `owner`) are set to `None` explicitly
- [ ] T021 [P] [US1] Create `backend/infrahub/graphql/queries/repository_branch_status/kind_dispatch.py` with the frozen dataclass `RepositoryKindPolicy(kind: str, sync_with_git_filter: bool | None, attribute_names: frozenset[str], permission_name: str)` and `policy_for_kind(kind: str) -> RepositoryKindPolicy` returning `CoreRepository` (filter `True`, attributes `commit`, `sync_status`, `internal_status`, permission `Repository`) or `CoreReadOnlyRepository` (filter `None`, attributes plus `ref`, permission `ReadOnlyRepository`), and raising `ValidationError` naming the kind for anything else (a future implementer of `CoreGenericRepository` fails loudly instead of returning a half-empty row set)
- [ ] T022 [P] [US1] Create `backend/infrahub/graphql/queries/repository_branch_status/permissions.py` with `RepositoryBranchStatusPermissionGuard` taking the `GraphqlContext` in its constructor and two methods: `ensure_any_kind_viewable()` (pre-lookup: `has_permission` for `ObjectPermission(namespace="Core", name=<kind>, action="view", decision=PermissionDecisionFlag.ALLOW_ALL)` on `Repository` or `ReadOnlyRepository`, else raise `PermissionDeniedError` before any database access) and `ensure_kind_viewable(policy)` (post-lookup: `raise_for_permission` on the resolved kind). Accessing `context.active_permissions` on a context without a `PermissionManager` raises `InitializationError`; catch only that, at this one site, and re-raise as `PermissionDeniedError` (a missing manager is a denial, not a 500). Denial messages come from `PermissionManager.raise_for_permission` and expose no internals. Precedent: `backend/infrahub/graphql/queries/event.py`

### Resolver, wiring and registration

- [ ] T023 [US1] Create `backend/infrahub/graphql/queries/repository_branch_status/resolver.py` with `RepositoryBranchStatusResolver`, a callable class whose constructor takes one required parameter, `build_source: Callable[[InfrahubDatabase], RepositoryBranchAttributesSource]`, and whose `__call__(self, root, info, id, limit, offset, name__value, partial_match, status__value, order, sync_status__value, internal_status__value, own_values_only)` runs, in this order: (1) argument validation raising `ValidationError` for `limit < 1` or `offset < 0`, and delegating `order` validation to the existing `standard_node_ordering_from_order_input`; (2) `RepositoryBranchStatusPermissionGuard.ensure_any_kind_viewable()`; (3) `NodeManager.get_one_by_id_or_default_filter(db, id=id, kind=InfrahubKind.GENERICREPOSITORY, branch=<default branch>, raise_on_error=True)` so a miss raises `NodeNotFoundError` exactly as other repository lookups do; (4) `policy_for_kind(node.get_kind())`; (5) `ensure_kind_viewable(policy)`; (6) one `Branch.get_list(db, limit=None, exclude_global=True, exclude_terminal=True, branch_filters=BranchListFilters(name=..., partial_match=..., status=..., sync_with_git=policy.sync_with_git_filter), node_ordering=...)` (the parameter names are `branch_filters` and `node_ordering`, verified against `backend/infrahub/core/branch/models.py`, not `filters` and `ordering`); (7) selected attribute names = `extract_graphql_fields(info)` node keys intersected with `policy.attribute_names`, plus `commit` when `own_values_only` is true (FR-008); (8) `self.build_source(db).read(...)`; (9) rows, then `order_rows` only when `order` is `None`, then `page_rows`; (10) `count` computed as the length of the ordered row list only when `count` is in the selection (FR-011); (11) branch scalars including `sync_with_git` straight off the `Branch` object, and attribute payloads through `build_attribute_payload`. In increment A the `sync_status__value`, `internal_status__value` and `own_values_only` arguments are accepted and not applied; say so in the docstring in plain terms, with no task or increment id (`.agents/rules/code-doc-style.md`). No `try`/`except` in this class. The source factory is a constructor parameter rather than a module-level call so the FR-008 test (T043) can construct the resolver with a recording fake instead of patching
- [ ] T024 [US1] Create `backend/infrahub/graphql/queries/repository_branch_status/field.py` as the composition root, holding the wiring function `build_attribute_source(db: InfrahubDatabase) -> RepositoryBranchAttributesSource` returning `StubRepositoryBranchAttributesSource(default_branch_name=registry.default_branch)` (the only place that reads `registry` for this feature), and the field `InfrahubRepositoryBranchStatus = Field(InfrahubRepositoryBranchStatusType, required=True, id=String(required=True), limit=Int(default_value=40), offset=Int(default_value=0), name__value=String(), partial_match=Boolean(default_value=False), status__value=Argument(InfrahubBranchStatus), order=Argument(MetadataOrderInput), sync_status__value=String(), internal_status__value=String(), own_values_only=Boolean(default_value=False), resolver=RepositoryBranchStatusResolver(build_source=build_attribute_source), description=<SDL description> + " (preview: attribute values are placeholders, not yet read from the graph)")`. This module, not the package `__init__.py`: putting it in the init would breach `dev/knowledge/backend/package-init-files.md` and create a cycle, because the init would import `resolver.py` for the resolver while `resolver.py` would need the factory back from the init
- [ ] T025 [US1] Register `InfrahubRepositoryBranchStatus` on `InfrahubBaseQuery` in `backend/infrahub/graphql/schema.py` next to `InfrahubTaskBranchStatus`, importing it directly as `from .queries.repository_branch_status.field import InfrahubRepositoryBranchStatus`. Do not re-export through `backend/infrahub/graphql/queries/__init__.py`: the comparable hand-written queries (`event`, `task`, `diff.tree`) are all imported directly in `schema.py` and are absent from that file, and aggregating re-exports across submodules is what `dev/knowledge/backend/package-init-files.md` warns against
- [ ] T026 [US1] Regenerate and commit generated files: `uv run invoke schema.generate-graphqlschema`, diff `schema/schema.graphql` against `contracts/graphql-repository-branch-status.graphql` (field names, argument defaults, descriptions, the `sync_with_git` argument on `InfrahubBranch`), `uv run invoke schema.validate-graphqlschema`, then `cd frontend/app && pnpm codegen` and commit `frontend/app/src/shared/api/graphql/generated/types.ts`. Any divergence from the contract is fixed in code, not in the contract, unless the plan is wrong, in which case the contract file and this tasks.md are updated in the same commit

### Tests for increment A

- [ ] T027 [P] [US1] Unit tests in `backend/tests/unit/graphql/queries/test_repository_branch_status.py` for the pure modules: `paging.py` (value filters including the `commit`-anchored rule for `own_values_only` and its independence from the caller's selection, default ordering with the default branch in the middle of the input, paging at boundaries, `offset` beyond the end returns an empty list), `payload.py` (dropdown label and colour resolved from a real `AttributeSchema`, unknown value yields `None` fields without raising, `None` input yields `None`), `kind_dispatch.py` (both kinds, unknown kind raises `ValidationError` whose message names the kind), `stub.py` (identical output for identical input, all four `sync_status` values appear across twelve names, `internal_status` follows `is_default_branch`), and `RepositoryBranchAttributes` (`get` miss returns `None`, duplicate triple raises `ValueError`)
- [ ] T028 [US1] Component tests in `backend/tests/component/graphql/queries/test_repository_branch_status.py` following the `TestInfrahubApp` and `prepare_graphql_params` pattern of `test_branch.py`, using the T012 and T013 fixtures: membership per kind including exclusion of the global, `MERGED` and `DELETING` branches and of the non-syncing branch for `CoreRepository` only, and inclusion of all five non-terminal statuses so an implementation filtering on `OPEN` alone fails (quickstart A2, FR-002); `count` on every page, default order with the default branch first, `offset` at the tail, `order` by `created_at` overriding the default (A3); `name__value` exact and with `partial_match`, `status__value` including `MERGED` yielding an empty set and `count: 0` with no error; repository resolved by `name` as well as by uuid; unknown `id` returns a `NodeNotFoundError` in `errors` with `data: null`; `limit: 0` and `offset: -1` return `ValidationError`; `ref` null on the read-write kind and present on the read-only kind from one document (A6); `sync_with_git` true on every row of the read-write kind and carrying both true and false across the read-only kind's rows (FR-003); values identical across two calls and the field description in the built schema containing "preview" (A7)
- [ ] T029 [US1] Permission matrix component tests in the same `backend/tests/component/graphql/queries/test_repository_branch_status.py` using `tests.helpers.permissions.define_permissions`, each executed on the default branch and on a user branch: `ALLOW_ALL` returns rows; separate `ALLOW_DEFAULT` and `ALLOW_OTHER` grants return rows; `ALLOW_DEFAULT` only denied; `ALLOW_OTHER` only denied; no grant denied and, through `CountingInfrahubDatabase`, zero database queries executed (denial precedes the lookup); anonymous session whose anonymous role grants `ALLOW_ALL` returns rows; anonymous session without a grant denied; a `GraphqlContext` constructed without a `PermissionManager` denied with `PermissionDeniedError` rather than `InitializationError`. Every denial asserts `data` is null and the message contains neither a kind list nor a traceback
- [ ] T030 [US1] Zero-bus-sends component test in `backend/tests/component/graphql/queries/test_repository_branch_status.py`: for each supported document shape (both kinds, with and without `count`, with each filter, with `order`), `TestHelper.get_message_bus_recorder().messages` is empty afterwards (FR-015, SC-007)

### Changelog, handoff and gate

- [ ] T030a [P] [US1] Add `changelog/+branch-list-sync-with-git-filter.added.md` with the `creating-changelog-entries` skill, describing the `sync_with_git` argument on the `InfrahubBranch` query as it landed (grep the diff for the exact argument name first). This increment ships a user-visible GraphQL change, so it needs a fragment even though the new query itself stays unlogged while its values are fabricated
- [ ] T031 [US1] Run `/pre-ci` for the changed areas, then open the increment A pull request requesting GraphQL schema sign-off (new root field and three types, `sync_with_git` on `InfrahubBranch`) and authorization sign-off (the permission check moves into the resolver because the checker pipeline cannot see a hand-written root field, and this is the first read requiring a decision covering both the default branch and other branches; spec.md, Governance Gates). The PR description states the release rule, links `contracts/graphql-repository-branch-status.md`, lists the arguments the stub accepts but ignores, and names the blast radius of T009: the id tiebreaker changes `ORDER BY` for every standard-node list ordering by `created_at` or `updated_at`, not only the branch read, so list the standard-node surfaces it touches and the test run that covers them
- [ ] T032 [US1] Handoff: post `contracts/graphql-repository-branch-status.md` to the frontend team with the codegen instructions in its final section, state that the card is built without the git-derived drift column for now, announce the stub window to the team, and create a Jira task under the delivery epic IFC-3104 titled "Remove InfrahubRepositoryBranchStatus stub" so the stub cannot outlive the frontend work. Delivery work lives under IFC; INFP is JPD and holds product planning only, already linked to the epic. Ask the frontend team which e2e directory the card's test belongs in: the spec says `tests/e2e/branches/`, but `tests/e2e/repository/` exists and is the closer fit for a repository-page card

**Checkpoint**: The frontend team can build the Branches card. Quickstart A1 through A7 pass.
`uv run pytest backend/tests/unit/graphql/queries/test_repository_branch_status.py
backend/tests/component/graphql/queries/test_repository_branch_status.py` is green.

---

## Phase 4: User Story 1, Increment B: graph read (Priority: P1) [PR 3]

**Goal**: Replace the fabricated values with the real per-branch attribute read through the core
primitive; make the attribute-value filters real; pin inheritance, rebase and the query-count
invariant by test; delete the stub. The contract does not change.

**Independent Test**: Quickstart B1 through B8. `stub.py` is absent from the tree. The query count
for one page is equal at 5 and 200 branches.

### Core primitive

- [ ] T033 [US1] Implement `RepositoryBranchAttributesQuery(Query)` in `backend/infrahub/core/query/repository.py` per `contracts/core-primitive.md`: `name = "repository-branch-attributes"`, `type = QueryType.READ`, `insert_return = False`, `insert_limit = False`; constructor takes only primitives (`repository_ids`, `branch_names`, `attribute_names`, `default_branch_name`, `global_branch_name`) and `$at` binds from `self.at`. `query_init` builds one statement: `UNWIND $branch_names AS branch_name MATCH (br:Branch {name: branch_name})`, `WITH ..., CASE WHEN br.is_isolated THEN br.branched_from ELSE $at END AS default_window`, `MATCH (n:Node)-[:HAS_ATTRIBUTE]->(a:Attribute) WHERE n.uuid IN $repository_ids AND a.name IN $attribute_names`, `WITH DISTINCT n, a, branch_name, default_window` before two `CALL` subqueries electing the visible `HAS_ATTRIBUTE` edge and the visible `HAS_VALUE` edge with the per-branch predicate from data-model.md (comparison operators copied verbatim from `Branch.get_query_filter_path`: non-strict `from <=` with strict `to >`, the two arms being `from <= t AND to IS NULL` and `from <= t AND to > t`. Read them off the branch loop, not off the `branch_agnostic` shortcut higher in the same method, which uses a strict `from <` and would drop an edge written at exactly the query time or exactly at a branch's `branched_from`), `ORDER BY r.branch_level DESC, r.from DESC, r.status ASC LIMIT 1`, keeping only `status = "active"`; `RETURN` only `n.uuid`, `branch_name`, `a.name`, `a.uuid`, `av.value`, `r_value.branch`, `r_value.from`. `get_data()` yields `RepositoryBranchAttributeValue` with `own_value = (r_value.branch == branch_name)`. Load the `neo4j-cypher-guide` skill before writing the statement; model the election on `infrahub.database.validation._check_duplicate_attributes` and the grouped read on `infrahub.core.query.diff.DiffCountChanges`
- [ ] T034 [US1] Run `EXPLAIN` on the statement against the 200-branch fixture from a component test or a scratch script, confirm index use on `Branch.name` and `Node.uuid`, no Cartesian product and no eager operator between the `UNWIND` and the subqueries, and paste the plan into the increment B PR description (plan.md, Constitution Check V)
- [ ] T035 [US1] Implement `RepositoryBranchAttributesReader(RepositoryBranchAttributesSource)` in `backend/infrahub/core/repository_branch_status/reader.py`: constructor `(db: InfrahubDatabase, default_branch_name: str, global_branch_name: str)`, all required, no defaults, no `registry` access; `read()` returns an empty `RepositoryBranchAttributes` without executing when `branch_names` or `attribute_names` is empty, de-duplicates `branch_names` preserving order, runs exactly one `RepositoryBranchAttributesQuery.init(...)` and `execute(...)`, and builds the lookup from `get_data()`. No `try`/`except`: database errors and `ValueError` from a duplicate triple propagate to the caller
- [ ] T036 [US1] Confirm every consumer imports from the owning submodule (`...repository_branch_status.reader`, `.models`, `.interface`) and leave `backend/infrahub/core/repository_branch_status/__init__.py` empty. These three symbols live in three different submodules, and `dev/knowledge/backend/package-init-files.md` permits a curated re-export only out of a single submodule: aggregating across several is what makes importing one symbol drag in every submodule's dependencies

### Resolver swap

- [ ] T037 [US1] In `backend/infrahub/graphql/queries/repository_branch_status/field.py`, change `build_attribute_source` to return `RepositoryBranchAttributesReader(db=db, default_branch_name=registry.default_branch, global_branch_name=GLOBAL_BRANCH_NAME)`, and remove the "(preview: attribute values are placeholders, not yet read from the graph)" suffix from the field description. This is the whole swap: one line in the composition root, with the resolver unchanged because it codes against `RepositoryBranchAttributesSource`
- [ ] T038 [US1] Delete `backend/infrahub/graphql/queries/repository_branch_status/stub.py` and its unit tests in `backend/tests/unit/graphql/queries/test_repository_branch_status.py`; replace the A7 stub-visibility component test in `backend/tests/component/graphql/queries/test_repository_branch_status.py` with an assertion that the built schema description no longer contains "preview". `git ls-files backend/infrahub/graphql/queries/repository_branch_status/stub.py` must print nothing
- [ ] T039 [US1] In `RepositoryBranchStatusResolver.__call__` in `backend/infrahub/graphql/queries/repository_branch_status/resolver.py`, apply `apply_value_filters` between the source read and ordering so `sync_status__value`, `internal_status__value` and `own_values_only` narrow rows and `count` server-side (FR-013, FR-014); drop the docstring sentence saying those arguments are inert; keep the selected-attribute set equal to the GraphQL selection intersected with the policy, widened by `commit` when `own_values_only` is true (FR-008)

### Tests for increment B

- [ ] T040 [P] [US1] Component tests for the primitive in `backend/tests/component/core/query/test_repository_branch_attributes.py` using the T012 and T013 fixtures and repositories created per test: direct reader call with two branch names and one attribute reproducing the example in `contracts/core-primitive.md` (FR-009, B7); inheritance at the fork point with imports `c1` on main, branch `b1`, `c2` on main, branch `b2` (B1, including `updated_at` on `b1` equal to main's write time for `c1`); own import on `b1` then rebase of `b2` (B2); a repository never imported returns `commit.value` `None` and `sync_status` `unknown` (B3); a branch name with no `Branch` node yields no row and `get` returns `None`; empty `branch_names` and empty `attribute_names` execute no query (`CountingInfrahubDatabase.count_for("repository-branch-attributes") == 0`); two repositories in one call are both resolved; the same document against 5 and 200 branches gives an equal `sum(query_counts.values())` while `rows_for("repository-branch-attributes")` grows (FR-007, SC-002, B5)
- [ ] T041 [P] [US1] Differential component test in `backend/tests/component/core/query/test_repository_branch_attributes.py`: for every branch in the shared fixture, including the legacy `is_isolated=False` branch, the primitive's `(value, updated_at)` for `commit` equals `NodeManager.get_one(db, id=..., branch=<that branch>)` followed by reading `commit.value` and `commit.updated_at` (B6a; pins the operators to `Branch.get_query_filter_path`)
- [ ] T042 [US1] Component tests added to `backend/tests/component/graphql/queries/test_repository_branch_status.py`: `sync_status__value: "error-import"` against 200 branches of which 3 wrote `error-import` on their own branch returns exactly those 3 and `count: 3` on one page (B4, SC-003; the stored values are hyphenated, so write them from `RepositorySyncStatus.ERROR_IMPORT.value` rather than as a literal); `own_values_only: true` returns only the branches holding their own `commit` value, and returns the same rows for a document selecting only `sync_status` (FR-014); inheritance through GraphQL (`b1` shows `c1` with main's `updated_at`); a never-imported repository yields rows with null `commit.value` and no error; `sync_status` payload carries the schema's label and colour (FR-004); omitting `count` still returns `edges` with the same query count as including it (FR-011); query count for one page equal at 5 and 200 branches through the resolver
- [ ] T043 [US1] FR-008 component test in `backend/tests/component/graphql/queries/test_repository_branch_status.py`: build a `RepositoryBranchStatusResolver` with a recording fake subclassing `RepositoryBranchAttributesSource` as its `build_source`, register it on a throwaway schema, and execute against it. No monkeypatching and no `unittest.mock`: the resolver takes its source factory as a constructor parameter precisely so this test injects (`.agents/rules/testing-python.md`). Assert that a document selecting only `commit` results in `attribute_names == {"commit"}` reaching `read` with `sync_status` absent; that a document selecting only `sync_status` with `own_values_only: true` results in `attribute_names == {"sync_status", "commit"}`; and that `ref` is never requested for the read-write kind

### Documentation and gate

- [ ] T044 [P] [US1] Add `changelog/+repository-branch-status-query.added.md` with the `creating-changelog-entries` skill, describing the new query and the `sync_with_git` filter on `InfrahubBranch` as they landed (grep the diff for the exact argument names before writing)
- [ ] T045 [P] [US1] Add a section to `docs/docs/git-integration/branch-synchronization.mdx` showing the example document from `contracts/graphql-repository-branch-status.md`, the inheritance rule for branches that never imported, the permission requirement, and the warning that `updated_at` on an inherited row is not a last-import time; then `uv run invoke docs.generate`, `uv run invoke docs.validate` and `uv run invoke docs.lint`
- [ ] T045a [P] [US1] Record the two backend architecture changes in `dev/knowledge/backend/`, which the constitution requires and which no other task covers. In `query-pattern.md`, add the cross-branch grouped attribute read to the core patterns: `UNWIND` over a branch-name list joined to `Branch`, `WITH DISTINCT` before the election subqueries, the per-branch visibility predicate and its `is_isolated` window, and the Python-side backfill for branches that produced no row. Name the two prior instances of the shape so the next author finds all three. In `permissions.md`, add a short section on enforcing permission inside a hand-written root field: why the checker pipeline cannot see one, the pre-lookup then post-lookup pair that avoids leaking whether an id resolves, and that a context without a `PermissionManager` is a denial
- [ ] T045b [P] [US1] Add `backend/tests/query_benchmark/test_repository_branch_attributes.py` benchmarking `RepositoryBranchAttributesQuery` across the branch counts the slice targets, following the existing `test_node_get_list.py` shape. `EXPLAIN` (T034) is a one-off review; this is the regression guard the constitution's Performance Standards ask for on a feature whose whole purpose is a query-cost profile
- [ ] T046 [US1] Error-path review of every file under `backend/infrahub/core/repository_branch_status/`, `backend/infrahub/core/query/repository.py` and `backend/infrahub/graphql/queries/repository_branch_status/` against `dev/guidelines/backend/exceptions.md`: `grep -n "except" <paths>` must show only the single `InitializationError` catch in `permissions.py`; every raised error is an Infrahub `Error` subclass; every raise has a component test that provokes it (cross-check T027 through T029 and T040 through T043); record the checklist in the PR description
- [ ] T047 [US1] Run `/pre-ci`, then open the increment B pull request with the `EXPLAIN` plan (T034) and the error-path checklist (T046). Acceptance: `stub.py` deleted, quickstart B1 through B8 pass, Jira subtask from T032 closed

**Checkpoint**: User Story 1 backend is complete. The Branches card renders true values with no
contract change.

---

## Phase 5: User Story 2: the periodic sync stops querying per branch (Priority: P2) [PR 4]

**Goal**: `get_repositories_commit_per_branch` reads every repository's `commit` and
`internal_status` for every branch through the reader in fixed chunks, bounded by
`1 + ceil(N / 100)` queries for N branches across all repositories. Its own reviewed change
(spec, Governance Gates).

**Independent Test**: Quickstart C1 and C2. `CountingInfrahubDatabase.count_for("repository-branch-attributes") <= ceil(200 / 100)`
for a 200-branch fixture; the `-global-` key is gone; existing sync flow tests pass unchanged in
outcome.

**Dependency**: requires T035 (the reader). Can start as soon as T035 and T036 are merged, in
parallel with the rest of Phase 4.

- [ ] T048 [P] [US2] Add `REPOSITORY_BRANCH_READ_CHUNK_SIZE = 100` to `backend/infrahub/git/constants.py` with a one-line comment saying why it is a plain constant rather than a setting (no operator has a reason to tune it, and a setting would drag in the generated Compose env block and the configuration docs). The comment cites no spec document: `.agents/rules/code-doc-style.md` keeps spec references out of source
- [ ] T049 [US2] Refactor `get_repositories_commit_per_branch` in `backend/infrahub/git/utils.py`: one `NodeManager.query` on the default branch for the repository nodes of the requested kind (the `repository` object and branch-agnostic fields callers keep using now come from the default branch); branch names from `registry.branch` minus `GLOBAL_BRANCH_NAME`; build `RepositoryBranchAttributesReader(db=db, default_branch_name=registry.default_branch, global_branch_name=GLOBAL_BRANCH_NAME)` once at the top of the function (the flow entry point is the composition root); iterate `itertools.batched(branch_names, REPOSITORY_BRANCH_READ_CHUNK_SIZE)` calling `reader.read(repository_ids=..., branch_names=chunk, attribute_names=("commit", "internal_status"))`; fill `RepositoryData.branches[name]` with the commit value or `None` and `RepositoryData.branch_info[name]` with `RepositoryBranchInfo(internal_status=...)`. Writing `None` needs `RepositoryData.branches` widened from `dict[str, str]` to `dict[str, str | None]` in `backend/infrahub/git/models.py`; follow the widened type through `ComputedAttributeTrigger.populate_branch_commit` in `backend/infrahub/computed_attribute/models.py`, whose `branch_commit: dict[str, str]` is fed straight from it and whose `repository_commit` returns that value as `str`. The declared type already understates today's behaviour, since the per-branch `commit.value` can be unset; this makes it honest rather than introducing the case. A `None` `internal_status` lookup (attribute never created on any visible branch, which cannot happen after repository creation) logs a warning naming repository and branch and falls back to `RepositoryInternalStatus.INACTIVE.value`, the safe over-conservative choice (`dev/guidelines/backend/exceptions.md`, best-effort fallback). The `-global-` key is no longer written. No `try`/`except` around the chunk loop: a failing chunk aborts the read, because a partial `RepositoryData` would silently skip branches in the sync
- [ ] T050 [US2] Confirm the two callers need no change and record it in the PR: `sync_remote_repositories` in `backend/infrahub/git/tasks.py` reads the default branch and the staging branch only; `gather_trigger_computed_attribute_python` in `backend/infrahub/computed_attribute/gather.py` indexes `branches[...]` by branch name and never by `-global-`
- [ ] T051 [US2] Update `backend/tests/component/git/test_utils.py`: remove the `-global-` expectations from `test_get_repositories_commit_per_branch_main`, `test_get_repositories_commit_per_branch_non_main_default_branch` and `test_get_repositories_commit_per_branch_branches`; add a 200-branch test with `CountingInfrahubDatabase` asserting `count_for("repository-branch-attributes") <= math.ceil(200 / REPOSITORY_BRANCH_READ_CHUNK_SIZE)` and exactly one repository-node query (FR-010, C1); assert `RepositoryData.repository.default_branch.value`, `.location.value` and, for a read-only repository, `.ref.value` carry the default branch's values even when a user branch wrote different ones (the old loop left whichever branch it visited last, so all three change provenance, not just the first two); assert a branch whose commit resolves to `None` appears with `None` and an `inactive` `internal_status`; assert two repositories of different kinds are both present with per-branch values
- [ ] T052 [P] [US2] Add a test to `backend/tests/component/computed_attribute/test_gather.py` that, with three non-global branches and one Python computed attribute, `gather_trigger_computed_attribute_python` resolves `branches[branch.name]` for every non-global branch without a `KeyError` (critique E8)
- [ ] T052a [US2] Extend `backend/tests/integration_docker/test_computed_attributes.py` with a case exercising a Python computed attribute on a repository across more than one branch after this refactor. The constitution requires a distributed-stack test for changes involving computed attributes, and this increment rewrites the structure the trigger gather reads; T052 covers the gather call in-process but not the trigger firing end to end. If the existing cases already cover it, say so in the PR with the case names instead of adding one
- [ ] T053 [US2] Run the existing sync flow tests `uv run pytest backend/tests/component/git/` and confirm the same repositories are bootstrapped and synced as before (C2); record the run in the PR
- [ ] T054 [P] [US2] Add `changelog/+repository-sync-single-read.changed.md` with the `creating-changelog-entries` skill describing the bounded read as it landed (grep the diff for the constant's value)
- [ ] T055 [P] [US2] Update `dev/knowledge/backend/git-sync.md` with a section on the sync read path: one repository-node query, one `RepositoryBranchAttributesQuery` per chunk of `REPOSITORY_BRANCH_READ_CHUNK_SIZE` branch names, the absence of the `-global-` key, and where the reader is built
- [ ] T056 [US2] Run `/pre-ci`, then open the increment C pull request with the query-count assertion output in the description

**Checkpoint**: User Story 2 complete. SC-004 holds by test.

---

## Phase 6: Polish and Cross-Cutting Concerns [PR 5]

- [ ] T057 [P] Grep `dev/specs/infp-671-cross-branch-repo-status/` for every figure and identifier the implementation may have changed (`40`, `100`, `1 + ceil(N / 100)`, per-page query counts, module and class names) and update every file that repeats a stale value in one commit (AGENTS.md, Always Do). Then update the source PRD in Confluence, which still carries the pre-analysis wording on FR-001 (anchors on "id or HFID", which cannot resolve), FR-010 (`ceil(N / chunk_size)`, missing the repository-node read) and FR-014 (own value defined against the selected attributes). Leaving it stale means the product source of truth contradicts what shipped
- [ ] T058 [P] Perform the manual dev-stack check from quickstart.md (`uv run invoke dev.start`, load demo schema and data, run the example document at `http://localhost:8000/graphql`, create a `sync_with_git: false` branch and confirm it disappears from the read-write repository's rows)
- [ ] T059 Confirm the card's pytest-playwright E2E test is tracked on IFC-3130 (Branches card on the repository page), which carries it in scope, and that the directory settled in T032 is recorded there. The constitution requires an E2E test for a user-facing feature and this slice defers it to the card, so the deferral holds only while that issue does. Separately, file Python SDK exposure of `InfrahubRepositoryBranchStatus` as a follow-up under IFC-3104. Nothing goes under INFP: that is JPD, for product planning, and its link to the epic is the connection
- [ ] T060 Final `uv run invoke docs.validate` and `uv run invoke schema.validate-graphqlschema` on the merged tree, confirming no generated file is stale after the three increments

---

## Dependencies and Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies
- **Phase 2 (Foundational)**: T005 to T007 in sequence (filter, Cypher, GraphQL argument); T008 then T009; T010 to T013 after their code tasks. Blocks Phase 3
- **Phase 3 (US1, increment A)**: T014 to T022 all parallel after Phase 2; T023 after T014 to T022; T024 after T023; T025 after T024; T026 after T025; T027 parallel with T023 onward; T028 to T030 after T026; T030a any time after T007; T031 after all tests and T030a; T032 after T031 merges
- **Phase 4 (US1, increment B)**: T033 then T034 then T035 then T036; T037 to T039 after T036; T040 and T041 after T036 (parallel with T037 to T039); T042 and T043 after T039; T044, T045, T045a and T045b parallel after T039 (T045b needs only T033); T046 after T043; T047 last
- **Phase 5 (US2)**: T048 any time; T049 after T036 (the reader), independent of T037 to T047; T050 to T052 after T049; T052a after T052; T053 after T051; T054 and T055 parallel after T049; T056 last
- **Phase 6**: after all three increments merge

### User story dependencies

- **US1** is delivered in two increments. Increment A is the MVP and has no dependency on increment B.
- **US2** depends on the reader (T035, T036) only. It does not depend on the resolver swap (T037 to
  T039) and can be opened as a PR while increment B's tests are still being written, but it must
  merge after increment B so `develop` never carries two readers of the same values.

### Critical path

T005 to T009 (foundational) then T014 to T026 (contract stub) then T031 (increment A PR). Everything
the frontend team needs is on that path; increment B and C are off the frontend's critical path.

---

## Parallel Execution Examples

### Increment A after Phase 2

```text
Parallel group 1 (different files, no shared state):
  T014 RepositoryBranchAttributeValue        backend/infrahub/core/query/repository.py
  T015 RepositoryBranchAttributes            backend/infrahub/core/repository_branch_status/models.py
  T016 RepositoryBranchAttributesSource      backend/infrahub/core/repository_branch_status/interface.py
  T017 graphene types                        backend/infrahub/graphql/types/repository_branch_status.py
  T018 paging.py                             backend/infrahub/graphql/queries/repository_branch_status/paging.py
  T019 stub.py                               backend/infrahub/graphql/queries/repository_branch_status/stub.py
  T020 payload.py                            backend/infrahub/graphql/queries/repository_branch_status/payload.py
  T021 kind_dispatch.py                      backend/infrahub/graphql/queries/repository_branch_status/kind_dispatch.py
  T022 permissions.py                        backend/infrahub/graphql/queries/repository_branch_status/permissions.py

Then sequential: T023 resolver class, T024 field.py composition root, T025 registration, T026 regeneration.
Parallel with T023 onward: T027 unit tests, T030a changelog fragment.
After T026, parallel: T028, T029, T030 (same file, coordinate by class; or one implementer).
```

### Increment B after the reader exists (T036)

```text
Parallel group:
  T037 + T038 + T039 resolver swap (one implementer, three files)
  T040 + T041 primitive component tests      backend/tests/component/core/query/test_repository_branch_attributes.py
  T045a knowledge docs                       dev/knowledge/backend/query-pattern.md, permissions.md
  T045b primitive benchmark                  backend/tests/query_benchmark/test_repository_branch_attributes.py
  T048 + T049 increment C refactor           backend/infrahub/git/constants.py, backend/infrahub/git/utils.py
```

---

## Implementation Strategy

### MVP first: increment A only

1. Phase 1 and Phase 2.
2. Phase 3 through T031. Merge once GraphQL schema sign-off is given.
3. T032: hand the contract to the frontend team. They start the card; this backend work continues
   on increment B without blocking them.

### Incremental delivery

1. Increment A merged: frontend unblocked, contract final, fabricated values, release rule in force.
2. Increment B merged: true values, filters real, stub deleted, release rule lifted, changelog and
   docs land. US1 complete.
3. Increment C merged: sync bounded, its own changelog and knowledge doc. US2 complete.
4. Phase 6 polish.

### Two implementers

- Implementer A: Phase 2 then Phase 3 (the frontend-facing path), then Phase 4 tests (T040 to T043).
- Implementer B: after T036 lands, Phase 5 in parallel with Implementer A's Phase 4 work.

---

## Notes

- Critique X1 is adopted (2026-09-03): `own_values_only` filters on the branch's own `commit` value
  only, independent of the caller's selection, and `commit` is read even when unselected. FR-014,
  FR-008, the SDL description, the contract document and T018, T023, T027, T039, T042, T043 all
  state it that way.
- `payload.py`, `kind_dispatch.py`, `permissions.py` and `interface.py` are listed in plan.md's
  Project Structure. They split responsibilities the plan first assigned to `resolver.py` and
  `stub.py` so each module has one reason to change and the stub-to-reader swap is a single wiring
  line.
- Adopted from the cross-artifact analysis (2026-09-04):
  - The composition root is `field.py`, not the package `__init__.py`, which stays empty. Wiring in
    the init would breach `dev/knowledge/backend/package-init-files.md` and would not import: the
    init needs `resolver.py` for the resolver while `resolver.py` needs the source factory back.
    `schema.py` imports the field directly, as it already does for `event`, `task` and `diff.tree`.
  - The resolver is a callable class taking `build_source` as a required constructor parameter, so
    T043 injects a recording fake rather than monkeypatching a module attribute.
  - `sync_with_git` is restored as a row field (FR-003, matching the PRD). It reads constant `true`
    on the read-write kind, but the read-only kind's row set is every branch, so the value varies and
    a caller cannot otherwise get it without a second request.
  - Nothing in code, in a docstring, in a test name, in a log message or in the SDL description names
    a ticket, a task id or a delivery increment (`.agents/rules/code-doc-style.md`). Those live in
    commit messages, PR descriptions, changelog fragments and this directory.
- Verify tests fail before implementing where a task lists the test next to the code it pins.
- Commit after each task or logical group. Never force push. Use the `commit` skill.
