# Implementation report: pull request 2, GraphQL API

- **Feature**: owners and sources of nodes, attributes and relationships (advanced RBAC, phase P1), storage option E
- **Jira**: [IFC-3627](https://opsmill.atlassian.net/browse/IFC-3627), in the epic [IFC-3625](https://opsmill.atlassian.net/browse/IFC-3625)
- **Spec directory**: `dev/specs/infp-753-rbac-owners-option-e`
- **Branch**: `rbac-phase-1-implementation-ifc3627-enevw`, based on pull request 1 ([#11620](https://github.com/opsmill/infrahub/pull/11620), branch `gma-20261117-ifc3626`, head `b77bcf2fb9`)
- **Base commit**: `0c44f461d3` (the task list update for pull request 2, on top of `b77bcf2fb9`)
- **Head commit**: the commit of this report, on top of `5f37e5265e`
- **Wall-clock time**: about 6 hours, 2026-11-26 10:15Z to 16:15Z
- **Status**: DONE. Every task of "2. GraphQL API" in tasks.md is ticked. The review ran with `/code-review`.

## 1. Outcome

- A user sets the owners of a node, an attribute or a relationship field in the create, update and upsert mutations, by ID, by HFID with a kind, or by name.
- A user reads the `ownership` block (state, origin, origin node, owners) on a node, on each attribute and on each relationship field, and `target_ownership` and `target_field_ownership` on profiles and object templates.
- A user reads, sets and filters the sources of a node.
- A user filters lists by owner, by "no owner" and by source. The filters apply before pagination.
- The attribute `owner` field and `is_protected` with its filters are deprecated. Their behaviour does not change.
- The activity log shows the display labels of owners and sources.
- `schema/schema.graphql` and the frontend GraphQL types are regenerated.

## 2. Chunk ledger

| Chunk | Tasks | ✅ / ⚠️ / ❌ | Commits | Flagged upward |
|---|---|---|---|---|
| 1. Add back the deferred code | T152 (closes T018, T019, T027, T043, T136) | 6 / 0 / 0 | `7f07174d0a` | The revert of `f3b47495d9` had one conflict in test_profile_owners.py. The query-count removal of `259305a5c8` stays. |
| 2. Node owners in GraphQL | T037 to T041 | 5 / 0 / 0 | `de23a507f7` | The IP address, IP prefix and repository creates do not use the main create, so they call the same owner write. |
| 3. User story 1 tests, activity log | T026, T032, T052 | 3 / 0 / 0 | `1b418839e1` | T052 for attribute owner lists waited for T117 and was done in chunk 5. |
| 4. Profile and template owners | T076 | 1 / 0 / 0 | `c235897c0c` | `target_ownership` is on the shared `node_metadata` type and is null on other kinds. |
| 5. Field owners, deprecated `owner` | T115, T116, T117, T119, rest of T052 | 5 / 0 / 0 | `12a6be2992` | The read and the write of `owner` were already in pull request 1. dev/knowledge/backend/ownership.md updated. |
| 6. User story 3 tests | T106, T107 | 2 / 0 / 0 | `70b9bb1ea9` | Test helpers moved to backend/tests/helpers/ownership.py. |
| 7. Upgrade tests, `is_protected` | T060, T067, T068 | 3 / 0 / 0 | `896a0eeb94`, `4529b1dae9` (orchestrator) | The chunk gave `GraphqlContext.ownership_resolver` a default. The orchestrator made it required again (see §6). |
| 8. Node sources | T131, T135 | 2 / 0 / 0 | `f6a56bd939`, `3bf19c4c1b` | Chunk 7 broke a test that it did not run; chunk 8 fixed it. |
| 9. Full-stack tests | T033, T073, T110, T111, T133 | 5 / 0 / 0 | `446e70c8dd` | Kinds `InfraDevice` and `InfraInterfaceL3`; raw GraphQL, because the SDK does not know the owner inputs. |
| 10. Generated files | T056, T150 | 2 / 0 / 0 | `8faaabf5a9` | The agent was stopped before T044 and T151. |
| 11. Benchmarks, lint, quickstart | T044, T151 | 2 / 0 / 0 | `14eab625d7` | Quickstart scenario 6 ran by hand with an upgrade from 1.12.3. |
| Review fixes | 4 findings | 4 / 0 / 0 | `3d0b3395a9`, `1e2ce01f82`, `7525979eae`, `5f37e5265e` | See §5. |

## 3. Tasks not completed

None of the tasks of pull request 2. Tasks of pull request 3 and T149 (the consolidated changelog) stay open, as planned.

## 4. Local-pass evidence

Environment for all rows: local Linux VM, the uv venv of the repository, Docker 29.10.1. "testcontainers" means Neo4j 2026.10.1 started by testcontainers. "image" means `registry.opsmill.io/opsmill/infrahub:e2e-ifc3627`. The rows before the review fixes ran on the image built from `3bf19c4c1b`; the code in `backend/infrahub` did not change between that commit and `14eab625d7`. The later commits change the backend code, so the image was built again from `da39eede02` for the last two rows.

| Test id | Type | Run command | Passed at | Environment | Verbatim pass line |
|---|---|---|---|---|---|
| backend/tests/unit/core/ownership (test_input.py, test_resolution.py) | unit | `uv run pytest backend/tests/unit/core/ownership -q` | 2026-11-26T10:29:19Z | n/a | `71 passed, 1 warning in 0.11s` |
| test_filter.py, test_owner_lookup.py, test_profile_owners.py, test_attribute_owners_and_sources.py, test_global_owner_writes.py, test_ownership_scenarios.py, test_template_owners.py | component | `uv run pytest <those paths> -q -n 4 -p no:randomly` | 2026-11-26T10:29:33Z | testcontainers | `312 passed, 3 xfailed, 5 warnings in 263.58s (0:04:23)` |
| backend/tests/component/graphql/metadata/test_node_metadata_owner_input.py | component | `uv run pytest <file> -q -p no:randomly` | 2026-11-26T10:42:26Z | testcontainers | `5 passed, 1 warning in 36.23s` |
| backend/tests/component/graphql/test_manager.py | component | `uv run pytest <file>` | 2026-11-26T10:48:15Z | testcontainers | `14 passed, 1 warning in 34.11s` |
| backend/tests/component/graphql/metadata/test_graphql_node_owners.py (11 tests), backend/tests/component/graphql/queries/test_event_owner_changes.py | component | `uv run pytest <both files> -p no:cacheprovider` | 2026-11-26T11:03:11Z | testcontainers | `12 passed, 1 warning in 69.07s (0:01:09)` |
| backend/tests/component/graphql/metadata/test_graphql_target_owners.py::TestTargetOwners (4 tests) | component | `uv run pytest -p no:cacheprovider -q <file>` | 2026-11-26T11:13Z | testcontainers | `4 passed, 1 warning in 37.09s` |
| test_graphql_field_owner_inputs.py (6 tests), test_event_owner_changes.py attribute case, test_manager.py::test_generate_object_types | component | `uv run pytest -q -p no:cacheprovider <3 files>` | 2026-11-26T11:44:26Z | testcontainers | `22 passed, 1 warning in 71.35s` |
| test_graphql_field_owners.py::TestFieldOwners, test_graphql_owner_field.py::TestDeprecatedOwnerField (whole metadata directory) | component | `uv run pytest backend/tests/component/graphql/metadata -q` | 2026-11-26T11:55:27Z | testcontainers | `97 passed, 1 warning in 140.87s (0:02:20)` |
| backend/tests/component/graphql/metadata/test_graphql_owner_upgrade.py (4 tests) | component | `uv run pytest <file> -v -p no:cacheprovider` | 2026-11-26T12:08:37Z | testcontainers | `4 passed, 1 warning in 41.09s` |
| backend/tests/component/graphql/auth (3 permission checker files pass the resolver) | component | `uv run pytest backend/tests/component/graphql/auth -q -p no:cacheprovider -n 4` | 2026-11-26T12:11:53Z | testcontainers | `124 passed, 9 warnings in 56.45s` |
| backend/tests/component/graphql/metadata/test_graphql_node_sources.py (6 tests) | component | `uv run pytest <file> -q -p no:randomly` | 2026-11-26T12:15:07Z | testcontainers | `6 passed, 1 warning in 41.70s` |
| test_graphql_field_owner_inputs.py (is_protected expectation), test_manager.py::test_generate_filters, with metadata, core/ownership, unit/graphql | component, unit | `uv run pytest -n 4 <suites>` | 2026-11-26T12:22:24Z | testcontainers | `623 passed, 5 warnings in 189.78s (0:03:09)` |
| tests/e2e/ownership (test_node_owners.py, test_profile_template_owners.py, test_field_owners.py, test_node_sources.py) | e2e | `INFRAHUB_TESTING_IMAGE_VER=e2e-ifc3627 INFRAHUB_TESTING_DOCKER_PULL=false uv run pytest -c tests/e2e/pytest.ini tests/e2e/ownership -p no:randomly` | 2026-11-26T14:08:30Z | image | `4 passed in 137.39s (0:02:17)` |
| backend/tests/integration_docker/test_schema_migration.py::TestSchemaMigrations::test_owners_follow_a_renamed_attribute_and_a_changed_kind | integration | `INFRAHUB_TESTING_IMAGE_VER=e2e-ifc3627 INFRAHUB_TESTING_DOCKER_PULL=false uv run pytest <file> -v -p no:cacheprovider` | 2026-11-26T12:32:41Z | image | `3 passed, 1 xfailed, 1 warning in 119.98s (0:01:59)` |
| backend/tests/component/core/ownership/test_filter.py (4 new indexed attribute cases) | component | `uv run pytest <file> -q -p no:randomly` | 2026-11-26T16:00Z | testcontainers | `37 passed, 1 warning in 141.79s` |
| test_graphql_field_owners.py::test_links_of_descendants_give_the_owners_of_the_field_of_the_node_that_holds_them | component | `uv run pytest <file>` | 2026-11-26T16:00Z | testcontainers | `5 passed, 1 warning in 48.11s` |
| test_event_owner_changes.py::test_activity_log_reads_the_label_of_a_source_on_the_branch_of_the_event | component | `uv run pytest <file>` | 2026-11-26T16:00Z | testcontainers | `3 passed, 1 warning in 46.49s` |
| backend/tests/component/graphql/mutations/test_ipam.py::test_ipaddress_create_writes_its_owners_as_the_account_of_the_request | component | `uv run pytest <file>` | 2026-11-26T16:00Z | testcontainers | `32 passed, 1 warning in 83.16s` |
| All component suites above after the review fixes | component | `uv run pytest -n 4 backend/tests/component/graphql/metadata backend/tests/component/graphql/queries/test_event*.py backend/tests/component/core/ownership backend/tests/component/core/test_node_get_list_query*.py backend/tests/component/graphql/mutations/test_ipam.py backend/tests/component/graphql/mutations/test_repository.py -q -p no:randomly` | 2026-11-26T16:01:47Z | testcontainers | `547 passed, 5 warnings in 241.11s (0:04:01)` |
| backend/tests/unit/graphql, backend/tests/unit/core/ownership after the review fixes | unit | `uv run pytest -n 4 backend/tests/unit/graphql backend/tests/unit/core/ownership -q -p no:randomly` | 2026-11-26T16:01:49Z | n/a | `383 passed, 5 warnings in 6.66s` |
| tests/e2e/ownership on the image built from `da39eede02` | e2e | `INFRAHUB_TESTING_IMAGE_VER=e2e-ifc3627 INFRAHUB_TESTING_DOCKER_PULL=false uv run pytest -c tests/e2e/pytest.ini tests/e2e/ownership -p no:randomly` | 2026-11-26T21:47:30Z | image | `4 passed in 131.29s (0:02:11)` |
| backend/tests/integration_docker/test_schema_migration.py on the image built from `da39eede02` | integration | `INFRAHUB_TESTING_IMAGE_VER=e2e-ifc3627 INFRAHUB_TESTING_DOCKER_PULL=false uv run pytest <file> -p no:cacheprovider` | 2026-11-26T21:49:43Z | image | `3 passed, 1 xfailed, 1 warning in 122.48s (0:02:02)` |
| backend/tests/query_benchmark/ownership/test_no_owner_overhead.py (head) | benchmark | `uv run pytest <file> -s -p no:cacheprovider --no-cov -q --session-timeout=10800` | 2026-11-26T13:20:40Z (end) | testcontainers, no other test stack | `4 passed, 1 warning in 2653.39s (0:44:13)` |

Quickstart scenarios of user stories 1 to 5 ran on the same image with a scratch test that is not committed: `5 passed in 131.09s (0:02:11)`, 2026-11-26T14:55:58Z. Scenario 6 (the upgrade) ran by hand: data on release 1.12.3, then `infrahub db ownership-report` and `infrahub upgrade` with the image, 2026-11-26T15:32:19Z to 15:35:44Z, `Upgrade complete SUCCESS`.

Each test file that a chunk added was proven able to fail: the chunk broke the matching code for a moment and saw the test fail, then restored it. Each review fix test failed before its fix.

## 5. Review findings

Review mode: command (/code-review)

| Severity | File | Finding | Result |
|---|---|---|---|
| important | backend/infrahub/core/query/node.py | An owner or source filter was dropped when the list query also started from an indexed attribute filter. | Fixed in `3d0b3395a9`: no index start when an owner or source filter is present. |
| important | backend/infrahub/graphql/resolvers/many_relationship.py | With `include_descendants`, the links of descendant nodes showed the field owners of the parent node. | Fixed in `1e2ce01f82`: each link uses the node that holds it. |
| important | backend/infrahub/graphql/queries/event.py | The activity log read the labels on the branch of the request, so a source that exists on one branch only showed as "deleted source". | Fixed in `7525979eae`: labels are read on the branch of each event. |
| pre-existing | backend/infrahub/graphql/mutations/ipam.py, repository.py | Owners given at the create of an IP address, an IP prefix or a repository were written as the system user. | Fixed in `5f37e5265e` for the owner and source write. The node itself is still created as the system user, as before. |
| nit | backend/infrahub/core/ownership/input.py | A `field_owners` entry without `owners` sets the field to inherit. The input text of the node-level `owners` says "left out: no change". | Deferred: the contract does not say what a field entry without `owners` means. Decision for the maintainer. |
| nit | backend/infrahub/core/ownership/input.py | An owner given by `name` without `kind` is looked up as an account group only. | Deferred: the contract says "Without `kind`: the name of an account group", and its error list also names a name that matches an account and a group. Decision for the maintainer. |
| nit | backend/infrahub/core/ownership/models.py | `OwnerReference` is a dataclass; backend/AGENTS.md asks for Pydantic models. | Deferred: the ownership module of pull request 1 uses dataclasses for all its models. |

## 6. Autonomous decisions

- Before the run, the orchestrator changed the spec set (commit `0c44f461d3`), after two answers of the maintainer on 2026-11-26:
  - The origin of a field that takes the owners of its node is `NODE`, as in the engineering design. It replaces `OBJECT`.
  - T031 is dropped, because two tests of test_owner_sets.py cover it.
  - T018, T019, T027, T043 and T136 were open again, because pull request 1 had removed their code. T152 was added to bring it back.
  - T044 and T106 do not assert query counts (decision of 2026-11-18).
- Chunk order: user story 5 (T060, T067, T068) ran after user story 3, because its scenarios read the attribute `ownership` that T115 adds. T044 ran with the last chunk, because it is a benchmark run, not a test.
- `GraphqlContext.ownership_resolver`: chunk 7 gave it a default so that the permission tests run with no edit. dev/guidelines/backend/component-design.md requires every collaborator as a required parameter, and only 4 places build the context. So the orchestrator made it required again (`4529b1dae9`), and the 3 permission checker tests pass the resolver. What the tests check did not change.
- The chunk 10 agent was stopped before it finished. A new agent did T044 and T151, after the maintainer agreed.
- The base benchmark first ran at the same time as an E2E stack. The 7 base rows that could have overlapped ran again alone.
- This report is in a new file. `opsmill-implement-report.md` keeps the report of pull request 1.
- No towncrier fragment: the changelog is one consolidated set after all pull requests are in the feature branch (T149).

## 7. Suggested next steps

1. Decide the open points of pull request 1 code that this run found:
   - The deprecated `owner` returns an owner copied from an object template (state `INHERIT`). FR-014 says "own owner".
   - The diff and the activity log show "deleted owner". The spec says "deleted group" (E-1, FR-008); an owner can also be an account.
   - backend/tests/component/templates/test_template_owners.py has a query-count test from pull request 1, against the decision of 2026-11-18.
2. Decide the two deferred nits of §5 (`field_owners` without `owners`, `name` without `kind`), and whether `target_field_ownership(fields:)` must refuse an unknown field name (today it skips it), and which of `owner` and `owners` wins on one attribute (today `owners`).
3. Note for the pull request text: the object file load row of the benchmark is 10.3% slower on head than on base, from one run of each (measurements.md, "Pull request 2: cost for a customer with no owners (2026-11-26)"). In pull request 1, the same row was 15.1% faster. The pull request text gives the table.
4. Run `/pre-ci`, then open the pull request against `gma-20261117-ifc3626` (pull request 1).
