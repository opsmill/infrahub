# Feature Specification: Scoped number pools — one pool serves every scope

**Feature Branch**: `feature-number-pools-1.12` (no slice branch created; the user asked for nothing to be committed)

**Created**: 2026-10-02

**Status**: Draft

**Epic**: [IFC-3185](https://opsmill.atlassian.net/browse/IFC-3185) — Number pool improvements, part 3, pool allocation scopes (JPD INFP-308)

**Input**: `SCOPED-POOLS-PRD.md` — "PRD: Scoped number pools — one pool serves every scope", P3 of
the Number Pools PRD, grilled on 2026-10-01 against `feature-number-pools-1.12`. Plus the user's
delivery constraint: establish the GraphQL interface first (placeholder data where unavoidable),
then the utilization and allocation interfaces, then the internals, so that the frontend is
unblocked as early as possible and the remaining work can be split and run concurrently.

**Sources of truth**, in order of precedence for P3:

| Precedence | Document |
|-----------|----------|
| 1 | `SCOPED-POOLS-PRD.md` (repo root, 2026-10-01) |
| 2 | [Number Pools - PRD, simple as possible](https://opsmill.atlassian.net/wiki/spaces/Product/pages/870514689) |
| 3 | [Number Pools PRD](https://opsmill.atlassian.net/wiki/spaces/Product/pages/854818817/Number+Pools+PRD) (base PRD, INFP-308) |

Where a lower-precedence document says something this specification does not repeat, it stands.
Where they differ, the higher-precedence document wins and this specification follows it.

## Scope

P3 lets a pool say which fields divide its number space, so that one pool serves every site, every
site-and-tenant pair, or whatever the operator names. "The next free number" becomes "the next free
number within the division the object being written belongs to". A pool that names no scope behaves
exactly as it does today.

| Slice | Content | In P3 |
|-------|---------|-------|
| P1 | Several weighted ranges per pool, ranges declared in the schema (`dev/specs/ifc-3065-number-pool-ranges`) | Landed on this branch; consumed, not changed |
| P2 | Numbers a user gives the pool: provide, attach, detach, provenance, attribute-anchored records (`dev/specs/ifc-3184-pool-number-attach`) | In flight; the consolidation journey (User Story 7) waits for it |
| P3 | `allocation_scope` on the pool and in number-pool attribute parameters; per-division allocation and utilization | Yes |
| Frontend | Scope on the pool form, a per-division view | No; the read shape must carry everything those screens will need |

### Guiding principles for P3

1. **The scope decides which number comes next, and nothing else.** It never refuses a value,
   never validates one, never arbitrates a duplicate. Whether a value is valid stays with the
   attribute's uniqueness constraints and its own domain.
2. **The pool, its records and its scope are branch-agnostic; the objects are branch-aware.** Every
   read sits at that seam: a record counts in every division its object occupies on any live
   branch. The pool may waste a number across branches; it can never hand the same number to two
   objects in one division.
3. **A pool that says nothing changes nothing.** Unscoped pools issue the query they issue today and
   report the figures they report today.
4. **Nothing about a division is stored.** A record's division is derived from its owning object's
   fields at read time. Setting, changing or clearing a scope moves no data.

### Delivery order (user constraint)

The user asked for the work to be sequenced so the frontend is unblocked first and the rest can be
split across people:

1. **Internal schema first**: the `allocation_scope` attribute on the pool kind and the matching
   field in the number-pool attribute parameters, because every generated type derives from them.
2. **The GraphQL interface next**: the scope readable and writable on the pool, and the per-division
   figures on the pool utilization query, with the shapes frozen. Where the real reads do not exist
   yet, a scoped pool reports the whole pool as one division; an unscoped pool's single-division
   row is its permanent behaviour, not a placeholder.
3. **The utilization and allocation interfaces**: the per-division utilization getter and the
   allocator entry point that takes the writer's division, as seams other work plugs into.
4. **The internals**: the division-key resolver, the scoped records lookup, division enumeration,
   the validators and the schema-load checker, in parallel once the seams exist.

User Story 1 below is the contract story. Nothing after it may rename, retype or remove a field it
publishes.

## User Scenarios & Testing *(mandatory)*

The priority on each user story is the order in which this slice is built, following the delivery
order above. Every story belongs to slice P3.

### User Story 1 - The scope and the per-division figures are on the API (Priority: P1)

A frontend or SDK consumer reads a pool and sees its scope; writes a pool with a scope through
create, update or upsert and reads it back; and reads the pool utilization query and sees one row
per division with the figures it needs to draw a per-site view. The schema contract carries the same
field for number-pool attributes. The shapes are final: later stories fill them in but do not change
them.

**Why this priority**: The frontend and the SDK can only start once the contract exists and will not
move. Publishing it first lets that work and the backend internals proceed concurrently.

**Independent Test**: Export the GraphQL schema and the published attribute-parameter contract,
regenerate the frontend and SDK types, then round-trip a scope through the pool mutations and read
the utilization query on an unscoped pool and on a scoped pool.

**Acceptance Scenarios**:

1. **Given** the pool create, update and upsert inputs, **When** `allocation_scope: ["site"]` is
   sent, **Then** the pool saves and reads back `["site"]`; **When** the field is omitted or sent
   empty, **Then** the pool reads back as having no scope.
2. **Given** an unscoped pool, **When** its utilization is read, **Then** the per-division listing
   holds exactly one row with an empty division key whose figures equal the pool's headline figures.
3. **Given** a scoped pool, **When** its utilization is read, **Then** each per-division row
   identifies its division by the scope entries in force on the reading branch, in scope order, with
   each entry's value: for a relationship entry the related object's identifier and display label,
   for an attribute entry the attribute's value. Each row carries utilization,
   default-branch utilization and other-branch utilization for that division.
4. **Given** the exported GraphQL schema, the OpenAPI schema and the published attribute-parameter
   contract, **When** the generated SDK and frontend types are regenerated, **Then** they carry
   `allocation_scope` on the pool and on number-pool attribute parameters and the per-division
   rows on the utilization result, with no other change to existing fields.
5. **Given** a number-pool attribute declaring `parameters.allocation_scope: ["site"]`, **When** the
   schema loads, **Then** the pool it creates reads back that scope.

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
3. **Given** a scoped pool, **When** an object's scoped field is changed in the same request that
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

### User Story 3 - Which site is about to run out (Priority: P2)

An operator reads a scoped pool's utilization and sees the fullest division as the headline, with
every division listed, including those with objects but no numbers yet, so that a site about to run
out is visible before it does.

**Why this priority**: Reporting is what makes a scoped pool operable, and it depends on the division
reads User Story 2 introduces.

**Independent Test**: On a scoped pool with uneven occupancy across sites, read the utilization query
and compare the headline, the per-division rows and the per-range rows against the records.

**Acceptance Scenarios**:

1. **Given** sites A (50 records), B (two objects, no records) and C (no objects) on a 100-number
   pool scoped by site, **When** utilization is read, **Then** the headline is 50 %, A reports
   50 of 100, B reports 0 of 100, and there is no row for C.
2. **Given** a scoped pool, **When** the default-branch and other-branch utilization figures are
   read, **Then** they are computed over the fullest division.
3. **Given** a scoped pool with ranges 1–50 and 51–100, site A holding forty numbers in 1–50 and
   site B holding thirty in 51–100, **When** the per-range rows are read, **Then** 1–50 reports
   80 % (A's forty of fifty) and 51–100 reports 60 % (B's thirty of fifty), while the headline
   reports A's 40 of 100.
4. **Given** a division listing, **When** an object of the kind exists on a non-default branch only,
   **Then** its division appears in the listing.

---

### User Story 4 - Scope declared in the schema (Priority: P2)

A schema author declares `allocation_scope` on a number-pool attribute and every object gets a
per-site number from a pool nobody created by hand. Changing the declaration on the default branch
updates the pool; editing the scope directly on the pool is refused.

**Why this priority**: Schema-created pools are the second kind of pool and must gain the same
capability; they build on User Story 2's allocation and User Story 1's parameter contract.

**Independent Test**: Load a schema declaring a scoped number-pool attribute, allocate from two
sites, change the declaration on the default branch, reload, and attempt a direct edit on the pool.

**Acceptance Scenarios**:

1. **Given** a Device kind whose `vlan_id` is a number-pool attribute with ranges 100–200 and scope
   `["site"]`, **When** devices in two sites allocate, **Then** both receive 100.
2. **Given** that schema, **When** the scope is cleared on the default branch and the schema
   reloaded, **Then** the next allocation returns 102.
3. **Given** a schema-created pool, **When** its scope is edited directly through the pool's update,
   **Then** the edit is refused and the error points at the schema in the default branch.
4. **Given** a number-pool attribute whose declared scope names an optional field, a many
   relationship or a path into a related node, **When** the schema loads, **Then** the load is
   refused naming the entry.

---

### User Story 5 - A scope that has no answer is refused (Priority: P2)

An operator who names a field that cannot yield one value per object is refused when saving the
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
   it allocates per site; on `b1`, per site and pod; and the default branch's utilization groups
   by site only. No read fails.
3. **Given** a scope whose every entry is unknown on the reading branch, **When** allocation and
   utilization run there, **Then** the pool behaves as unscoped on that branch.
4. **Given** `b1` merged, **When** allocation runs on any branch, **Then** it allocates per the
   full scope.
5. **Given** an object deleted on `b1` but live on the default branch, **When** allocation runs on
   either branch, **Then** its number still counts in its division.

---

### User Story 7 - Replace a pool per site with one scoped pool (Priority: P3, deferred: gated on P2 attach, not delivered by this slice)

An operator with one pool per site keeps one of them, sets its scope to site, widens its ranges,
attaches the objects the other pools served, and deletes the rest. No new mechanism is needed
beyond attach.

**Why this priority**: Consolidation is the brownfield journey and depends on P2's attach landing on
this branch. Attach is not built at the time of writing, so this story is specified here for
traceability and carried by no change set of this slice; it is verified when attach lands. A new
scoped pool adopts nothing; the old pools' numbers are invisible to it until their objects are
attached.

**Independent Test**: With attach available, run the journey end to end and check the per-division
figures and the next allocation.

**Acceptance Scenarios**:

1. **Given** per-site pools P_A and P_B each having handed out 1–10, **When** P_A is scoped by site
   and the ten site-B objects are attached to it, **Then** P_A reports A 10 of 100 and B 10 of 100,
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

1. **Given** one scoped pool and N per-site pools serving the same objects, **When** concurrent
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
  The record occupies A and C until `b1` merges or is deleted. A collision in C is the uniqueness
  constraint's to refuse, if one exists.
- A scope is set from `b1` naming a field only `b1`'s schema has: saved, live on every branch,
  ignored where unknown. After `b1` merges every branch allocates per the full scope.
- Transient divergence while a schema branch is open: the default branch (scope effectively
  `["site"]`) and `b1` (`["site", "pod"]`) can each hand 1 to a site-A device at the same moment.
  Under the merged definition those are different divisions; under the coarser reading they are the
  same. Accepted as the price of ignoring unknown entries, and independent of how allocation is
  locked.
- A scope entry is an attribute rather than a relationship: the division key is the attribute's
  value, resolved as a union over branches like a relationship peer.
- An object is deleted on `b1` but live on the default branch: its record still counts. Branch `b1`
  is deleted: the deleting-branch exclusion already in the read drops its edges on the next read.
- Two user-created pools over one kind and attribute carry different scopes: allowed. Each allocates
  within its own division over its own ranges; nothing pool-side arbitrates.
- A scope is widened on a pool holding records: numbers taken under the finer division become free.
  Narrowed: more numbers appear taken. No number already handed out changes.
- A pool's last range is removed on a scoped pool: every division reports 0 of 0 and allocation
  raises the existing pool-exhausted error, as P1 defines.
- A scoped field is cleared or its peer deleted on a branch while the object lives on: the object
  occupies no division on that branch for that entry and its record is counted in the divisions it
  occupies on the other branches. A required field cannot be empty on save, so this is reachable
  only through a peer deletion, which the existing cascade rules govern.
- A scope entry is an attribute of a kind whose value is not a single comparable scalar (list,
  JSON): refused at save, as an entry that cannot define one division per object.
- `allocation_scope` is sent as an empty list: the pool is unscoped; reading it back reports no
  scope. Sent as `null` on update: clears the scope.
- A duplicate entry inside one scope (`["site", "site"]`): refused at save, naming the entry.
- A scope names the pool's own number-pool attribute: refused at save; the entry would make the
  division depend on the number being allocated.

## Requirements *(mandatory)*

### Functional Requirements

Requirement numbers FR-001 to FR-013 are the PRD's, unchanged in meaning, so that the alignment check
and later slices can trace them. FR-014 onward are the contract and delivery requirements this
specification adds.

#### Allocating per division

- **FR-001**: With a scope set, allocation MUST return the lowest free number in the heaviest range
  that is not held by any record whose owning object sits in the writer's division on any live
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
  counts in every division its owning object occupies on any non-deleting branch at the read time.
  *(PRD FR-007; User Story 2, scenario 5; User Story 6, scenario 5)*
- **FR-008**: A scope entry that the reading branch's schema does not define MUST be ignored for
  that read, for allocation and utilization alike, and MUST NOT fail the read. With every entry
  unknown the pool behaves unscoped on that branch. *(PRD FR-008; User Story 6, scenarios 2 and 3)*
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

- **FR-011**: On a scoped pool, the headline utilization MUST equal the utilization of the fullest
  division, and the per-division listing MUST include every division occupied by an object of the
  kind on any live branch, reporting 0 for a division holding no record. The branch-split figures
  are computed over the fullest division. *(PRD FR-011; User Story 3, scenarios 1 and 2)*

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
- **FR-015**: The pool utilization query MUST expose a per-division listing on the existing result,
  not through a separate query. On an unscoped pool the listing holds exactly one row with an empty
  division key whose figures equal the pool's headline figures. *(User Story 1, scenario 2)*
- **FR-016**: Each per-division row MUST identify its division by the scope entries in force on the
  reading branch, in scope order, each with its value: a relationship entry by the related object's
  identifier and display label, an attribute entry by the attribute's value. A related object that
  cannot be read on any branch is labelled by its identifier; an object holding nothing for an entry
  is identified by an empty value. Each row MUST carry the division's utilization, default-branch
  utilization and other-branch utilization. *(User Story 1, scenario 3)*
- **FR-017**: On a scoped pool holding several ranges, every per-range row MUST report the fullest
  division within that range: the largest count, over divisions, of that range's values held in one
  division, against the range's size. The headline and its branch split report the fullest division
  over the whole effective space. Every figure the pool reports is therefore a worst case, and a
  range about to run out in one site is visible even when another range hides it in the headline.
  *(User Story 3, scenario 3)*
- **FR-018**: The generated artefacts (GraphQL schema export, OpenAPI schema, SDK and frontend
  types, attribute-parameter documentation) MUST carry the new fields and MUST be regenerated, never
  edited. The contract published by User Story 1 MUST NOT be renamed, retyped or removed by any
  later story in this slice. *(User Story 1, scenario 4)*
- **FR-019**: Until the division reads exist, a scoped pool's per-division listing MAY report the
  whole pool as one division with an empty key. This transitional behaviour MUST be replaced before
  the slice ships and MUST NOT be observable on an unscoped pool, where the single row is the
  permanent behaviour.

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
- **Division key** *(new, derived, never persisted)*: the tuple of scope-entry values of a record's
  owning object, computed at read time from the object's own fields, over every live branch.
- **Division enumeration** *(new read)*: the distinct division tuples over objects of the kind on
  any live branch, with record counts. The one place the pool reads the kind's data rather than its
  own records, by decision.
- **Per-division utilization row** *(new read shape)*: a division key plus utilization,
  default-branch utilization and other-branch utilization for that division.
- **Pools-referencing-field lookup** *(new, shared)*: which pools name a given kind and field. Used
  by the schema-load check, the pool mutation, and the existing kind and attribute rename and
  removal paths.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A deployment running one pool per site expresses the same thing as one scoped pool,
  and adding a site adds no pool. *(PRD SC-001)*
- **SC-002**: An object is never blocked by a number used in another division. It cannot be
  *allocated* a number used in its own; it can be *given* one unless a uniqueness constraint
  refuses. *(PRD SC-002)*
- **SC-003**: A deployment that sets no scope sees no change: the existing number-pool suites pass
  with identical figures and the unscoped allocation query is unchanged. *(PRD SC-003)*
- **SC-004**: A deployment whose numbers are not yet distinct per site can scope a pool by site
  immediately, without declaring a uniqueness constraint, and every number handed out afterwards is
  distinct within its site. *(PRD SC-004)*
- **SC-005**: Allocation throughput of one scoped pool under concurrent load, against N per-site
  pools serving the same objects, is measured and reported before P3 ships. No gate: the figure
  decides whether a finer lock key is taken. *(PRD SC-005)*
- **SC-006**: Allocation latency on a fully occupied 4094-number pool with a three-entry scope (two
  relationships, one attribute) and five live branches is measured and reported before P3 ships. No
  gate: the report names the occupancy at which a stored division key would be needed. *(PRD
  SC-006)*
- **SC-007**: The frontend and SDK can start from the published contract alone: after User Story 1
  lands, the exported GraphQL and OpenAPI schemas and the regenerated types contain every field the
  pool form and a per-division view need, and no later story in the slice changes them.
- **SC-008**: Every refusal this slice introduces names what the user must change: the offending
  scope entry on a pool save or an attribute-parameter load, the dependent pool on an unsafe schema
  load, the default-branch schema on a direct edit of a schema-created pool.

## Behaviour changes for the changelog

| Entry | Category |
|-------|----------|
| A number pool can declare `allocation_scope`; allocation and utilization are then per division. | Feature |
| Number-pool attributes accept `parameters.allocation_scope`; the schema-created pool carries it and direct edits are refused. | Feature |
| The pool utilization query gains a per-division listing; on an unscoped pool it holds one row. | Changed read shape (additive) |
| A pool save naming a scope entry that is optional, many, nested, duplicated, non-scalar or the pool's own attribute is refused. | New refusal |
| A schema load that would make a scoped entry optional, absent or many while a pool depends on it is refused naming the pool. | New refusal |

## Approvals needed

Using the repository's "ask first" list.

- [x] Database schema or migration change — one new attribute on a core node through the internal
  schema update; no graph migration, no new edge, no new property on the record.
- [x] GraphQL schema modification — `allocation_scope` on the pool's create, update, upsert and
  read types; per-division rows on the pool utilization query.
- [x] Published schema contract (ADR 0010) — `allocation_scope` in the number-pool attribute
  parameters; one review shared with P1's `ranges` and P2's query-surface changes.
- [ ] New dependency
- [ ] CI/CD workflow change
- [ ] Authentication or authorization change

## Assumptions

- P1 has landed only in part on this branch: the range kind, its GraphQL contract and the per-range
  utilization rows shipped; allocation over a range set and the effective-space calculator have
  not. The division filter is independent of the range walk, so the two land in either order; the
  per-division denominator uses whatever size calculation is current when each lands.
- P2's foundational re-anchoring has landed on this branch (records point at the attribute; the
  liveness read is a union across branches with the deleting-branch exclusion). The records lookup
  does not yet resolve each record to its owning object; the division hop adds that resolution
  inside the same subquery. The attach mutation is not built; only User Story 7 waits for it.
- The scope-path notation is the one uniqueness constraints already use, parsed by the same code.
- The writer's division is read from the node as it will be saved. On create through the ordinary
  path relationships are applied before attributes; on create through a template and on update the
  pool handling is deferred until every field is applied, so the same holds. Verified at planning
  time.
- Per-division rows live on the existing pool utilization query (PRD open question 1, resolved
  here): the frontend already reads that query for the pool detail, and one query keeps the
  headline and the breakdown consistent by construction.
- A scope entry may name any required attribute whose value is a single comparable scalar,
  dropdown and enum attributes included (PRD open question 3, resolved to its stated default, with
  list and JSON kinds excluded because they cannot define one division per object).
- The occupancy at which derived scope becomes too slow is answered by SC-006's report, not here
  (PRD open question 2).
- A schema-declared scope is reconciled onto the schema-created pool from the default-branch
  schema only, as P1 does for ranges; a branch's declaration takes effect on the pool when it
  merges. FR-009 validation of the declaration still runs on the branch being loaded.
- Per-range rows on a scoped pool report the fullest division within each range (FR-017), because
  a range runs out per division. The alternative, every range row computed over the headline's
  fullest division, was rejected because it hides a range exhausted in a site the headline does not
  name. A division breakdown inside every range row stays additive if wanted later.
- SC-005 (concurrent throughput) is a timed functional scenario, not a single-query benchmark; SC-006
  (one allocation's latency and plan) is a query benchmark. Both record figures, neither gates.
- The read-side signal of which entries are in force on a branch stays out of scope. Adding a field
  later is additive and does not break the frozen contract; FR-018 forbids renames, retypes and
  removals, not additions.
- Allocation locks on the pool as today; a per-division lock key is an implementation choice
  taken only if SC-005 says so.
- No read-side signal that a scope entry is unresolved on the current branch. Useful, not required
  for v1.
- No frontend ships in this slice. The read shape is designed so the pool form and a per-division
  view need no further backend change.

## Out of scope

- The frontend: scope on the pool form, a per-division view.
- Any pool-side refusal of a value, including in-division duplicates and a scope over a
  `unique: true` attribute.
- A stored division key, a CRUD hook on scoped-field changes, a rescoping batch. SC-006 decides if
  ever.
- A per-division lock. SC-005 decides.
- Moving records between pools. Consolidation goes through attach.
- Attach itself, and therefore the consolidation journey (User Story 7): specified for
  traceability, delivered when P2's attach lands.
- A read-side signal for unresolved scope entries.
- Pools generated per site, or any automatic creation of a pool per division.
- Changing the meaning of any existing utilization field for an unscoped pool.

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
| Open question 1 (utilization shape) | FR-015, FR-016; Assumptions |
| Open question 2 (occupancy threshold) | SC-006; Assumptions |
| Open question 3 (enum or dropdown entries) | FR-020; Assumptions |
| Key entities | Key Entities, plus the per-division row |
| Implementation Decisions, Testing Decisions | Carried verbatim into the plan phase; not reopened here |
| User's delivery constraint | Delivery order, User Story 1, FR-018, FR-019, SC-007 |
