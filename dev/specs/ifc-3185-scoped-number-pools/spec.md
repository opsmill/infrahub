# Feature Specification: Scoped number pools — one pool serves every scope

**Feature Branch**: `feature-number-pools-1.12` (no slice branch created; the user asked for nothing to be committed)

**Created**: 2026-10-02

**Status**: Draft

**Epic**: [IFC-3185](https://opsmill.atlassian.net/browse/IFC-3185) — Number pool improvements, part 3, pool allocation scopes (JPD INFP-308)

**Input**: `SCOPED-POOLS-PRD.md` — "PRD: Scoped number pools — one pool serves every scope", P3 of
the Number Pools PRD, grilled on 2026-10-01 against `feature-number-pools-1.12`. Plus the user's
delivery constraint: publish the GraphQL surface first (mock data where the real reads do not
exist yet), then the utilization and allocation seams, then the internals, so that the frontend is
unblocked as early as possible and the remaining work can be split and run concurrently. Plus the
frontend team's needs for the number pool screens, notes supplied by the user on 2026-10-06, and
the decisions of the grilling session of the same day on the shape of the GraphQL surface.

**Sources of truth**, in order of precedence for P3:

| Precedence | Document |
|-----------|----------|
| 1 | `SCOPED-POOLS-PRD.md` (repo root, 2026-10-01) |
| 2 | [Number Pools - PRD, simple as possible](https://opsmill.atlassian.net/wiki/spaces/Product/pages/870514689) |
| 3 | [Number Pools PRD](https://opsmill.atlassian.net/wiki/spaces/Product/pages/854818817/Number+Pools+PRD) (base PRD, INFP-308) |

Where a lower-precedence document says something this specification does not repeat, it stands.
Where they differ, the higher-precedence document wins and this specification follows it. The
frontend needs and the grilling decisions of 2026-10-06 define the GraphQL surface; the PRDs say
nothing about its shape beyond "agree the per-division read before implementation".

## Frontend needs (input, 2026-10-06)

- Every range of the pool, selectable as "all ranges" or one range. For each range: id, start,
  end, weight and utilization figures.
- Utilization: an unscoped pool reports pool figures; a scoped pool reports one row per division,
  each with the split between the default branch and the other branches.
- A query returning the divisions associated with one range.
- Allocated number rows: count, number, holder (id, hfid, display label, kind), branch and
  provenance. Filters: branch, provenance. Search: dropped for v1.
- Divisions: the complete list with display label, utilization and branch split. No pagination;
  the frontend searches locally.

## Scope

P3 lets a pool say which fields divide its number space, so that one pool serves every site, every
site-and-tenant pair, or whatever the operator names. "The next free number" becomes "the next free
number within the division the node being written belongs to". A pool that names no scope behaves
exactly as it does today. The reads a frontend needs for a number pool, scoped or not, are
published on a GraphQL surface dedicated to number pools; the generic resource-pool queries are
frozen for number pools.

| Slice | Content | In P3 |
|-------|---------|-------|
| P1 | Several weighted ranges per pool, ranges declared in the schema (`dev/specs/ifc-3065-number-pool-ranges`) | Landed in part on this branch: the range kind and its mutations, the migration giving every existing pool one range, the shorthand mirror; allocation over a range set and the shared effective-space calculation have not. Consumed, not changed |
| P2 | Numbers a user gives the pool: provide, attach, detach, provenance, attribute-anchored records (`dev/specs/ifc-3184-pool-number-attach`) | In flight; the consolidation journey (User Story 7) waits for it. The provenance P2 specified for the pool queries is carried by this slice's dedicated surface |
| P3 | `allocation_scope` on the pool and in number-pool attribute parameters; per-division allocation and utilization; the dedicated GraphQL surface | Yes |
| Frontend | Scope on the pool form, the range view, the division view, the allocation list | No; the dedicated surface carries everything those screens need, and their migration to it is its own ticket |
| Generic resource-pool queries | `InfrahubResourcePoolUtilization`, `InfrahubResourcePoolAllocated` and their types | Frozen for number pools: shape and meaning unchanged, descriptions gain a note |

### Guiding principles for P3

1. **The scope decides which number comes next, and nothing else.** It never refuses a value,
   never validates one, never arbitrates a duplicate. Whether a value is valid stays with the
   attribute's uniqueness constraints and its own domain.
2. **The pool, its records and its scope are branch-agnostic; the nodes are branch-aware.** Every
   read sits at that seam: a record counts in every division its node occupies on any live
   branch. The pool may waste a number across branches; it can never hand the same number to two
   nodes in one division.
3. **A pool that says nothing changes nothing.** Unscoped pools issue the query they issue today and
   report the figures they report today.
4. **Nothing about a division is stored.** A record's division is derived from its holder's fields
   at read time. Setting, changing or clearing a scope moves no data.
5. **Number-pool reads live on a surface shaped like number pools.** Divisions, the scope in force,
   ranges with absolute figures, holders and provenance are published on
   queries dedicated to number pools, never as number-pool-only arguments or fields on the generic
   queries, which stay as they are.

### Delivery order (user constraint)

The user asked for the work to be sequenced so the frontend is unblocked first and the rest can be
split across people:

1. **Internal schema first**: the `allocation_scope` attribute on the pool kind and the matching
   field in the number-pool attribute parameters, because every generated type derives from them.
2. **The dedicated GraphQL surface next**, with its shapes frozen: utilization with absolute
   figures per pool and per range, the divisions list, the allocation list with holder, provenance
   and range, and the scope in force on the reading branch. Pool, range and allocation data are
   real from the first change set; the divisions of a scoped pool are a deterministic mock until
   the division reads exist. An unscoped pool never returns mock data. The generic queries gain a
   description note and nothing else.
3. **The utilization and allocation seams**: the per-division utilization getter and the
   allocator entry point that takes the writer's division, as seams other work plugs into.
4. **The internals**: the division resolver, the scoped records lookup, division enumeration,
   the validators and the schema-load checker, in parallel once the seams exist.
5. **Mock removal**: the real division reads replace the mock partition in the three queries, the
   mock is deleted, and a test asserts that no mock division is returned.

User Story 1 below is the contract story. Nothing after it may rename, retype or remove a field it
publishes.

## User Scenarios & Testing *(mandatory)*

The priority on each user story is the order in which this slice is built, following the delivery
order above. Every story belongs to slice P3. Throughout, "division" is the tuple of values that
divides a scoped pool's space and "allocation scope" is the pool setting that names the fields.

### User Story 1 - The number-pool GraphQL surface is published and frozen (Priority: P1)

A frontend or SDK consumer reads a pool and views its allocation scope; writes a pool with a scope
through create, update or upsert and reads it back; and builds the pool page, the range view, the
division view and the allocation list from three queries dedicated to number pools:
`InfrahubNumberPoolUtilization`, `InfrahubNumberPoolDivisions` and `InfrahubNumberPoolAllocations`
([contract](./contracts/graphql-number-pool-surface.md)). The generic queries the consumer used
until now keep working unchanged. The shapes are final: later stories replace the mocked divisions
of a scoped pool with real ones but change no field.

**Why this priority**: The frontend and the SDK can only start once the contract exists and will not
move. Publishing it first lets that work and the backend internals proceed concurrently.

**Independent Test**: Export the GraphQL schema and the published attribute-parameter contract,
regenerate the frontend and SDK types, round-trip a scope through the pool mutations, then read the
three queries on an unscoped pool and on a scoped pool and compare them with the contract's
examples.

**Acceptance Scenarios**:

1. **Given** the pool create, update and upsert inputs, **When** `allocation_scope: ["site"]` is
   sent, **Then** the pool saves and reads back `["site"]`; **When** the field is omitted or sent
   empty, **Then** the pool reads back as having no scope.
2. **Given** an unscoped pool with two ranges, **When** `InfrahubNumberPoolUtilization` is read,
   **Then** the result carries `allocation_scope: []`, pool figures with `size`, `used`,
   `used_default_branch`, `used_branches` and the three percentages, one row per range ordered by
   start with id, display label, start, end, weight and the same figures block.
3. **Given** a scoped pool read on a branch whose schema defines every entry, **When**
   `InfrahubNumberPoolUtilization` is read with a `division`, **Then** `allocation_scope` lists the
   entries in force in scope order; read without `division`, **Then** it is refused naming the
   pool and the branch; read on a branch that defines none of them, **Then** `allocation_scope` is
   empty and the figures are pool-wide.
4. **Given** an unscoped pool, **When** `InfrahubNumberPoolDivisions` is read, **Then** it lists
   exactly one division with no entry, an empty display label and figures equal to the pool's;
   **Given** a scoped pool, **Then** it lists every division holding at least one value, with its
   entries (path, value, display label, peer kind), a display label joining the entries' labels,
   and figures over the whole pool, ordered by utilization descending then display label.
5. **Given** a pool tracking values on two branches, one of them provided by a user and held by no
   range, another inside a range but listed in the attribute's excluded values, **When**
   `InfrahubNumberPoolAllocations` is read, **Then** those two values are not listed, and each
   other row carries the value, the branch, the holder (id, hfid, kind, display label read on the
   row's branch), the identifier, the provenance, the range holding it and the holder's division
   (empty on an unscoped pool), ordered by value then branch then holder id and paginated with
   `offset` and `limit`; **When** `branch`, `provenance` or `range_id` is given, **Then** only
   matching rows are returned and `count` reports them before pagination.
6. **Given** a scoped pool, **When** `InfrahubNumberPoolAllocations` is read with a `division`
   filter on a path in force, **Then** only rows whose holder carries the given values are
   returned; **When** `InfrahubNumberPoolUtilization` is read with a `division` giving a value for
   every entry in force, **Then** the pool figures and every range row report that division; **When** that `division` omits an entry in force, **Then** the
   utilization query is refused naming the missing entries; **When** the pool is unscoped, or the
   path is not in force on the reading branch, or a path is given twice, **Then** either query is
   refused naming the pool or the entry.
7. **Given** `pool_id` naming an IP pool, an unknown node, or `range_id` naming a range of another
   pool, **When** any of the three queries is read, **Then** it is refused with the existing
   not-found or validation error naming the id.
8. **Given** a scoped pool at contract time, **When** the three queries are read, **Then** the
   divisions listed, the `division` on each row and the `division` filter agree: every row's
   division is one of the listed divisions, and the `used` figure of a division equals the number
   of distinct values among the rows returned when filtering on it. An unscoped pool returns no
   mock division.
9. **Given** the exported GraphQL schema before and after the contract change set, **When** the
   two are diffed, **Then** the only change to `PoolUtilization`, `PoolAllocated`,
   `PoolAllocatedNode`, `IPPrefixUtilizationEdge`, `IPPoolUtilizationResource` and the two generic
   root fields is description text, and the frontend's existing utilization and allocated queries
   return what they returned before.
10. **Given** the exported GraphQL schema, the OpenAPI schema and the published
    attribute-parameter contract, **When** the generated SDK and frontend types are regenerated,
    **Then** they carry `allocation_scope` on the pool and on number-pool attribute parameters and
    every type of the dedicated surface, with no other change to existing fields.

---

### User Story 2 - One pool, every site, from day one (Priority: P1)

An operator creates one pool scoped by site, and every device in every site gets the lowest number
free within its own site. Adding a site adds no pool. The operator can set, change or clear the
scope at any time without losing what the pool has handed out.

**Why this priority**: This is the capability the slice exists for. Without it an estate of two
hundred sites needs two hundred pools.

**Independent Test**: Create a pool over 1–100 with scope `["site"]`, create devices in several sites
through the ordinary allocation path, and check which numbers come back, on one branch and on two.

**Acceptance Scenarios**:

1. **Given** a pool over 1–100 with scope `["site"]` and nothing allocated, **When** a device in
   site A and a device in site B each allocate, **Then** both receive 1, a second device in A
   receives 2, and a device in a brand-new site C receives 1 with no pool having been created.
2. **Given** the same pool, **When** a device in site A is given the number 1 explicitly with the
   pool named, **Then** it saves and is tracked, and the next allocation in A returns 3. Nothing was
   refused; a uniqueness constraint, if declared, is what would have refused it.
3. **Given** a scoped pool, **When** a node's scoped field is changed in the same request that
   allocates, **Then** the number is allocated in the new division (a device created in site C with
   `from_pool` receives the number free in C).
4. **Given** a pool with no scope, **When** numbers are allocated, **Then** the behaviour and the
   query issued are what they are today, and the existing number-pool suites pass with identical
   figures.
5. **Given** device D1 in site A holding 5 on the default branch and moved to site C on branch
   `b1`, **When** allocation runs on the default branch, **Then** it returns 6 in A, 6 in C, and 5
   in a site D. **When** `b1` is deleted, **Then** 5 is free in C on the next read with no cleanup
   write.
6. **Given** fifty concurrent creates in site A, **When** they all allocate from one scoped pool,
   **Then** they receive fifty distinct numbers; fifty in A and fifty in B receive 1–50 twice.
7. **Given** a pool scoped by site with 5 held in A and in B, **When** the scope is cleared,
   **Then** the next allocation is 6; **When** it is set again, **Then** A and B each allocate 6 next
   and a new site C receives 1. No record was moved or rewritten.
8. **Given** a scoped pool with a scope of two entries (site and tenant), **When** devices in
   (A, T1), (A, T2) and (B, T1) allocate, **Then** each receives 1.
9. **Given** a scope naming a required attribute rather than a relationship, **When** devices with
   different values of that attribute allocate, **Then** each value is its own division.

---

### User Story 3 - Which site is about to run out, and which numbers it holds (Priority: P2)

An operator views every division holding numbers, ordered from the fullest, and for one division
its figures over the pool and over each range and the numbers it holds, so that a site about to
run out is visible before it does. The mock partition of User Story 1 is replaced by these reads.

**Why this priority**: Reporting is what makes a scoped pool operable, and it depends on the division
reads User Story 2 introduces.

**Independent Test**: On a scoped pool with uneven occupancy across sites, read the three dedicated
queries and compare the headline, the division rows, the range rows and the filtered allocation
list against the records.

**Acceptance Scenarios**:

1. **Given** sites A (50 records), B (two nodes, no records) and C (no nodes) on a 100-number
   pool scoped by site, **When** `InfrahubNumberPoolUtilization` and `InfrahubNumberPoolDivisions`
   are read, **Then** the divisions list holds A alone with 50 of 100, there is no division for B
   or C, and the utilization query read without `division` is refused.
2. **Given** a scoped pool, **When** the utilization of one division is read, **Then** its
   default-branch and other-branch figures are computed over that division.
3. **Given** a scoped pool with ranges 1–50 and 51–100, site A holding forty numbers in 1–50 and
   site B holding thirty in 51–100, **When** `InfrahubNumberPoolUtilization` is read with the
   division of site A, **Then** the headline reports 40 of 100, 1–50 reports 40 of 50 and 51–100
   reports 0 of 50; **When** it is read with the division of site B, **Then** the headline reports
   30 of 100, 1–50 reports 0 of 50 and 51–100 reports 30 of 50.
4. **Given** a division listing, **When** a node of the kind holds a value on a non-default
   branch only, **Then** its division appears in the listing, labelled by the peer's display
   label or, when the peer cannot be read, by its id.
5. **Given** device D1 holding 5 in site A on the default branch and moved to site C on `b1`,
   **When** `InfrahubNumberPoolAllocations` is filtered on site A, **Then** D1's two rows are
   returned (one per branch, the `b1` row's division naming C); **When** filtered on site C,
   **Then** the same two rows are returned, so 5 counts in A and in C and the two divisions'
   `used` figures do not sum to the pool's.
6. **Given** a scoped pool after this story lands, **When** the three queries are read, **Then** no
   value or label beginning with `mock-` is returned.

---

### User Story 4 - Scope declared in the schema (Priority: P2)

A schema author declares `allocation_scope` on a number-pool attribute and every node gets a
per-site number from a pool nobody created by hand. Changing the declaration on the default branch
updates the pool; editing the scope directly on the pool is refused.

**Why this priority**: Schema-created pools are the second kind of pool and must gain the same
capability; they build on User Story 2's allocation and User Story 1's parameter contract.

**Independent Test**: Load a schema declaring a scoped number-pool attribute, allocate from two
sites, change the declaration on the default branch, reload, and attempt a direct edit on the pool.

**Acceptance Scenarios**:

1. **Given** a Device kind whose `vlan_id` is a number-pool attribute with ranges 100–200 and scope
   `["site"]`, **When** the schema loads, **Then** the pool it creates reads back that scope;
   **When** devices in two sites allocate, **Then** both receive 100.
2. **Given** that schema, **When** the scope is cleared on the default branch and the schema
   reloaded, **Then** the next allocation returns 102.
3. **Given** a schema-created pool, **When** its scope is edited directly through the pool's update,
   **Then** the edit is refused and the error points at the schema in the default branch.
4. **Given** a number-pool attribute whose declared scope names an optional field, a many
   relationship or a path into a related node, **When** the schema loads, **Then** the load is
   refused naming the entry.

---

### User Story 5 - A scope that has no answer is refused (Priority: P2)

An operator who names a field that cannot yield one value per node is refused when saving the
pool, and a schema author who would break a scoped field from the schema side is refused with the
dependent pool named.

**Why this priority**: These two refusals are what keep a scoped pool from being configured into a
state where "the writer's division" has no answer. They are cheap and must ship with the capability.

**Independent Test**: Save pools with invalid scope entries and load schemas that invalidate an
entry a pool depends on; check every refusal names what it must.

**Acceptance Scenarios**:

1. **Given** a kind where `description` is optional, `interfaces` is a many relationship and `site`
   is a required one, **When** a pool is saved with scope `["description"]`, `["interfaces"]` or
   `["site__name__value"]`, **Then** each save is refused and the error names the entry.
2. **Given** a pool scoped by `site`, **When** a schema is loaded that makes `site` optional,
   removes it, or makes it cardinality many, **Then** each load is refused and the error names the
   pool.
3. **Given** a pool scoped by `["site", "pod"]` saved from a branch whose schema has `pod`, **When**
   a schema is loaded on the default branch, where `pod` has never existed, **Then** the absence of
   `pod` there is not a violation.

---

### User Story 6 - Schema and pool changes travel together through branches (Priority: P3)

A schema author working on a branch scopes a pool by a field that exists only in that branch's
schema. The pool saves, allocation keeps working everywhere, and the finer division applies on every
branch once the schema merges.

**Why this priority**: The branch seam is what makes the feature safe in a branching system; the
single-branch behaviour of User Stories 2 to 5 must exist before the divergence cases can be
tested.

**Independent Test**: Every scenario here uses at least two branches, because a single-branch test
cannot distinguish a union from an allocating-branch read.

**Acceptance Scenarios**:

1. **Given** branch `b1` whose schema declares `pod` required on Device while the default branch
   does not, **When** scope `["site", "pod"]` is saved on `b1`, **Then** it saves; **When** the
   same scope is saved on the default branch, **Then** it is refused naming `pod`.
2. **Given** that scope saved from `b1`, **When** allocation runs on the default branch, **Then**
   it allocates per site; on `b1`, per site and pod; and `InfrahubNumberPoolDivisions` read on the
   default branch reports `allocation_scope: ["site"]` with one-entry divisions while on `b1` it
   reports `["site", "pod"]` with two-entry divisions. No read fails.
3. **Given** a scope whose every entry is unknown on the reading branch, **When** allocation and
   the three queries run there, **Then** the pool behaves as unscoped on that branch and the
   queries report an empty `allocation_scope`.
4. **Given** `b1` merged, **When** allocation runs on any branch, **Then** it allocates per the
   full scope.
5. **Given** a node deleted on `b1` but live on the default branch, **When** allocation runs on
   either branch, **Then** its number still counts in its division.

---

### User Story 7 - Replace a pool per site with one scoped pool (Priority: P3, deferred: gated on P2 attach, not delivered by this slice)

An operator with one pool per site keeps one of them, sets its scope to site, widens its ranges,
attaches the nodes the other pools served, and deletes the rest. No new mechanism is needed
beyond attach.

**Why this priority**: Consolidation is the brownfield journey and depends on P2's attach landing on
this branch. Attach is not built at the time of writing, so this story is specified here for
traceability and carried by no change set of this slice; it is verified when attach lands. A new
scoped pool adopts nothing; the old pools' numbers are invisible to it until their nodes are
attached.

**Independent Test**: With attach available, run the journey end to end and check the division
figures and the next allocation.

**Acceptance Scenarios**:

1. **Given** per-site pools P_A and P_B each having handed out 1–10, **When** P_A is scoped by site
   and the ten site-B nodes are attached to it, **Then** P_A reports A 10 of 100 and B 10 of 100,
   the next allocation in B returns 11, and P_B can be deleted.

---

### User Story 8 - The cost of a scoped pool is measured before it ships (Priority: P3)

A platform engineer reads a report of allocation latency and throughput on a scoped pool at
realistic occupancy and decides, on numbers, whether a finer lock or a stored division key is
needed.

**Why this priority**: The design chooses derived scope and a pool-level lock on purpose; the
measurement is what validates the choice. It gates nothing.

**Independent Test**: Run the two measurements on the feature branch and record the figures in the
spec directory.

**Acceptance Scenarios**:

1. **Given** one scoped pool and N per-site pools serving the same nodes, **When** concurrent
   allocation is driven against both, **Then** throughput for both is recorded.
2. **Given** a fully occupied 4094-number pool with a three-entry scope (two relationships, one
   attribute) and five live branches, **When** one allocation runs, **Then** its latency and query
   plan are recorded, with the occupancy at which a stored division key would be needed named.

---

### Edge Cases

- A scoped pool over an attribute declared `unique: true`: today the pool still skips every value
  present on the attribute anywhere, so a scope over a unique attribute degrades to pool-wide
  allocation and nothing is refused. Once P2 retires that skip, the pool offers a number held in
  another division and the uniqueness validator refuses the save; the remedy is the operator's,
  clear the scope or change the ranges, and attaching the holder does not help since the attached
  record sits in its own division. Either way the pool validates nothing about its attribute, and
  no test of this slice asserts the refusal.
- A device holding a tracked 5 moves from site A to site C on branch `b1`: the pool writes nothing.
  The record occupies A and C until `b1` merges or is deleted, and the allocation list returns its
  rows under a filter on A and under a filter on C. A collision in C is the uniqueness constraint's
  to refuse, if one exists.
- A scope is set from `b1` naming a field only `b1`'s schema has: saved, live on every branch,
  ignored where unknown. After `b1` merges every branch allocates per the full scope.
- Transient divergence while a schema branch is open: the default branch (scope in force
  `["site"]`) and `b1` (`["site", "pod"]`) can each hand 1 to a site-A device at the same moment.
  Under the merged definition those are different divisions; under the coarser reading they are the
  same. Accepted as the price of ignoring unknown entries, and independent of how allocation is
  locked.
- A scope entry is an attribute rather than a relationship: the division value is the attribute's
  value, resolved as a union over branches like a relationship peer.
- A node is deleted on `b1` but live on the default branch: its record still counts. Branch `b1`
  is deleted: the deleting-branch exclusion already in the read drops its edges on the next read.
- Two user-created pools over one kind and attribute carry different scopes: allowed. Each allocates
  within its own division over its own ranges; nothing pool-side arbitrates.
- A scope is widened on a pool holding records: numbers taken under the finer division become free.
  Narrowed: more numbers appear taken. No number already handed out changes.
- A pool's last range is removed: the dedicated utilization query lists no range, every figure
  reports `size` 0, and the allocation list is empty. Allocation raises
  the existing pool-exhausted error, as P1 defines.
- A tracked value sits inside a range but the attribute lists it in `excluded_values`, or it falls
  outside the attribute's `min_value` / `max_value`: the allocation list does not list it and the
  value counts in no figure.
- A pool holds several ranges: its deprecated `start_range` / `end_range` pair is null, and the
  dedicated surface computes every figure from the range set, so it reports the pool where the
  generic queries, which read the pair, cannot.
- A scoped field is cleared or its peer deleted on a branch while the node lives on: the node
  occupies no division on that branch for that entry and its record is counted in the divisions it
  occupies on the other branches. A required field cannot be empty on save, so this is reachable
  only through a peer deletion, which the existing cascade rules govern.
- A scope entry is an attribute of a kind whose value is not a single comparable scalar (list,
  JSON): refused at save, as an entry that cannot define one division per node.
- `allocation_scope` is sent as an empty list: the pool is unscoped; reading it back reports no
  scope. Sent as `null` on update: clears the scope.
- A duplicate entry inside one scope (`["site", "site"]`): refused at save, naming the entry.
- A scope names the pool's own number-pool attribute: refused at save; the entry would make the
  division depend on the number being allocated.
- A `division` filter names a path in force with a value no holder carries: an empty list and
  `count` 0, not a refusal. A `division` filter on an unscoped pool, or on a pool none of whose
  entries the reading branch defines: refused naming the pool and the branch.
- `range_id` names a range of another pool: refused naming the pool and the range.
- A `division` filter with a partial tuple on a two-entry scope (`[{path: "site", value: A}]`):
  accepted by the allocations query, which returns every row held in site A across tenants;
  refused by the utilization query naming the missing entry, because numbers are unique per
  (site, tenant) pair and figures over several divisions match no space the pool allocates from.
- The frontend's existing `InfrahubResourcePoolUtilization` and `InfrahubResourcePoolAllocated`
  reads on a scoped pool: pool-wide figures and the whole pool's values, as before the slice.

## Requirements *(mandatory)*

### Functional Requirements

Requirement numbers FR-001 to FR-013 are the PRD's, unchanged in meaning, so that the alignment check
and later slices can trace them. FR-014 onward are the contract and delivery requirements this
specification adds.

#### Allocating per division

- **FR-001**: With a scope set, allocation MUST return the lowest free number in the heaviest range
  that is not held by any record whose holder sits in the writer's division on any live
  branch. *(PRD FR-001; User Story 2, scenario 5)*
- **FR-002**: The writer's division MUST be taken from the node as it will be saved, relationships
  included, so that a create or update that sets a scoped field and allocates in one request
  allocates in the new division. *(PRD FR-002; User Story 2, scenario 3)*
- **FR-003**: The scope MUST never refuse, validate or deduplicate a value. A provided number
  already held in the writer's division is accepted and tracked. *(PRD FR-003; User Story 2,
  scenario 2)*
- **FR-004**: Two allocations in the same division of the same pool MUST never return the same
  number, whatever branches they run on. *(PRD FR-004; User Story 2, scenario 6)*
- **FR-005**: A pool with no scope MUST behave exactly as it does today, including the query it
  issues. *(PRD FR-005; User Story 2, scenario 4)*
- **FR-006**: Setting, changing or clearing a scope MUST keep every record and move no data; the
  next read applies the new derivation. *(PRD FR-006; User Story 2, scenario 7)*

#### The branch seam

- **FR-007**: A record's division MUST be resolved as a union over every live branch: the record
  counts in every division its holder occupies on any non-deleting branch at the read time.
  *(PRD FR-007; User Story 2, scenario 5; User Story 6, scenario 5)*
- **FR-008**: A scope entry that the reading branch's schema does not define MUST be ignored for
  that read, for allocation and for the three dedicated queries alike, and MUST NOT fail the read.
  With every entry unknown the pool behaves unscoped on that branch. *(PRD FR-008; User Story 6,
  scenarios 2 and 3)*
- **FR-009**: A scope entry MUST be either a relationship of cardinality one or an attribute, and
  MUST be required on the kind. A scope naming an optional field, a many relationship, or a path
  into a related node MUST be refused when the pool is saved, and the error MUST name the entry.
  Validation runs against the schema of the branch the mutation runs on, and applies to a scope
  that changes: an update or upsert whose `allocation_scope` equals the stored value is accepted on
  every branch without re-validation, so a scope saved from a branch that knows an entry is not
  refused when the whole pool is re-sent from a branch that does not. *(PRD FR-009; User Story 5,
  scenario 1; User Story 6, scenario 1)*
- **FR-010**: A schema load MUST be refused when it would make a scope entry that exists in that
  branch's schema optional, absent, or cardinality many while a pool depends on it, and the error
  MUST name the pool. An entry that never existed on that branch is not a violation. *(PRD FR-010;
  User Story 5, scenarios 2 and 3)*

#### Reporting

- **FR-011**: On a scoped pool, utilization MUST be read for one division at a time, and the
  division listing MUST include every division whose holders hold at least one tracked value on any
  live branch, ordered by utilization descending so that the fullest division is its first row. A
  division whose nodes hold no value is not listed. The branch-split figures are computed over the
  division read. *(PRD FR-011, changed: no headline reports the fullest division, and the listing
  holds only divisions holding a value; User Story 3, scenarios 1 and 2)*

#### Pools the schema creates

- **FR-012**: A number-pool attribute MUST accept an optional `allocation_scope` in its parameters,
  in the same notation as on the pool. The pool the schema creates MUST carry it, and a later
  default-branch schema load that changes it MUST update the pool. FR-009's rules apply to the
  schema being loaded, on the branch it is loaded on. *(PRD FR-012; User Story 4)*
- **FR-013**: Setting `allocation_scope` directly on a schema-created pool MUST be refused with the
  existing error pointing at the schema in the default branch. *(PRD FR-013; User Story 4,
  scenario 3)*

#### The API contract (added by this specification)

- **FR-014**: `allocation_scope` MUST be readable on the pool and writable through the pool's
  create, update and upsert inputs as an optional list of scope entries. Omitted or empty means no
  scope; explicit null on update clears it. *(User Story 1, scenario 1)*
- **FR-015**: A query dedicated to number pools, `InfrahubNumberPoolUtilization`, MUST return for
  one pool: the scope in force on the reading branch, the pool's figures, one row per range ordered
  by start with the range's id, display label, start, end, weight and figures. The query MUST
  accept a `division` argument naming one division with a value for every scope entry in force on
  the reading branch; with it, the pool's figures and every range row report that division, a
  range in which it holds no value reporting `used` 0. `division` MUST be required on a pool whose
  scope in force is not empty, and its absence refused naming the pool and the branch (FR-011). A
  `division` that omits an entry in force MUST be refused naming the missing entries; the other
  `division` refusals of FR-024 apply. *(User Story 1, scenarios 2 and 3;
  User Story 3, scenarios 1 to 3)*
- **FR-016**: A division MUST be identified by one entry per scope entry in force on the reading
  branch, in scope order, each entry carrying the path, the value (a relationship entry: the
  peer's id; an attribute entry: the value as text; a holder holding nothing for the entry: an
  empty string), a display label (the peer's display label, falling back to its id when the peer
  cannot be read on any branch; an attribute entry: the value as text) and, for a relationship
  entry whose peer can be read, the peer's kind. A division's display label joins the entries'
  labels with " / ". The same entry type MUST identify a division in the divisions list and on an
  allocation row. *(User Story 1, scenario 4; User Story 3, scenario 4)*
- **FR-017**: On a scoped pool, every range row MUST report the division given as `division`: that
  division's count of the range's values against the range's size, with its branch split, and
  `used` 0 for a range in which the division holds no value. *(User Story 3, scenario 3)*
- **FR-018**: The generated artefacts (GraphQL schema export, OpenAPI schema, SDK and frontend
  types, attribute-parameter documentation) MUST carry the new fields and MUST be regenerated, never
  edited. The contract published by User Story 1 MUST NOT be renamed, retyped or removed by any
  later story in this slice. *(User Story 1, scenario 10)*
- **FR-019**: Until the division reads exist, the three dedicated queries MAY report the divisions
  of a scoped pool from one deterministic mock partition: every row of the pool is put in one of
  three divisions named `mock-1`, `mock-2` and `mock-3` by a stable hash of its holder's id, the
  entries carry the real scope paths in force, and the divisions list, the division on each row and
  the division filter read the same partition so that lists, filters and counts agree. The mock
  MUST NOT be observable on an unscoped pool. It MUST be removed before the slice ships, and a test
  MUST assert that no value or label beginning with `mock-` is returned by any of the three queries
  on a scoped pool. *(User Story 1, scenario 8; User Story 3, scenario 6)*
- **FR-022**: A query dedicated to number pools, `InfrahubNumberPoolDivisions`, MUST return for one
  pool the scope in force, the count of divisions and the complete list of divisions, each with its
  entries, display label and figures, ordered by utilization descending then display label, without
  pagination. On an unscoped pool, or on a branch where no entry is in force, the list MUST hold
  exactly one division with no entry, an empty display label and figures equal to the pool's. On a
  scoped pool the list holds the divisions FR-011 lists, each with figures over the pool's whole
  space. A division's figures per range are read from `InfrahubNumberPoolUtilization` with
  `division` (FR-015). *(User Story 1, scenario 4; User Story 3, scenarios 1 and 4)*
- **FR-023**: A query dedicated to number pools, `InfrahubNumberPoolAllocations`, MUST return for
  one pool a paginated list of rows, one per (record, branch-resolved value), each carrying the
  value, the branch holding it, the holder (id, hfid, kind, display label read on the row's
  branch), the identifier, the provenance (`ALLOCATED` or `PROVIDED`), the range holding the value
  and the holder's division on the row's branch (empty on an unscoped pool). The list holds only
  values of the pool's space (FR-028). Rows are ordered by value, then branch, then holder id,
  and `count` reports the filtered rows before `offset` and `limit`. *(User Story 1, scenario 5)*
- **FR-024**: `InfrahubNumberPoolAllocations` MUST accept the filters `division`, `range_id`,
  `branch` and `provenance`, combined with "and". A `division` filter is a list of
  (path, value) entries; a partial tuple is allowed; a row matches when its holder carries the
  requested value for every given entry on at least one live branch (FR-007). A `division` filter
  MUST be refused on a pool whose scope in force is empty, and an entry whose path is not in force
  or is given twice MUST be refused naming the entry. A `range_id` that is not a range of the pool
  MUST be refused naming the pool and the range. A `pool_id` that is not a number pool MUST be
  refused with the existing not-found error. *(User Story 1, scenarios 6 and 7; User Story 3,
  scenario 5)*
- **FR-025**: Because a holder's division is a union over live branches (FR-007), one value MAY
  appear in two divisions of the divisions list and under two division filters. Consumers MUST NOT
  sum per-division `used` figures; the pool's `used` is the distinct count over the whole space.
  The contract MUST state this. *(User Story 3, scenario 5)*
- **FR-026**: Every utilization figure on the dedicated surface MUST be one block carrying the
  absolute `size`, `used`, `used_default_branch` and `used_branches` and the three percentages
  `utilization`, `utilization_default_branch` and `utilization_branches`, applied alike to the
  pool, each range and each division. `used` counts distinct values of the measured space, never
  rows; `used_branches` counts values held on another branch and not on the default branch. The
  percentages keep the names and meaning of `PoolUtilization`. *(User Story 1, scenario 2)*
- **FR-027**: The three dedicated queries MUST report the scope in force on the reading branch
  (`allocation_scope` on the utilization and divisions results, the paths accepted in a division
  filter), empty for an unscoped pool and for a scoped pool none of whose entries the branch
  defines. *(User Story 1, scenario 3; User Story 6, scenarios 2 and 3)*
- **FR-028**: The provenance of each tracked number that P2 specified for the pool queries MUST be
  carried by the dedicated surface as `provenance` on each row, and MUST NOT be added to the
  generic queries. `InfrahubNumberPoolAllocations` MUST list only values of the pool's space: inside
  one of the pool's ranges, not among the attribute's `excluded_values`, and within its
  `min_value` / `max_value` when set. A value the list leaves out counts in no figure of the
  dedicated surface. *(User Story 1, scenario 5)*
- **FR-029**: The generic queries `InfrahubResourcePoolUtilization` and
  `InfrahubResourcePoolAllocated` and their types MUST keep their shape and meaning for every pool
  kind. For a number pool they report pool-wide figures and the whole pool's values, scope or not.
  Their descriptions MUST gain a note directing number-pool consumers to the dedicated queries; no
  `@deprecated` is added, because GraphQL cannot deprecate a field for one pool kind. *(User Story
  1, scenario 9)*
- **FR-030**: The three dedicated queries MUST read the pool, its ranges and its records
  branch-agnostically and list values from every live branch, as `InfrahubResourcePoolAllocated`
  does for number pools; the `branch` filter keeps rows whose value is held on that branch; the
  scope in force, the pool's display label and refusal messages come from the request's branch; a
  holder's display label and hfid are read on the row's branch; and every read honours the
  request's `at`. *(User Story 1, scenario 5; User Story 6, scenario 2)*

#### Scope entries

- **FR-020**: A scope entry MUST use the schema-path notation uniqueness constraints already use: a
  relationship name, or an attribute name with or without its value suffix. A duplicate entry, an
  entry naming the pool's own number-pool attribute, and an attribute whose value is not a single
  comparable scalar (list or JSON kinds) MUST be refused at save naming the entry.
- **FR-021**: The scope MUST be stored on the pool as a branch-agnostic attribute, like the pool. No
  per-branch copy of the scope exists; FR-008 is how a branch that cannot resolve an entry copes.

### Key Entities *(include if feature involves data)*

- **Number pool** (existing): gains `allocation_scope`, an optional list of schema paths in the
  notation uniqueness constraints already use. Branch-agnostic, like the pool. Two kinds as today:
  user-created (scope editable on the pool) and schema-created (scope owned by the schema
  declaration).
- **Number-pool attribute parameters** (existing, published contract under ADR 0010): gain the same
  field. One scope per schema-declared attribute, because one schema-created pool exists per kind
  and attribute.
- **Pool record** (existing, attribute-anchored since P2's foundational work): unchanged. Nothing
  about a division is stored on it.
- **Division** *(new, derived, never persisted)*: the tuple of values of the scope entries in force,
  taken from a record's holder, computed at read time from the holder's own fields, over every live
  branch. Published as a list of division entries (path, value, display label, peer kind).
- **Division enumeration** *(new read)*: the distinct divisions over nodes of the kind on
  any live branch, with record counts. The one place the pool reads the kind's data rather than its
  own records, by decision.
- **Utilization figures** *(new read shape)*: one block of absolute and relative figures (size,
  used, used on the default branch, used on other branches, and the three percentages), applied to
  the pool, each range and each division.
- **Allocation row** *(new read shape)*: one tracked value as held on one branch: value, branch,
  holder, identifier, provenance, range and division.
- **Number-pool GraphQL surface** *(new)*: the three root query fields `InfrahubNumberPoolUtilization`,
  `InfrahubNumberPoolDivisions` and `InfrahubNumberPoolAllocations` and their types, hand-written
  beside the generic resource-pool queries.
- **Pools-referencing-field lookup** *(new, shared)*: which pools name a given kind and field. Used
  by the schema-load check, the pool mutation, and the existing kind and attribute rename and
  removal paths.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A deployment running one pool per site expresses the same thing as one scoped pool,
  and adding a site adds no pool. *(PRD SC-001)*
- **SC-002**: A node is never blocked by a number used in another division. It cannot be
  *allocated* a number used in its own; it can be *given* one unless a uniqueness constraint
  refuses. *(PRD SC-002)*
- **SC-003**: A deployment that sets no scope sees no change: the existing number-pool suites pass
  with identical figures and the unscoped allocation query is unchanged. *(PRD SC-003)*
- **SC-004**: A deployment whose numbers are not yet distinct per site can scope a pool by site
  immediately, without declaring a uniqueness constraint, and every number handed out afterwards is
  distinct within its site. *(PRD SC-004)*
- **SC-005**: Allocation throughput of one scoped pool under concurrent load, against N per-site
  pools serving the same nodes, is measured and reported before P3 ships. No gate: the figure
  decides whether a finer lock key is taken. *(PRD SC-005)*
- **SC-006**: Allocation latency on a fully occupied 4094-number pool with a three-entry scope (two
  relationships, one attribute) and five live branches is measured and reported before P3 ships. No
  gate: the report names the occupancy at which a stored division key would be needed. *(PRD
  SC-006)*
- **SC-007**: The frontend and SDK can start from the published contract alone: after the contract
  change set lands, the exported GraphQL schema contains every type and field of the dedicated
  surface and `allocation_scope` on the pool and its inputs, the frontend can build the pool page,
  the range view, the division view and the allocation list from the three dedicated queries alone,
  and no later change set in the slice renames, retypes or removes any of them.
- **SC-008**: Every refusal this slice introduces names what the user must change: the offending
  scope entry on a pool save or an attribute-parameter load, the dependent pool on an unsafe schema
  load, the default-branch schema on a direct edit of a schema-created pool, the entry or the pool
  on a rejected division filter, the range on a rejected `range_id`.
- **SC-009**: The exported GraphQL schema diff of the contract change set shows no change to
  `PoolUtilization`, `PoolAllocated`, `PoolAllocatedNode`, `IPPrefixUtilizationEdge`,
  `IPPoolUtilizationResource` and the two generic root fields other than description text.
- **SC-010**: From the contract change set on, a scoped pool's divisions list, the division on each
  allocation row and the division-filtered lists agree: every row's division is a listed division,
  and a division's `used` equals the number of distinct values among the rows returned when
  filtering on it.
- **SC-011**: At the end of the slice no mock division is returned by any of the three dedicated
  queries, and the test asserting it passes.

## Behaviour changes for the changelog

| Entry | Category |
|-------|----------|
| A number pool can declare `allocation_scope`; allocation and utilization are then per division. | Feature |
| Number-pool attributes accept `parameters.allocation_scope`; the schema-created pool carries it and direct edits are refused. | Feature |
| Three GraphQL queries dedicated to number pools report utilization with absolute figures per pool and per range, the divisions of a scoped pool, and the tracked numbers with holder, provenance, range and division. | Feature |
| The generic `InfrahubResourcePoolUtilization` and `InfrahubResourcePoolAllocated` queries keep their shape; their descriptions direct number-pool consumers to the dedicated queries. | Changed description |
| A pool save naming a scope entry that is optional, many, nested, duplicated, non-scalar or the pool's own attribute is refused. | New refusal |
| A schema load that would make a scoped entry optional, absent or many while a pool depends on it is refused naming the pool. | New refusal |

## Approvals needed

Using the repository's "ask first" list.

- [x] Database schema or migration change — one new attribute on a core node through the internal
  schema update; no graph migration, no new edge, no new property on the record.
- [x] GraphQL schema modification — `allocation_scope` on the pool's create, update, upsert and
  read types; three new root query fields with their object types, input and enum; description
  text on the generic resource-pool queries and types.
- [x] Published schema contract (ADR 0010) — `allocation_scope` in the number-pool attribute
  parameters; one review shared with P1's `ranges` and P2's changes, in which this slice's
  dedicated surface is named as the carrier of P2's provenance.
- [ ] New dependency
- [ ] CI/CD workflow change
- [ ] Authentication or authorization change

## Assumptions

- P1 has landed only in part on this branch: the range kind, its mutations with overlap
  validation, the pool mutations that accept `ranges` and the deprecated `start_range` /
  `end_range` shorthand, the migration giving every existing pool one range, and the mirror that
  keeps the shorthand equal to the bounds of a pool's single range (null for a pool holding none
  or several). Allocation still draws from the shorthand, so it works on a pool holding exactly one
  range; allocation over a range set and the shared effective-space calculation have not landed.
  The division filter is independent of the range walk, so the two land in either order. The
  dedicated surface computes every `size` and `used`, and the values of the pool's space it lists,
  from the range set, the attribute's `excluded_values` and its `min_value` / `max_value`, never
  from the shorthand, and switches to P1's shared calculation when it lands without a contract
  change.
- P2's foundational re-anchoring has landed on this branch: the `IS_RESERVED` record is a global
  edge from the pool to the holder's attribute vertex, re-anchored by migration with the legacy
  pool source edges deleted and shared-attribute records collapsed; the liveness read is a union
  across branches with the deleting-branch exclusion; each record carries a provenance, absent
  meaning allocated; a record is closed once no branch reaches its attribute vertex, through the
  branch-agnostic retirement queries. The records lookup does not yet resolve each record to
  its holder; the division hop adds that resolution inside the same subquery. The attach mutation
  is not built; only User Story 7 waits for it.
- The scope-path notation is the one uniqueness constraints already use, parsed by the same code.
- The writer's division is read from the node as it will be saved. On create through the ordinary
  path relationships are applied before attributes; on create through a template and on update the
  pool handling is deferred until every field is applied, so the same holds. Verified at planning
  time.
- Number-pool reads live on three root query fields (form A) rather than on one root object with
  sub-fields (form B); see Open points.
- The divisions list and the allocation rows use flat lists (`divisions`, `allocations`, `ranges`)
  rather than the `edges { node }` wrapping of the generic queries, so the dedicated surface is
  uniform; the frontend's existing hooks are not reused for it.
- A scope entry may name any required attribute whose value is a single comparable scalar,
  dropdown and enum attributes included (PRD open question 3, resolved to its stated default, with
  list and JSON kinds excluded because they cannot define one division per node).
- The occupancy at which derived scope becomes too slow is answered by SC-006's report, not here
  (PRD open question 2).
- A schema-declared scope is reconciled onto the schema-created pool from the default-branch
  schema only, as P1 does for ranges; a branch's declaration takes effect on the pool when it
  merges. FR-009 validation of the declaration still runs on the branch being loaded.
- Utilization on a scoped pool is read for one division at a time (FR-011, FR-015, FR-017).
  Reporting the fullest division by default, as the PRD's FR-011 asked, was rejected by the user on
  2026-10-07: those figures describe a division the user did not choose. The fullest division is
  the first row of the divisions list, which is ordered by utilization.
- SC-005 (concurrent throughput) is a timed functional scenario, not a single-query benchmark; SC-006
  (one allocation's latency and plan) is a query benchmark. Both record figures, neither gates.
- Allocation locks on the pool as today; a per-division lock key is an implementation choice
  taken only if SC-005 says so.
- Data mocks are acceptable on the feature branch: the contract change set ships the divisions of
  a scoped pool as a deterministic partition so the frontend can build against real shapes with
  plausible data, and the mock is removed before the slice ships (FR-019).
- No frontend ships in this slice. The dedicated surface is designed so the pool form, the range
  view, the division view and the allocation list need no further backend change.

## Out of scope

- The frontend: scope on the pool form, the range view, the division view, the allocation list,
  and the migration of the existing pool and allocated-values pages to the dedicated queries (own
  ticket).
- The SDK helpers `get_pool_allocated_resources` and `get_pool_resources_utilization` (own ticket).
- Search on the allocation list.
- New mutations: bulk attach and detach, identifier-only reservation. A "next free value in a
  division" query.
- Any change to the generic resource-pool queries' shape or meaning.
- Any pool-side refusal of a value, including in-division duplicates and a scope over a
  `unique: true` attribute.
- A stored division key, a CRUD hook on scoped-field changes, a rescoping batch. SC-006 decides if
  ever.
- A per-division lock. SC-005 decides.
- Moving records between pools. Consolidation goes through attach.
- Attach itself, and therefore the consolidation journey (User Story 7): specified for
  traceability, delivered when P2's attach lands.
- Pools generated per site, or any automatic creation of a pool per division.
- Changing the meaning of any existing utilization field for an unscoped pool.

## Open points

- Form A (several root query fields, `InfrahubNumberPoolUtilization`, `InfrahubNumberPoolDivisions`,
  `InfrahubNumberPoolAllocations`) versus form B (one root object `InfrahubNumberPool` with
  sub-fields): form A is published; the user wants the choice re-judged at the final review of the
  surface, before the slice ships.

## Traceability to the PRD

| PRD item | Spec item |
|----------|-----------|
| FR-001 to FR-013 | FR-001 to FR-013, same numbers |
| Journey P1 | User Story 2 |
| Journey P2 | User Story 4 |
| Journey P3 | User Story 7 |
| User stories 7, 14 | User Stories 3 and 8 |
| User stories 8, 10, 11, 12 | User Stories 5 and 6 |
| SC-001 to SC-006 | SC-001 to SC-006, same numbers |
| Open question 1 (utilization shape) | FR-015, FR-016, FR-022, FR-026; Assumptions; the contract |
| Open question 2 (occupancy threshold) | SC-006; Assumptions |
| Open question 3 (enum or dropdown entries) | FR-020; Assumptions |
| Key entities | Key Entities, plus the division, the utilization figures, the allocation row and the dedicated surface |
| Implementation Decisions, Testing Decisions | Carried verbatim into the plan phase; not reopened here |
| User's delivery constraint | Delivery order, User Story 1, FR-018, FR-019, SC-007, SC-010, SC-011 |
| Frontend needs and grilling decisions of 2026-10-06 (not in the PRD) | User Story 1, FR-015, FR-016, FR-019, FR-022 to FR-030, SC-009 to SC-011, Open points |
| P2's provenance (`dev/specs/ifc-3184-pool-number-attach`) | FR-028; the contract |
