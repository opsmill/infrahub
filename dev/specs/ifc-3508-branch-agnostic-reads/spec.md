# Feature Specification: Branch-Agnostic Reads That Return the Right Branch's Data

**Feature Branch**: `branch-agnostic-reads`

**Created**: 2026-10-30

**Status**: Draft

**Jira**: [IFC-3508](https://opsmill.atlassian.net/browse/IFC-3508)

**Input**: User description: "`branch-agnostic-wip/brief.md` and associated docs". The brief records decisions settled in a review session on 2026-10-29 and 2026-10-30, after an audit of every branch-agnostic read (`branch-agnostic-wip/audit-report.md`, tests in `branch-agnostic-wip/audit-tests/`). Neither file is committed.

## Background

Some data in Infrahub is branch-agnostic: accounts, account groups, global permissions, number pools, IP prefix pools, IP address pools and the validators of a proposed change exist once and are the same on every branch. Some relationships are branch-agnostic too, for example the `resources` and `ip_namespace` of an IP pool and the `definition` of an artifact or generator validator. These link a branch-agnostic node to branch-aware nodes that may exist on any branch.

When Infrahub needs one answer across every branch, it runs a branch-agnostic read. That read accepts edges from every branch at once and picks the newest edge by comparing edges from different branches. After a node, a link or a value changes on one branch, the read picks the edge of the wrong branch:

- A node deleted on branch B is hidden on the default branch too, because B's `deleted` edge outranks the default branch's `active` edge.
- A value or node that the default branch removed after branch B was created disappears for B too, although B still holds it.
- A value set on an unmerged branch replaces the default branch's value in a read on the default branch.

Some callers run a branch-agnostic read although they need the default branch's answer, and some writes leave a `-global-` edge and a branch edge of the same type between the same two vertices. The audit found 46 component tests that fail on the current code. The most severe effects are a change on a branch that grants or removes global permissions on every branch, and duplicate allocations from IP pools.

The work ships as seven pull requests. User Stories 1 to 6 are PRs 1 to 6, numbered to match. PR 7 adds the `active_on_branches` field of User Story 6 (FR-041 and FR-042).

| PR | User story | Base branch | Depends on |
|---|---|---|---|
| 1 | Global permissions follow the default branch | `stable` | Nothing |
| 2 | Reads of `-global-` data leave the branch-agnostic path | `release-1.12` | Nothing |
| 3 | IP pools never hand out a value still in use on a live branch | `release-1.12` | Nothing |
| 4 | Deleting a branch-agnostic node checks every live branch | `release-1.12` | PR 3 |
| 5 | Reads never return a deleted peer, and no link mixes `-global-` and branch edges | `release-1.12` | PR 3, and PR [#11220](https://github.com/opsmill/infrahub/pull/11220) merged into `release-1.12` |
| 6 | Branch-agnostic relationships return every live peer, with values from one branch | `release-1.12` | PR 5 |
| 7 | Peers read through a branch-agnostic relationship report the branches they exist on (User Story 6) | `release-1.12` | PR 6 |

PR 6 also carries two parts of User Story 5: FR-023 and the removal of shape 2 pairs (FR-025). Both make a read on a branch return a peer that the branch deleted, which works only once PR 6 builds that peer from its chosen branch (research R13).

PRs 1 and 3 fix the effects users are most likely to hit and do not wait for PR #11220.

## Terms

- **Live branch**: a branch that is not `-global-` and whose status is not `DELETING`. Merged branches stay live until they are deleted or rebased.
- **Branch window**: the edges one live branch reads. A window holds the branch's own edges and its origin branch's edges up to the time the branch was created, capped at the read time. Every window includes `-global-` edges. `-global-` has no window of its own.
- **Latest edge in a window**: an `active` edge visible in the window that no other edge of its competing group outranks. An edge outranks another when it has a higher `branch_level`, or the same `branch_level` and a later `from`.
- **Exists on a branch**: the node's latest `IS_PART_OF` edge in that branch's window is `active`.
- **Read across branches**: a read matches a node when, in at least one live branch's window, the latest edges along the path are active and lead to the value.

## Clarifications

### Session 2026-10-30

- Q: Where does the peer existence check (FR-018) apply, given that the retirement check closes a branch-agnostic relationship's `-global-` link once no live branch holds both ends? → A: Only on branch-aware relationships whose peer kind is branch-agnostic or a generic with a branch-agnostic implementation, on reads on one branch and on branch-agnostic reads. A branch-agnostic relationship gets no check on any read: it returns a peer while its `-global-` link is open, including on a branch that deleted the peer.
- Q: What data does Infrahub hold after a branch-aware node with a branch-agnostic relationship is deleted on one branch? → A: The node's `IS_PART_OF` edge is `deleted` on that branch, and no edge is written on that branch for the branch-agnostic link. The `-global-` link stays `active`, and the node is returned as a peer of the relationship on every branch, until the node exists on no live branch and the retirement check closes the link (FR-023).
- Q: Should this feature add an `active_on_branches` data point, and where? → A: Yes. Add `active_on_branches: [String!]` to `InfrahubNodeMetadata`, filled for peers returned through a branch-agnostic relationship and for nodes from other branch-agnostic reads, and `null` elsewhere. It is computed only when requested, and ships as its own PR after PR 6 (FR-041, FR-042).
- Q: What does this feature add for attributes? → A: Nothing. The branch a peer's values come from follows from `active_on_branches` and the order of FR-029. A list of branches per attribute is out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Global permissions follow the default branch (Priority: P1)

An administrator manages accounts, account groups, roles and global permissions. A change made on a branch to group membership, to the roles of a group or to the permissions of a role must not change anyone's global permissions until the branch is merged. Today such a change applies on every branch at once, including the default branch: a user who may manage accounts can add themselves to an administrator group on a branch and receive `super_admin` everywhere.

With this change, global permissions, the role list returned at login and the single sign-on group member check read the default branch, combined with `-global-`, whatever branch the request is on. Object permissions keep reading the request branch, as they do today.

**Why this priority**: it is a privilege escalation that needs no review and no merge. It is the highest-severity effect the audit found.

**Independent Test**: on branch B, add an account to a group whose role holds `super_admin`. Load the account's global permissions on the default branch and on B. Both return no `super_admin` until B is merged.

**Acceptance Scenarios**:

1. **Given** an account is added on branch B to a group whose role holds `super_admin`, **When** the account's global permissions are loaded on the default branch or on B, **Then** neither includes `super_admin`.
2. **Given** a global permission is linked to a role on branch B, **When** permissions are loaded on B, **Then** they include only the permissions linked on the default branch.
3. **Given** an account is removed from a group, a role is removed from a group, a role is deleted, or a permission is removed from a role on branch B, **When** permissions are loaded on the default branch, **Then** they still include the permission granted on the default branch.
4. **Given** a user with `MANAGE_ACCOUNTS` but without `EDIT_DEFAULT_BRANCH` adds themselves to an administrator group on branch B, **When** they send a `BranchMerge` for B to B's GraphQL endpoint, **Then** the merge is refused.
5. **Given** a role is removed from a group on branch B, **When** the account logs in, **Then** the login response still lists the role.
6. **Given** the change on branch B is merged into the default branch, **When** permissions are loaded on any branch, **Then** they include the change.
7. **Given** an account that holds `super_admin` only through a group membership added on branch B, **When** it sends a mutation that changes an account to B's GraphQL endpoint, **Then** the mutation is refused, because accounts are branch-agnostic and the change would apply on every branch.

---

### User Story 2 - Reads of `-global-` data leave the branch-agnostic path (Priority: P3)

Several callers run a branch-agnostic read on data that has edges only on `-global-`: branch-agnostic nodes read through branch-agnostic links. A normal read on any branch returns the same result for them, at the cost of a single-branch read. These callers stop running a branch-agnostic read. What a user views does not change.

The callers are the account loader of the GraphQL API, the external identity read by account, the webhook invalidation by key-value, the number pool synchronizer and upserter, the conflict recorder of proposed change validations, and the migration that recomputes global permission display labels.

**Why this priority**: there is no wrong result to fix. It keeps these reads off the slower branch-agnostic path that later stories change.

**Independent Test**: the existing tests of each caller pass unchanged.

**Acceptance Scenarios**:

1. **Given** any of the listed callers, **When** it runs on any branch, **Then** it returns the same result as before the change.

---

### User Story 3 - IP pools never hand out a value still in use on a live branch (Priority: P1)

A network engineer allocates prefixes and addresses from IP prefix pools and IP address pools while several branches are open. An allocation must never return a prefix or address that any live branch still holds. Today two cases return a value that is in use:

- A prefix or address allocated on the default branch, then deleted there after branch B was created, is allocated again on B while B still holds it.
- When the pool's namespace is deleted on branch B, the pool on the default branch treats the whole range as free.

Allocation on a branch also uses only the namespace and resources that exist on that branch, because the allocated prefix or address is created on that branch and must point at nodes that exist there. When they do not exist, the allocation fails with an error that says why.

Number pools are already correct on `release-1.12`. This story moves them onto the same shared branch window logic as the IP pools, with no change in what they allocate.

**Why this priority**: a duplicate IP allocation reaches devices and is hard to notice. Any IP pool user can hit it by deleting an allocated value on the default branch while an older branch is open.

**Independent Test**: allocate a prefix on the default branch, create branch B, delete the prefix on the default branch, then allocate on B. The allocation returns a different prefix.

**Acceptance Scenarios**:

1. **Given** a prefix (or address, IPv4 or IPv6) allocated on the default branch and deleted there after branch B was created, **When** the pool allocates on B, **Then** it does not return that prefix (or address).
2. **Given** a pool's namespace deleted on branch B, **When** the pool allocates on the default branch, **Then** it does not return a prefix or address that the default branch already holds.
3. **Given** a pool whose namespace exists only on branch B, **When** the pool allocates on the default branch, **Then** the allocation fails with an error that names the pool, the namespace and the default branch.
4. **Given** a pool none of whose resources exist on the allocating branch, **When** the pool allocates there, **Then** the allocation fails with an error that names the pool and the branch.
5. **Given** a pool with some resources that exist on the allocating branch and some that do not, **When** the pool allocates, **Then** it allocates only from the resources that exist on that branch.
6. **Given** a namespace, a prefix and a pool linked to them, all created on branch B, **When** the pool allocates on B, **Then** it succeeds; **and when** B is merged, **Then** the pool also allocates on the default branch.
7. **Given** number pools, **When** the existing number pool tests and the audit's number pool tests run, **Then** they all pass.

---

### User Story 4 - Deleting a branch-agnostic node checks every live branch (Priority: P2)

An administrator deletes a branch-agnostic node, for example an account group. The node disappears on every branch at once. The delete must be refused when it would break a constraint on any live branch, not only on the branch the request was sent to. Today the check runs on the request branch only.

**Why this priority**: without it, a delete on the default branch leaves a required relationship empty on another branch, and a later read on that branch fails.

**Independent Test**: on the default branch, link P to G1 through a required relationship; create branch B; on the default branch, move P to G2 and delete G1. The delete is refused and the error names B and P.

**Acceptance Scenarios**:

1. **Given** a peer on branch B has a required relationship to the node, and the peer is not also being deleted, **When** the node is deleted on the default branch, **Then** the delete is refused and the error names B and the peer.
2. **Given** P reaches the node on branch B only through the default branch's edge from before B was created, and B wrote nothing, **When** the node is deleted on the default branch, **Then** the delete is refused.
3. **Given** a peer would be removed through `on_delete=cascade` on branch B but not on the request branch, **When** the node is deleted, **Then** the delete is refused and the error names B and the peer.
4. **Given** no live branch would break a constraint, **When** the node is deleted, **Then** the delete succeeds and cascading deletes write only on the request branch.
5. **Given** a branch-aware node, **When** it is deleted, **Then** the check behaves as it does today.

---

### User Story 5 - Reads never return a deleted peer, and no link mixes `-global-` and branch edges (Priority: P2)

A user reads a branch-aware relationship whose peer kind is branch-agnostic, or a generic with a branch-agnostic implementation. For example, an account role's `groups` after a group was deleted. The read must return a peer only if the peer exists in the read's view: the request branch for a normal read, and each live branch's window for a branch-agnostic read.

A branch-agnostic relationship, such as a pool's `resources`, needs no such check. Its link is on `-global-`, and the retirement check closes the link once no live branch holds both ends. While the link is open, the peer exists on at least one live branch, and User Story 6 returns it on every branch, including a branch that deleted it.

Two kinds of write today leave a `-global-` edge and a branch edge of the same type between the same two vertices, which no read can rank correctly:

- Deleting a branch-agnostic node writes a `-global-` `deleted` edge on its branch-aware links.
- Deleting a branch-aware node on a branch writes a branch `deleted` edge on its branch-agnostic relationships.

After PRs 5 and 6, no pair of vertices holds both a `-global-` edge and a branch edge of the same type. The deletes write the edges below, and two graph migrations convert or remove the existing pairs: PR 5 converts the first kind and PR 6 removes the second. Every read gives the same answer before and after the migration, at every point in time.

**Why this priority**: it fixes the GraphQL error a user receives when reading `CoreAccountRole.groups` after a group was deleted.

**Independent Test**: on the default branch, link a role to group G1; create branch B; remove the role from G1 on the default branch; delete G1. On both branches, reading the role's groups does not return G1 and raises no error.

**Acceptance Scenarios**:

1. **Given** a branch-agnostic node deleted after branch B was created, and a link to it removed on the default branch after B was created, **When** the link is read on the default branch or on B, **Then** it is not returned on either.
2. **Given** a prefix in a pool's `resources` deleted on every live branch, **When** the pool's `resources` are read on any branch, or a list is filtered through them, **Then** the prefix is not returned or matched, because the retirement check closed the `-global-` link.
3. **Given** a branch-aware node deleted on branch B with a branch-agnostic relationship to another node, **When** the node is deleted, **Then** no edge is written on B for that relationship, and the `-global-` link stays open while the default branch holds the node. This scenario ships in PR 6.
4. **Given** a branch-agnostic node deleted on the default branch, **When** its branch-aware links are inspected, **Then** each link is closed on the default branch when its latest default-branch edge is `active`, a `deleted` edge is written on each user branch whose own latest edge for the link is `active`, and nothing is written on `-global-` or on branches that only inherited the link.
5. **Given** a database with links that hold both a `-global-` edge and a branch edge of the same type, **When** the migration runs, **Then** reads at several timestamps return the same results before and after, and no pair of either known shape remains.
6. **Given** a pair of vertices that holds mixed edges in neither known shape, **When** the migration runs, **Then** the pair is not changed and the migration logs how many such pairs it found.
7. **Given** a relationship between two branch-aware kinds that is not branch-agnostic, **When** it is read, **Then** the read is unchanged.
8. **Given** a branch-agnostic node deleted on the default branch while branch B only inherited a link to it, **When** B is rebased, **Then** the link is closed on B and B writes no edge of its own for it.
9. **Given** the same situation, **When** B is merged instead, **Then** the merge writes nothing for the link.
10. **Given** a link that branch B added to a branch-agnostic node, and that B lost when the node was deleted, **When** B is merged, **Then** the default branch has no active link.

---

### User Story 6 - Branch-agnostic relationships return every live peer, with values from one branch (Priority: P2)

A user reads a branch-agnostic relationship, for example the `resources` of an IP prefix pool or the `definition` of a validator in a proposed change. The relationship returns every peer that is linked and exists on at least one live branch, whichever branch the read is sent to. This is what `stable` already does. What the audit found wrong is which edge wins after a peer, a link or a value changes on one branch.

Each returned peer shows all of its values from one branch, chosen in this order:

1. the request branch, when the peer exists there;
2. the default branch;
3. the other live branches, ordered by name.

`-global-` is never chosen. A peer never combines values from several branches. The node object returned for the peer belongs to the chosen branch, so its later reads and saves use that branch.

Adding a link on a branch-agnostic relationship is refused only when the peer is deleted on every live branch. Saving a branch-agnostic relationship finds the current peers with the same rule, so replacing the peer of a cardinality-one relationship removes the previous peer.

**Why this priority**: the core schema has few branch-agnostic relationships, and the effects need a change on one branch while another is open. The cause of [IFC-3444](https://opsmill.atlassian.net/browse/IFC-3444) (a user check skipped because its definition was deleted on another branch) is one of these effects.

**Independent Test**: link gadget G to widget W through a branch-agnostic relationship, delete G on branch B, and read W's gadgets on the default branch: G is returned. Rename G on B and read W's gadgets on the default branch: G shows the default branch's name.

**Acceptance Scenarios**:

1. **Given** a peer deleted on branch B but still existing on the default branch, **When** the relationship is read on the default branch or on B, **Then** the peer is returned.
2. **Given** a peer deleted on the default branch after branch B was created, **When** the relationship is read on B, **Then** the peer is returned.
3. **Given** a peer whose name was changed on branch B, **When** the relationship is read on the default branch, **Then** the peer shows the default branch's name; **and when** peers are ordered by name on the default branch, **Then** they are ordered by the default branch's names.
4. **Given** a node that exists only on two older branches, **When** it is reached through a branch-agnostic read, **Then** all its values come from the branch whose name sorts first.
5. **Given** a cardinality-one relationship of a peer changed on the default branch after branch B was created and also on B, **When** the peer is read, **Then** exactly one related node is returned and no error is raised.
6. **Given** a branch-agnostic node reached through a branch-agnostic read, **When** its branch-aware `roles` are read, **Then** they are the roles linked on the request branch.
7. **Given** a peer that exists on the default branch but was deleted on branch B, **When** a link to it is added on the default branch, **Then** the link is saved.
8. **Given** a peer deleted on every live branch, **When** a link to it is added, **Then** the link is refused.
9. **Given** a cardinality-one branch-agnostic relationship whose peer G was deleted on branch B, **When** the peer is replaced with G2 on the default branch, **Then** a read on the default branch returns only G2.
10. **Given** a plain list query of the peer's kind on the default branch, **When** a peer exists only on branch B, **Then** the list does not include it.
11. **Given** a prefix in a pool's `resources` deleted on branch B and still existing on the default branch, **When** the pool's `resources` are read on B with `node_metadata { active_on_branches }`, **Then** the prefix is returned and `active_on_branches` lists the default branch and not B.
12. **Given** a relationship that is not branch-agnostic, **When** its peers are read with `node_metadata { active_on_branches }`, **Then** the field is `null`.

### Edge Cases

- A merged branch that is not deleted or rebased stays live, so a value it still holds stays taken in every pool and a peer it still holds is still returned.
- A branch whose status is `DELETING` is never live: its values are free and its peers are not returned.
- A pool namespace that cannot be read on the allocating branch for any reason fails the allocation with the named error; the allocation never treats the whole range as free.
- A branch-agnostic node always exists on every live branch, because its `IS_PART_OF` edge is on `-global-`, so it always takes its values from the request branch.
- A rebase of branch B moves B's fork point past the default branch's `deleted` edge, so a link closed on the default branch also closes on B. A merge of B carries nothing for a link B only inherited.
- The number of edges written when a branch-agnostic node is deleted depends on how many branches changed a link to the node, not on how many branches are open.
- Reads that are not branch-agnostic, between branch-aware kinds, keep their current query and cost.

## Requirements *(mandatory)*

### Functional Requirements

**Global permissions (User Story 1)**

- **FR-001**: Infrahub MUST compute an account's global permissions, and the permissions of the anonymous role, from the default branch combined with `-global-`, whatever branch the request is on.
- **FR-002**: The role list returned at login and the single sign-on group member check MUST read the default branch combined with `-global-`.
- **FR-003**: Object permissions MUST keep reading the request branch.
- **FR-004**: A `BranchMerge` sent to a branch's own GraphQL endpoint by a user who gained administrator rights only on that branch MUST be refused.

**Reads of `-global-` data (User Story 2)**

- **FR-005**: Callers that read only branch-agnostic nodes through branch-agnostic links MUST read without the branch-agnostic flag and return the same results as before.

**Pools (User Story 3)**

- **FR-006**: A pool MUST treat a value as taken while any live branch holds it, including through the value's `IS_PART_OF` edge.
- **FR-007**: A pool MUST decide whether its namespace exists per live branch, so that a namespace deleted on one branch does not free the range on another.
- **FR-008**: Allocation on branch X MUST use only the pool's namespace and resources that exist on X.
- **FR-009**: When the pool's namespace does not exist on X, allocation MUST fail with an error that names the pool, the namespace and X.
- **FR-010**: When none of the pool's resources exist on X, allocation MUST fail with an error that names the pool and X.
- **FR-011**: A pool's links to its namespace and resources MUST stay valid while the peer exists on at least one live branch.
- **FR-012**: Number pools MUST use the same branch window logic as IP pools, with no change in the values they allocate or report as used.
- **FR-013**: Infrahub MUST have one shared definition of a branch window, used by pools, by the retirement check of branch-agnostic fields and by every read across branches.

**Deleting a branch-agnostic node, the check (User Story 4)**

- **FR-014**: Before deleting a branch-agnostic node, Infrahub MUST check every live branch and refuse the delete when, on any branch, a peer with a required relationship to the node is not also being deleted, or a peer would be removed through `on_delete=cascade` there but not on the request branch.
- **FR-015**: The error MUST name each branch and each peer that blocks the delete.
- **FR-016**: The check MUST write nothing, and cascading deletes MUST write only on the request branch.
- **FR-017**: The check for a branch-aware node MUST be unchanged.

**Peer existence and edges between the same two vertices (User Story 5)**

- **FR-018**: A read that follows a branch-aware relationship MUST return a peer only if the peer exists in the read's view, when the peer kind is branch-agnostic or a generic with a branch-agnostic implementation. A branch-agnostic relationship gets no such check: it returns a peer while its `-global-` link is open, and the retirement check closes the link once no live branch holds both ends (FR-023, FR-028). This applies to peer reads and their counts, node list prefetches of relationships, peer id lists, filters and ordering through relationships, reads of one relationship by identifier, and every other read of `IS_RELATED` edges that research R6 lists as affected.
- **FR-019**: The peer existence check MUST use the same definition of a live peer as the retirement check of branch-agnostic fields.
- **FR-020**: Reads of relationships that are not branch-agnostic, between branch-aware kinds, MUST be unchanged, except the peer id list of FR-040, which is corrected for every read.
- **FR-021**: Deleting a branch-agnostic node MUST, for each branch-aware link and for its `IS_PROTECTED`, `HAS_OWNER` and `HAS_SOURCE` edges: close the link on the default branch when the default branch's latest edge is `active`; write a `deleted` edge on each user branch whose own latest edge is `active`; and write nothing on `-global-` or on branches that only inherited the link.
- **FR-022**: When choosing the latest edge of a link to delete, Infrahub MUST rank by `branch_level` first, then by `from`.
- **FR-023**: Deleting a branch-aware node on any branch, including the default branch, MUST NOT write branch edges on its branch-agnostic relationships. The `-global-` link MUST close through the retirement check once no live branch holds both ends. This requirement ships in PR 6.
- **FR-024**: No pair of vertices may hold both a `-global-` edge and a branch edge of the same type, for `IS_RELATED`, `IS_PROTECTED`, `HAS_OWNER` and `HAS_SOURCE`.
- **FR-025**: A graph migration MUST convert the existing `-global-` `deleted` edges on branch-aware links into what the new delete writes, keeping the original `from`, and MUST remove the existing `deleted` edges on the default branch or a user branch on branch-agnostic relationships, whether a delete or a merge wrote them. It MUST log the count of mixed pairs that match neither shape and leave them unchanged. The conversion of shape 1 ships in PR 5 and the removal of shape 2 in PR 6.
- **FR-026**: Every read MUST give the same answer before and after the migration, at every point in time.
- **FR-027**: The internal documentation of the database schema MUST state the rule of FR-024, the peer existence check, and that a branch-agnostic relationship has no branch edges.

**Branch-agnostic relationship reads (User Story 6)**

- **FR-028**: A branch-agnostic read of a relationship, and its count, MUST return a peer when the link and the peer exist on at least one live branch.
- **FR-029**: Each peer MUST take all its attribute values, cardinality-one peers, ordering values and `created_at`/`updated_at` metadata from one branch: the request branch when the peer exists there, otherwise the default branch, otherwise the first other live branch by name. `-global-` MUST never be chosen.
- **FR-030**: The node object built for a peer MUST belong to the chosen branch.
- **FR-031**: Adding a link on a branch-agnostic relationship MUST be refused only when the peer is deleted on every live branch.
- **FR-032**: Saving a branch-agnostic relationship MUST read its current peers with the rule of FR-028 and close the `-global-` link of a peer it replaces.
- **FR-033**: A branch-agnostic list query of nodes MUST match a node that exists on at least one live branch, and MUST return a node merged from a branch once.
- **FR-034**: A plain list query of a branch-aware kind MUST keep following the request branch.
- **FR-038**: A branch-agnostic lookup by HFID, and a branch-agnostic filter on a list query or on a relationship's peers, MUST match a node when, in at least one live branch's window, the latest edges along the path are active and lead to the value.
- **FR-039**: Filters on a read on one branch MUST NOT cost more database hits than they do once PR #11220 is merged.
- **FR-041**: The GraphQL type `InfrahubNodeMetadata` MUST have a field `active_on_branches: [String!]`. For a peer returned through a branch-agnostic relationship, and for a node returned by another branch-agnostic read, it MUST list the names of the live branches on which the node exists, sorted by name. For every other node it MUST be `null`.
- **FR-042**: `active_on_branches` MUST be computed only when the query requests it. A query that does not request it MUST keep its database hits.

**Peer id list for object conversion (User Story 5)**

- **FR-040**: The peer id list used to validate an object conversion MUST NOT include former peers, on any read.

**Every PR**

- **FR-035**: Each PR MUST include a component test that fails on the current code and passes with the fix, moved from the audit tests where one exists.
- **FR-036**: Each PR that changes a query MUST report the database hits of the affected read paths before and after the change, measured with Neo4j `PROFILE`.
- **FR-037**: Each change a user can notice MUST have a changelog fragment.

### Key Entities

- **Branch window**: the set of edges one live branch reads at a given time; defined under Terms.
- **Link**: the `Relationship` vertex between two nodes with its `IS_RELATED` edges and its `IS_PROTECTED`, `HAS_OWNER` and `HAS_SOURCE` edges.
- **Mixed pair**: two vertices joined by both a `-global-` edge and a branch edge of the same type. Two known shapes: a `-global-` `deleted` edge on a branch-aware link, and a branch `deleted` edge on a branch-agnostic relationship.
- **Chosen branch**: the one branch from which a peer reached through a branch-agnostic read takes all its values.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After PRs 1 to 6, every failing test from the audit passes. That is 46 tests on the audited commit, or the adapted count where `release-1.12` already fixes a case. The 7 control tests still pass. This holds after the assertion changes the brief lists, and after any other assertion that a decision of the brief changes; each such change is recorded in the PR description.
- **SC-002**: No change made on an unmerged branch alters the global permissions of any account, in any of the 10 permission scenarios of the audit.
- **SC-003**: No IP pool allocation returns a prefix or address held by a live branch, in any of the 8 IP pool scenarios of the audit, for IPv4 and IPv6.
- **SC-004**: Reads of relationships between branch-aware kinds that are not branch-agnostic show the same number of database hits before and after, on the same data set.
- **SC-005**: After the migration, zero mixed pairs of the two known shapes remain, and reads at several timestamps return identical results before and after.
- **SC-006**: Each PR description reports the database hits of the affected read paths before and after: reads of relationships to branch-agnostic kinds, reads of group members, branch-agnostic reads with many live branches, deleting a branch-agnostic node with many live branches, and IP pool allocation with many live branches and past allocations.

## Assumptions

- The branch support of a node, attribute or relationship cannot change after the schema is first loaded.
- Merge and rebase do not write `-global-` edges.
- A link on a branch-agnostic relationship is always written on `-global-`, including from a mutation on a branch. The one exception today, the delete on a branch, is removed by FR-023, which ships in PR 6.
- A normal read on a user branch already includes `-global-` edges up to the read time, so a change on `-global-` is visible on every branch at once.
- PR [#11220](https://github.com/opsmill/infrahub/pull/11220) stays as it is and is not ported to `release-1.12`. PRs 5 and 6 start only after it is merged into `stable` and then into `release-1.12`.
- The earlier branch-agnostic code at commit `7015435c4` (local branch `branch-agnostic-source`) holds the window helpers, the rewrite of the list filter and the branch-agnostic lookup by HFID. PRs 3, 5 and 6 bring it in; it is not cherry-picked as a whole.
- Branch-agnostic reads are uncommon, so a slower branch-agnostic path is acceptable if it returns correct results. Reads on one branch must not get slower.
- The check before deleting a branch-agnostic node uses the request branch's schema for every live branch. A branch whose schema made a relationship required or optional differently is checked with the request branch's rule. This is a known limit.
- How PR 1 is disclosed is decided outside this specification. Every PR is planned as a normal PR.
- The graph migration is a database migration, which needs explicit approval. The plan was approved in the review session; the code still needs review. Removing edges is a hard delete, which the constitution allows only for branch deletion; PR 5 records an explicit exception, because the removed edges break the edge constraints of the database schema and the replacement edges keep the history.

## Open Questions

These come from the brief and stay open. Each one blocks only the tasks that depend on it. When implementation reaches such a task, it stops and asks.

1. **Does a merge copy a branch `deleted` edge on a branch-agnostic relationship to the default branch?** This decides whether the migration's second shape also removes edges on the default branch. To check in PR 6.
2. **How does the default branch close a link when a branch-agnostic node is deleted?** The database schema documentation says closing an edge on the same branch only sets `to`. The current delete both sets `to` and writes a `deleted` edge. The new delete and the migration must follow one of the two on the default branch.
3. **Does any caller save a peer obtained through a branch-agnostic read?** This decides whether saving a node object built on the chosen branch needs a guard. To check in PR 6.

## Out of Scope

- How PR 1 is disclosed.
- A force delete of a branch-agnostic node that cascades to other branches, for when branches still depend on it.
- Whether object permissions granted on a branch allow writes to branch-agnostic kinds.
- Refusing a pool link to a peer that exists on only one branch.
- IP pools that allocate a new value on every call with the same identifier ([IFC-3496](https://opsmill.atlassian.net/browse/IFC-3496)).
- Filters and lookups by value on a branch ([IFC-3488](https://opsmill.atlassian.net/browse/IFC-3488)), which PR #11220 fixes.
- `active_on_branches` for nodes read on one branch through a relationship that is not branch-agnostic.
- A list, per attribute, of the live branches on which the attribute holds the returned value.
