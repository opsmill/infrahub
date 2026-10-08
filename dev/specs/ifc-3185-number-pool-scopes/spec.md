# Feature Specification: Number pool allocation scopes

**Feature Branch**: `pmi-number-pool-scopes-spec-ifc-3185` (from `feature-number-pools-1.12`)

**Created**: 2026-10-08

**Status**: Draft

**Input**: User description: [IFC-3185](https://opsmill.atlassian.net/browse/IFC-3185) (Number pool improvements, part 3, pools allocation scopes), read with the Number Pools PRD in Notion filtered to allocation scopes, the child tickets of the epic, the description of PR #10932, the code of the branch `feature-number-pools-1.12`, and thirteen decisions of the product owner recorded under [Decisions of the product owner](#decisions-of-the-product-owner).

## Problem

A number that only has to be distinct within a scope (per site, per pod) forces an operator to create and maintain one number pool per scope, and to keep creating pools as scopes are added. A pool has nowhere to record the scope it serves, so when a node in one site is created or updated, nothing checks that its number came from that site's pool rather than another site's. (PRD, problem 3.)

## Decisions of the product owner

These thirteen decisions were taken by the product owner after the sources were written. They override the Notion PRD, the Jira tickets and the description of PR #10932 wherever they differ.

1. A number pool and its allocation scope can only reference attributes and relationships that exist in the schema on the default branch.
2. An allocation scope cannot be modified after the pool is created, neither on a schema-defined pool nor on a user-created pool.
3. An allocation scope element is not a plain string holding the attribute name. It stores the unique identifier of the attribute or relationship (the schema element id), so that it can be referenced.
4. The user views each element with a readable name. When a query returns the allocation scope, each element is an object holding both the identifier and the name (`id` and `name`), not a string.
5. The structure described in PR #10932 was communicated to the frontend team. It changes only to apply decision 4 (a list of `{id, name}` objects where it listed strings). This is a breaking change relative to the PR description. The rest of that structure stays unless a reason to change it is documented in this spec or the plan.
6. Renaming a scoped attribute or relationship is allowed. Removing it, making it optional, or changing its cardinality is refused while a pool's scope depends on it.
7. The division of a node is read on the branch the request runs on.
   - The division is the set of values of the node's scope elements: the peer id of a relationship, the value of an attribute.
   - This applies to the node being written and to the holders of the numbers the pool already tracks.
   - It is a normal branch read: a node not changed on that branch reads as on the default branch.
   - If a scope element does not exist in the schema of that branch, the request returns an error and allocates or returns nothing.
   - Known limitation, accepted and not fixed: a holder that exists only on another branch is not visible from the request branch, so its number is not counted in its division. Two branches can hand out the same number in the same division, and both holders keep it after the merge. Example: R1, created on `b2` in site A, receives 1; R2, created on `b1` in site A, also receives 1.
8. `InfrahubNumberPoolDivisions` lists only the divisions that hold at least one value.
9. For a scope declared in the schema (`parameters.allocation_scope` on a schema-created pool), each declared name is resolved to an element id against the candidate schema being loaded, and the declaration is compared to the stored scope by id. With a pool storing `{id: X, name: "site"}`:
   - `site` is renamed to `location` and the file still declares `["site"]`: the load is refused, and the error says that `site` was renamed to `location` and asks to update `allocation_scope`.
   - `site` is renamed to `location` and the file declares `["location"]`: the load is accepted, because the ids match, and the stored name becomes `location` in the same load.
   - The file declares another element (`["role"]`): the load is refused, because the scope is immutable.
10. Attributes of kind `List`, `JSON` and `Any` are refused as scope elements, so a division holds only scalar values: the peer id of a relationship or the value of a scalar attribute. This revision of 2026-10-09 replaces the earlier version of this decision, which accepted `List` and `JSON` attributes, and is to be confirmed with the product owner. It matches the refusal of these kinds in Jira IFC-3348.
11. When a caller provides a number together with a scoped pool, the pool records it under the writer's division and does not refuse it, even when the pool already tracks that number in the same division. The attribute's uniqueness constraints remain the only refusal. This overrides the refusal in PRD FR-016 and Jira IFC-3349.
12. A scope element written as a path (`role__value`, or any entry containing `__`) is refused, and the error tells the user to write the element name (`role`). This overrides the normalisation of `role__value` to `role` in Jira IFC-3348.
13. Decision 7 also applies to the three dedicated queries: their figures and their division filter read each holder's division on the branch the query runs on. This changes the example figures of the PR #10932 fixed dataset that the frontend team has seen.

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
11. **Given** a pool scoped by `site`, **When** a device in site A is updated to move to site B and allocate in the same request, **Then** it receives the lowest number free within site B.
12. **Given** a pool scoped by `site`, **When** a device allocates on a branch whose schema does not define `site` on the device kind (a branch created before `site` was added on the default branch), **Then** the request is refused and nothing is allocated (decision 7).

---

### User Story 2 - View how full each division is and which numbers it holds (Priority: P2)

An operator who opens a scoped number pool views the divisions that hold numbers, the figures of each division over the whole pool and over each range, and every tracked number with its holder, branch, provenance and range. The three dedicated GraphQL queries of PR #10932 answer these questions from the pool's records, and the frontend team builds the pool page on them.

**Why this priority**: A scoped pool that cannot be read per division hides a division that is about to run out (PRD FR-020). The frontend epic IFC-3363 depends on this contract.

**Independent Test**: Load a pool scoped by `site` with numbers in three sites and none in a fourth, then run the three queries and compare the answers with the loaded data.

**Acceptance Scenarios**:

1. **Given** a pool scoped by `site` with ranges 1 to 50 and 51 to 100, where site A holds 40 values, site B holds 30 and site D holds none, **When** the operator lists the divisions, **Then** the list holds sites A and B, each with its figures over the whole pool, ordered by utilization descending then by display label, and site D is absent (decision 8).
2. **Given** that pool, **When** the operator asks for the utilization of site B, **Then** the answer gives the figures of site B over the whole pool and over each range.
3. **Given** that pool, **When** the operator asks for its utilization without naming a division, **Then** the query is refused, because figures over several divisions match no space the pool allocates from.
4. **Given** an unscoped pool, **When** the operator asks for its utilization, **Then** the answer covers the whole pool; **and when** a division is given, **Then** the query is refused.
5. **Given** a scoped pool, **When** the operator lists its allocations filtered by a division, a range, a branch or a provenance, **Then** only the matching rows come back, with the count of rows before pagination, and each row carries its value, branch, holder, identifier, provenance and range.
6. **Given** any query that returns the allocation scope, **When** the operator reads it, **Then** each element is an object with the schema element `id` and its readable `name`.
7. **Given** device D1 holding 5 in site A on the default branch and moved to site C on branch `b1`, **When** the operator lists the divisions on `b1`, **Then** 5 counts under site C; **and when** the operator lists them on the default branch, **Then** 5 counts under site A (decision 7).

---

### User Story 3 - Declare the scope of a schema-defined pool (Priority: P3)

A schema author declares, in the parameters of a number-pool attribute, the allocation scope of the pool the schema creates. The pool is created with that scope when the schema loads on the default branch. The scope is resolved against the schema of the default branch and stored on the pool as element identifiers and names. On a later load the declaration is compared to the stored scope by id, so that a renamed element can be declared under its new name.

**Why this priority**: A pool the schema creates is configured from the schema, so anything that configures it has to be declarable there (PRD FR-043). It depends on the scope existing on the pool (User Story 1).

**Independent Test**: Load a schema whose number-pool attribute declares `allocation_scope`, then read the pool and allocate from two divisions.

**Acceptance Scenarios**:

1. **Given** a schema whose number-pool attribute declares `parameters.allocation_scope: ["site"]`, **When** the schema loads on the default branch, **Then** the pool it creates carries that scope, stored as the identifier and the name of the `site` relationship.
2. **Given** that schema, **When** nodes in two sites are created, **Then** both receive the lowest number free within their own site.
3. **Given** a schema-created pool scoped by `site`, **When** a later schema load declares `["role"]` or clears the declaration for the same attribute, **Then** the load is refused and the error names the attribute and says the scope cannot change after the pool is created (decision 9).
4. **Given** a schema whose declared scope names an element that is optional, many, on a related node, or absent from the kind on the default branch, **When** the schema loads, **Then** the load is refused and the error names the element.
5. **Given** a schema that declares a scope on a branch for an element that exists only on that branch, **When** the schema loads on that branch, **Then** the load is refused, because a scope can only reference elements of the default branch's schema (decision 1).
6. **Given** a schema-created pool scoped by `site`, **When** a schema load renames `site` to `location` and still declares `["site"]`, **Then** the load is refused and the error says that `site` was renamed to `location` and asks to update `allocation_scope` (decision 9).
7. **Given** a schema-created pool scoped by `site`, **When** a schema load renames `site` to `location` and declares `["location"]`, **Then** the load is accepted and the pool's scope reads `location` as the element's name (decision 9).

---

### User Story 4 - Keep a scoped pool valid when the schema changes (Priority: P4)

A schema author who changes a field that a pool's scope references is refused when the change would stop the field from giving exactly one value per node, and the error names the pool. Renaming such a field is allowed: the scope references the field by its identifier, so the stored readable name follows the new name.

**Why this priority**: Without this guard a scope can silently stop dividing the pool (PRD FR-019). It depends on User Story 1.

**Independent Test**: Create a scoped pool, then load schema changes that make the field optional, many, removed, or renamed, and check each outcome.

**Acceptance Scenarios**:

1. **Given** a pool scoped by `site`, **When** a schema load makes the `site` relationship optional, changes its cardinality to many, or removes it, **Then** the load is refused and the error names the pool and the field (decision 6).
2. **Given** a pool scoped by `site`, **When** a schema load makes the pool's tracked attribute `unique: true`, **Then** the load is refused and the error names the pool, because a globally unique number cannot repeat per division.
3. **Given** a user-created pool scoped by `site`, **When** a schema load renames the `site` relationship to `location`, **Then** the load succeeds, the pool keeps allocating per site, and the scope reads `location` as the element's name (decision 6).
4. **Given** a pool scoped by `site`, **When** the schema change is loaded on a branch other than the default branch, **Then** it is refused on that branch as well, so that the refusal does not wait for the merge.

---

### Edge Cases

- A scope names the same element twice: refused, the error names the element.
- A scope is given as an empty list: the pool is created without a scope, exactly as if the field had been left out.
- A scope element is given by name and by identifier in the same request: both resolve to the same stored element; a name that does not resolve on the default branch is refused.
- A scope element is an attribute of kind `List`, `JSON` or `Any`: refused when the pool is saved, and the error names the element and its kind (decision 10).
- A relationship entry points at a peer that exists on a branch only: the division value is the peer id; on the default branch the holder reads as having no peer and contributes an empty value (decision 7).
- A node holds no peer or no value for a scope element (data written before the element became required): it is treated as an empty division value, both for allocation and for the queries.
- A holder exists only on another branch: the known limitation of decision 7 applies. It is documented and asserted by a test, not fixed.
- A scoped field on a node that already holds a tracked number is changed, moving the node to a division where that number is already taken: the pool does not refuse the change. Only the attribute's uniqueness constraints decide whether a value is valid (PRD FR-017). The pool reports the number under its new division from then on.
- A scope is created on a pool whose attribute already holds the same number twice within one division: the pool tracks none of that data (PRD FR-010), so creation is accepted, and the numbers it hands out from then on are distinct within each division.
- A user provides a number together with a scoped pool (the attach path of IFC-3184): the pool records it under the writer's division and refuses nothing, even when it already tracks that number in the division; the next allocation in that division skips it (FR-014, decision 11).
- Two user-created pools on the same kind and attribute carry different scopes: allowed; each pool tracks only its own records, and a number is checked against the scope of the pool named in the request.
- The pool's kind is a generic: the scope elements must be declared on the generic itself, so that every implementing kind carries them.
- A query names a division entry that is not in the pool's scope, or gives a value for an entry the pool does not have: refused, the error names the entry.
- A request runs on a branch whose schema does not define a scope element on the pool's kind (a branch created before the element was added on the default branch, and not rebased since): the request is refused and nothing is allocated or returned (decision 7). Once the branch is rebased, the element exists there and the request works.
- The whole range of one division is full while other divisions have free numbers: the request from the full division is refused with the pool-exhausted error; other divisions keep allocating.

## Requirements *(mandatory)*

### Functional Requirements

#### The allocation scope on a pool

- **FR-001**: A number pool MUST be able to carry an optional allocation scope: an ordered list of elements, each referencing one attribute or one relationship of the kind the pool is attached to. With a scope set, the pool allocates within the combination of those elements' values, one division per combination. With no scope, the pool's ranges are one shared space and the pool behaves exactly as today. (PRD FR-014.)
- **FR-002**: Each scope element MUST store the unique identifier of the schema element (the id of the attribute or relationship on the default branch) together with its readable name. The identifier is the reference; the name is for display. The `allocation_scope` attribute that exists on the pool today stores plain names; it MUST store `{id, name}` objects instead. (Decisions 3 and 4.)
- **FR-003**: On creation, a scope element MUST be accepted as the schema element's identifier or as its name. Either form MUST resolve against the schema of the default branch, whatever branch the request runs on, and MUST be stored as the identifier and the name. A value that resolves to nothing on the default branch MUST be refused, and the error MUST name it. (Decision 1.)
- **FR-004**: A scope element MUST reference either a relationship of cardinality one or an attribute of a scalar kind (any kind except `List`, `JSON` and `Any`), and either way the element MUST be required on the pool's kind. A scope element that is optional, that is an attribute of kind `List`, `JSON` or `Any`, that is a relationship of cardinality many, that is a path into a related node or into a property (contains `__`; the error tells the user to write the element name), that names the pool's own tracked attribute, or that appears twice in the scope MUST be refused when the pool is saved, and the error MUST name the element. (PRD FR-015; Jira IFC-3348; decisions 10 and 12.)
- **FR-005**: When the pool's kind is a generic, every scope element MUST be declared on the generic. (Jira IFC-3348.)
- **FR-006**: A scope MUST be refused on a pool whose tracked attribute is `unique: true`, because a globally unique number cannot repeat per division. (Jira IFC-3348, IFC-3352.)
- **FR-007**: An allocation scope MUST NOT be changed or cleared after the pool is created, on a user-created pool and on a schema-created pool alike. An update that sends a scope different from the stored one, or `null`, MUST be refused with an error saying the scope cannot change after creation. An update that sends the stored scope unchanged MUST be accepted. (Decision 2.)
- **FR-008**: A pool's scope MUST be independent of the attribute's uniqueness constraints. A scope that does not match a constraint, or one set where no constraint exists, MUST be accepted without a warning. Uniqueness constraints keep behaving exactly as today and remain the only thing that makes a value invalid. (PRD FR-017.)

#### Allocating within a division

- **FR-009**: The division of a node MUST be the tuple of its values for the scope elements, in scope order: for a relationship element the peer's id, for an attribute element the scalar value as stored, with no normalisation. A node holding nothing for an element MUST contribute an empty value. (PR #10932; decision 10.)
- **FR-010**: With a scope set, every number the pool hands out MUST be the lowest number free within the division of the node being written, across the pool's ranges in their allocation order, and MUST be checked against that division only. A number tracked in another division MUST NOT block the allocation, and a number tracked in the same division MUST NOT be handed out again. (PRD FR-014, FR-016.)
- **FR-011**: The division of the node being written MUST be read from the node as it will be saved, on the branch of the request, so that a create and an update that changes a scoped field allocate in the division the node ends up in. The division of each holder of a tracked number MUST be read on the branch of the request as well, as a normal branch read: a holder not changed on that branch reads as on the default branch, and a holder that exists only on another branch is not visible. (Decision 7.)
- **FR-012**: Allocation against an identifier MUST stay repeatable on a scoped pool: a request with an identifier the pool already holds a record for MUST return the number it already had. (PRD FR-032.)
- **FR-013**: The lock taken during allocation MUST be keyed on the pool and the division, so that writers in different divisions allocate in parallel and writers in one division are serialised. (PRD, "The allocator"; Jira IFC-3349.)
- **FR-014**: When a caller provides a number together with a scoped pool (the attach path delivered by IFC-3184, which records the number with the provenance `provided`), the pool MUST record it under the writer's division like any other record and MUST NOT refuse it: the pool has no duplicate rule (IFC-3184 FR-028), and the attribute's uniqueness constraints remain the only refusal (FR-008). From then on the number MUST count as used in that division, so the next allocation in that division skips it. (PRD FR-016, first half; IFC-3184 FR-028; decision 11.)
- **FR-015**: Which numbers are unavailable within a division MUST be worked out in the database. The amount of data inside a pool's ranges MUST NOT change how much memory one allocation holds. (PRD FR-013.)
- **FR-016**: When the schema of the request's branch does not define a scope element on the pool's kind, an allocation, an attach and each dedicated query MUST be refused with an error naming the element and the branch, and MUST allocate or return nothing. (Decision 7.)

#### Reading a scoped pool

- **FR-017**: Infrahub MUST expose the three dedicated number-pool queries described in PR #10932: `InfrahubNumberPoolUtilization`, `InfrahubNumberPoolDivisions` and `InfrahubNumberPoolAllocations`, answering from the pool's records in the database.
- **FR-018**: In every type of those queries that returns the allocation scope, `allocation_scope` MUST be a list of objects, each with the schema element `id` and its readable `name`, instead of the list of strings the PR description shows. Each division entry returned MUST carry the element's `id` beside its `path` (the element's name). This is the breaking change of decision 5. The input that filters by division keeps `path` and `value` as in the PR description.
- **FR-019**: `InfrahubNumberPoolUtilization` MUST require a division on a scoped pool, giving a value for every scope element, and MUST report that division's figures over the whole pool and over each range. On an unscoped pool it MUST report the pool's figures and MUST refuse a division. (PR #10932.)
- **FR-020**: `InfrahubNumberPoolDivisions` MUST list every division that holds at least one value the pool tracks, each holder's division being read on the branch the query runs on (FR-022), with that division's figures over the whole pool, ordered by utilization descending then by display label. A division that holds no value MUST NOT be listed. On an unscoped pool the list MUST be empty. (Decision 8; the fullest division is the first row, PRD FR-020.)
- **FR-021**: `InfrahubNumberPoolAllocations` MUST list the numbers the pool tracks, inside the pool's space, with optional filters on division (which may name a subset of the scope elements), range, branch and provenance, paginated with `offset` and `limit`, and MUST return the count of matching rows before pagination. Each row MUST carry the value, the branch holding it, the holder (id, hfid, kind, display label), the identifier, the provenance and the range. (PR #10932.)
- **FR-022**: The figures and the division filter of the three queries MUST read each holder's division on the branch the query runs on (FR-011): a holder moved to another site on a branch is counted under the new site on that branch and under the old site on the default branch. One value counts in one division per branch read. (Decisions 7 and 13.)
- **FR-023**: The existing `InfrahubResourcePoolUtilization` and `InfrahubResourcePoolAllocated` queries MUST keep their shape and their behaviour. For a number pool they ignore the allocation scope, and their descriptions MUST say so and point to the dedicated queries. (PR #10932.)

#### Declaring the scope in the schema

- **FR-024**: The number-pool attribute kind MUST accept an optional `allocation_scope` list in its parameters, holding the names of the scope elements. The parameter exists today and refuses every change on a later load; it MUST instead accept a later load whose declaration matches the stored scope by id, as FR-026 describes. (PRD FR-043; decision 9.)
- **FR-025**: When the schema creates a pool, the declared scope MUST be resolved against the schema of the default branch, validated with the rules of FR-004 to FR-006, and stored on the pool as identifiers and names. A declaration that fails those rules MUST refuse the schema load, and the error MUST name the attribute and the element.
- **FR-026**: On every schema load, the declaration of an attribute whose pool already exists MUST be resolved to element ids against the candidate schema and compared to the stored scope by id. A declaration whose ids differ from the stored ids, or that is cleared, MUST refuse the load, and the error MUST name the attribute and say the scope cannot change after the pool is created. A declaration whose name no longer resolves because the element was renamed MUST refuse the load, and the error MUST say which element was renamed to which name and ask to update `allocation_scope`. A declaration carrying the new name of a renamed element MUST be accepted, and the stored name MUST follow in the same load. (Decisions 2 and 9.)
- **FR-027**: A schema load on a branch other than the default branch that declares a scope referencing an element absent from the default branch's schema MUST be refused. (Decision 1.)

#### Keeping a scope valid when the schema changes

- **FR-028**: A schema change that would make a scoped element optional, remove it, change its cardinality, or make the pool's tracked attribute `unique: true` MUST be refused while a pool's scope depends on it, on every branch, and the error MUST name every dependent pool and the element. (PRD FR-019; Jira IFC-3352; decision 6.)
- **FR-029**: Renaming a scoped element MUST be allowed. After the rename the stored readable name of the element MUST match the new name, on every pool that references it, and allocation and the queries MUST keep working without any change to the pools. (Decisions 3 and 6.)

#### Behaviour that does not change

- **FR-030**: A pool with no scope MUST behave exactly as it does today: same numbers handed out, same figures reported, same errors. (PRD FR-014, SC-009.)
- **FR-031**: A scope MUST NOT change what a pool records. The pool still tracks only the numbers it handed out and the numbers a user told it to track. (PRD FR-009, P3 "Independent of P2".)
- **FR-032**: A number given back to the pool when its holder or its branch is deleted MUST be given back within its division, with no change to the existing cleanup. (PRD FR-034, FR-035.)

### Key Entities *(include if feature involves data)*

- **Number pool**: the existing branch-agnostic node attached to one kind and one attribute, with ranges. Its `allocation_scope` attribute changes from a list of names to a list of scope elements, fixed at creation.
- **Allocation scope element**: one entry of a pool's scope. References one attribute or one relationship of the pool's kind by its schema element identifier, and carries the element's readable name. Ordered within the scope.
- **Division**: the tuple of values a node holds for the scope elements, in scope order, read on the branch of the request. Not stored: derived from the holder nodes when allocating and when reading. One division is one space the pool allocates from.
- **Tracked number record**: the existing record that links a pool to the attribute of a holder node, with its identifier and provenance (`allocated` or `provided`). Unchanged by this feature; the division of a record is derived from its holder.
- **Number-pool attribute parameters**: the existing parameters of the number-pool attribute kind in the schema. The existing optional `allocation_scope` list of element names is compared to the stored scope by id on every later load (FR-026).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A deployment that maintained one pool per site expresses the same thing as one scoped pool, and adding a site adds no pool. (PRD SC-007.)
- **SC-002**: A node cannot be given a number already used in its own division, and is never blocked by a number used in another division. (PRD SC-008.)
- **SC-003**: A deployment that sets no scope sees no change at all: every existing number-pool test passes unchanged, except the test that clears a scope with `null`, replaced by the refusal of FR-007. (PRD SC-009.)
- **SC-004**: A deployment whose numbers are not yet distinct per site can scope a pool by site immediately, without declaring a uniqueness constraint and without cleaning its data first, and every number handed out afterwards is distinct within its site. (PRD SC-010.)
- **SC-005**: Allocation does not get slower or heavier as the amount of data inside a pool's ranges grows: the memory held by one allocation does not depend on the number of tracked values, and the latency of a scoped allocation measured on a live stack is reported next to the latency of an unscoped one. (PRD SC-012; Jira IFC-3354.)
- **SC-006**: An operator can tell from one query which division is the fullest, and the frontend team can build the pool page on the three queries without a further backend change.
- **SC-007**: Every refusal in this feature names the element, the pool or the attribute at fault, so that the operator can correct the request without reading the server logs.

## Assumptions

- The ranges of a pool (IFC-3065) are in the working tree: `CoreNumberPoolRange` nodes, the allocator draining the ranges heaviest first and lowest start first, and the utilization reader measuring the effective space (ranges clipped to the attribute's bounds minus its excluded values). This feature divides that space.
- The manual-attach work (IFC-3184) is in the working tree: a write carrying `value` and `from_pool` records the number with the provenance `provided`, and the pool has no duplicate rule. FR-014 states what this feature adds to that path (the record counts in the writer's division).
- The `allocation_scope` attribute on the pool and the `allocation_scope` parameter of the number-pool attribute kind are in the working tree (IFC-3334, PR #10917), storing plain element names, with an update that clears the scope accepted. No released version of Infrahub stores a scope, so the stored shape changes to `{id, name}` objects without a data migration.
- PR #10932 (the three dedicated queries served from a fixed dataset) is open against another branch and must be rebased onto `feature-number-pools-1.12` before its contract is updated to decision 4.
- A scope element given by name resolves within the pool's kind, where attribute names and relationship names are unique together.
- Infrahub treats a schema change as a rename when the loaded schema carries the element's id with the new name; the stored readable name is refreshed from the default branch's schema whenever that schema is loaded, so that a rename cannot leave a stale name behind.
- The frontend work (pool form, pool page) is tracked in IFC-3363 and is out of scope here. The backend contract must expose everything that page needs.
- The SDK pull requests named in Jira IFC-3356 (infrahub-sdk-python #1371 and #1402) are merged on the SDK's `pmi-number-pool-range-protocols` branch and carry `allocation_scope` as a list of strings in the generated schema models; PR #10949 points the `python_sdk` submodule at SDK commit `1bd89c8`, which carries them, and that commit is not in the SDK's `infrahub-develop` yet.
- The documentation pages for scoping a pool and reading it with the dedicated queries belong to this feature, in the resource-manager section of the user documentation.

## Out of scope

- Changing an allocation scope after creation, including widening or narrowing it (PRD FR-018 is overridden by decision 2).
- Automatic creation of a pool per scope, or any pool generated per site.
- Search, pagination or other sort orders of the divisions list (Jira IFC-3329).
- The frontend pool form and pool page (IFC-3363).
- Fixing the known limitation of decision 7.
- Pools attached to a generic so that kinds sharing the generic share a number space: unchanged, the pool's kind may already be a generic.
- What happens to a scoped pool when its kind is deleted from the schema: today's behaviour for number pools applies, unchanged.

## Source statements replaced by the decisions

- Jira IFC-3348 stored an entry written as `role__value` as `role`. Decision 12 refuses any entry containing `__` (FR-004).
- PRD FR-016 and Jira IFC-3349 refuse a provided number that the pool already tracks in the writer's division. Decision 11 records it in the division and refuses nothing (FR-014), as the attach path of IFC-3184 already does (IFC-3184 FR-028).
- Jira IFC-3347 and IFC-3329 count a value under every division its holder occupies on any live branch (a union over branches). Decisions 7 and 13 read a holder's division on the branch of the request, so FR-022 counts a value under one division per branch read.
- Jira IFC-3348 validated a scope against the schema of the branch where the pool is saved, and Jira IFC-3354 planned a pool scoped by a field that exists on one branch only, with entries applied per branch. Decision 1 replaces both: the default branch's schema is the only reference, and decision 7 refuses a request on a branch whose schema lacks an element.
