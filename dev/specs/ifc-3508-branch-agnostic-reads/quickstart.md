# Quickstart: Validating Branch-Agnostic Reads

How to check that each PR does what the spec says. The expected behavior is in [contracts/user-visible-behavior.md](contracts/user-visible-behavior.md). The structures are in [data-model.md](data-model.md).

## Prerequisites

- A running Docker daemon. Component tests start Neo4j with testcontainers.
- Python dependencies installed: `uv sync --all-groups`.
- The audit tests, which are not committed, are in `branch-agnostic-wip/audit-tests/` of the `branch-agnostic-reads` worktree. Each PR moves the tests it fixes into `backend/tests/component/`.

Run every test command from `backend/`:

```bash
uv run --no-sync pytest <path> -p no:randomly -q
```

## Before a PR: confirm the tests fail

For the PR's audit test file, copy it into `backend/tests/component/core/` and run it on the base branch. The expected failures are:

| PR | Audit file | Expected on the base branch |
|---|---|---|
| 1 | `test_audit_branch_agnostic_permission_reads.py` | 10 fail, 3 pass. Apply the two assertion changes the brief lists first. |
| 3 | `test_audit_branch_agnostic_pool_reads_release_1_12.py` | 8 IP pool tests fail, 4 number pool tests pass |
| 5, 6 | `test_audit_branch_agnostic_relationship_reads.py` | 11 fail, 4 pass |
| 6 | `test_audit_branch_agnostic_node_reads.py` | 13 fail |

## After each PR

### PR 1

- Run `backend/tests/component/core/test_account.py`, `backend/tests/component/permissions/` and `backend/tests/component/graphql/auth/query_permission_checker/test_merge_operation_checker.py`. All pass.
- The moved permission tests pass, including the new merge test (contract: Permissions).
- Run `test_audit_branch_agnostic_graphql_repro.py::<permission test>`. The account has no `super_admin` on the default branch.

### PR 2

- The existing tests of each changed caller pass unchanged.
- Run `rg -n "branch_agnostic=True" backend/infrahub`. None of the callers listed in research R3 as changed remain.

### PR 3

- Run `backend/tests/unit/core/query/test_branch_windows.py`. It passes.
- Run `backend/tests/component/core/resource_manager/`. It passes, including the number pool files.
- The moved IP pool tests pass for IPv4 and IPv6.
- The two new allocation tests raise the errors in the contract.
- Run the benchmark for IP pool allocation with many live branches and past allocations. Record the database hits before and after in the PR description.

### PR 4

- Run `backend/tests/component/core/test_node_manager_delete.py`. It passes.
- The new test with a peer that reaches the node only through the default branch's edge from before the branch was created is refused, and the error names the branch and the peer.

### PR 5

- The peer existence check tests pass. A read of a branch-aware relationship between branch-aware kinds renders the same Cypher as before; a test compares the query text.
- Run the benchmarks for:
  - a list of `CoreTransformPython` with `repository`;
  - a read of a relationship between branch-aware kinds, which should show no change.

### PR 6

- The moved node-read and relationship-read tests pass.
- The tests brought from `7015435c4` pass: `TestBranchAgnosticLookupByHFID`, `TestBranchAgnosticPeerFilter` and `test_branch_agnostic_filter_through_the_parent_relationship`.
- Run the benchmark for branch-agnostic reads with many live branches.
- A GraphQL read on branch B of a pool's `resources`, where a prefix was deleted on B only, returns the prefix with the default branch's values and no error.
- The `m083` migration test passes for both shapes. Reads at several timestamps match before and after, and a second run changes nothing.

### PR 7

- Run `backend/tests/component/graphql/metadata/test_active_on_branches.py` and `test_active_on_branches_cost.py`. They pass.
- A read of a pool's `resources` on branch B, where a prefix was deleted on B only, returns the prefix with `active_on_branches` holding the default branch and not B.
- A read that does not request `active_on_branches` runs the same queries as on PR 6's branch. Record the database hits with and without the field in the PR description.

## Before pushing any PR

From the repository root:

```bash
uv run invoke format
uv run invoke lint
uv run ruff check . --exclude python_sdk
uv run ruff format --check --exclude python_sdk .
uv run invoke docs.validate
```

Then ask the user to run `/pre-ci`.
