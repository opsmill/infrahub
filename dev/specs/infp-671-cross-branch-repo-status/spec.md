# Feature Specification: Cross-branch Repository Status Query

**Feature Branch**: `cross-branch-repo-status-infp-671`

**Created**: 2026-09-03

**Status**: Draft

**Jira**: [INFP-671](https://opsmill.atlassian.net/browse/INFP-671) (Git repository sync visibility), second backend slice

**Source PRD**: [PRD: Cross-branch repository status query](https://opsmill.atlassian.net/wiki/spaces/Product/pages/865894402/PRD+Cross-branch+repository+status+query) (Confluence, Product space)

**Sibling PRD**: [PRD: Git repository commit visibility](https://opsmill.atlassian.net/wiki/spaces/Product/pages/858816518). Its P3 covers the same Branches card from the git side (remote head per branch, read from a task worker). This spec is the graph half only. Neither is complete without the other, and shipping this spec does not close that P3.

**Related**: [INFP-670](https://opsmill.atlassian.net/browse/INFP-670), [INFP-672](https://opsmill.atlassian.net/browse/INFP-672), [INFP-557](https://opsmill.atlassian.net/browse/INFP-557), [INFP-492](https://opsmill.atlassian.net/browse/INFP-492), [INFP-606](https://opsmill.atlassian.net/browse/INFP-606), [INFP-393](https://opsmill.atlassian.net/browse/INFP-393)

**Frontend design**: [Git sync visibility canvas](https://claude.ai/design/p/d8efb789-c722-4622-b8d8-0bceb7054774?file=Git+sync+visibility.dc.html&via=share), section 1 (the Branches card on the repository page)

**Input**: User description: "The specifications are in Confluence, read them from here: <https://opsmill.atlassian.net/wiki/spaces/Product/pages/865894402/PRD+Cross-branch+repository+status+query>"

## Problem Statement

A repository in Infrahub has a status per branch: whether the last import on that branch succeeded, and which commit that branch has imported. Today the repository page shows the status of the default branch only. Establishing the state of the other branches means opening each branch in turn; an operator hunting the one branch whose import failed may open up to 200 pages.

The periodic sync has the same problem on the server side: once per cycle it asks the graph for the repository's commit on every branch, one query per branch.

This feature adds one read, anchored on a repository, that returns the repository's status as seen from every relevant branch, paginated over branches, with server-side filtering and counting. The same read replaces the per-branch loop in the periodic sync.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See every branch's repository status from the repository page (Priority: P1)

A developer or infrastructure manager opens a connected repository. The Branches card lists each branch in scope with its import status and imported commit, paginated and filterable, without the user opening any other branch.

**Why this priority**: This is the visible pain INFP-671 was opened for. It turns "in sync" from a statement about the default branch into a statement about the repository, and makes a failed import on any branch findable from one page.

**Independent Test**: Load a repository with a dozen branches where one branch has a failed import on its own branch. Open the repository page. All branches appear with their own status and commit in one request, and the failing branch is identifiable without navigating away.

**Delivery**: The Branches card and its pytest-playwright test under `tests/e2e/branches/` are delivered by the frontend team under INFP-671, built against `contracts/graphql-repository-branch-status.md`. This backend slice is complete when the query and the sync refactor land with their component tests. The constitution's end-to-end requirement attaches to the card, not to this slice.

**Acceptance Scenarios**:

1. **Given** a read-write repository (CoreRepository) with 12 branches that sync with git, one of which has import status `error-import` on its own branch, **When** the user opens the repository page, **Then** the card lists the branches with each one's import status and commit as resolved from that branch, the failing branch shows its error status using the colour and label defined for that status in the schema, and the rows and their graph-resolved values arrive from a single request.
2. **Given** a branch created in Infrahub after the repository existed and never imported on that branch, **When** the user views the card, **Then** that row shows the commit the default branch held at the branch's fork point, not an empty value and not an error.
3. **Given** a read-only repository (CoreReadOnlyRepository), **When** the user opens the repository page, **Then** every branch is listed with its tracked `ref` and `commit`, and branches that have not pinned their own ref show the value inherited from the default branch.
4. **Given** a read-write repository and a branch that does not sync with git, **When** the user views the card, **Then** that branch is absent from the row set and from the count.
5. **Given** a repository with 200 branches of which 3 have failed to import, **When** the user filters by import status, **Then** exactly those 3 rows are returned and the count is 3, without paging through healthy rows.
6. **Given** the card's git-derived remote-head column (owned by the sibling PRD) is unavailable because no task worker can answer, **When** the user opens the repository page, **Then** the rows and every value this feature owns still render.

**What "a single request" claims**: It is a statement about the rows and the graph-resolved values this feature owns. Those MUST all arrive in one request, and the count and every filter MUST be applied server-side. It is not a claim about the finished card. The sibling PRD's remote-head column has its own data path and its own failure states, so the assembled card may issue a second request for it. Two consequences bind here: this query MUST NOT depend on a task worker, and its rows MUST render even when the git-derived column is unavailable.

---

### User Story 2 - The periodic sync stops querying per branch (Priority: P2)

The periodic repository sync reads each repository's commit and internal status for every branch once per cycle. Today it issues one graph query per branch. After this feature, it reads the same values through the new cross-branch primitive, in chunks of branches, so the number of queries no longer grows one-for-one with the branch count.

**Why this priority**: It ships independently of the user-facing card and is independently measurable, but the operator-facing value in P1 is the reason the ticket exists. It also changes a once-a-minute read path, so it warrants its own reviewed change.

**Independent Test**: Run a sync cycle against a repository with 200 branches while counting graph queries. The count is bounded by one repository-node read plus the branch count divided by the chunk size, rounded up, and only `commit` and `internal_status` are read.

**Acceptance Scenarios**:

1. **Given** a repository with 200 branches, **When** a sync cycle runs, **Then** the repository commit and internal status for every branch are read without one query per branch, and only `commit` and `internal_status` are requested.
2. **Given** the same fixture, **When** the sync's read path is instrumented, **Then** the number of graph queries is at most `1 + ceil(200 / chunk_size)` for the configured chunk size.

---

### Edge Cases

- **Branch with no attribute value of its own**: The row resolves to the default branch's value at the branch's fork point (`branched_from`). This is the true value for that branch, since branch data inherits the same way and file access is commit-addressed. It is not an error state and is not flagged in the payload.
- **Rebase moves the displayed commit**: A rebase advances `branched_from`, so an untouched branch's inherited commit follows the default branch forward with no git activity on that branch. This is correct and is stated so it is not filed as a bug.
- **Branch created over an existing remote branch**: Branch creation points the local git branch at the remote tip while the graph still reports the fork-point commit until the first import. This is a known write-path inaccuracy that this query surfaces rather than repairs (INFP-670 territory).
- **Repository never imported anywhere**: Inheritance falls back to the value at repository creation on the global branch. `commit` is unset there, so the row is genuinely empty.
- **Branch with no remote counterpart** (created before the repository was added): Appears with inherited values. There is nothing on the git side to compare against, and this feature makes no comparison.
- **Attribute `updated_at` on an inherited row**: Belongs to the default branch's write, not to an import on that branch. It MUST NOT be presented as a "last import" time.
- **Read-only repository at scale**: `commit` and `ref` are branch-aware, so most rows show the same inherited pair. Accepted as correct. The "own value only" filter (FR-014) is what makes diverged branches findable from the graph, independently of whether the sibling PRD's remote check has run.
- **Several hundred branches**: Page cost does not grow with branch count. The sync job's cost is chunked.
- **More branches than the database query size limit**: The branch read is unpaged, so beyond that limit it takes the standard chunked path and page cost grows one execution per chunk. Stated so FR-007 is not read as an unconditional promise; no repository is expected to reach it.
- **Git-derived column unavailable**: Not a condition of this query. Its rows resolve and render regardless; the column reports its own state per the sibling PRD.
- **Caller lacks permission on non-default branches**: The query is denied outright. It does not return a trimmed row set that silently omits branches.
- **Every branch filtered out**: The query returns an empty row set and a count of 0, not an error.
- **Repository id or name does not resolve**: The query fails with the same not-found behaviour as other repository lookups.

## Requirements *(mandatory)*

### Functional Requirements

#### Contract

- **FR-001**: System MUST expose a GraphQL query `InfrahubRepositoryBranchStatus`, anchored on a repository id or name (the repository kinds declare no human-friendly id; the lookup is the same id-or-default-filter lookup other repository reads use), returning `edges { node }` plus an optional `count`, with `limit` defaulting to 40, no hard maximum, and `offset`. *Verify*: page boundaries and count against a fixture of known branch count.
- **FR-002**: The row set MUST be, for CoreRepository, the branches with `sync_with_git` true; for CoreReadOnlyRepository, all branches. Branches in `MERGED` or `DELETING` status MUST be excluded from both, and the global branch MUST be excluded. Every other branch status MUST be included. *Verify*: fixture carrying one branch per status plus a non-synced branch; assert membership per repository kind.
- **FR-003**: Each row MUST carry the branch's own `name`, `status`, `is_default`, `sync_with_git` and `branched_from`, plus the repository's per-branch attribute values as that branch resolves them. `sync_with_git` is both a row-set criterion (FR-002) and a row value: it is constant `true` on the read-write kind, where FR-002 selects on it, but it varies per row on the read-only kind, whose row set is every branch. Dropping it would force a caller rendering a read-only repository to issue a second request for a value this row set already knows. *Verify*: a branch with its own commit returns its own value; an untouched branch returns the default branch's fork-point value; a read-only repository's rows carry both `true` and `false` for `sync_with_git`.
- **FR-004**: Attribute payloads MUST reuse the existing GraphQL attribute types (`TextAttribute` and `Dropdown`), so Dropdown attributes carry `value`, `label` and `color`. *Verify*: `sync_status` returns the schema's hex colour and label, and the frontend renders it through the existing dropdown cell with no new mapping.
- **FR-005**: `ref` MUST be present for the read-only kind and null for the read-write kind, dispatched on repository kind rather than probed. *Verify*: assert both kinds against one query document.
- **FR-006**: Branch-name partial match, branch status filter and ordering MUST be query arguments, not client-side operations. Default order is default branch first, then branch name ascending, overridable through the existing metadata order input. *Verify*: the filtered row set and the count both change server-side.
- **FR-013**: System MUST support filtering rows by repository attribute value, at minimum `sync_status`. *Verify*: the row set and the count both narrow to the failing branches server-side.
- **FR-014**: System MUST support restricting rows to branches holding their own `commit` value rather than an inherited one. `commit` is written by every import, so this is the graph's record of "imported on this branch". The filter MUST NOT depend on which fields the caller selected. *Verify*: fixture where two of twelve branches have imported on their own branch; assert only those two are returned, and that a document selecting only `sync_status` returns the same two rows.

#### Efficiency

- **FR-007**: The number of database queries needed to serve a page MUST be independent of the number of branches in the row set, up to the configured database query size limit. Above that limit the unpaged branch read takes the standard chunked path and adds one execution per chunk; the attribute read stays one statement per page. *Verify*: instrument query execution; run the same document against fixtures with 5 and 200 branches and assert the two counts are equal. No specific count is prescribed.
- **FR-008**: System MUST read only the attributes the caller selected, plus `commit` when `own_values_only` is set. *Verify*: the attribute-name set reaching the core read equals the GraphQL selection, plus `commit` when `own_values_only` is true; an unselected attribute is absent from the query parameters otherwise.
- **FR-009**: The core primitive MUST take an explicit branch-name list and attribute-name set and MUST be callable without GraphQL. *Verify*: unit test invokes it directly with two branch names and one attribute.
- **FR-010**: The periodic sync's per-branch repository read (`get_repositories_commit_per_branch`) MUST use the primitive and MUST NOT issue one query per branch. Its query count MUST be bounded by `1 + ceil(N / chunk_size)` for N branches, the one being the single repository-node read that precedes the chunks. *Verify*: instrument; assert the bound holds at 200 branches with the configured chunk size.
- **FR-011**: `count` MUST be computed only when selected. *Verify*: instrument; assert no counting operation when the field is omitted.
- **FR-015**: The query MUST resolve entirely from the graph. It MUST NOT issue a git operation, send a message-bus request, or depend on a task worker being available. *Verify*: instrument message-bus sends; assert zero for every document this contract supports.

#### Access

- **FR-012**: The query MUST require view permission on the repository kind covering both the default branch and non-default branches, regardless of the branch the query is issued against, and MUST deny the query rather than trim rows. Separate `ALLOW_DEFAULT` and `ALLOW_OTHER` grants combine and satisfy this the same way a single `ALLOW_ALL` grant does. *Verify*: a user holding `ALLOW_DEFAULT` only is denied, on the default branch and on another branch; a user holding `ALLOW_OTHER` only is denied; `ALLOW_ALL` succeeds; separate `ALLOW_DEFAULT` and `ALLOW_OTHER` grants succeed.

### Key Entities

No new entities, no schema change, no migration.

- **CoreGenericRepository / CoreRepository / CoreReadOnlyRepository**: Branch-agnostic at node level, so the repository is visible from every branch. `name`, `description`, `location` and `operational_status` are branch-agnostic and read once.
- **`commit`, `sync_status`, `internal_status`**: Branch-local attributes on CoreRepository, read per branch.
- **`commit`, `ref`**: Branch-aware attributes on CoreReadOnlyRepository, read per branch.
- **Branch**: A standard (non-schema) node. Joined to repository attribute edges only by name. Supplies the row identity, the branch-level row fields (`name`, `status`, `is_default`, `branched_from`) and the row-set criterion `sync_with_git`.
- **Not an entity here: the remote head.** It is not in the graph, so it cannot be a row value of this query. It reaches the same card through the sibling PRD's worker read.

### Design Consequences (from the PRD)

These are constraints the PRD established by verifying the codebase. They bound the planning phase rather than prescribe it.

- **Prior art for the grouped read**: the diff count query pattern already reads one statement over a branch-name list and groups on the edge's branch, with a Python-side backfill for branches that produced no rows. The database validation module already resolves per-branch visibility with branch-level ordering and a `branched_from` fallback.
- **The node manager cannot serve this.** It keys nodes by uuid and attributes by node and name, so one repository yields one node object even when read branch-agnostically. The branch is projected at the query layer and discarded at the manager layer.
- **Two resolver shapes.** Paginating branches first and then reading attributes works while every filter is a branch property. Once FR-013 or FR-014 is in play, the attribute read must run over all in-scope branches and pagination applies after it, or the page boundaries and the count are wrong. Both paths satisfy FR-007.
- **The git-derived column cannot be a filter here.** A value the graph does not hold cannot narrow, order or count the row set without reading every in-scope branch from outside the graph, which would put a worker round trip on the critical path of every page view and violate FR-015. Displaying drift works (sibling PRD P3); querying by drift does not, and needs a stored per-branch upstream commit (Out of Scope).
- **Reused plumbing**: the existing paginated branch list's query, filter dataclass, metadata order input and global-branch exclusion. Only a `sync_with_git` filter is missing from the branch list filters.
- **Reused GraphQL types**: the existing `Dropdown` and `TextAttribute` types produce the same TS types the existing table cells already consume. They carry inherited fields (`permissions`, `is_from_profile`, `source`, `owner`) that will always resolve to null here. Accepted, since `updated_at` from the same interface is wanted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can determine the import status and imported commit of every branch of a repository without opening another branch or a worker log.
- **SC-002**: The number of database queries to serve a page is identical at 5 branches and at 200, asserted by instrumentation. The pattern being replaced differs by a factor of 40 across those two fixtures.
- **SC-003**: An operator can isolate the failing branches of a 200-branch repository in one request, filtered and counted server-side.
- **SC-004**: The periodic sync's per-cycle repository read no longer issues one query per branch.
- **SC-005**: No new node kind, no new attribute, no migration, and no new write to any repository attribute.
- **SC-006**: Adding a future per-branch attribute (such as a stored upstream commit or a last-import timestamp) costs one field on the row type and one name in the caller's attribute set, with no change to the connection contract.
- **SC-007**: Every supported query document is served with zero message-bus sends and no dependency on a task worker.

### Behaviour Pinned by Test

- A freshly created branch that syncs with git reports the default branch's fork-point commit, not an empty value.
- After the default branch imports a newer commit, an untouched branch still reports the fork-point commit, and reports the newer one after a rebase.
- Every supported document produces zero message-bus sends.
- The query count is equal at 5 and 200 branches.
- A user holding `ALLOW_DEFAULT` only is denied whichever branch the query is issued against; `ALLOW_ALL` succeeds; separate `ALLOW_DEFAULT` and `ALLOW_OTHER` grants succeed.

## Constitution Alignment

- **II. Branch-Safe by Default**: read-only, writes nothing, so no merge behaviour to specify. The one branch-semantics risk, inheritance through `branched_from`, is pinned by tests rather than described in prose.
- **III. Type Safety & Explicit Contracts**: typed GraphQL fields reusing the existing attribute types; the primitive's branch list and attribute set are explicit parameters.
- **IV. Test Discipline**: inheritance behaviour and the query-count invariant are both asserted by instrumentation, not assumed.
- **V. Query Performance & Efficiency**: the point of the slice. Query count independent of branch count for the read path, selection-aware attribute reads, optional count, and it removes an existing per-branch loop rather than adding one.
- **VII. Simplicity & Maintainability**: no schema, no migration, no new status value, and it reuses the existing branch-list plumbing and the existing grouped-read pattern rather than adding parallel mechanisms.

## Governance Gates

| Gate | Status |
| --- | --- |
| Database schema or migration | Ruled out. Nothing added, nothing written. |
| GraphQL schema modification | Requires sign-off. One additive hand-written query plus its types, and a `sync_with_git` filter on the existing branch filters. |
| New dependencies | None. |
| CI/CD workflow changes | None. |
| Authentication / authorization | Requires sign-off. No new permission is defined, but the enforcement is new: the permission checker pipeline cannot see a hand-written root field, so the check moves into the resolver, and this is the first read to require a decision covering both the default branch and other branches. Both are precedents a reviewer should see. |

Not on that list but with comparable reach: the sync job's read path changes. The per-branch repository read feeds the once-a-minute sync, so its refactor (User Story 2) should be its own reviewed change with the query-count assertion attached.

## Assumptions

- Repository nodes are branch-agnostic, so every branch sees the repository and the row set is genuinely "branches", not "branches where the repository exists".
- The in-memory branch registry already holds every branch, so the branch page is a standard-node read with no extra machinery.
- A branch-local attribute on a branch-agnostic node is created on the global branch, so the "never written anywhere" fallback is the global value rather than a walk through the default branch's history.
- The frontend can feed the existing table shell and dropdown cell from a hand-written query.
- The Branches card is assembled from this query plus, once the sibling PRD's P3 lands, a git-derived column on a separate data path. This contract stands whether or not that column exists.
- The `limit` default of 40 follows the existing paginated list convention in the GraphQL API.
- The chunk size used by the periodic sync (FR-010) is a configured constant; its value is a planning decision, not a product one.
- Code references in the PRD point at `develop` as of 2026-09-02. Line anchors will drift.

## Out of Scope

- Upstream commit and "N behind", and any live git read. Displaying them on this card is the sibling PRD's P3, which reads the remote head from a task worker's local copy and needs nothing from this feature beyond the rows. Querying by them (filtering, ordering or counting branches by drift) requires a stored per-branch upstream commit that no PRD yet owns. SC-006 keeps that cheap to add later.
- A per-branch last-import timestamp. It would be a new attribute written by the importer, a separate effort. This query will surface it once it exists. Attribute `updated_at` comes along with the reused attribute types and MUST NOT be wired to a "Last import" column, because on an inherited row it is the default branch's write time.
- `import_error` and `activity` attributes, and any new status value.
- The Commits tab and the commit log (sibling PRD).
- The global branches view and extra columns on it, including the branch-linked-to-several-repositories question.
- Gating merges on branch state (INFP-670).
- Renaming `sync_status`, and any change to what its values mean.
- Repairing the create-branch-over-existing-remote-branch inaccuracy.

## Open Questions

None block this feature. One belongs to the pair of PRDs rather than to either: does the Branches card fetch the git-derived drift column in a second request, or does a resolver fan out to a worker for it? Either satisfies FR-015, since neither changes this query's contract. Decision (2026-09-03): the card is built without the drift column for now; the column is added when the sibling PRD's P3 settles its data path.
