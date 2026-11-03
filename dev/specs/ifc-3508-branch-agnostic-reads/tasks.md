# Tasks: Branch-Agnostic Reads That Return the Right Branch's Data

**Input**: Design documents from `dev/specs/ifc-3508-branch-agnostic-reads/` ([plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md))

**Jira**: [IFC-3508](https://opsmill.atlassian.net/browse/IFC-3508)

**Tests**: required. FR-035 requires, for every PR, a component test that fails on the current code and passes with the fix.

**Organization**: one phase per user story, and each user story is one PR, except User Story 6, which is PRs 6 and 7 (PR 7 adds `active_on_branches`, FR-041 and FR-042). Phases follow the PR order in the brief, not the priority order, because the PRs depend on each other (see Dependencies). US1 (P1) and US3 (P1) ship first. US2 (P3) is small and independent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story, and therefore the PR, that the task belongs to
- Run every test command from `backend/` with `uv run --no-sync pytest <path> -p no:randomly -q`.

## Path Conventions

- Backend source: `backend/infrahub/`
- Tests: `backend/tests/unit/`, `backend/tests/component/`, `backend/tests/benchmark/`
- Audit tests (not committed): `branch-agnostic-wip/audit-tests/` in the `branch-agnostic-reads` worktree
- Earlier code: commit `7015435c4` (local branch `branch-agnostic-source`), read with `git show 7015435c4:<path>`

## Stop-and-ask gates

The brief says to stop and ask where a fix depends on an open question. These tasks are gates. Implementation stops at the gate, reports the evidence to the user, and waits for an answer before any task that depends on it:

- T061 (open question 1, PR 6)
- T062 (open question 2, PR 5)
- T085 (open question 3, PR 6)
- T014 (the E2E test exception, PR 1)
- T119, only when `python_sdk` holds a typed copy of `InfrahubNodeMetadata` (PR 7)

---

## Phase 1: Setup (shared)

**Purpose**: confirm the starting state that every PR measures against.

- [ ] T001 Copy each audit test file from `branch-agnostic-wip/audit-tests/` into a scratch copy of `backend/tests/component/core/` on `origin/release-1.12`, run it, and record the pass and fail counts per file in `dev/specs/ifc-3508-branch-agnostic-reads/quickstart.md` under "Before a PR". Expected counts are in that section. Do not commit the copies.
- [ ] T002 Check the state of PR #11220 with `gh pr view 11220 --json state,mergedAt,mergeCommit`, and whether its changes are in `origin/release-1.12`. Record the result in `dev/specs/ifc-3508-branch-agnostic-reads/plan.md` under "Delivery by PR". PRs 5 and 6 cannot start until it is merged.

---

## Phase 2: Foundational

No task blocks every story. The shared branch window module ships in US3 (PR 3), and it blocks US4, US5 and US6. US1 and US2 do not need it.

---

## Phase 3: User Story 1 - Global permissions follow the default branch (Priority: P1) — PR 1

**Goal**: global permissions, the login role list and the single sign-on member check read the default branch combined with `-global-` (FR-001 to FR-004).

**Independent Test**: on branch B, add an account to a group whose role holds `super_admin`. Permissions on the default branch and on B do not include `super_admin` until B is merged.

**Base**: `origin/stable`. Branch: `fix-global-permissions-default-branch-ifc-3508`.

### Tests for User Story 1

- [X] T003 [US1] Create a worktree for branch `fix-global-permissions-default-branch-ifc-3508` from `origin/stable`, and check that `backend/infrahub/core/account.py`, `backend/infrahub/auth/auth.py` and `backend/infrahub/auth/auth_groups/service.py` match research R2.
- [X] T004 [P] [US1] Move the tests of `branch-agnostic-wip/audit-tests/test_audit_branch_agnostic_permission_reads.py` into `backend/tests/component/core/test_account_global_permissions.py`:
  - In `test_global_permission_linked_on_branch_grants_permission_on_default`, change the expected permissions on the branch to `{'edit_default_branch'}`.
  - In `test_membership_added_on_branch_grants_permission_on_default`, add the same check on the branch, expecting `set()`.
  - Remove debug output and unused fixtures.
  - Do not use `SUPER_ADMIN_PERMISSION`, which does not exist on `stable`.
  - Confirm the tests that are not controls fail.
- [X] T005 [P] [US1] Add `test_login_roles_keep_role_removed_on_branch` (from the audit permission file) to `backend/tests/component/core/test_account.py`, next to `test_fetch_account_groups_and_roles`. Confirm it fails.
- [X] T006 [P] [US1] Add `test_group_members_keep_member_removed_on_branch` and `test_group_members_skip_member_added_on_branch` (from the audit permission file) to `backend/tests/component/auth/auth_groups/test_member_reads.py`, reusing the fixtures in `backend/tests/component/auth/auth_groups/conftest.py`. Confirm they fail. Result: both pass on `stable`, because `_add_member` loads the group with `prefetch_relationships=True` and `get_peers` reuses the cached default-branch members. The tests stay as regression tests; they do not fail before the fix.
- [X] T007 [P] [US1] Add `backend/tests/component/api/test_permissions_on_branch.py`, following the HTTP client fixtures of `backend/tests/component/api/test_20_graphql.py`, with two tests:
  - An account with `MANAGE_ACCOUNTS` but not `EDIT_DEFAULT_BRANCH` adds itself to an administrator group on branch B through `CoreAccountGroupUpdate` sent to `/graphql/B`, then sends `BranchMerge(name: "B")` to `/graphql/B`. The merge is refused (spec US1 scenario 4).
  - An account that holds `super_admin` only through a membership added on B sends a mutation that changes an account to `/graphql/B`. It is refused (spec US1 scenario 7).

  Confirm both fail.

### Implementation for User Story 1

- [X] T008 [US1] In `backend/infrahub/core/account.py::fetch_permissions` and `::fetch_role_permissions`, resolve the default branch with `registry.get_branch(db=db, branch=registry.default_branch)` and run `AccountGlobalPermissionQuery` and `AccountRoleGlobalPermissionQuery` on it without `branch_agnostic`. Keep the request branch for the object permission queries (FR-001, FR-003).
- [X] T009 [P] [US1] Remove `branch_agnostic=True` from `group.roles.get_peers` in `backend/infrahub/auth/auth.py::fetch_account_groups_and_roles` (FR-002).
- [X] T010 [P] [US1] Remove `branch_agnostic=True` from `members_rel.get_peers` in `backend/infrahub/auth/auth_groups/service.py::AutoCreatedGroupsService._add_member` (FR-002).
- [X] T011 [US1] Run T004-T007 and the existing suites: `backend/tests/component/core/test_account.py`, `backend/tests/component/permissions/`, `backend/tests/component/graphql/auth/query_permission_checker/` and `backend/tests/component/auth/auth_groups/`. All pass.
- [X] T012 [P] [US1] Update `docs/docs/deploy-manage/user-management/permissions-roles/overview.mdx`: global permissions, group memberships and roles take effect from the default branch, and a change made on a branch applies only after the branch is merged. Object permissions follow the request branch. Run `uv run invoke docs.lint`.
- [X] T013 [P] [US1] Add a `fixed` changelog fragment in `changelog/` with the `creating-changelog-entries` skill. It says that a change made on a branch to group membership, roles or global permissions no longer changes global permissions until the branch is merged.
- [X] T014 [US1] Gate: ask the reviewer whether the E2E exception in `plan.md` "Complexity Tracking" is approved. If it is not, add one E2E test under `tests/e2e/` for scenario 1 of US1. Result: the user approved the exception on 2026-10-30; no E2E test is added.
- [ ] T015 [US1] Run the pre-push checks in `quickstart.md`, open the PR against `stable`, and report that this PR changes no query (no benchmark needed). How the PR is disclosed is decided outside this plan.

**Checkpoint**: US1 is complete and reviewable on its own.

---

## Phase 4: User Story 2 - Reads of `-global-` data leave the branch-agnostic path (Priority: P3) — PR 2

**Goal**: callers that read only `-global-` data stop passing `branch_agnostic=True`, with unchanged results (FR-005).

**Independent Test**: the existing tests of each changed caller pass unchanged.

**Base**: `origin/release-1.12`. Branch: `global-only-reads-ifc-3508`.

- [X] T016 [US2] Create a worktree for `global-only-reads-ifc-3508` from `origin/release-1.12`. Result: created at `.claude/worktrees/global-only-reads-ifc-3508` from `cb19b585e`, with no upstream.
- [X] T017 [US2] Classify the callers research R3 found outside the brief:
  - `backend/infrahub/pools/number_pool_repository.py` (3 calls)
  - `backend/infrahub/pools/number_pool_lookup.py`
  - `backend/infrahub/pools/scoped_number_pool_reader.py` (2 calls)
  - `backend/infrahub/core/migrations/graph/m080_number_pool_ranges/migration.py`

  For each call, check the branch support of the kind it reads and of every relationship it follows, for example `CoreNumberPoolRange.pool`, in `backend/infrahub/core/schema/definitions/`. Record the result in the PR description. Only calls verified as reading `-global-` data are changed in T024. `m080` is a shipped migration and is not edited. Result: on the current `release-1.12` the migration is `m081_number_pool_ranges`, left unchanged. In `number_pool_repository.py`, only `delete_pool` reads `CoreNumberPool`; `get_used` and `get_free` run `NumberPoolGetUsed` and `NumberPoolGetFree`, which read branch-aware values across live branches and never read the flag, so they stay unchanged for PR 3.
- [X] T018 [P] [US2] Remove `branch_agnostic=True` from the `get_many` call in `backend/infrahub/graphql/loaders/account.py`, and remove its comment.
- [X] T019 [P] [US2] Remove `branch_agnostic=True` from `NodeManager.query` in `backend/infrahub/graphql/resolvers/resolver.py::is_externally_managed_resolver`.
- [X] T020 [P] [US2] Remove `branch_agnostic=True` from `NodeManager.query` in `backend/infrahub/webhook/tasks/invalidate.py`.
- [X] T021 [P] [US2] Remove `branch_agnostic=True` from all three calls in `backend/infrahub/pools/schema_number_pool_synchronizer.py`.
- [X] T022 [P] [US2] Remove `branch_agnostic=True` from all three calls in `backend/infrahub/pools/schema_number_pool_upserter.py`.
- [X] T023 [P] [US2] Remove `branch_agnostic=True` from `proposed_change.validations.get_peers` in `backend/infrahub/core/integrity/object_conflict/conflict_recorder.py::ObjectConflictValidatorRecorder.get_validator`.
- [X] T024 [US2] Apply the same change to the calls T017 verified. Result: changed `NumberPoolRepository.delete_pool`, `NumberPoolRangeLookup.get_ranges` and both calls in `ScopedNumberPoolReader`; `branch_agnostic` is also removed from the `NumberPoolRangeNodeReader` protocol, which required it.
- [X] T025 [US2] Check whether `GetGlobalPermissionAttributesQuery` in `backend/infrahub/core/migrations/graph/m062_recompute_permission_display_labels.py` reads the `branch_agnostic` argument. If it ignores the argument, remove it from both calls as a no-op and say so in the PR. If it does not ignore it, leave the shipped migration unchanged and record why. Result: `query_init` matches only `-global-` edges, hardcoded, and never reads the flag; the argument is removed from both calls.
- [X] T026 [US2] Run the tests of each changed caller:
  - `backend/tests/component/graphql/`, filtered with `-k account`
  - `backend/tests/component/webhook/`
  - `backend/tests/component/pools/`
  - `backend/tests/component/core/resource_manager/`
  - `backend/tests/component/core/integrity/`
  - `backend/tests/component/core/migrations/graph/`, filtered with `-k m062`

  All pass unchanged. Result: all pass; `backend/tests/component/core/integrity/` does not exist on `release-1.12`, so the conflict recorder was tested through `backend/tests/integration/proposed_change/test_proposed_change_conflict.py` and `test_proposed_change_cardinality_one_conflict.py`, `-k m062` matches no test, so `test_062_recompute_permission_display_labels.py` was run directly, and the 42 `-k account` failures in `graphql/auth/query_permission_checker/` come from the filter deselecting their setup tests and pass when those files run unfiltered.
- [ ] T027 [US2] Run the pre-push checks in `quickstart.md` and open the PR against `release-1.12`. Add no changelog fragment, because no user can notice the change. Result: pre-push checks pass; the PR is not opened, because the user asked for a local branch.

**Checkpoint**: US2 is complete and independent of the other stories.

---

## Phase 5: User Story 3 - IP pools never hand out a value still in use on a live branch (Priority: P1) — PR 3

**Goal**:

- one shared branch window module (FR-013);
- IP pool free values computed across live branch windows (FR-006, FR-007);
- allocation on branch X using only the namespace and resources that exist on X (FR-008 to FR-011);
- number pools moved onto the shared windows with no change in results (FR-012).

**Independent Test**: allocate a prefix on the default branch, create B, delete the prefix on the default branch, then allocate on B. A different prefix is returned.

**Base**: `origin/release-1.12`. Branch: `branch-windows-ip-pools-ifc-3508`.

### Tests and benchmarks for User Story 3

- [ ] T028 [US3] Create a worktree for `branch-windows-ip-pools-ifc-3508` from `origin/release-1.12`.
- [ ] T029 [P] [US3] Bring `backend/tests/benchmark/test_node_list_filter.py` from `7015435c4` (`git show 7015435c4:backend/tests/benchmark/test_node_list_filter.py`) and adapt it to the `release-1.12` API, so later PRs can report filter costs against it (research R12).
- [ ] T030 [P] [US3] Add `backend/tests/benchmark/test_ip_pool_allocation.py`. It allocates from an IP prefix pool and an IP address pool with 50 live branches and at least 1,000 past allocations, and sums database hits with Neo4j `PROFILE` as `test_node_list_filter.py` does. Run it on the base branch and record the numbers.
- [ ] T031 [P] [US3] Move the 8 IP pool tests of `branch-agnostic-wip/audit-tests/test_audit_branch_agnostic_pool_reads_release_1_12.py` (IPv4 and IPv6) into `backend/tests/component/core/resource_manager/test_ip_pool_branch_windows.py`, and confirm they fail. Move its 4 number pool tests into `backend/tests/component/core/resource_manager/test_number_pool_branch_windows.py`, and confirm they pass; they guard against regressions.
- [ ] T032 [P] [US3] Add allocation tests to `backend/tests/component/core/resource_manager/test_ip_pool_allocation_on_branch.py`, one per acceptance scenario 3-6 of spec US3:
  - namespace only on branch B, allocation on the default branch: `ResourceNotFoundError` naming the pool, the namespace and the branch;
  - no resource exists on X: `PoolExhaustedError` naming the pool and X, for both pool kinds;
  - some resources missing on X: only the existing ones are used;
  - namespace, prefix and pool created on B: allocation succeeds on B, and on the default branch after B is merged.
- [ ] T033 [P] [US3] Extend `backend/tests/component/core/resource_manager/test_number_pool_query.py`:
  - pin the current per-branch results of `NumberPoolGetAllocated` and `NumberPoolGetFree` in a state with two live branches and a value deleted on the default branch after branching;
  - add a read at a time before a branch was created.

  Both pass on the base branch.

### Implementation for User Story 3

- [ ] T034 [US3] Create `backend/infrahub/core/query/branch_windows.py` with `build_branch_windows_query`, `render_window_filter` and `render_outranks`, as specified in `contracts/branch-window-helpers.md`, including `carry` and `include_deleting`. Import only `infrahub.core.constants`, and `Timestamp` under `TYPE_CHECKING`.
- [ ] T035 [P] [US3] Add `backend/tests/unit/core/query/test_branch_windows.py`, covering:
  - the disabled form;
  - parameters;
  - carried variables;
  - `deleting_branches` emitted only with `include_deleting`;
  - the rendered predicates naming the variables they are given.
- [ ] T036 [US3] Replace the window collection in `backend/infrahub/core/query/agnostic_retention.py::UNRETAINED_AGNOSTIC_FIELD_PREDICATE` with `build_branch_windows_query(carry=["agnostic_candidates"], time_param="at")`. Keep `UNRETAINED_AGNOSTIC_FIELD_EVALUATION` unchanged. Run `backend/tests/component/core/agnostic_retirement/` and `backend/tests/component/core/migrations/graph/m078_retire_agnostic_property_edges/`.
- [ ] T037 [US3] Replace the inline window collection in `backend/infrahub/core/query/branch_agnostic_retirement.py` with the shared clause. Run `backend/tests/component/core/agnostic_retirement/`.
- [ ] T038 [US3] In `backend/infrahub/core/query/resource_manager.py`:
  - replace `LIVE_BRANCHES_QUERY` with the shared clause (`include_deleting=True`);
  - rename `fork_at` to `origin_at` in every fragment that reads the windows: `_live_on_some_branch`, `LIVE_ATTRIBUTE_VALUES_QUERY`, `INHERITED_OPEN_VALUES_QUERY`, the division filters and `NumberPoolAttributeBranchValuesQuery`;
  - check that each fragment skips the default branch's entry, whose origin is NULL.

  Run T031's number pool tests, T033 and `backend/tests/component/core/resource_manager/`; all pass.
- [ ] T039 [US3] Rewrite `IPPrefixSubnetFetchFree` in `backend/infrahub/core/query/ipam.py` in the flat window form of research R4:
  - the windows clause opens the query;
  - the namespace check passes when `any(window …)` finds its `IS_PART_OF` edge latest and active, and yields no row otherwise;
  - an allocated child is kept when, in some window, its `IS_PART_OF`, both `ip_namespace` `IS_RELATED` edges, `HAS_ATTRIBUTE` and `HAS_VALUE` are latest and active;
  - candidates are bounded by `r.from <= $windows_at` and `r.to` later than the oldest `origin_at`.
- [ ] T040 [US3] Apply T039 to `IPv6PrefixSubnetFetchFree` in `backend/infrahub/core/query/ipam.py`.
- [ ] T041 [US3] Apply T039 to `IPPrefixIPAddressFetchFree` in `backend/infrahub/core/query/ipam.py`.
- [ ] T042 [US3] Apply T039 to `IPv6PrefixIPAddressFetchFree` in `backend/infrahub/core/query/ipam.py`.
- [ ] T043 [US3] In `backend/infrahub/core/node/resource_manager/ip_prefix_pool.py::CoreIPPrefixPool.get_resource` and `::get_next`, read the namespace and resources on the allocating branch as research R4 describes:
  - read the namespace id with `ip_namespace.get_peer_id()`, then load it with `NodeManager.get_one(branch=X)`;
  - read resources by peer id, then `NodeManager.get_many(branch=X)`;
  - raise `ResourceNotFoundError` when the namespace is missing on X, and `PoolExhaustedError` when no resource remains;
  - replace the `IndexError`.

  Use the message templates in `contracts/user-visible-behavior.md`.
- [ ] T044 [US3] Apply T043 to `backend/infrahub/core/node/resource_manager/ip_address_pool.py::CoreIPAddressPool`.
- [ ] T045 [US3] Run T031-T035 and:
  - `backend/tests/component/core/resource_manager/`
  - `backend/tests/component/core/ipam/`
  - `backend/tests/component/graphql/resource_manager/`
  - `backend/tests/component/graphql/queries/test_resource_pool.py`

  All pass.
- [ ] T046 [US3] Run T030 again and record the database hits before and after in the PR description. If allocation is significantly slower, change the approach before review.
- [ ] T047 [P] [US3] In `dev/knowledge/backend/query-pattern.md`, add a short rule that a query needing an answer across branches builds its windows with `core/query/branch_windows.py`, and point to it. Check the file against its size range in `dev/guidelines/repository-organization.md`.
- [ ] T048 [P] [US3] Update `docs/docs/resource-manager/allocate-ip-prefix.mdx` and `docs/docs/resource-manager/allocate-ip-address.mdx`:
  - allocation on a branch uses the pool's namespace and resources that exist on that branch;
  - a value is not reused while any open branch holds it;
  - the two new errors.

  Run `uv run invoke docs.lint`.
- [ ] T049 [P] [US3] Add changelog fragments with the `creating-changelog-entries` skill:
  - `fixed`: IP pools no longer allocate a value still in use on another branch, or after the namespace is deleted on a branch;
  - `changed`: allocation on a branch where the pool's namespace or resources do not exist fails with a named error, and the prefix pool raises the same error as the address pool when no resource is usable.
- [ ] T050 [US3] Run the pre-push checks in `quickstart.md` and open the PR against `release-1.12`, with the benchmark results.

**Checkpoint**: US3 is complete. US4 can start, and US5 can start once PR #11220 is in `release-1.12`.

---

## Phase 6: User Story 4 - Deleting a branch-agnostic node checks every live branch (Priority: P2) — PR 4

**Goal**: the delete of a branch-agnostic node is refused when any live branch would break a constraint (FR-014 to FR-017).

**Independent Test**: P is linked to G1 on the default branch through a required relationship; B is created; P is moved to G2 on the default branch; deleting G1 is refused, and the error names B and P.

**Base**: PR 3's branch, rebased on `release-1.12` once PR 3 merges. Branch: `agnostic-delete-check-ifc-3508`.

- [ ] T051 [US4] Create a worktree for `agnostic-delete-check-ifc-3508` from `branch-windows-ip-pools-ifc-3508`.
- [ ] T052 [P] [US4] Add `backend/tests/component/core/test_node_manager_delete_agnostic.py`, with one test per acceptance scenario 1-5 of spec US4, including the case where P reaches G1 on B only through the default branch's edge from before B was created.
  - First look for an existing schema fixture with a required relationship from a branch-aware kind to a branch-agnostic kind, and with a cascade. Only if none exists, add those kinds to `backend/tests/helpers/schema/agnostic_retirement.py`.
  - Confirm scenarios 1-3 fail.
- [ ] T053 [US4] Add a window mode to `RelationshipGetByIdentifierQuery` in `backend/infrahub/core/query/relationship.py`:
  - the windows clause opens the query;
  - it starts from the ids of the delete set;
  - it keeps a row when, in a window, both `IS_RELATED` edges are latest and active and both nodes exist;
  - it returns the window name.

  Add `window_name: str | None = None` to `RelationshipPeersData`. The single-branch mode keeps its query unchanged.
- [ ] T054 [US4] In `backend/infrahub/core/node/delete_validator.py::NodeDeleteValidator`, for a branch-agnostic node:
  - run the window-mode query for each level of cascade;
  - group the rows by `window_name`;
  - run the existing walk once per window;
  - raise the existing `ValidationError`, with ` on branch '<name>'` added, for a required peer left behind in a window or a cascade that reaches a peer only outside the request branch's window.

  The path for a branch-aware node is unchanged.
- [ ] T055 [US4] Check that `backend/infrahub/core/manager.py::NodeManager.delete` needs no change beyond passing what the validator needs, and that cascading deletes still write only on the request branch (FR-016).
- [ ] T056 [US4] Run T052, `backend/tests/component/core/test_node_manager_delete.py`, and the GraphQL delete mutation tests under `backend/tests/component/graphql/mutations/` (`-k delete`). All pass.
- [ ] T057 [US4] Add `backend/tests/benchmark/test_delete_agnostic_node.py`. It deletes a `CoreAccountGroup` with 50 live branches and 10,000 group memberships elsewhere in the database. Record the database hits before and after in the PR description.
- [ ] T058 [P] [US4] Add a `fixed` changelog fragment: deleting a branch-agnostic object is refused when another branch still requires it, and the error names the branch and the object.
- [ ] T059 [US4] Run the pre-push checks in `quickstart.md` and open the PR against `release-1.12` once PR 3 is merged.

**Checkpoint**: US4 is complete.

---

## Phase 7: User Story 5 - Reads never return a deleted peer, and no link mixes `-global-` and branch edges (Priority: P2) — PR 5

**Goal**:

- the peer existence check (FR-018 to FR-020);
- the new delete writes and ranking for a branch-agnostic node (FR-021, FR-022);
- the object conversion peer list (FR-040);
- the documentation (FR-027).

**Independent Test**: a role is linked to group G1 on the default branch; B is created; the role is removed from G1 on the default branch; G1 is deleted. Reading the role's groups on either branch does not return G1 and raises no error.

**Base**: the feature branch `branch-agnostic-links-ifc-3508`, created from `origin/release-1.12` after PR 3 and PR #11220 are in it (research R13). Branch: `peer-existence-check-ifc-3508`.

### Gates and inventory

- [ ] T060 [US5] Confirm PR 3 and PR #11220 are merged into `origin/release-1.12` (see T002). Then create the feature branch `branch-agnostic-links-ifc-3508` from it, and a worktree for `peer-existence-check-ifc-3508` from the feature branch.
- [ ] T062 [US5] Gate for open question 2: present research R7's evidence and recommendation (on the default branch, set `to` and write a `deleted` edge with the same `from`, as every user delete does) to the user, and stop. Record the answer under "Open Questions" in `spec.md` and in research R7. T075, T080, T128 and T130 depend on it.
- [ ] T063 [US5] List every query under `backend/infrahub/` that reads `IS_RELATED` (`rg -l IS_RELATED backend/infrahub`). For each, record whether it can read a branch-agnostic relationship or a relationship to a branch-agnostic kind, and whether it needs the check, in a table appended to `research.md` R6. Include `RelationshipCountPerNodeQuery`, the targeted uniqueness validation query, `DependentNodesQuery` and `backend/infrahub/core/validators/relationship/count.py`.

### Tests for User Story 5

- [ ] T064 [P] [US5] Add `backend/tests/unit/core/schema/test_peer_existence_check.py` for `needs_peer_existence_check`. Cover:
  - a branch-agnostic relationship, which returns false;
  - a branch-agnostic peer node;
  - a generic with one branch-agnostic implementation;
  - a generic with only branch-aware implementations;
  - a branch-aware relationship between branch-aware nodes.
- [ ] T065 [P] [US5] Move `test_deleting_group_removes_it_from_role_after_role_removed_on_branch` and `test_graphql_role_groups_after_group_deleted_with_role_removed_on_branch` from `branch-agnostic-wip/audit-tests/test_audit_branch_agnostic_relationship_reads.py` into `backend/tests/component/core/relationship/test_peer_existence.py`. Add tests for:
  - spec US5 scenarios 1, 2, 4 and 8-10 (scenario 3 ships in PR 6, T126);
  - the brief's two new PR 5 tests: a branch-agnostic node deleted after branching with the link removed on the default branch after branching, and a filter through a pool's `resources` on a branch where the prefix is deleted on every live branch (the prefix is not matched, through the retirement check);

  Confirm the tests that check today's wrong results fail.
- [ ] T066 [P] [US5] Add `test_query_text_unchanged_for_branch_aware_relationships` to `backend/tests/component/core/test_relationship_query.py`. It asserts that `RelationshipGetPeerQuery` and `NodeListGetRelationshipsQuery`, for a branch-aware relationship between branch-aware kinds, render the same Cypher as on the base branch (FR-020).
- [ ] T067 [P] [US5] Add a test to `backend/tests/component/core/convert_object_type/` where a former peer is not counted when validating an object conversion (FR-040), and confirm it fails.

### Implementation for User Story 5

- [ ] T068 [US5] Add `needs_peer_existence_check(relationship_schema, peer_schema, schema_branch) -> bool` to `backend/infrahub/core/schema/relationship_schema.py` (data-model.md "Peer existence check").
- [ ] T069 [US5] In `backend/infrahub/core/query/relationship.py::RelationshipGetPeerQuery.query_init`, when the helper returns true, add the check that the peer's latest `IS_PART_OF` edge is `active` under the request branch filter. The count uses the same lines. In branch-agnostic mode, render the window version from the brief: open with the windows clause, and keep a peer only when its latest `IS_PART_OF` edge is `active` in at least one live window. The link ranking stays as it is until T095.
- [ ] T070 [US5] Add an optional parameter to `backend/infrahub/core/query/node.py::NodeListGetRelationshipsQuery` listing the relationship identifiers that need the check, and render the check for them. In `backend/infrahub/core/manager.py`, compute that list with the helper and pass it.
- [ ] T071 [US5] In `backend/infrahub/core/query/relationship.py::GetAllPeersIds`:
  - filter `e2`;
  - check that the latest `e1` and `e2` are `active`;
  - render the existence check for the identifiers the caller passes.

  In `backend/infrahub/core/convert_object_type/object_conversion.py`, pass them (FR-040).
- [ ] T072 [US5] Render the existence check in `RelationshipGetByIdentifierQuery` (both modes) for the identifiers `NodeDeleteValidator` passes, in `backend/infrahub/core/query/relationship.py` and `backend/infrahub/core/node/delete_validator.py`.
- [ ] T073 [US5] In `backend/infrahub/core/query/subquery.py`, render the existence check in `build_subquery_filter` and `build_subquery_order` when the helper returns true for the filtered or ordered relationship. In `build_subquery_order`, keep the peer element named. Build on PR #11220's version of `build_subquery_filter`.
- [ ] T074 [US5] Add the check to each other query T063 marked as needing it.
- [ ] T075 [US5] Rewrite `RelationshipDeleteAllQuery` in `backend/infrahub/core/query/relationship.py` as research R7 decides:
  - rank by `branch_level DESC, from DESC, status ASC`;
  - for a branch-aware node, keep today's writes, ranked as above. T129 in PR 6 stops writing branch edges on its branch-agnostic relationships (FR-023, research R13);
  - for a branch-agnostic node, close the default branch's edge as T062 decided, write a `deleted` edge on each live user branch whose own latest edge is `active`, and write nothing on `-global-`;
  - apply the same rules to `IS_PROTECTED`, `HAS_OWNER` and `HAS_SOURCE`.

  Update `backend/infrahub/core/node/__init__.py::Node.delete` only where the call needs new arguments. Depends on T062.
- [ ] T076 [US5] Run T064-T067, plus:
  - `backend/tests/component/core/test_node_manager_delete.py`
  - `backend/tests/component/core/relationship/`
  - `backend/tests/component/core/test_relationship_query.py`
  - `backend/tests/component/core/test_node_query.py`
  - `backend/tests/component/core/agnostic_retirement/`
  - `backend/tests/component/core/test_branch_merge.py`
  - `backend/tests/component/core/test_branch_rebase.py`
  - `backend/tests/component/graphql/`

  All pass.

### Measurement, documentation and delivery

- [ ] T079 [US5] Add `backend/tests/benchmark/test_peer_existence_check.py` with three reads:
  - a list of `CoreTransformPython` with `repository`;
  - `CoreStandardGroup.members` with 5,000 members;
  - a branch-aware relationship between branch-aware kinds.

  Record the database hits before and after in the PR description. The third read must not change (SC-004).
- [ ] T080 [US5] Update `dev/knowledge/backend/database-schema.md`, next to the paragraph on retirement:
  - the peer existence check, and that it applies only to branch-aware relationships whose peer kind is branch-agnostic or a generic with a branch-agnostic implementation;
  - that a branch-agnostic node's delete writes no `-global-` edge on its branch-aware links;
  - the "Soft Deletes" correction that follows from T062.
- [ ] T082 [P] [US5] Add changelog fragments:
  - `fixed`: reading the groups of a role after a group was deleted no longer fails, and relationships no longer return a node deleted in the read's branch;
  - `fixed`: validating an object conversion no longer counts former peers.
- [ ] T083 [US5] Run the pre-push checks in `quickstart.md`, including `uv run invoke docs.validate`, and open the PR against the feature branch. The description states the T063 table, the answer to open question 2, and the benchmark results.

**Checkpoint**: US5 is complete. US6 can start.

---

## Phase 8: User Story 6 - Branch-agnostic relationships return every live peer, with values from one branch (Priority: P2) — PR 6

**Goal**:

- the window rule for peers (FR-028);
- one branch per node for values (FR-029);
- the node object's branch (FR-030);
- adding and saving links (FR-031, FR-032);
- list queries (FR-033, FR-034);
- the window form of filters and HFID lookup (FR-038, FR-039);
- from User Story 5: no branch edge on a branch-agnostic relationship when a branch-aware node is deleted (FR-023), and migration `m083`, which converts shape 1 pairs and removes shape 2 edges (FR-024 to FR-026), after the read changes (research R13).

**Independent Test**: gadget G is linked to widget W through a branch-agnostic relationship and deleted on B. Reading W's gadgets on the default branch returns G. After G is renamed on B, the default branch's read shows the default branch's name.

**Base**: PR 5's branch. It merges into the feature branch. Branch: `agnostic-relationship-reads-ifc-3508`.

- [ ] T084 [US6] Create a worktree for `agnostic-relationship-reads-ifc-3508` from `peer-existence-check-ifc-3508`.
- [ ] T085 [US6] Gate for open question 3:
  - Search the callers of `get_peers`, `query_peers`, `get_many`, `get_one` and `get_one_by_id_or_default_filter` with `branch_agnostic=True` for a node object that is changed and saved (research R9 lists the known ones).
  - Add `test_validator_read_branch_agnostic_still_saves_on_global` to `backend/tests/component/core/integrity/`. It builds a `CoreValidator` through `ObjectConflictValidatorRecorder.get_validator` on a user branch and checks that its save writes on `-global-`.
  - Report the findings to the user, and stop. T092 depends on the answer.
- [ ] T061 [US6] Gate for open question 1:
  - Add `test_merge_does_not_copy_branch_deleted_edge_of_agnostic_relationship` to `backend/tests/component/core/agnostic_retirement/test_on_merge.py`. On branch B, delete a branch-aware node that has a branch-agnostic relationship, merge B, and assert that the default branch has no `deleted` `IS_RELATED` edge for that link.
  - Write a read-only Cypher count of default-branch `deleted` edges on branch-agnostic links that have a user-branch `deleted` edge with an earlier `from` (research R8), and run it on any available copy of a real database.
  - Report both results to the user, and stop. Continue with T128 and T130 only after the user confirms how shape 2 handles default-branch copies.

### Tests for User Story 6

- [ ] T086 [P] [US6] Move the 13 tests of `branch-agnostic-wip/audit-tests/test_audit_branch_agnostic_node_reads.py` into `backend/tests/component/core/test_branch_agnostic_reads.py`. Where an assertion assumed a rule the brief did not choose, change it to the brief's rule (request branch, then default branch, then the others by name) and record each change in the PR description. Confirm they fail.
- [ ] T087 [P] [US6] Move the remaining failing tests of `test_audit_branch_agnostic_relationship_reads.py` (peers, saves, `NodeNotFoundError` on adding a link) into `backend/tests/component/core/relationship/test_branch_agnostic_relationship_reads.py`, keeping its 4 controls. Confirm the failing ones fail.
- [ ] T088 [P] [US6] Bring the following from `git show 7015435c4:backend/tests/component/core/test_reads_by_value_on_branch.py` into `backend/tests/component/core/test_branch_agnostic_reads.py`:
  - `TestBranchAgnosticLookupByHFID`
  - `TestBranchAgnosticPeerFilter`
  - `test_branch_agnostic_filter_through_the_parent_relationship`
  - the helpers `BranchDataset` and `_update`

  Use `backend/tests/helpers/schema/agnostic_retirement.py`. Keep PR #11220's tests `test_branch_agnostic_lookup_by_hfid_finds_the_default_branch_value` and `test_branch_agnostic_filter_finds_the_default_branch_value` passing.
- [ ] T089 [P] [US6] Add tests to `backend/tests/component/core/test_branch_agnostic_reads.py` for:
  - spec US6 scenario 4 (a node that exists only on two older branches takes all values from the first by name);
  - scenario 6 (the `roles` of a branch-agnostic node read through a branch-agnostic read are the request branch's);
  - scenario 10;
  - the output of `backend/infrahub/pools/number_pool_usage_nodes.py::PeerSummaryReader.read` when a node's display label differs between branches.
- [ ] T126 [P] [US6] Add `backend/tests/component/core/relationship/test_delete_on_branch_agnostic_relationship.py` with:
  - spec US5 scenario 3: deleting a branch-aware node on B writes no edge on B for its branch-agnostic relationship, and the `-global-` link stays open while the default branch holds the node;
  - a GraphQL read, on the default branch and on B, of a pool's `resources` with `properties` requested, where a prefix was deleted on B only. It returns the prefix with the default branch's values and no error (spec Clarifications, 2026-10-30);
  - the same read after the prefix is also deleted on the default branch returns nothing, because the retirement check closed the link.

  Confirm the first test fails (B still gets a `deleted` edge).

### Implementation for User Story 6

- [ ] T090 [US6] Add `render_window_choice` to `backend/infrahub/core/query/branch_windows.py` (contract "Choosing one window per node"), and its unit test to `backend/tests/unit/core/query/test_branch_windows.py`.
- [ ] T091 [US6] In `backend/infrahub/core/query/node.py::NodeListGetInfoQuery`, in branch-agnostic mode:
  - open with the windows clause;
  - choose the first window, in the order of FR-029, in which the node's latest `IS_PART_OF` is `active`;
  - return that window with each row, and drop nodes with no window.

  Use the same window for the metadata subqueries.
- [ ] T092 [US6] In `backend/infrahub/core/manager.py::NodeManager.get_many`:
  - build each node object on its chosen branch;
  - pass a `node_windows` map (data-model.md) to `NodeListGetAttributeQuery` and `NodeListGetRelationshipsQuery`;
  - pass `branch_agnostic` and the windows to the `get_many` call for missing peers in `_enrich_node_dicts_with_relationships`.

  Depends on T085.
- [ ] T093 [US6] In `backend/infrahub/core/query/node.py::NodeListGetAttributeQuery`, when `node_windows` is given:
  - add `WITH n, $node_windows[n.uuid] AS window` after the node match;
  - use `render_window_filter(edge="r", window="window")` in every ranked `CALL` (`HAS_ATTRIBUTE`, `HAS_VALUE`, `IS_PROTECTED`, source, owner, profile), keeping the `ORDER BY branch_level DESC, from DESC LIMIT 1`;
  - use the window in the `created_at` and `updated_at` subqueries.
- [ ] T094 [US6] Apply T093 to `NodeListGetRelationshipsQuery` in `backend/infrahub/core/query/node.py`. Also rank `r1` and `r2` by `branch_level` before `from`, and render the existence check inside the window.
- [ ] T095 [US6] In `backend/infrahub/core/query/relationship.py::RelationshipGetPeerQuery`, in branch-agnostic mode:
  - keep a peer when in some window both link edges and the peer's `IS_PART_OF` are latest and active (the count follows);
  - choose each peer's window as in T091 for ordering, through `_emit_peer_order_entries`;
  - remove the `WHEN $is_branch_agnostic` arms that can never be reached.
- [ ] T096 [US6] Bring the window form of `build_subquery_filter` from `48789ecad`/`7015435c4` into `backend/infrahub/core/query/subquery.py`, used only when `branch_agnostic` is true, on top of PR #11220's single-branch query, which stays unchanged (FR-039). Pass `branch_windows` through `NodeGetListQuery.query_init` in `backend/infrahub/core/query/node.py` and through `RelationshipGetPeerQuery.query_init`.
- [ ] T097 [US6] In `backend/infrahub/core/query/subquery.py`, read `build_subquery_order` and `build_subquery_order_metadata` inside the node's chosen window when the query is branch-agnostic.
- [ ] T098 [US6] In `backend/infrahub/core/query/node.py::NodeGetListQuery.query_init`, in branch-agnostic mode, replace the top-level `IS_PART_OF` match on every branch with the window check, and return each node once (FR-033).
- [ ] T099 [US6] Bring `NodeGetByHFIDQuery._build_branch_agnostic_query` (flat form) from `7015435c4` into `backend/infrahub/core/query/node.py`, on top of PR #11220's version (FR-038).
- [ ] T100 [US6] In `backend/infrahub/core/relationship/model.py`:
  - check that `Relationship._get_peer` now finds a peer that exists on any live branch and raises `NodeNotFoundError` only when none does (FR-031);
  - check that `RelationshipManager.save` → `refresh_update_details` → `get_db_peers` finds a peer deleted on another branch and closes its `-global-` link when replaced (FR-032).

  Change the code where either check fails.
- [ ] T101 [US6] Update the expected results of the existing branch-agnostic tests that the decisions change, and record each change in the PR description:
  - `backend/tests/component/core/test_node_query.py::test_query_NodeListGetAttributeQuery_branch_agnostic`
  - `test_node_query.py::test_query_NodeListGetRelationshipsQuery_branch_agnostic`
  - `backend/tests/component/core/test_relationship_query.py::test_query_RelationshipGetPeerQuery_branch_agnostic`
  - `backend/tests/component/core/test_manager_node.py::test_get_many_branch_agnostic`
  - `backend/tests/component/core/test_node_get_list_query.py::test_query_NodeGetListQuery_metadata_branch_agnostic`
- [ ] T127 [US6] List every caller under `backend/infrahub/` that reads the peers of a branch-agnostic relationship and then loads a peer on the request branch (start from T063's table and `rg -n "get_peers|get_peer\(|query_peers|GetAllPeersIds" backend/infrahub`). For each, check that it handles a peer that does not exist on the request branch, or change it. Append the table to research R13 and to the PR description.
- [ ] T128 [US6] Add the migration tests under `backend/tests/component/core/migrations/graph/m083_separate_global_and_branch_link_edges/` (`conftest.py`, `test_migration.py`, `test_resume.py`), following `m081_reanchor_number_pool_reservations`:
  - build shape 1 pairs, shape 2 pairs on the default branch and on a user branch, and one pair of another shape, through the old write paths, before T075 and T129;
  - read at several timestamps before and after, through the reads of T091-T095;
  - assert that no shape 1 or shape 2 pair is left and that the other pair is unchanged and logged;
  - run the migration twice.

  Depends on T061 and T062.
- [ ] T129 [US6] In `backend/infrahub/core/query/relationship.py::RelationshipDeleteAllQuery`, for a branch-aware node, process only links whose `Relationship` vertex has `branch_support = "aware"`, on any branch including the default branch, so its branch-agnostic relationships get no branch edge (FR-023). `RetireNodeAgnosticFieldsQuery` already closes their `-global-` link once no live branch holds both ends. Depends on T091-T095 and T127.
- [ ] T130 [US6] Add `backend/infrahub/core/migrations/graph/m083_separate_global_and_branch_link_edges/` (`__init__.py`, `migration.py`, `queries.py`): an `ArbitraryMigration` with `minimum_version = 82` and the three steps of research R8, using data-model.md's shape rules, with shape 2 as T061 decided for default-branch edges. Batch with `CALL {…} IN TRANSACTIONS`. Set `GRAPH_VERSION` to 83 in `backend/infrahub/core/graph/__init__.py`, after checking the latest number on `release-1.12`. Run T128.
- [ ] T102 [US6] Run T061, T085-T090, T126 and T128, and:
  - `backend/tests/component/core/`
  - `backend/tests/component/graphql/`
  - `backend/tests/component/pools/`
  - `backend/tests/unit/core/query/`
  - `backend/tests/component/core/agnostic_retirement/`
  - `backend/tests/component/core/test_branch_merge.py`
  - `backend/tests/component/core/test_branch_rebase.py`

  All pass.
- [ ] T103 [US6] Run `backend/tests/benchmark/test_node_list_filter.py` (filters on one branch must match PR #11220's cost, FR-039), and add a branch-agnostic read with 50 live branches to `backend/tests/benchmark/test_peer_existence_check.py`. Record before and after in the PR description.
- [ ] T104 [P] [US6] Update `docs/docs/branches/branch-agnostic-data.mdx`: a branch-agnostic relationship returns every peer that exists on a live branch, including on a branch that deleted the peer, and each peer shows the values of one branch, in the order of FR-029. Replace the part that describes what happens to a branch-agnostic relationship when a node is deleted on a branch. Run `uv run invoke docs.lint`.
- [ ] T131 [P] [US6] Update `dev/knowledge/backend/database-schema.md`, next to the text T080 added: the rule that no pair of vertices holds both a `-global-` edge and a branch edge of the same type (FR-024), and that a branch-agnostic relationship has no branch edges.
- [ ] T105 [P] [US6] Add a `fixed` changelog fragment: branch-agnostic relationships, such as IP pool resources and validator definitions, return peers that exist on any open branch with consistent values, and adding such a link no longer fails when the peer was deleted on another branch. A node deleted on one branch stays a peer of a branch-agnostic relationship until it is deleted on every branch. Add an upgrade note: migration `m083` is one-way.
- [ ] T106 [US6] Run the pre-push checks in `quickstart.md`, including `uv run invoke docs.validate`, and open the PR against the feature branch. The description states the hard-delete exception of `m083` and its reason (plan.md "Complexity Tracking"), the answers to open questions 1 and 3, the T127 table and the benchmark results.
- [ ] T132 [US6] Once PRs 5 and 6 are merged into the feature branch, merge `origin/release-1.12` into it, run the pre-push checks in `quickstart.md` and the suites of T076 and T102, and open the PR from the feature branch against `release-1.12`. Its description links PRs 5 and 6 and repeats the hard-delete exception of `m083`.

**Checkpoint**: all six stories are complete.

---

## Phase 9: User Story 6, part 2 - Peers read through a branch-agnostic relationship report the branches they exist on (Priority: P2) — PR 7

**Goal**: a GraphQL read of a branch-agnostic relationship can request `node_metadata { active_on_branches }`. For each peer it returns the names of the live branches on which the peer exists, sorted by name. The field is `null` for every other node, and a query that does not request it keeps its database hits (FR-041, FR-042).

**Independent Test**: link prefix X to pool P's `resources` on the default branch, create branch B, and delete X on B. Read P's `resources` on B with `node_metadata { active_on_branches }`: X is returned, and the list holds the default branch's name and not B.

**Base**: PR 6's branch, rebased on `release-1.12` once the feature branch merges. Branch: `active-on-branches-ifc-3508`. This PR changes the GraphQL schema. The user approved the change on 2026-10-30 (spec Clarifications).

### Setup for PR 7

- [ ] T110 [US6] Once PR 6 is in review, create a worktree for `active-on-branches-ifc-3508` from PR 6's branch. Check that:
  - `backend/infrahub/core/query/branch_windows.py` provides `build_branch_windows_query` and `render_window_filter` as `contracts/branch-window-helpers.md` describes;
  - `ManyRelationshipResolver` in `backend/infrahub/graphql/resolvers/many_relationship.py` and `SingleRelationshipResolver` in `backend/infrahub/graphql/resolvers/single_relationship.py` still pass `branch_agnostic=rel_schema.branch is BranchSupportType.AGNOSTIC` to `NodeManager.query_peers` and to the data loader.

### Tests for PR 7

- [ ] T111 [P] [US6] Add `backend/tests/component/graphql/metadata/test_active_on_branches.py`. Build the data with the schema of `backend/tests/helpers/schema/agnostic_retirement.py` (the branch-agnostic cardinality-one relationship `gadget`), the cardinality-many relationship of `backend/tests/component/conftest.py::branch_aware_node_with_agnostic_attrs_schema`, and a pool's `resources`. Cover:
  - spec US6 scenario 11: a peer deleted on B that exists on the default branch, read on B, is returned with the default branch's name only;
  - a peer that exists on the default branch and on B lists both names, sorted by name;
  - a peer created on B only, read on the default branch, lists B only;
  - a branch whose status is `DELETING` is not listed;
  - a cardinality-one and a cardinality-many relationship, and for the cardinality-many relationship both resolver paths, the one through the data loader and the one without it (`ManyRelationshipResolver.resolve` selects between them);
  - spec US6 scenario 12: `active_on_branches` on a peer of a relationship that is not branch-agnostic, and on the `node_metadata` of a top-level list query, is `null`.

  Confirm the tests fail on PR 6's branch because the field does not exist.
- [ ] T112 [P] [US6] Add `backend/tests/component/graphql/metadata/test_active_on_branches_cost.py`, using `CountingInfrahubDatabase` from `backend/tests/helpers/db_query_counter.py`:
  - a read of a pool's `resources` that does not request `active_on_branches` runs the same queries, by name and count, as on PR 6's branch, and runs `NodeActiveBranchesQuery` zero times (FR-042);
  - the same read with the field requested runs `NodeActiveBranchesQuery` once per resolver call, not once per peer.
- [ ] T113 [P] [US6] Add `backend/tests/component/core/query/test_node_active_branches.py` for `NodeActiveBranchesQuery`. Cover the cases of T111 at the query level, plus a node whose uuid has several `Node` vertices after a kind migration (see the docstring of `backend/infrahub/core/query/agnostic_retention.py`): it returns one list per uuid.
- [ ] T114 [P] [US6] Add `backend/tests/unit/graphql/test_metadata_options.py`. `get_metadata_options_from_fields` sets `MetadataOptions.ACTIVE_ON_BRANCHES` when `active_on_branches` is in the fields, and not otherwise; the other options are unchanged.

### Implementation for PR 7

- [ ] T115 [US6] Add `ACTIVE_ON_BRANCHES = auto()` to `MetadataOptions` in `backend/infrahub/core/constants/__init__.py`, without adding it to `TIMESTAMPS`, `USERS` or `USER_TIMESTAMPS`. In `backend/infrahub/graphql/metadata.py::get_metadata_options_from_fields`, set it when `active_on_branches` is in the fields.
- [ ] T116 [US6] Add `backend/infrahub/core/query/node_active_branches.py` with `NodeActiveBranchesQuery(node_ids, at)`, a read query that:
  - opens with `build_branch_windows_query(at=..., enabled=True)`;
  - for each node uuid and each window, takes the node's latest `IS_PART_OF` edge in the window with `render_window_filter`, ranked `branch_level DESC, from DESC, status ASC`, and keeps the window's name when that edge is `active`;
  - uses the same definition of a live node as the retirement check (FR-019);
  - returns one row per node uuid with the names sorted.

  Its `get_data()` returns a frozen dataclass that maps each node uuid to a `list[str]` (constitution III).
- [ ] T117 [US6] In `backend/infrahub/graphql/manager.py::define_node_metadata`, add `active_on_branches` to `InfrahubNodeMetadata` as a list of non-null strings that is not required, with a description that it is filled only for nodes read through a branch-agnostic relationship. In `backend/infrahub/core/node/__init__.py::Node._build_meta_response`, return `None` for `active_on_branches`, so every node outside T118's path returns `null`.
- [ ] T118 [US6] In `ManyRelationshipResolver` and `SingleRelationshipResolver`, when the relationship's branch support is `agnostic` and `node_metadata` requests `active_on_branches`:
  - after the peers are loaded, run `NodeActiveBranchesQuery` once for all peer uuids of the call, on both the data loader path and the path without it;
  - write each peer's list into its `node_metadata` response.

  When the field is not requested, run nothing (FR-042).
- [ ] T119 [US6] List the other GraphQL reads that return nodes read across branches (`rg -n "branch_agnostic=True" backend/infrahub/graphql`), including `backend/infrahub/graphql/queries/resource_manager.py`. For each one whose response has `node_metadata`, fill `active_on_branches` as T118 does, or state in the PR description why it returns `null`. Then check whether `python_sdk` holds a typed copy of `InfrahubNodeMetadata` (`rg -n InfrahubNodeMetadata python_sdk`). If it does, stop and ask the user, because a change to the submodule needs its own PR first (AGENTS.md "Submodules").
- [ ] T120 [US6] Regenerate the generated files and commit them: `uv run invoke schema.generate-graphqlschema` (updates `schema/schema.graphql`), then `cd frontend/app && pnpm codegen`.
- [ ] T121 [US6] Run T111-T114, plus:
  - `backend/tests/component/graphql/metadata/`
  - `backend/tests/component/graphql/resolvers/`
  - `backend/tests/component/graphql/test_graphql_query.py`
  - `backend/tests/component/graphql/test_graphql_read_rel_query.py`
  - `backend/tests/unit/graphql/`

  All pass.

### Measurement, documentation and delivery for PR 7

- [ ] T122 [US6] Add a case to `backend/tests/benchmark/test_graphql_query.py`: a read of a pool's `resources` with many peers and many live branches, with and without `active_on_branches`. Report the database hits of both, measured with `PROFILE`, in the PR description (FR-036). Without the field, the hits match PR 6's branch.
- [ ] T123 [P] [US6] Update `docs/docs/branches/branch-agnostic-data.mdx` with `node_metadata { active_on_branches }`: what it lists, when it is `null`, and a query example on a pool's `resources`. Run `uv run invoke docs.lint`.
- [ ] T124 [P] [US6] Add an `added` changelog fragment with the `creating-changelog-entries` skill. It says that a read of a branch-agnostic relationship, such as a pool's `resources`, can request `node_metadata { active_on_branches }` to view on which branches each peer exists.
- [ ] T125 [US6] Run the pre-push checks in `quickstart.md`, and open the PR against `release-1.12` once the feature branch has merged (T132).

**Checkpoint**: all six stories and PR 7 are complete.

---

## Phase 10: Polish and cross-cutting checks

- [ ] T107 Once all six PRs are merged, run every audit test file from `branch-agnostic-wip/audit-tests/` against `origin/release-1.12`, and record in `dev/specs/ifc-3508-branch-agnostic-reads/quickstart.md` that SC-001 to SC-003 hold, listing any assertion changed and why.
- [ ] T108 Update "Delivery by PR" in `dev/specs/ifc-3508-branch-agnostic-reads/plan.md` with the seven PR numbers and their merge commits.
- [ ] T109 Grep `dev/specs/ifc-3508-branch-agnostic-reads/` for any figure or decision that a PR changed (for example an error class, a migration number or an open question's answer), and update every file that repeats it in the same commit.

---

## Dependencies & Execution Order

### Phase dependencies

- Setup (T001-T002): no dependency.
- US1 (PR 1): depends only on T001. Based on `stable`.
- US2 (PR 2): no dependency.
- US3 (PR 3): no dependency. It blocks US4, US5 and US6.
- US4 (PR 4): depends on US3.
- US5 (PR 5): depends on US3 merged and PR #11220 in `release-1.12` (T002, T060). It merges into the feature branch, not into `release-1.12`. Its gate T062 blocks T075, T080, T128 and T130.
- US6 (PR 6): depends on US5. It merges into the feature branch. Its gate T085 blocks T092, and its gate T061 blocks T128 and T130. T129 and T130 come after T091-T095 (research R13). T132 merges the feature branch into `release-1.12` after PRs 5 and 6.
- US6 part 2 (PR 7): depends on PR 6, and opens against `release-1.12` after T132 (T110-T125). Its gate T119 applies only when `python_sdk` holds a typed copy of `InfrahubNodeMetadata`.
- Polish (T107-T109): after all PRs merge.

### Within each story

- Tests first: confirm they fail, then implement.
- The windows helper (T034) comes before every query that uses it.
- Benchmarks run on the base branch before the change and again after it.
- Documentation and changelog tasks marked [P] can run alongside the implementation.

### Parallel opportunities

- US1, US2 and US3 can be developed at the same time by different people. They use different base branches or different files.
- Inside US1: T004-T007 together, then T009 and T010 together.
- Inside US2: T018-T023 together.
- Inside US3: T029-T033 together; T035 alongside T036-T038; T047-T049 alongside T039-T044.
- Inside US5: T064-T067 together.
- Inside US6: T086-T089 and T126 together; T104, T105 and T131 alongside the implementation.
- Inside PR 7: T111-T114 together; T123 and T124 alongside T115-T121.

## Parallel Example: User Story 3

```text
Task: "T029 Bring test_node_list_filter.py benchmark from 7015435c4"
Task: "T030 Add test_ip_pool_allocation.py benchmark"
Task: "T031 Move the IP pool and number pool audit tests"
Task: "T032 Add allocation-on-branch tests"
Task: "T033 Pin number pool query results"
```

## Implementation Strategy

### First delivery

US1 (PR 1) and US3 (PR 3) close the effects users are most likely to hit: a privilege escalation, and duplicate IP allocations. They do not wait for PR #11220. Ship them first, and US2 alongside.

### Incremental delivery

1. US1, US2 and US3 in parallel. Each is reviewed and merged on its own.
2. US4 once US3 is merged.
3. US5 once PR #11220 is in `release-1.12`, after its gates are answered, into the feature branch.
4. US6 on top of US5, into the feature branch. The feature branch then merges into `release-1.12` (T132).
5. PR 7 on top of PR 6.

Each PR adds value on its own and leaves no read worse than before. PRs 5 and 6 reach `release-1.12` together through the feature branch. That is why the peer existence check and the delete writes for a branch-agnostic node ship together in US5, and why the delete writes for a branch-aware node (FR-023) and migration `m083` ship in PR 6, after its read changes (research R13).

## Notes

- Cite symbols, not line numbers, in code, commits and PR descriptions.
- Commit after each task or logical group, on the PR's own branch, not on `branch-agnostic-reads`.
- Every PR description reports database hits before and after for the paths it changes, or states that it changes no query.
- Stop at every gate. Do not choose an answer to an open question without the user.
