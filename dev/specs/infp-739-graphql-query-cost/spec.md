# Feature Specification: Estimated and Actual Cost of GraphQL Queries for Each Relationship Field

**Feature Branch**: `fac/graphql-proactive-analyzer-rrake`

**Jira**: [INFP-739](https://opsmill.atlassian.net/browse/INFP-739)

**Created**: 2026-10-07

**Status**: Draft

**Input**: The INFP-739 card and the idea brief in its comments, decided in a grilling session on 2026-10-07. Items in the brief that the session did not explicitly confirm keep their "[CLAUDE RECOMMENDED – based on X]" label here.

## Summary

A team that renders artifacts or runs generators from GraphQL queries over a large data set cannot tell, before or after a run, how much work a query causes or which relationship field causes it. Infrahub records the depth and height of each query, not the number of nodes, resolver calls or database rows. To find the field that multiplies the rows, an engineer has to trace a run.

The work depends mostly on how many peers each relationship returns, and that number varies widely between nodes. On one customer's `CablingPlanLogical` query, for one logical network:

| Step in the query | Average over the whole database | Traced logical network |
| --- | --- | --- |
| Devices per logical network | 84 (4,866 / 58) | 938 |
| Interfaces per device | 44 (215,764 / 4,866) | 16.8 |
| Share of link endpoints with a link | 51% | 89% |

Errors multiply at each step of a query:

- An estimate from averages gives about 23,000 single-relationship resolver calls, against an actual 183,000. That is eight times too low.
- Using the actual device count at the first step, and averages after it, gives about 254,000. That is 1.4 times too high.

The trace these figures come from is not linked, and the customer is not named in the sources.

Neo4j's own statistics cannot give peers per relationship, because every relationship goes through the same `IS_RELATED` edge and Relationship vertex, and the relationship identifier is only a property. Time does not measure work either: in the trace, pages of the same size took between 0.7 and 54 seconds.

This feature lets the person who diagnoses or writes a query view, for each relationship field, the expected, worst-case and actual work. It delivers:

- statistics about node counts and peers per relationship, computed by a scheduled background task
- an estimate for each relationship field, with an expected and a worst-case figure
- actual counts for each field, returned when a request asks for them
- the estimate in the existing `InfrahubGraphQLQueryReport` query

Not decided yet:

- how old the statistics may be, which the refresh interval sets
- whether `infrahub-private-tests` needs a CI change to run the synthetic data set
- the design of the later uses described under "Out of scope"

## User Scenarios & Testing *(mandatory)*

Two people use this feature:

- Main user: whoever diagnoses a slow query. That can be an OpsMill support or backend engineer, or a customer operator.
- Second user: whoever writes a query and wants to check its cost before saving it.

Both journeys below are part of the brief's P1 journey, "diagnose a slow query from its estimated and actual work for each field". They are split so that each can be tested on its own.

### User Story 1 - Diagnose a slow query from its estimated and actual work for each field (Priority: P1)

An engineer investigates a slow artifact render. They run the stored query through `/api/query`, or the same query through `/graphql`, with the same variables and the cost-details request header. The response lists each relationship field with its expected and worst-case estimate and the actual nodes, resolver calls and database rows it caused. The engineer views which field multiplies the rows without tracing a run.

**Why this priority**: Today the only way to find the field that causes the work is to trace a run. This journey replaces the trace for the diagnosis that motivated the card.

**Independent Test**: Load a fixture where one top-level node has far more peers than the average. Run a stored query on that node with and without the cost-details header. Compare both responses, and compare the reported actual counts with counts computed by hand.

**Acceptance Scenarios**:

1. **Given** a stored query whose top-level node has far more peers than the average, **When** the engineer runs it through `/api/query` with the cost-details header and its variables, **Then**:
    - the response `extensions` list each relationship field with its expected and worst-case estimate and its actual nodes, resolver calls and database rows
    - the field with the most actual resolver calls is the one whose peers multiply the rows
2. **Given** the same request without the cost-details header, **When** it runs, **Then** the response is the same as today and no work is counted for each field.
3. **Given** a mutation sent with the cost-details header, **When** it runs, **Then** the header is ignored and the response is the same as today.
4. **Given** a relationship added to the schema since the last statistics refresh, **When** a query that reads it runs with the header, **Then** that field has an empty estimate with the reason "no statistics", and its actual counts are still returned.

---

### User Story 2 - Check the estimated cost of a query before running or saving it (Priority: P1)

The person who writes a query submits the query and, optionally, its variables to `InfrahubGraphQLQueryReport`. They view the expected and worst-case figures for each relationship field, the branch the statistics describe and the time they were computed. The query itself does not run.

**Why this priority**: It gives the same estimate as User Story 1 before any work is done. It is the way to check a query before saving it as a stored query or an artifact definition.

**Independent Test**: Submit a fixture query, with and without variables, to `InfrahubGraphQLQueryReport`, with an account that can read every kind in the query and with one that cannot. Compare the figures with values computed by hand.

**Acceptance Scenarios**:

1. **Given** a query and its variables, **When** someone submits them to `InfrahubGraphQLQueryReport`, **Then** the report returns the expected and worst-case figures for each field, the branch the statistics describe (main) and the time they were computed.
2. **Given** the same query without variables, **When** it is submitted to the report, **Then** the estimate is labelled "statistics only".
3. **Given** an account without read permission on one kind in the query, **When** it calls the report, **Then** it gets the permission error that running the query would return, and no counts.

---

### Edge Cases

The brief lists cases where the estimate is less reliable. In each case the actual counts are still correct, and the estimate states what it is based on.

- No statistics yet, or a kind or relationship added since the last refresh: the estimate for the field is empty with the reason "no statistics", and the actual counts are still returned (FR-012).
- Data on main changed since the last refresh: the estimate can be wrong. The time the statistics were computed shows how old they are (FR-011). Node counts stay current because they are scaled by the database's current label counts (FR-017).
- A request on a branch other than main, or at a past time: the counted first step reads that branch and time. Statistics from main apply below it, and the worst case is labelled with its source and promises nothing (FR-008, FR-013).
- An equality filter on an attribute that is not unique, without variables: the estimate uses the kind's whole node count, capped by `limit`, so it is too high.
- A filter on a nested relationship field: the estimate assumes the filter keeps every peer, so it is too high. The actual count next to it shows the difference.
- Display labels rendered from templates, profile values and permission filtering: the estimate does not cover the reads they cause, so the actual rows exceed the estimate on those fields (FR-014).
- A query that goes from many nodes to one node and back out to many: many paths reach the same node, so the worst case must still be an upper bound in that shape (FR-008).

## Requirements *(mandatory)*

### Functional Requirements

#### Cost details on requests

- **FR-001**: When a request to `/graphql` or `/api/query` carries the cost-details header, the response MUST include under `extensions` the actual nodes, resolver calls and database rows for each relationship field. Without the header, the response MUST be the same as today. Test: send the same request with and without the header and compare.
- **FR-002**: Requests without the header MUST NOT count work for each field and MUST NOT run counting queries. Test: send a request without the header and check that no counting ran.
- **FR-004**: The cost details MUST give the estimate next to the actual counts for each field. Test: run a fixture query and check both numbers for each field.
- **FR-015**: On a mutation, the system MUST ignore the header and return the same response as today. Test: send a mutation with and without the header and compare.

#### The report query

- **FR-003**: `InfrahubGraphQLQueryReport` MUST accept an optional `variables` argument and return the estimate for each relationship field. Test: submit a fixture query and compare with values computed by hand.
- **FR-010**: The report MUST return an estimate only if the account has read permission, on the request's branch, for every kind in the analyzed query. Otherwise it MUST return the permission error that running the query would return, and no counts. Today the report analyzes the query with no permission check. Test: use an account that lacks read permission on one kind.

#### How the estimate is computed

- **FR-005**: When variable values are given, the estimate MUST use actual counts for the top-level nodes and for each relationship field directly under them, grouped by the concrete kind of the peers. Statistics apply only below that. Test: a fixture where two concrete kinds under one generic have very different peer counts.
- **FR-013**: The counted first step MUST read the request's branch and `at` time. Test: on a branch that adds peers to the target, the counted step matches the branch's data.
- **FR-006**: Without variables, the estimate MUST be labelled "statistics only". Test: call the report without variables.
    - [CLAUDE RECOMMENDED – based on FR-005 and critique finding E1] A request to `/graphql` or `/api/query` always runs with its variable values, so its first step is always counted. The report has variable values when its `variables` argument is given, and an empty object counts as given.
- **FR-007**: Each field MUST have a worst-case figure next to the expected figure. Test: check both figures for each field.
- **FR-008**: The expected figure MUST use the mean number of peers for each concrete kind. The worst case MUST be an upper bound on main when main has not changed since the refresh. On other branches and times, the worst case MUST be labelled with its source and makes no promise. Test: on an unchanged fixture, no target exceeds the worst case on any field. The fixture includes a query that goes from many nodes to one node and back out.
    - [CLAUDE RECOMMENDED – based on SafeBound, see Sources] Compute the worst case with the bound built from per-node peer counts. At each step, pair the largest number of paths that can reach one node with the largest peer counts, until the previous step's path count is used up. When a histogram is missing, fall back to the product of the maximum peers per node at each step. A simpler rule, "the sum of the k largest peer counts", is not an upper bound when many paths reach the same node.
- **FR-014**: The estimate MUST cover relationship fields, and `count` fields on many-cardinality relationships at one count query per parent node. It does not cover display labels rendered from templates, profile values or permission filtering. The actual counts MUST include the rows those reads cause. Test: a fixture query with a `count` field and a `display_label` field.
- **FR-017**: At request time, the estimate MUST scale the stored node counts by the database's current label counts. Test: add nodes without a refresh, and check that the estimated node count includes them.
- **FR-018**: When a step's node is in the list of nodes with the most peers, the estimate MUST use that node's stored peer count. Test: a statistics-only estimate for a query on a listed node equals its stored count at that step.

#### Statistics and where they come from

- **FR-009**: Each statistic in the store MUST match a value computed by hand on a fixture. This includes the histogram buckets and the list of nodes with the most peers. Test: a fixture with a known peer distribution.
- **FR-011**: Every estimate MUST state the branch its statistics describe and the time they were computed. Test: after a refresh, check both values.
- **FR-012**: A field without statistics MUST have an empty estimate with the reason "no statistics", and its actual counts MUST still be returned. Test: add a relationship to the schema without a refresh.
- **FR-016**: A scheduled background task MUST compute the statistics. Requests MUST only read them. Test: run the task on a fixture and check the store, then check that requests do not start a refresh.

The brief numbers requirements by when they were decided, not by topic, so the numbers above are not in order. They keep the brief's numbers so that both documents can be compared.

### Terms used in the requirements

The brief uses these counts without defining them. [CLAUDE RECOMMENDED – based on the brief's figures counting "single-relationship resolver calls" for each parent node] For each relationship field of a request:

- **Nodes**: the number of peers returned for the field, summed over every parent node that reaches it.
- **Resolver calls**: the number of times the field was resolved, which is one call for each parent node that reaches it.
- **Database rows**: the number of rows the database returned to the queries run to resolve the field.

### Key Entities

- **Statistics store** (new): describes the data on main at the time of the last refresh. It holds:
    - the node count for each concrete kind, from the database's label counts; the count for a generic is the sum of its concrete kinds
    - for each relationship identifier, side and concrete kind:
        - the share of nodes with at least one peer
        - the mean number of peers
        - a histogram of peers per node, with each bucket's maximum; the median, the 95th percentile and the maximum are read from it
        - the list of nodes with the most peers and their exact peer counts; for a kind with fewer nodes than the list's length, it covers every node
    - the branch the statistics describe and the time they were computed

    It is kept in a cache outside the versioned graph, with a version number. Each server process holds a copy in memory.
- **Scheduled statistics refresh** (new): a background task that computes the statistics store from main.
- **Cost details** (new): the content of the response `extensions` when the cost-details header is present. For each relationship field, it gives the estimate (expected and worst case), the actual counts, and where the statistics come from (branch and time).
- **Estimate for a field**: the expected and worst-case nodes, resolver calls and database rows for one relationship field, and its source: "counted" for the first step when variables are given, "statistics only" otherwise, or empty with the reason "no statistics".
- **`InfrahubGraphQLQueryReport`** (existing, extended): gains an optional `variables` argument, a read-permission check and estimate fields.
- **Analyzer query tree** (existing): the tree of fields that the GraphQL analyzer already builds for each query on `/graphql` and `/api/query`. The estimate is computed over this tree. The analyzer already detects queries that target one node.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a synthetic data set with the first step counted, the estimated single-relationship resolver calls are between half and twice the actual count. The data set reproduces the customer's distribution, including the correlation between steps, and lives in `infrahub-private-tests`.
- **SC-002**: [CLAUDE RECOMMENDED – based on FR-001 and FR-002] Requests without the cost-details header run the same number of database queries as today.
- **SC-003**: [CLAUDE RECOMMENDED – based on FR-005] A request with the header runs at most one extra database query for the top-level node, plus one for each relationship field directly under it.
- **SC-004**: [CLAUDE RECOMMENDED – based on User Story 1, acceptance scenario 1] On a fixture where one field multiplies the rows, an engineer identifies that field from one request's cost details, without tracing the run.

## Assumptions

- Label counts include deleted nodes and nodes that exist only on other branches. On the customer's data, the error is small: there are 2% more `HAS_VALUE` edges than attributes. An account can learn approximate totals that include other branches' data. This is accepted.
- A scheduled background task computes the statistics. The cost of the aggregation is therefore not a reason to leave a statistic out.
- [CLAUDE RECOMMENDED – based on FR-008 needing exact bucket maximums] The refresh reads every node of each kind rather than a sample, because a sample can miss the maximum. How it stays within the memory limit of a transaction is decided during planning.
- There is no copy of the customer's database. Confirming the 183,000 figure needs the customer to run the query with the header after release. That confirmation is not a merge condition.
- The first version reports separate counts and no combined cost figure, because no metrics collect the data needed to set its weights.
- The cost details are requested with a header, not a URL parameter, because `/api/query` turns every URL parameter except `branch`, `at`, `update_group` and `subscribers` into a query variable.
- The first version changes no Infrahub integration. Whether the Python SDK needs a way to send the header is not known.
- This feature adds no UI, so it has no pytest-playwright test. Component tests stay in `opsmill/infrahub`, and the customer-shaped data set lives in `infrahub-private-tests`.
- The refresh interval is a setting. The brief does not say how old the statistics may be, so the default interval is not decided. The plan proposes one.

### Decided during planning

The brief leaves these to the plan:

- the name of the cost-details header
- which cache holds the statistics
- how the refresh computes the histograms without one very large transaction

### Governance gates crossed (AGENTS.md "Ask First")

- Database schema or migration change: not crossed. The statistics live in a cache, not in the graph.
- GraphQL schema change: crossed. A new `variables` argument and new estimate fields on `InfrahubGraphQLQueryReport`.
- API contract change: crossed. A new request header on `/graphql` and `/api/query`, and new `extensions` content.
- New dependency: not crossed. [CLAUDE RECOMMENDED – based on LpBound needing a linear-program solver for each query] Compute the bound in Infrahub, with no solver library.
- CI/CD workflow change: not crossed in `opsmill/infrahub`. Whether `infrahub-private-tests` needs a CI change is not known.
- Authorization change: crossed. A read-permission check on `InfrahubGraphQLQueryReport`. No new permission.

## Out of Scope

- Limiting how many artifact and generator runs happen at once by their total estimated cost (the brief's P2, not yet worked through). In the customer case, about 100 heavy renders ran at the same time. Related: [INFP-689](https://opsmill.atlassian.net/browse/INFP-689).
- Sizing Cypher pages and loader batches from the estimate (the brief's P3, not yet worked through). Large reads use a fixed page size of 5,000, so a large read re-runs the sorted query once per page. Related: [INFP-502](https://opsmill.atlassian.net/browse/INFP-502).
- Prometheus metrics for estimated and actual cost.
- A single combined cost figure.
- Admission based on cost. Admission is decided in a middleware before the request body is read, and priority is declared by the client (ADR 0008), so weighting by cost needs its own ADR.
- Warnings when a query is imported.
- Adjusting the statistics with the branch diff summary.
- Refreshing when the number of created or deleted nodes passes a share of a kind's count. PostgreSQL's model is to refresh after 50 rows plus 10% of the table have changed.
- Distinct values per attribute.
- Estimating display labels rendered from templates, profile values and permission filtering.
- Mutations.
- [CLAUDE RECOMMENDED – based on GraphQL queries being trees without cycles or group-by] LpBound and other bounds that need a linear-program solver. Revisit if P3 estimates Cypher queries that join back on themselves.
- Random walks (Wander Join). This is the fallback if SC-001 fails, but it would break SC-003.
- Predicting cost from the history of actual costs for each stored query and target. To be evaluated before P2.

## Open Questions

1. How old may the statistics be? The interval of the scheduled refresh sets this.
2. Does `infrahub-private-tests` need a CI change to run the synthetic data set?
3. Which trace and which customer do the `CablingPlanLogical` figures come from? Neither is linked yet.
4. For limiting concurrent renders later: does the last actual cost of a stored query for the same target predict better than the estimate?

## Sources

- [INFP-739](https://opsmill.atlassian.net/browse/INFP-739): the card description and the idea brief in its comments.
- Code at commit [6a1f295](https://github.com/opsmill/infrahub/tree/6a1f2952cd21176a5ade8f71b41101cdcefcfece) of `opsmill/infrahub`:
    - query depth and height recorded: [app.py#L305-L306](https://github.com/opsmill/infrahub/blob/6a1f2952cd21176a5ade8f71b41101cdcefcfece/backend/infrahub/graphql/app.py#L305-L306)
    - analyzer query tree: [analyzer.py#L164](https://github.com/opsmill/infrahub/blob/6a1f2952cd21176a5ade8f71b41101cdcefcfece/backend/infrahub/graphql/analyzer.py#L164); detection of queries that target one node: [analyzer.py#L413](https://github.com/opsmill/infrahub/blob/6a1f2952cd21176a5ade8f71b41101cdcefcfece/backend/infrahub/graphql/analyzer.py#L413)
    - `InfrahubGraphQLQueryReport`: [graphql_query_report.py](https://github.com/opsmill/infrahub/blob/6a1f2952cd21176a5ade8f71b41101cdcefcfece/backend/infrahub/graphql/queries/graphql_query_report.py)
    - URL parameters turned into variables on `/api/query`: [query.py#L185-L189](https://github.com/opsmill/infrahub/blob/6a1f2952cd21176a5ade8f71b41101cdcefcfece/backend/infrahub/api/query.py#L185-L189)
    - page size of 5,000: [config.py#L404](https://github.com/opsmill/infrahub/blob/6a1f2952cd21176a5ade8f71b41101cdcefcfece/backend/infrahub/config.py#L404)
    - admission middleware: [middleware.py#L112](https://github.com/opsmill/infrahub/blob/6a1f2952cd21176a5ade8f71b41101cdcefcfece/backend/infrahub/api/admission/middleware.py#L112); [ADR 0008](https://github.com/opsmill/infrahub/blob/6a1f2952cd21176a5ade8f71b41101cdcefcfece/dev/adr/0008-client-declared-request-priority.md)
- [PostgreSQL: Statistics used by the planner](https://www.postgresql.org/docs/current/planner-stats.html), [Row estimation examples](https://www.postgresql.org/docs/current/row-estimation-examples.html), [Updating planner statistics](https://www.postgresql.org/docs/current/routine-vacuuming.html#VACUUM-FOR-STATISTICS)
- [Leis et al., How Good Are Query Optimizers, Really? (PVLDB 2015)](http://www.vldb.org/pvldb/vol9/p204-leis.pdf)
- [SafeBound: A Practical System for Generating Cardinality Bounds (SIGMOD 2023)](https://arxiv.org/pdf/2211.09864)
- [LpBound: Pessimistic Cardinality Estimation using ℓp-Norms of Degree Sequences (SIGMOD 2025)](https://arxiv.org/pdf/2502.05912)
- [Wander Join: Online Aggregation via Random Walks (SIGMOD 2016)](https://cse.hkust.edu.hk/~yike/sigmod16.pdf)
- The trace of the customer's `CablingPlanLogical` query: not linked.
