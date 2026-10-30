# Tasks: Branch-Agnostic Reads That Return the Right Branch's Data

**Input**: Design documents from `dev/specs/ifc-3508-branch-agnostic-reads/` ([plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md))

**Jira**: [IFC-3508](https://opsmill.atlassian.net/browse/IFC-3508)

**Tests**: required. FR-035 requires, for every PR, a component test that fails on the current code and passes with the fix.

**Organization**: one phase per user story, and each user story is one PR. Phases follow the PR order in the brief, not the priority order, because the PRs depend on each other (see Dependencies). US1 (P1) and US3 (P1) ship first. US2 (P3) is small and independent.

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

- T061 (open question 1, PR 5)
- T062 (open question 2, PR 5)
- T085 (open question 3, PR 6)
- T014 (the E2E test exception, PR 1)

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
- [ ] T012 [P] [US1] Update `docs/docs/deploy-manage/user-management/permissions-roles/overview.mdx`: global permissions, group memberships and roles take effect from the default branch, and a change made on a branch applies only after the branch is merged. Object permissions follow the request branch. Run `uv run invoke docs.lint`.
- [ ] T013 [P] [US1] Add a `fixed` changelog fragment in `changelog/` with the `creating-changelog-entries` skill. It says that a change made on a branch to group membership, roles or global permissions no longer changes global permissions until the branch is merged.
- [X] T014 [US1] Gate: ask the reviewer whether the E2E exception in `plan.md` "Complexity Tracking" is approved. If it is not, add one E2E test under `tests/e2e/` for scenario 1 of US1. Result: the user approved the exception on 2026-10-30; no E2E test is added.
- [ ] T015 [US1] Run the pre-push checks in `quickstart.md`, open the PR against `stable`, and report that this PR changes no query (no benchmark needed). How the PR is disclosed is decided outside this plan.

**Checkpoint**: US1 is complete and reviewable on its own.

---

## Phase 4: User Story 2 - Reads of `-global-` data leave the branch-agnostic path (Priority: P3) — PR 2

**Goal**: callers that read only `-global-` data stop passing `branch_agnostic=True`, with unchanged results (FR-005).

**Independent Test**: the existing tests of each changed caller pass unchanged.

**Base**: `origin/release-1.12`. Branch: `global-only-reads-ifc-3508`.

- [ ] T016 [US2] Create a worktree for `global-only-reads-ifc-3508` from `origin/release-1.12`.
- [ ] T017 [US2] Classify the callers research R3 found outside the brief:
  - `backend/infrahub/pools/number_pool_repository.py` (3 calls)
  - `backend/infrahub/pools/number_pool_lookup.py`
  - `backend/infrahub/pools/scoped_number_pool_reader.py` (2 calls)
  - `backend/infrahub/core/migrations/graph/m080_number_pool_ranges/migration.py`

  For each call, check the branch support of the kind it reads and of every relationship it follows, for example `CoreNumberPoolRange.pool`, in `backend/infrahub/core/schema/definitions/`. Record the result in the PR description. Only calls verified as reading `-global-` data are changed in T024. `m080` is a shipped migration and is not edited.
- [ ] T018 [P] [US2] Remove `branch_agnostic=True` from the `get_many` call in `backend/infrahub/graphql/loaders/account.py`, and remove its comment.
- [ ] T019 [P] [US2] Remove `branch_agnostic=True` from `NodeManager.query` in `backend/infrahub/graphql/resolvers/resolver.py::is_externally_managed_resolver`.
- [ ] T020 [P] [US2] Remove `branch_agnostic=True` from `NodeManager.query` in `backend/infrahub/webhook/tasks/invalidate.py`.
- [ ] T021 [P] [US2] Remove `branch_agnostic=True` from all three calls in `backend/infrahub/pools/schema_number_pool_synchronizer.py`.
- [ ] T022 [P] [US2] Remove `branch_agnostic=True` from all three calls in `backend/infrahub/pools/schema_number_pool_upserter.py`.
- [ ] T023 [P] [US2] Remove `branch_agnostic=True` from `proposed_change.validations.get_peers` in `backend/infrahub/core/integrity/object_conflict/conflict_recorder.py::ObjectConflictValidatorRecorder.get_validator`.
- [ ] T024 [US2] Apply the same change to the calls T017 verified.
- [ ] T025 [US2] Check whether `GetGlobalPermissionAttributesQuery` in `backend/infrahub/core/migrations/graph/m062_recompute_permission_display_labels.py` reads the `branch_agnostic` argument. If it ignores the argument, remove it from both calls as a no-op and say so in the PR. If it does not ignore it, leave the shipped migration unchanged and record why.
- [ ] T026 [US2] Run the tests of each changed caller:
  - `backend/tests/component/graphql/`, filtered with `-k account`
  - `backend/tests/component/webhook/`
  - `backend/tests/component/pools/`
  - `backend/tests/component/core/resource_manager/`
  - `backend/tests/component/core/integrity/`
  - `backend/tests/component/core/migrations/graph/`, filtered with `-k m062`

  All pass unchanged.
- [ ] T027 [US2] Run the pre-push checks in `quickstart.md` and open the PR against `release-1.12`. Add no changelog fragment, because no user can notice the change.

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
- the new delete writes and ranking (FR-021 to FR-023);
- the migration (FR-024 to FR-026);
- the object conversion peer list (FR-040);
- the documentation (FR-027).

**Independent Test**: a role is linked to group G1 on the default branch; B is created; the role is removed from G1 on the default branch; G1 is deleted. Reading the role's groups on either branch does not return G1 and raises no error.

**Base**: `origin/release-1.12`, after PR 3 and PR #11220 are in it. Branch: `peer-existence-check-ifc-3508`.

### Gates and inventory

- [ ] T060 [US5] Confirm PR 3 and PR #11220 are merged into `origin/release-1.12` (see T002). Then create a worktree for `peer-existence-check-ifc-3508` from it.
- [ ] T061 [US5] Gate for open question 1:
  - Add `test_merge_does_not_copy_branch_deleted_edge_of_agnostic_relationship` to `backend/tests/component/core/agnostic_retirement/test_on_merge.py`. On branch B, delete a branch-aware node that has a branch-agnostic relationship, merge B, and assert that the default branch has no `deleted` `IS_RELATED` edge for that link.
  - Write a read-only Cypher count of default-branch `deleted` edges on branch-agnostic links that have a user-branch `deleted` edge with an earlier `from` (research R8), and run it on any available copy of a real database.
  - Report both results to the user, and stop. Continue with T077 only after the user confirms how shape 2 handles default-branch copies.
- [ ] T062 [US5] Gate for open question 2: present research R7's evidence and recommendation (on the default branch, set `to` and write a `deleted` edge with the same `from`, as every user delete does) to the user, and stop. Record the answer under "Open Questions" in `spec.md` and in research R7. T075, T077, T078 and T080 depend on it.
- [ ] T063 [US5] List every query under `backend/infrahub/` that reads `IS_RELATED` (`rg -l IS_RELATED backend/infrahub`). For each, record whether it can read a branch-agnostic relationship or a relationship to a branch-agnostic kind, and whether it needs the check, in a table appended to `research.md` R6. Include `RelationshipCountPerNodeQuery`, the targeted uniqueness validation query, `DependentNodesQuery` and `backend/infrahub/core/validators/relationship/count.py`.

### Tests for User Story 5

- [ ] T064 [P] [US5] Add `backend/tests/unit/core/schema/test_peer_existence_check.py` for `needs_peer_existence_check`. Cover:
  - a branch-agnostic relationship;
  - a branch-agnostic peer node;
  - a generic with one branch-agnostic implementation;
  - a generic with only branch-aware implementations;
  - a branch-aware relationship between branch-aware nodes.
- [ ] T065 [P] [US5] Move `test_deleting_group_removes_it_from_role_after_role_removed_on_branch` and `test_graphql_role_groups_after_group_deleted_with_role_removed_on_branch` from `branch-agnostic-wip/audit-tests/test_audit_branch_agnostic_relationship_reads.py` into `backend/tests/component/core/relationship/test_peer_existence.py`. Add tests for:
  - spec US5 scenarios 1-4 and 8-10;
  - the brief's two new PR 5 tests: a branch-agnostic node deleted after branching with the link removed on the default branch after branching, and a filter through a pool's `resources` on a branch where the prefix is deleted;
  - a GraphQL read, on the default branch and on B, of a pool's `resources` with `properties` requested, where a prefix was deleted on B. It must return no error. Without the branch edges PR 5 stops writing, `NodeManager.get_many` could drop the peer and raise a `KeyError` before PR 6 lands.

  Confirm the tests that check today's wrong results fail. If the GraphQL read fails after T069 and T075, bring the window check on `IS_PART_OF` from T091 into this PR, so no read is worse after PR 5 alone.
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
  - for a branch-aware node, process only links with `branch_support = "aware"`, on any branch including the default branch;
  - for a branch-agnostic node, close the default branch's edge as T062 decided, write a `deleted` edge on each live user branch whose own latest edge is `active`, and write nothing on `-global-`;
  - apply the same rules to `IS_PROTECTED`, `HAS_OWNER` and `HAS_SOURCE`.

  Update `backend/infrahub/core/node/__init__.py::Node.delete` only where the call needs new arguments. Depends on T062.
- [ ] T076 [US5] Run T061 and T064-T067, plus:
  - `backend/tests/component/core/test_node_manager_delete.py`
  - `backend/tests/component/core/relationship/`
  - `backend/tests/component/core/test_relationship_query.py`
  - `backend/tests/component/core/test_node_query.py`
  - `backend/tests/component/core/agnostic_retirement/`
  - `backend/tests/component/core/test_branch_merge.py`
  - `backend/tests/component/core/test_branch_rebase.py`
  - `backend/tests/component/graphql/`

  All pass.

### Migration for User Story 5

- [ ] T077 [US5] Add the migration tests under `backend/tests/component/core/migrations/graph/m083_separate_global_and_branch_link_edges/` (`conftest.py`, `test_migration.py`, `test_resume.py`), following `m081_reanchor_number_pool_reservations`:
  - build shape 1, shape 2 and one pair of another shape through the old write path, before T075;
  - read at several timestamps before and after;
  - assert that no shape 1 or shape 2 pair is left and that the other pair is unchanged and logged;
  - run the migration twice.

  Depends on T061 and T062.
- [ ] T078 [US5] Add `backend/infrahub/core/migrations/graph/m083_separate_global_and_branch_link_edges/` (`__init__.py`, `migration.py`, `queries.py`): an `ArbitraryMigration` with `minimum_version = 82` and the three steps of research R8, using data-model.md's shape rules. Batch with `CALL {…} IN TRANSACTIONS`. Set `GRAPH_VERSION` to 83 in `backend/infrahub/core/graph/__init__.py`, after checking the latest number on the base branch. Run T077.

### Measurement, documentation and delivery

- [ ] T079 [US5] Add `backend/tests/benchmark/test_peer_existence_check.py` with three reads:
  - a list of `CoreTransformPython` with `repository`;
  - `CoreStandardGroup.members` with 5,000 members;
  - a branch-aware relationship between branch-aware kinds.

  Record the database hits before and after in the PR description. The third read must not change (SC-004).
- [ ] T080 [US5] Update `dev/knowledge/backend/database-schema.md`, next to the paragraph on retirement:
  - the rule that no pair of vertices holds both a `-global-` edge and a branch edge of the same type;
  - the peer existence check;
  - that a branch-agnostic relationship has no branch edges;
  - the "Soft Deletes" correction that follows from T062.
- [ ] T081 [P] [US5] Update `docs/docs/branches/branch-agnostic-data.mdx` where it describes what happens to a branch-agnostic relationship when a node is deleted on a branch. Run `uv run invoke docs.lint`.
- [ ] T082 [P] [US5] Add changelog fragments:
  - `fixed`: reading the groups of a role after a group was deleted no longer fails, and relationships no longer return a node deleted in the read's branch;
  - `fixed`: validating an object conversion no longer counts former peers;
  - an upgrade note: migration `m083` is one-way.
- [ ] T083 [US5] Run the pre-push checks in `quickstart.md`, including `uv run invoke docs.validate`, and open the PR against `release-1.12`. The description states the hard-delete exception and its reason (plan.md "Complexity Tracking"), the T063 table, the answers to open questions 1 and 2, and the benchmark results.

**Checkpoint**: US5 is complete. US6 can start.

---

## Phase 8: User Story 6 - Branch-agnostic relationships return every live peer, with values from one branch (Priority: P2) — PR 6

**Goal**:

- the window rule for peers (FR-028);
- one branch per node for values (FR-029);
- the node object's branch (FR-030);
- adding and saving links (FR-031, FR-032);
- list queries (FR-033, FR-034);
- the window form of filters and HFID lookup (FR-038, FR-039).

**Independent Test**: gadget G is linked to widget W through a branch-agnostic relationship and deleted on B. Reading W's gadgets on the default branch returns G. After G is renamed on B, the default branch's read shows the default branch's name.

**Base**: PR 5's branch. Branch: `agnostic-relationship-reads-ifc-3508`.

- [ ] T084 [US6] Create a worktree for `agnostic-relationship-reads-ifc-3508` from `peer-existence-check-ifc-3508`.
- [ ] T085 [US6] Gate for open question 3:
  - Search the callers of `get_peers`, `query_peers`, `get_many`, `get_one` and `get_one_by_id_or_default_filter` with `branch_agnostic=True` for a node object that is changed and saved (research R9 lists the known ones).
  - Add `test_validator_read_branch_agnostic_still_saves_on_global` to `backend/tests/component/core/integrity/`. It builds a `CoreValidator` through `ObjectConflictValidatorRecorder.get_validator` on a user branch and checks that its save writes on `-global-`.
  - Report the findings to the user, and stop. T092 depends on the answer.

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
- [ ] T102 [US6] Run T085-T090 and:
  - `backend/tests/component/core/`
  - `backend/tests/component/graphql/`
  - `backend/tests/component/pools/`
  - `backend/tests/unit/core/query/`

  All pass.
- [ ] T103 [US6] Run `backend/tests/benchmark/test_node_list_filter.py` (filters on one branch must match PR #11220's cost, FR-039), and add a branch-agnostic read with 50 live branches to `backend/tests/benchmark/test_peer_existence_check.py`. Record before and after in the PR description.
- [ ] T104 [P] [US6] Update `docs/docs/branches/branch-agnostic-data.mdx`: a branch-agnostic relationship returns every peer that exists on a live branch, and each peer shows the values of one branch, in the order of FR-029. Run `uv run invoke docs.lint`.
- [ ] T105 [P] [US6] Add a `fixed` changelog fragment: branch-agnostic relationships, such as IP pool resources and validator definitions, return peers that exist on any open branch with consistent values, and adding such a link no longer fails when the peer was deleted on another branch.
- [ ] T106 [US6] Run the pre-push checks in `quickstart.md` and open the PR against `release-1.12`.

**Checkpoint**: all six stories are complete.

---

## Phase 9: Polish and cross-cutting checks

- [ ] T107 Once all six PRs are merged, run every audit test file from `branch-agnostic-wip/audit-tests/` against `origin/release-1.12`, and record in `dev/specs/ifc-3508-branch-agnostic-reads/quickstart.md` that SC-001 to SC-003 hold, listing any assertion changed and why.
- [ ] T108 Update "Delivery by PR" in `dev/specs/ifc-3508-branch-agnostic-reads/plan.md` with the six PR numbers and their merge commits.
- [ ] T109 Grep `dev/specs/ifc-3508-branch-agnostic-reads/` for any figure or decision that a PR changed (for example an error class, a migration number or an open question's answer), and update every file that repeats it in the same commit.

---

## Dependencies & Execution Order

### Phase dependencies

- Setup (T001-T002): no dependency.
- US1 (PR 1): depends only on T001. Based on `stable`.
- US2 (PR 2): no dependency.
- US3 (PR 3): no dependency. It blocks US4, US5 and US6.
- US4 (PR 4): depends on US3.
- US5 (PR 5): depends on US3 merged and PR #11220 in `release-1.12` (T002, T060). Its gates T061 and T062 block T075, T077, T078 and T080.
- US6 (PR 6): depends on US5. Its gate T085 blocks T092.
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
- Inside US6: T086-T089 together.

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
3. US5 once PR #11220 is in `release-1.12`, after its gates are answered.
4. US6 on top of US5.

Each PR adds value on its own and leaves no read worse than before. That is why the peer existence check and the change to the delete writes ship together in US5.

## Notes

- Cite symbols, not line numbers, in code, commits and PR descriptions.
- Commit after each task or logical group, on the PR's own branch, not on `branch-agnostic-reads`.
- Every PR description reports database hits before and after for the paths it changes, or states that it changes no query.
- Stop at every gate. Do not choose an answer to an open question without the user.
