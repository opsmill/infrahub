# Feature Specification: Number pool allocation scopes

**Feature Branch**: `number-pool-scopes-ifc-3185`

**Created**: 2026-10-08

**Status**: Draft

**Input**: User description: [IFC-3185](https://opsmill.atlassian.net/browse/IFC-3185) (Number pool improvements, part 3, pools allocation scopes), read with the Number Pools PRD in Notion filtered to allocation scopes, the child tickets of the epic, the description of PR #10932, and five decisions of the product owner recorded under [Decisions of the product owner](#decisions-of-the-product-owner).

## Problem

A number that only has to be distinct within a scope (per site, per pod) forces an operator to create and maintain one number pool per scope, and to keep creating pools as scopes are added. A pool has nowhere to record the scope it serves, so when a node in one site is created or updated, nothing checks that its number came from that site's pool rather than another site's. (PRD, problem 3.)

## Decisions of the product owner

These five decisions were taken by the product owner after the sources were written. They override the Notion PRD, the Jira tickets and the description of PR #10932 wherever they differ.

1. A number pool and its allocation scope can only reference attributes and relationships that exist in the schema on the default branch.
2. An allocation scope cannot be modified after the pool is created, neither on a schema-defined pool nor on a user-created pool.
3. An allocation scope element is not a plain string holding the attribute name. It stores the unique identifier of the attribute or relationship (the schema element id), so that it can be referenced.
4. The user views each element with a readable name. When a query returns the allocation scope, each element is an object holding both the identifier and the name (`id` and `name`), not a string.
5. The structure described in PR #10932 was communicated to the frontend team. It changes only to apply decision 4 (a list of `{id, name}` objects where it listed strings). This is a breaking change relative to the PR description. The rest of that structure stays unless a reason to change it is documented in this spec or the plan.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One pool serves every site (Priority: P1)

An operator creates one number pool for the `vlan_id` attribute of `InfraDevice` and gives it an allocation scope of one element, the `site` relationship of the device kind. From then on a device in site A and a device in site B both receive the lowest number free within their own site, and adding a site needs no new pool. A pool with no allocation scope keeps allocating from one shared space, exactly as today.

**Why this priority**: This is the capability the epic exists for (PRD problem 3, FR-014 to FR-016). Without it nothing else in this feature has a purpose.

**Independent Test**: Create a scoped pool through the GraphQL API, create nodes in two sites with `from_pool`, and verify the numbers each site receives. Create an unscoped pool and verify the behaviour of today.

**Acceptance Scenarios**:

1. **Given** a pool over 1 to 100 scoped by the `site` relationship, **When** a device in site A and a device in site B each allocate from it, **Then** both receive 1, and neither blocks the other.
2. **Given** that same pool, **When** a second device in site A allocates, **Then** it receives 2 (the lowest number free within site A).
3. **Given** a pool scoped by `site` and `role` (one relationship and one attribute), **When** a device allocates, **Then** it receives the lowest number free within the combination of its site and its role.
4. **Given** a pool with no allocation scope, **When** devices in several sites allocate, **Then** every number is distinct across the whole pool, as today.
5. **Given** a setup that ran one pool per site, **When** the same space is expressed as one scoped pool, **Then** adding a site needs no new pool.
6. **Given** a pool scoped by `site` and an attribute whose numbers are not yet distinct per site and carries no uniqueness constraint, **When** the pool is created, **Then** it is accepted, and every number it hands out from then on is distinct within its site.
7. **Given** a scoped pool, **When** a node allocates with an identifier the pool already holds a record for, **Then** it receives the number it already had.
8. **Given** a scoped pool, **When** two nodes in the same site allocate at the same time, **Then** they receive two different numbers.
9. **Given** a scoped pool, **When** the operator creates it with a scope element that is optional, that is a relationship of cardinality many, that points into a related node, that does not exist on the pool's kind in the schema of the default branch, or that names the pool's own tracked attribute, **Then** the save is refused and the error names the element.
10. **Given** an existing scoped pool, **When** the operator tries to change or clear its allocation scope, **Then** the update is refused and the error says the scope cannot be changed after creation.

---

### User Story 2 - View how full each division is and which numbers it holds (Priority: P2)

An operator who opens a scoped number pool views the divisions that hold numbers, the figures of each division over the whole pool and over each range, and every tracked number with its holder, branch, provenance and range. The three dedicated GraphQL queries of PR #10932 answer these questions from the pool's records, and the frontend team builds the pool page on them.

**Why this priority**: A scoped pool that cannot be read per division hides a division that is about to run out (PRD FR-020). The frontend epic IFC-3363 depends on this contract.

**Independent Test**: Load a pool scoped by `site` with numbers in three sites and none in a fourth, then run the three queries and compare the answers with the loaded data.

**Acceptance Scenarios**:

1. **Given** a pool scoped by `site` with ranges 1 to 50 and 51 to 100, where site A holds 40 values, site B holds 30 and site D holds none, **When** the operator lists the divisions, **Then** the list holds sites A and B, each with its figures over the whole pool, ordered by utilization descending then by display label, and site D is absent.
2. **Given** that pool, **When** the operator asks for the utilization of site B, **Then** the answer gives the figures of site B over the whole pool and over each range.
3. **Given** that pool, **When** the operator asks for its utilization without naming a division, **Then** the query is refused, because figures over several divisions match no space the pool allocates from.
4. **Given** an unscoped pool, **When** the operator asks for its utilization, **Then** the answer covers the whole pool; **and when** a division is given, **Then** the query is refused.
5. **Given** a scoped pool, **When** the operator lists its allocations filtered by a division, a range, a branch or a provenance, **Then** only the matching rows come back, with the count of rows before pagination, and each row carries its value, branch, holder, identifier, provenance and range.
6. **Given** any query that returns the allocation scope, **When** the operator reads it, **Then** each element is an object with the schema element `id` and its readable `name`.

---

### User Story 3 - Declare the scope of a schema-defined pool (Priority: P3)

A schema author declares, in the parameters of a number-pool attribute, the allocation scope of the pool the schema creates. The pool is created with that scope when the schema loads on the default branch. The scope is resolved against the schema of the default branch and stored on the pool as element identifiers and names.

**Why this priority**: A pool the schema creates is configured from the schema, so anything that configures it has to be declarable there (PRD FR-043). It depends on the scope existing on the pool (User Story 1).

**Independent Test**: Load a schema whose number-pool attribute declares `allocation_scope`, then read the pool and allocate from two divisions.

**Acceptance Scenarios**:

1. **Given** a schema whose number-pool attribute declares `parameters.allocation_scope: ["site"]`, **When** the schema loads on the default branch, **Then** the pool it creates carries that scope, stored as the identifier and the name of the `site` relationship.
2. **Given** that schema, **When** nodes in two sites are created, **Then** both receive the lowest number free within their own site.
3. **Given** a schema-created pool with a scope, **When** a later schema load declares a different scope, or clears it, for the same attribute, **Then** the load is refused and the error names the attribute and says the scope cannot change after the pool is created.
4. **Given** a schema whose declared scope names an element that is optional, many, on a related node, or absent from the kind on the default branch, **When** the schema loads, **Then** the load is refused and the error names the element.
5. **Given** a schema that declares a scope on a branch for an element that exists only on that branch, **When** the schema loads on that branch, **Then** the load is refused, because a scope can only reference elements of the default branch's schema (decision 1).

---

### User Story 4 - Keep a scoped pool valid when the schema changes (Priority: P4)

A schema author who changes a field that a pool's scope references is refused when the change would stop the field from giving exactly one value per node, and the error names the pool. Renaming such a field is allowed: the scope references the field by its identifier, so the stored readable name follows the new name.

**Why this priority**: Without this guard a scope can silently stop dividing the pool (PRD FR-019). It depends on User Story 1.

**Independent Test**: Create a scoped pool, then load schema changes that make the field optional, many, removed, or renamed, and check each outcome.

**Acceptance Scenarios**:

1. **Given** a pool scoped by `site`, **When** a schema load makes the `site` relationship optional, changes its cardinality to many, or removes it, **Then** the load is refused and the error names the pool and the field.
2. **Given** a pool scoped by `site`, **When** a schema load makes the pool's tracked attribute `unique: true`, **Then** the load is refused and the error names the pool, because a globally unique number cannot repeat per division.
3. **Given** a pool scoped by `site`, **When** a schema load renames the `site` relationship to `location`, **Then** the load succeeds, the pool keeps allocating per site, and the scope reads `location` as the element's name.
4. **Given** a pool scoped by `site`, **When** the schema change is loaded on a branch other than the default branch, **Then** it is refused on that branch as well, so that the refusal does not wait for the merge.

---

### Edge Cases

- A scope names the same element twice: refused, the error names the element.
- A scope is given as an empty list: the pool is created without a scope, exactly as if the field had been left out.
- A scope element is given by name and by identifier in the same request: both resolve to the same stored element; a name that does not resolve on the default branch is refused.
- A relationship entry points at a peer that exists on a branch only: the division value is the peer id, and the division is listed on the branch that holds the value, like any other value.
- A node holds no peer or no value for a scope element (data written before the element became required): it is treated as an empty division value, both for allocation and for the queries.
- A scoped field on a node that already holds a tracked number is changed, moving the node to a division where that number is already taken: the pool does not refuse the change. Only the attribute's uniqueness constraints decide whether a value is valid (PRD FR-017). The pool reports the number under its new division from then on.
- A scope is created on a pool whose attribute already holds the same number twice within one division: the pool tracks none of that data (PRD FR-010), so creation is accepted, and the numbers it hands out from then on are distinct within each division.
- Two user-created pools on the same kind and attribute carry different scopes: allowed; each pool tracks only its own records, and a number is checked against the scope of the pool named in the request.
- The pool's kind is a generic: the scope elements must be declared on the generic itself, so that every implementing kind carries them.
- A query names a division entry that is not in the pool's scope, or gives a value for an entry the pool does not have: refused, the error names the entry.
- A branch's schema no longer defines a scope element: this cannot happen, because the schema change is refused on every branch (User Story 4, scenario 4).
- The whole range of one division is full while other divisions have free numbers: the request from the full division is refused with the pool-exhausted error; other divisions keep allocating.

## Requirements *(mandatory)*

### Functional Requirements

#### The allocation scope on a pool

- **FR-001**: A number pool MUST be able to carry an optional allocation scope: an ordered list of elements, each referencing one attribute or one relationship of the kind the pool is attached to. With a scope set, the pool allocates within the combination of those elements' values, one division per combination. With no scope, the pool's ranges are one shared space and the pool behaves exactly as today. (PRD FR-014.)
- **FR-002**: Each scope element MUST store the unique identifier of the schema element (the id of the attribute or relationship on the default branch) together with its readable name. The identifier is the reference; the name is for display. (Decisions 3 and 4.)
- **FR-003**: On creation, a scope element MUST be accepted as the schema element's identifier or as its name. Either form MUST resolve against the schema of the default branch, whatever branch the request runs on, and MUST be stored as the identifier and the name. A value that resolves to nothing on the default branch MUST be refused, and the error MUST name it. (Decision 1.)
- **FR-004**: A scope element MUST reference either a relationship of cardinality one or an attribute, and either way the element MUST be required on the pool's kind. A scope element that is optional, that is a relationship of cardinality many, that is a path into a related node, that names the pool's own tracked attribute, or that appears twice in the scope MUST be refused when the pool is saved, and the error MUST name the element. (PRD FR-015; Jira IFC-3348.)
- **FR-005**: When the pool's kind is a generic, every scope element MUST be declared on the generic. (Jira IFC-3348.)
- **FR-006**: A scope MUST be refused on a pool whose tracked attribute is `unique: true`, because a globally unique number cannot repeat per division. (Jira IFC-3348, IFC-3352.)
- **FR-007**: An allocation scope MUST NOT be changed or cleared after the pool is created, on a user-created pool and on a schema-created pool alike. An update that sends a scope different from the stored one MUST be refused with an error saying the scope cannot change after creation. An update that sends the stored scope unchanged MUST be accepted. (Decision 2.)
- **FR-008**: A pool's scope MUST be independent of the attribute's uniqueness constraints. A scope that does not match a constraint, or one set where no constraint exists, MUST be accepted without a warning. Uniqueness constraints keep behaving exactly as today and remain the only thing that makes a value invalid. (PRD FR-017.)

#### Allocating within a division

- **FR-009**: The division of a node MUST be the tuple of its values for the scope elements, in scope order: for a relationship element the peer's id, for an attribute element the value as text. A node holding nothing for an element MUST contribute an empty value. (PR #10932.)
- **FR-010**: With a scope set, every number the pool hands out MUST be the lowest number free within the division of the node being written, across the pool's ranges in their allocation order, and MUST be checked against that division only. A number tracked in another division MUST NOT block the allocation, and a number tracked in the same division MUST NOT be handed out again. (PRD FR-014, FR-016.)
- **FR-011**: The division of the node being written MUST be read from the node as it will be saved, so that a create and an update that changes a scoped field allocate in the division the node ends up in.
- **FR-012**: Allocation against an identifier MUST stay repeatable on a scoped pool: a request with an identifier the pool already holds a record for MUST return the number it already had. (PRD FR-032.)
- **FR-013**: The lock taken during allocation MUST be keyed on the pool and the division, so that writers in different divisions allocate in parallel and writers in one division are serialised. (PRD, "The allocator"; Jira IFC-3349.)
- **FR-014**: When a caller provides a number together with a scoped pool, the number MUST be checked against the division of the node being written: a number the pool already tracks in that division MUST be refused with the same error any duplicate save gives, and a number tracked only in another division MUST be accepted. The paths that record a provided number for a pool are delivered by the manual-attach work (IFC-3184) and are not in the working tree, so this feature carries no task for FR-014: it is the rule those paths must apply when they land, and the division check they need (the used query with a division) is delivered here. (PRD FR-016, FR-028.)
- **FR-015**: Which numbers are unavailable within a division MUST be worked out in the database. The amount of data inside a pool's ranges MUST NOT change how much memory one allocation holds. (PRD FR-013.)

#### Reading a scoped pool

- **FR-016**: Infrahub MUST expose the three dedicated number-pool queries described in PR #10932: `InfrahubNumberPoolUtilization`, `InfrahubNumberPoolDivisions` and `InfrahubNumberPoolAllocations`, answering from the pool's records in the database.
- **FR-017**: In every type of those queries that returns the allocation scope, `allocation_scope` MUST be a list of objects, each with the schema element `id` and its readable `name`, instead of the list of strings the PR description shows. Each division entry returned MUST carry the element's `id` beside its `path` (the element's name). This is the breaking change of decision 5. The input that filters by division keeps `path` and `value` as in the PR description.
- **FR-018**: `InfrahubNumberPoolUtilization` MUST require a division on a scoped pool, giving a value for every scope element, and MUST report that division's figures over the whole pool and over each range. On an unscoped pool it MUST report the pool's figures and MUST refuse a division. (PR #10932.)
- **FR-019**: `InfrahubNumberPoolDivisions` MUST list every division whose holders hold at least one value the pool tracks on any live branch, with that division's figures over the whole pool, ordered by utilization descending then by display label. A division that holds no value MUST NOT be listed. On an unscoped pool the list MUST be empty. (PR #10932; the fullest division is the first row, PRD FR-020.)
- **FR-020**: `InfrahubNumberPoolAllocations` MUST list the numbers the pool tracks, inside the pool's space, with optional filters on division (which may name a subset of the scope elements), range, branch and provenance, paginated with `offset` and `limit`, and MUST return the count of matching rows before pagination. Each row MUST carry the value, the branch holding it, the holder (id, hfid, kind, display label), the identifier, the provenance and the range. (PR #10932.)
- **FR-021**: The figures of a division MUST count a value under the division its holder belongs to on the branch that holds the value, so that a holder moved to another site on a branch is counted under the new site on that branch and under the old site on the default branch.
- **FR-022**: The existing `InfrahubResourcePoolUtilization` and `InfrahubResourcePoolAllocated` queries MUST keep their shape and their behaviour. For a number pool they ignore the allocation scope, and their descriptions MUST say so and point to the dedicated queries. (PR #10932.)

#### Declaring the scope in the schema

- **FR-023**: The number-pool attribute kind MUST accept an optional `allocation_scope` list in its parameters, holding the names of the scope elements. (PRD FR-043.)
- **FR-024**: When the schema creates a pool, the declared scope MUST be resolved against the schema of the default branch, validated with the rules of FR-004 to FR-006, and stored on the pool as identifiers and names. A declaration that fails those rules MUST refuse the schema load, and the error MUST name the attribute and the element.
- **FR-025**: A schema load that changes or clears the declared scope of an attribute whose pool already exists MUST be refused, and the error MUST name the attribute. (Decision 2.)
- **FR-026**: A schema load on a branch other than the default branch that declares a scope referencing an element absent from the default branch's schema MUST be refused. (Decision 1.)

#### Keeping a scope valid when the schema changes

- **FR-027**: A schema change that would make a scoped element optional, remove it, change its cardinality, or make the pool's tracked attribute `unique: true` MUST be refused while a pool's scope depends on it, on every branch, and the error MUST name every dependent pool and the element. (PRD FR-019; Jira IFC-3352.)
- **FR-028**: Renaming a scoped element MUST be allowed. After the rename the stored readable name of the element MUST match the new name, on every pool that references it, and allocation and the queries MUST keep working without any change to the pools. (Decision 3.)

#### Behaviour that does not change

- **FR-029**: A pool with no scope MUST behave exactly as it does today: same numbers handed out, same figures reported, same errors. (PRD FR-014, SC-009.)
- **FR-030**: A scope MUST NOT change what a pool records. The pool still tracks only the numbers it handed out and the numbers a user told it to track. (PRD FR-009, P3 "Independent of P2".)
- **FR-031**: A number given back to the pool when its holder or its branch is deleted MUST be given back within its division, with no change to the existing cleanup. (PRD FR-034, FR-035.)

### Key Entities *(include if feature involves data)*

- **Number pool**: the existing branch-agnostic node attached to one kind and one attribute, with ranges. Gains an optional allocation scope, fixed at creation.
- **Allocation scope element**: one entry of a pool's scope. References one attribute or one relationship of the pool's kind by its schema element identifier, and carries the element's readable name. Ordered within the scope.
- **Division**: the tuple of values a node holds for the scope elements, in scope order. Not stored: derived from the holder nodes when allocating and when reading. One division is one space the pool allocates from.
- **Tracked number record**: the existing record that links a pool to the attribute of a holder node, with its identifier and provenance. Unchanged by this feature; the division of a record is derived from its holder.
- **Number-pool attribute parameters**: the existing parameters of the number-pool attribute kind in the schema. Gain the optional `allocation_scope` list of element names.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A deployment that maintained one pool per site expresses the same thing as one scoped pool, and adding a site adds no pool. (PRD SC-007.)
- **SC-002**: A node cannot be given a number already used in its own division, and is never blocked by a number used in another division. (PRD SC-008.)
- **SC-003**: A deployment that sets no scope sees no change at all: every existing number-pool test passes unchanged. (PRD SC-009.)
- **SC-004**: A deployment whose numbers are not yet distinct per site can scope a pool by site immediately, without declaring a uniqueness constraint and without cleaning its data first, and every number handed out afterwards is distinct within its site. (PRD SC-010.)
- **SC-005**: Allocation does not get slower or heavier as the amount of data inside a pool's ranges grows: the memory held by one allocation does not depend on the number of tracked values, and the latency of a scoped allocation measured on a live stack is reported next to the latency of an unscoped one. (PRD SC-012; Jira IFC-3354.)
- **SC-006**: An operator can tell from one query which division is the fullest, and the frontend team can build the pool page on the three queries without a further backend change.
- **SC-007**: Every refusal in this feature names the element, the pool or the attribute at fault, so that the operator can correct the request without reading the server logs.

## Assumptions

- The ranges of a pool (IFC-3065) exist in the working tree as `CoreNumberPoolRange` nodes. The allocator and the utilization reader still work from the pool's single `start_range` and `end_range`; the range-aware allocation of IFC-3065 is not in the working tree yet. This feature divides whichever space the pool allocates from, and its queries report per range from the pool's range nodes.
- The manual-attach work (IFC-3184) is in progress in the working tree: the record carries a provenance, but no path records a provided number yet. FR-014 names the behaviour those paths must have once they exist; it is not testable before they land.
- A version of the `allocation_scope` attribute and parameter exists on another branch (Jira IFC-3334, PR #10917). The working tree does not have it, and this spec does not use it as a source. The attribute is designed here from the five decisions.
- A scope element given by name resolves within the pool's kind, where attribute names and relationship names are unique together.
- The readable name stored with an element is refreshed from the default branch's schema whenever that schema is loaded, so that a rename cannot leave a stale name behind.
- The frontend work (pool form, pool page) is tracked in IFC-3363 and is out of scope here. The backend contract must expose everything that page needs.
- Which SDK changes the wrap-up ticket (IFC-3356) expects for this feature is not known from the sources.
- The documentation pages for scoping a pool and reading it with the dedicated queries belong to this feature, in the resource-manager section of the user documentation.

## Out of scope

- Changing an allocation scope after creation, including widening or narrowing it (PRD FR-018 is overridden by decision 2).
- Automatic creation of a pool per scope, or any pool generated per site.
- Search, pagination or other sort orders of the divisions list (Jira IFC-3329).
- The frontend pool form and pool page (IFC-3363).
- Ranges with weights and the range-aware allocator (IFC-3065), and attaching provided numbers to a pool (IFC-3184), beyond the division check of FR-014.
- Pools attached to a generic so that kinds sharing the generic share a number space: unchanged, the pool's kind may already be a generic.
- What happens to a scoped pool when its kind is deleted from the schema: today's behaviour for number pools applies, unchanged.

## Open points settled by judgment

- Which divisions the divisions list returns was not decided in Jira IFC-3329 (PRD FR-020 reads as every division that has nodes; PR #10932 lists only the divisions that hold a value). This spec follows PR #10932, the contract already communicated to the frontend team.
- Jira IFC-3348 (2026-10-08) validated a scope against the schema of the branch where the pool is saved, and Jira IFC-3354 planned a pool scoped by a field that exists on one branch only. Decision 1 replaces both: the default branch's schema is the only reference.
- Jira IFC-3352 refused the rename of a scoped field and asked the author to remove the entry first. Decision 3 makes the rename harmless, so the rename is allowed and the stored name follows it (FR-028).
