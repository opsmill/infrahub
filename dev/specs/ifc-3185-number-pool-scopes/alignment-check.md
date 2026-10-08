# Alignment check: Number pool allocation scopes

## Source

The source PRD is the union of:

- Jira epic [IFC-3185](https://opsmill.atlassian.net/browse/IFC-3185) (no description) and its child tickets IFC-3329, IFC-3334, IFC-3347, IFC-3348, IFC-3349, IFC-3352, IFC-3354, IFC-3356, plus the related frontend epic IFC-3363.
- The Notion page "Number Pools PRD" (`https://app.notion.com/p/opsmill/Number-Pools-PRD-3fb228b8302582e28e1e01cafd3526f3`), filtered to the parts that concern allocation scopes: problem 3, "One pool serves every scope", the P3 entry of "Slices of work", FR-013 to FR-020, FR-043, SC-007 to SC-010 and SC-012, the "Allocation scope on the pool" entity, the scope-related cases to get right, and the scope-related pieces of "How we plan to build it".
- The description of [PR #10932](https://github.com/opsmill/infrahub/pull/10932): the GraphQL surface of the three dedicated queries.
- The five decisions of the product owner, treated as part of the PRD and overriding the three other sources where they differ.

Fetched with the Jira and Notion connectors and `gh pr view`; no source was gated.

## Verdict

⚠️ MINOR DRIFT (proceeding)

The spec covers every scope-related requirement of the sources. The deviations below are either required by the five decisions, or are additions with a documented reason. None changes a requirement's meaning without a decision behind it.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| Minor | changed | PRD FR-018 (scope set, changed, cleared at any time); PRD FR-043 (declared scope may change on a later load) | FR-007, FR-025, Out of scope | The scope is immutable after creation. Required by decision 2 |
| Minor | changed | PRD FR-015 (an entry names a field); Jira IFC-3334 | FR-002, FR-003 | An element stores the schema element id and the name, and is given by id or by name. Required by decision 3; the name form is kept for schema authors and hand-written requests |
| Minor | changed | Jira IFC-3348 (validation against the branch where the pool is saved); Jira IFC-3354 (a scope that exists on one branch only) | FR-003, FR-026, User Story 3 scenario 5 | The default branch's schema is the only reference. Required by decision 1 |
| Minor | changed | Jira IFC-3352 (renaming a scoped field is refused) | FR-028, User Story 4 scenario 3 | A rename is allowed and the stored name follows it. Consequence of decision 3 |
| Minor | changed | PR #10932 (`allocation_scope: [String!]!`) | FR-017, contracts/graphql-number-pool-queries.md | `allocation_scope` is a list of `{id, name}` objects. Required by decisions 4 and 5, stated as a breaking change |
| Minor | added | PR #10932 (`NumberPoolDivisionEntry` without `id`) | FR-017, contracts/graphql-number-pool-queries.md | Each division entry carries the element `id` beside `path`. Additive; reason documented in research R11 |
| Minor | changed | PR #10932 ("scope in force on the request's branch") | FR-026, FR-027, contract wording | The scope is the pool's scope on every branch, because the schema guard refuses on every branch a change that would break an element. Consequence of decision 1 |
| Minor | added | Jira IFC-3348, IFC-3352 | FR-005, FR-006, FR-027 | The generic rule and the `unique: true` refusal come from the Jira tickets, not from the Notion PRD. Kept because Jira is a source |
| Minor | dropped | PRD FR-020 (one reading: every division that has nodes) | FR-019 | Only divisions holding a value are listed, as PR #10932 states; Jira IFC-3329 left this undecided. Flagged for product confirmation |
| Minor | changed | PRD FR-016 (provided numbers checked per division) | FR-014 | Kept as a requirement, but no task in this feature: the paths that record a provided number (IFC-3184) are not in the working tree. The division-aware used query they need is delivered here |
| None | missing | PRD FR-020 ("utilization as the fullest scope, with a figure per scope underneath") | FR-018, FR-019 | Delivered through the divisions list ordered by utilization descending (fullest first) and the per-division utilization query, as PR #10932 defines. Not drift |
| None | missing | PRD "Scope resolution" and "the allocator ... lock keyed on the pool and the scope" | FR-013, plan | Covered |
| None | missing | PRD SC-012, Jira IFC-3354 measurements | SC-005, quickstart measurements | Covered |
| None | missing | Jira IFC-3356 (docs, changelog, SDK pull requests, knowledge entry) | tasks T039 to T044 | Covered; the exact SDK change is not known from the sources and is recorded as such |

## Action

Proceed. No remediation pass was needed. Two points are flagged for the product owner in the completion summary: the divisions list contains only divisions that hold a value (research R10), and the rename of a scoped element is allowed rather than refused (consequence of decision 3).
