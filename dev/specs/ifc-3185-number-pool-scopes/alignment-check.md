# Alignment check: Number pool allocation scopes

## Source

The source PRD is the union of:

- Jira epic [IFC-3185](https://opsmill.atlassian.net/browse/IFC-3185) (no description) and its child tickets IFC-3329, IFC-3334, IFC-3346, IFC-3347, IFC-3348, IFC-3349, IFC-3352, IFC-3354, IFC-3356, with their "Detailed description" comments of 2026-10-08, plus the related frontend epic IFC-3363. The closed children IFC-3351, IFC-3353, IFC-3355, IFC-3357 and IFC-3358 ("Won't Do") were read for what they moved elsewhere.
- The Notion page "Number Pools PRD" (`https://app.notion.com/p/3fb228b8302582e28e1e01cafd3526f3`), filtered to the parts that concern allocation scopes: problem 3, "One pool serves every scope", the P3 entry of "Slices of work", FR-013 to FR-020, FR-043, SC-007 to SC-010 and SC-012, the "Allocation scope on the pool" entity, the scope-related cases to get right, and the scope-related pieces of "How we plan to build it".
- The description and the diff of [PR #10932](https://github.com/opsmill/infrahub/pull/10932): the GraphQL surface of the three dedicated queries and the fixed dataset.
- The thirteen decisions of the product owner, treated as part of the PRD and overriding the three other sources where they differ.

Fetched with the Jira and Notion connectors, `gh pr view` and `gh api`; no source was gated. The spec set was also checked against the code of `feature-number-pools-1.12`, which is not a requirement source but constrains what the plan can name.

## Verdict

⚠️ MINOR DRIFT (proceeding)

The spec covers every scope-related requirement of the sources. The deviations below are either required by the thirteen decisions, or are additions with a documented reason. No point is left for the product owner to confirm.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| Minor | changed | PRD FR-018 (scope set, changed, cleared at any time); PRD FR-043 (declared scope may change on a later load); Jira IFC-3348 ("the scope stays mutable on every pool type", `null` on update clears the scope) | FR-007, FR-026, Out of scope | The scope is immutable after creation; `null` on update is refused and the test that pinned the clear is replaced. Required by decision 2 |
| Minor | changed | PRD FR-015 (an entry names a field); Jira IFC-3334 (names stored) | FR-002, FR-003 | An element stores the schema element id and the name, and is given by id or by name. Required by decision 3; the name form is kept for schema authors and hand-written requests |
| Minor | changed | Jira IFC-3348 (validation against the branch where the pool is saved); Jira IFC-3354 (a scope that exists on one branch only, entries applied per branch) | FR-003, FR-016, FR-027, User Story 1 scenario 12, User Story 3 scenario 5 | The default branch's schema is the only reference, and a request on a branch whose schema lacks an element is refused. Required by decisions 1 and 7 |
| Minor | changed | Jira IFC-3352 (renaming a scoped field is refused; the author removes the entry first) | FR-029, User Story 4 scenario 3 | A rename is allowed and the stored name follows it. Required by decisions 3 and 6 |
| Minor | changed | Jira IFC-3352 (a declared `parameters.allocation_scope` makes the rename impossible) | FR-026, User Story 3 scenarios 6 and 7, contracts/number-pool-parameters.md | The declaration is compared to the stored scope by id; the rename passes when the declaration carries the new name. Required by decision 9 |
| Minor | unchanged | Jira IFC-3348 (`List` and `JSON` attributes refused) | FR-004, FR-009, edge cases | `List`, `JSON` and `Any` attributes are refused. Decision 10, revised on 2026-10-09, returns to the rule of the ticket |
| Minor | changed | Jira IFC-3347, IFC-3329 (a value counts under every division its holding object occupies on any live branch; site C reads `used_default_branch` 1 on the fixed dataset) | FR-011, FR-022, contracts/graphql-number-pool-queries.md example | A holding object's division is read on the branch of the request; a value counts in one division per branch read. Required by decision 7; the fixed dataset and its example change with it |
| Minor | changed | PR #10932 (`allocation_scope: [String!]!`) | FR-018, contracts/graphql-number-pool-queries.md | `allocation_scope` is a list of `{id, name}` objects. Required by decisions 4 and 5, stated as a breaking change |
| Minor | added | PR #10932 (`NumberPoolDivisionEntry` without `id`) | FR-018, contracts/graphql-number-pool-queries.md | Each division entry carries the element `id` beside `path`. Additive; reason documented in research R11 |
| Minor | changed | PR #10932 ("scope in force on the request's branch", refusals naming the branch) | FR-016, contract wording | The scope is the pool's scope on every branch; one refusal names the branch when its schema lacks an element. Consequence of decisions 1 and 7 |
| Minor | added | Jira IFC-3348, IFC-3352 | FR-005, FR-006, FR-028 | The generic rule and the `unique: true` refusal come from the Jira tickets, not from the Notion PRD. Kept because Jira is a source |
| Minor | changed | PRD FR-016 (a provided number already tracked in the writer's scope is refused); Jira IFC-3349 (an explicit number in A is tracked) | FR-014, edge cases | The provided number is recorded under the writer's division and not refused. Required by decision 11 |
| Minor | changed | Jira IFC-3348 (`role__value` stored as `role`) | FR-004 | Any entry containing `__` is refused, and the error gives the element name. Required by decision 12 |
| Minor | dropped | PRD FR-020 (one reading: every division that has nodes) | FR-020 | Only divisions holding a value are listed. Settled by decision 8 |
| Minor | changed | Jira IFC-3349 (the per-division lock in the allocator replaces the mutation-level pool lock on a scoped pool) | FR-013, plan "Allocation within a division", research R6 | Both locks are keyed per division; the mutation-level lock stays because on create the record is written at save time. Engineering judgment recorded in the research |
| Minor | changed | Jira IFC-3352 (a dedicated `pool.scope.dependency` checker plus a composite checker) ; earlier research R8 (a step in the schema endpoints) | plan "Declared scope and schema checker", research R8 | One checker registered beside the existing ones, no composite, because the aggregated checker runs every checker that supports a constraint name. Engineering judgment |
| None | missing | PRD FR-020 ("utilization as the fullest scope, with a figure per scope underneath") | FR-019, FR-020 | Delivered through the divisions list ordered by utilization descending (fullest first) and the per-division utilization query, as PR #10932 defines. Not drift |
| None | missing | PRD "Scope resolution" and "the allocator ... lock keyed on the pool and the scope" | FR-013, plan | Covered |
| None | missing | PRD SC-012, Jira IFC-3354 measurements and two-branch tests | SC-005, quickstart, tasks T040 and T041 | Covered; the two-branch scenarios follow decision 7 instead of the per-branch entries of IFC-3354 |
| None | missing | Jira IFC-3347 (rebase #10932, remove the duplicate test, update the PR description) | tasks T001 and T002 | Covered; the mock is updated to the `{id, name}` contract before the resolvers read the database |
| None | missing | Jira IFC-3356 (docs, changelog, knowledge entry, SDK pull requests #1371 and #1402, submodule pointer) | tasks T042 to T046 | Covered; the SDK task states what the two merged pull requests carry and what remains |
| None | missing | Jira IFC-3351 ("Won't Do": declare the scope on a number-pool attribute) | User Story 3, tasks T029 to T033 | The product owner reopens IFC-3351, reworded to decision 9, to track this story; recorded in tasks.md |

## Action

Proceed. No remediation pass was needed. The three points flagged after the first alignment pass were confirmed by the product owner and recorded as decisions 11, 12 and 13: a provided number already tracked in the writer's division is recorded, not refused (FR-014); an entry written as `role__value` is refused rather than stored as `role` (FR-004); the three queries read a holding object's division on the request branch (FR-022), which changes the fixed dataset's example figures that the frontend team has seen.
