# Quickstart: Validate merge and rebase refusals on a local instance

Schema changes are high risk, so the automated tests are completed by a matrix run against a local instance built
from the branch. Each case runs through three paths: branch merge, proposed-change merge and rebase.

## Prerequisites

- Docker, with enough memory for one stack at a time. Do not run test suites while the matrix runs.
- `uv sync --all-groups`, and the `python_sdk` submodule installed in the environment.

## Start a fresh stack

```bash
uv run invoke dev.destroy
uv run invoke dev.start --wait
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/api/schema/summary   # expect 200
```

The development stack mounts the worktree, so code changes need a restart (`dev.stop`, `dev.start --wait`), not a
rebuild. Use the API token from the development compose file. Start a fresh stack for every batch of about five
cases.

## Case setup

Every case uses its own kind (namespace `Testing`, branch-aware) and its own branch, so cases do not affect each
other. The steps are:

1. Load the base schema on the default branch.
2. Create the "before branching" data on the default branch, if any.
3. Create the branch and wait for it to be ready.
4. Make the branch change.
5. Make the default-branch change made after branching.
6. Record the schema and data of both branches, then run the path.

A refused case is then fixed and retried. A proposed change is created once per case, and its merge is run with
`wait_until_completion: true`.

## Cases that must be refused

| # | Base schema | On the branch | On the default branch after branching | Fix before retrying |
|---|---|---|---|---|
| R1 | `ticket_id` Text, optional | make `ticket_id` unique | two nodes with `ticket_id` `T-1` | delete one node |
| R2 | `note` Text, optional | make `note` mandatory | a node without `note` | set `note` |
| R3 | `name` only | add `note` Text, mandatory, no default value | a node | delete the node |
| R4 | `size` Text, optional | change `size` to Number | a node with `size` `big` | delete the node |
| R5 | `aaa`, `bbb` Text, optional | add the uniqueness constraint `[aaa, bbb]` | two nodes with the same `aaa` and `bbb` | delete one node |
| R6a | `vlan_id` Number, `role` Text mandatory | remove `role` | a number pool on `vlan_id` scoped by `role` | delete the pool |
| R6b | same as R6a | make `role` optional | same as R6a | delete the pool |
| R7 | `name` only | a node | add `extra` Text, mandatory, no default value | delete the node on the branch |
| R8 | `ticket_id` Text, optional, with `T-1` created before branching | a second node with `T-1` | make `ticket_id` unique | set the branch node to `T-2` |
| R9 | `note` Text, optional | a node without `note` | make `note` mandatory | set `note` on the branch |
| R10 | `size` Text, optional | a node with `size` `big` | change `size` to Number | delete the node on the branch |

## Cases that must be accepted

| # | Base schema | Before branching | On the branch | On the default branch after branching |
|---|---|---|---|---|
| A1 | `name` only | — | add `note` mandatory without default, then two nodes with `note` set | — |
| A2 | same as R1 | — | make `ticket_id` unique | two nodes with `T-1` and `T-2` |
| A3 | same as R2 | a node without `note` | set its `note`, then make `note` mandatory | — |
| A4 | same as R2 | a node without `note` | delete the node, then make `note` mandatory | — |
| A5 | `vlan_id` Number, `old_name` and `gone` Text, optional | a node with every attribute set | rename `old_name` to `new_name` (same id) and remove `gone` | an unscoped number pool on `vlan_id` |
| A8 | `name` only | — | a node, no schema change | — |

## Expected results

- R1–R10: every path is refused with the messages in [contracts/refusal-messages.md](contracts/refusal-messages.md).
  After the refusal, the branch is `OPEN` and both branches' schema and data match the recording. After the fix, the
  merge and rebase retries are accepted; a proposed-change retry stays refused with "Unable to merge proposed change
  containing failing checks" until its checks run again.
- A1–A5 and A8: every path is accepted. After a merge, the default branch's schema reloads and every value of the
  case's kind can be read; after a rebase, the branch's data can be read.

## Record the results

Write one line per case and path (case, path, expected, result, branch status, both branches unchanged, retry
result, message) and add the table to the pull request description.

## Automated checks

```bash
cd backend
uv run pytest tests/unit/core/schema/test_schema_branch.py tests/unit/core
uv run pytest -n 4 tests/component/core/constraint_validators tests/component/core/test_branch_merge.py \
  tests/component/core/test_branch_rebase.py tests/component/api/test_40_schema.py
uv run pytest tests/integration/schema_lifecycle/test_schema_validator_stored_data.py
cd ..
uv run ruff check . --exclude python_sdk
uv run ruff format --check --exclude python_sdk .
uv run invoke docs.validate
```

Integration tests that clone Git repositories leave `backend/repositories/` behind; delete it before the whole-repo
ruff check.
