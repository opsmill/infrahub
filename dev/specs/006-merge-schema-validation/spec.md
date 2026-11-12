# Feature Specification: Validate schema changes against both branches at merge and rebase

**Feature Branch**: `merge-schema-validation`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Schema changes must be validated against the data of both branches at merge,
proposed-change merge and rebase. Scope: the schema load, merge and rebase issues found while investigating the
report that merge and rebase skip the validators of `migration_required` schema changes. Base: latest
`origin/release-1.12`."

## Overview

A schema designer changes a schema on a branch, for example by making an attribute unique or mandatory. When they
load that change directly on the default branch, Infrahub checks the stored data and refuses the change if a node
does not comply. When the same change reaches the default branch through a merge, a proposed-change merge or a
rebase, those checks do not run, so the default branch can end up holding data that breaks its own schema: a
unique attribute with duplicate values, or a mandatory attribute without a value.

The reverse also happens. A schema change loaded on the default branch after a branch was created is never
checked against the data of that branch. Merging or rebasing the branch brings non-compliant data into a schema
that forbids it. When the change is a kind change, the merged values can no longer be read.

This feature makes merge, proposed-change merge and rebase check every schema change made on either side since the
branch was created, against the data the operation would produce. Without it, the only way to keep the default
branch's data compliant is to load every schema change directly on the default branch, and a kind change merged
this way leaves values that can no longer be read.

### Issues in scope

| # | Issue | Effect today |
|---|-------|--------------|
| 1 | The checks of migration-required schema changes (unique, optional, a new mandatory attribute without a default value, kind, uniqueness constraints, number pool scope) do not run at merge or rebase | A merge or rebase is accepted while the default branch holds data that breaks the branch's change |
| 2 | Schema changes made on the default branch after branching are not checked against the branch's data | A merge or rebase is accepted while the branch holds data that breaks the default branch's change |
| 3 | At merge, the schema checks run only when the branch's own changes include a schema change | A change made only on the default branch is never checked at merge |
| 4 | The optional, kind and new-attribute checks read the default branch as it was when the branch was created | Data created on the default branch after branching is not checked |
| 5 | The new-attribute check flags every node of the kind, with or without a value | Reading the default branch's current data, it would refuse branch nodes that already have a value |
| 6 | The schema used for the merge checks takes the branch's copy of every value, including values only the default branch changed | Checks of the branch's data compare against the branch's older schema; they miss violations but never refuse |
| 7 | Each attribute's schema is held in a form that depends on its kind | Building the merged schema must handle an attribute whose kind changed on one side |
| 8 | The proposed-change schema check builds its merged schema the same way as issue 6 | The checks shown on a proposed change miss violations that the merge then refuses |
| 9 | The regex, enum, length and choices checks read the default branch as it was when the branch was created | Values created on the default branch after branching are not checked at merge |
| 10 | A schema load on a branch reads two views: some checks (unique, Number, hierarchy, relationship checks) read the default branch's current data, others read it as it was at branching | The same load can be refused or accepted depending on which check runs |
| 11 | At merge, the check of a new mandatory relationship may flag branch nodes that set it | Possible false refusal; found by reading the code, not reproduced |
| 12 | An attribute added on the default branch with a default value may be missing on branch nodes after a merge | Possible missing values; found by reading the code, not verified |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Refuse a branch whose schema change is broken by the default branch's data (Priority: P1)

A schema designer changes a schema on a branch. Meanwhile, someone creates data on the default branch that does not
comply with that change. When the designer merges the branch, merges its proposed change, or rebases it, Infrahub
refuses the operation and names each non-compliant node, the same way a direct schema load on the default branch
would.

**Why this priority**: This is the reported defect. Without it, the default branch can hold data that breaks its own
schema, and the only defense is to load every schema change on the default branch directly.

**Independent Test**: Make one schema change of each migration-required type on a branch, create non-compliant data
on the default branch after branching, then merge, merge the proposed change and rebase. Each operation is refused.

**Acceptance Scenarios**:

1. **Given** a branch that makes an attribute unique and the default branch holding two nodes with the same value
   created after branching, **When** the user merges the branch, **Then** the merge is refused with a message naming
   the attribute and the nodes, the branch stays open, and neither branch changes.
2. **Given** a branch that makes an attribute mandatory and a node without a value on the default branch,
   **When** the user rebases the branch, **Then** the rebase is refused with a message naming the node.
3. **Given** a branch that adds a mandatory attribute without a default value and a node of that kind on the default
   branch, **When** the user merges the branch's proposed change, **Then** the merge is refused.
4. **Given** a branch that changes an attribute's kind from Text to Number and a value on the default branch that is
   not a number, **When** the user merges, **Then** the merge is refused and the message names the value.
5. **Given** a branch that adds a uniqueness constraint and two nodes on the default branch that share the values,
   **When** the user merges, **Then** the merge is refused.
6. **Given** a branch that removes an attribute, or makes it optional, while a number pool created on the default
   branch after branching uses it to scope its numbers, **When** the user merges, **Then** the merge is refused.
7. **Given** any of the refusals above, **When** the user fixes the data and retries the merge or rebase, **Then**
   the operation succeeds.

---

### User Story 2 - Refuse a branch whose data breaks a schema change made on the default branch (Priority: P1)

A schema designer loads a schema change on the default branch while other branches are open. An engineer then merges
or rebases one of those branches, which holds data that does not comply with the new schema. Infrahub refuses the
operation and names each non-compliant node on the branch.

**Why this priority**: Without it, a merge brings non-compliant data into the default branch, and a kind change can
leave values that cannot be read.

**Independent Test**: Create a branch with data, load a schema change on the default branch that the branch's data
breaks, then merge, merge the proposed change and rebase. Each operation is refused.

**Acceptance Scenarios**:

1. **Given** a branch that holds a node of a kind, and the default branch then adds a mandatory attribute without a
   default value to that kind, **When** the user merges or rebases, **Then** the operation is refused and names the
   node.
2. **Given** a branch that holds a duplicate value, and the default branch then makes the attribute unique,
   **When** the user merges, **Then** the merge is refused.
3. **Given** a branch that holds a node without a value, and the default branch then makes the attribute mandatory,
   **When** the user rebases, **Then** the rebase is refused.
4. **Given** a branch that holds the value "big", and the default branch then changes the attribute's kind from Text
   to Number, **When** the user merges, **Then** the merge is refused and no unreadable value reaches the default
   branch.
5. **Given** a branch that has not changed the schema at all, **When** only the default branch changed it and the
   user merges, **Then** the checks still run.

---

### User Story 3 - Keep accepting valid merges and rebases (Priority: P1)

An engineer merges or rebases a branch whose data complies with every schema change on both sides. The operation is
accepted exactly as before, with no new refusal and no noticeable extra wait.

**Why this priority**: A false refusal blocks normal work and has no workaround short of changing valid data.

**Independent Test**: Run the accepted scenarios below through merge, proposed-change merge and rebase; each one is
accepted and leaves the expected data on the default branch.

**Acceptance Scenarios**:

1. **Given** a branch that adds a mandatory attribute while the kind has no nodes, and then creates nodes with
   values, **When** the user merges, **Then** the merge is accepted.
2. **Given** a branch that makes an attribute unique while every value created on the default branch after branching
   is distinct, **When** the user merges, **Then** the merge is accepted.
3. **Given** a node without a value created before branching, and a branch that sets the value and then makes the
   attribute mandatory, **When** the user merges, **Then** the merge is accepted, because the branch's value is the
   one the merge produces.
4. **Given** a node without a value created before branching, and a branch that deletes the node and then makes the
   attribute mandatory, **When** the user merges, **Then** the merge is accepted.
5. **Given** a branch that renames or removes an attribute that no number pool uses, **When** the user merges,
   **Then** the merge is accepted.
6. **Given** a branch without schema changes on either side, **When** the user merges or rebases, **Then** the
   result is the same as before this feature and no schema check runs.

---

### User Story 4 - See the same violations on the proposed change that the merge would raise (Priority: P2)

A reviewer opens a proposed change. Its schema check lists every node that would make the merge fail, for schema
changes made on either side, so the reviewer does not learn about them only when the merge is refused.

**Why this priority**: The merge itself is protected by user stories 1 and 2; this story makes the review show the
same result earlier.

**Independent Test**: For each refused scenario of user stories 1 and 2, open a proposed change and compare its
schema check with the merge refusal.

**Acceptance Scenarios**:

1. **Given** a proposed change whose merge would be refused, **When** its checks complete, **Then** the schema check
   fails and lists the same nodes as the merge refusal.
2. **Given** a schema change made only on the default branch after branching, **When** the proposed change's checks
   complete, **Then** the schema check does not report that change as one the branch made.

---

### User Story 5 - Check regex, enum, length and choices against the default branch's current data at merge (Priority: P3)

A schema designer tightens a regex, an enum, a length limit or a list of choices on a branch. Values created on the
default branch after branching that break the new rule refuse the merge, as the unique and Number checks already do.

**Why this priority**: The same gap as user story 1 for four more properties. It is planned as a separate pull
request so the first change stays focused.

This user story also fixes the first cause of [IFC-3491](https://opsmill.atlassian.net/browse/IFC-3491): a merge or a rebase accepts the removal of a dropdown choice
or an enum value that a node created on the default branch after branching still uses. The merged schema built by
`apply_changes_since` fixes its second cause, a merged schema that keeps the dropdown choice the branch removed.

**Independent Test**: For each of the four properties, tighten the rule on a branch, create a violating value on the
default branch after branching, and merge.

**Acceptance Scenarios**:

1. **Given** a branch that adds a regex and a value on the default branch created after branching that does not
   match, **When** the user merges, **Then** the merge is refused.
2. **Given** a branch that removes a dropdown choice or an enum value, and a node created on the default branch
   after branching that uses it, **When** the user merges or rebases, **Then** the merge or the rebase is refused.

---

### User Story 6 - Confirm and fix the two suspected merge gaps (Priority: P3)

Two gaps were found by reading the code and have not been reproduced. Each one is confirmed or ruled out with a test
first, and fixed only if confirmed.

**Why this priority**: Neither is confirmed, and neither causes the reported defect.

**Independent Test**: A test that reproduces each scenario below on the current code.

**Acceptance Scenarios**:

1. **Given** a branch that adds a mandatory relationship and creates nodes that set it, **When** the user merges,
   **Then** the merge is accepted.
2. **Given** a branch that holds nodes of a kind, and the default branch then adds an attribute with a default value
   to that kind, **When** the user merges, **Then** every merged node holds the default value.

---

### Edge Cases

- **Both branches change the same schema property**: the checks use the value the merge would write. Infrahub
  reports this as a conflict to resolve before the merge, so the checks use the resolved value.
- **An attribute's kind changed on one side and another property changed on the other**: the merged schema holds
  both changes.
- **The default branch removed an attribute or a kind that the branch did not change**: the merged schema leaves it
  out; if the branch changed it, the branch's version is kept and checked.
- **An attribute was renamed on one side**: changes made on the other side follow the attribute under its new name.
- **The branch deleted the non-compliant node**: the deletion is honored and the node is not flagged.
- **Profiles and templates of a kind**: a kind change is also checked against the values stored on profiles and
  templates of that kind.
- **A new mandatory attribute of kind NumberPool**: the check confirms the pool can number every existing node,
  instead of flagging nodes without a value.
- **A refused proposed-change merge is retried after the data is fixed**: the proposed change's checks must run
  again before the merge is accepted. This is existing behavior and stays unchanged.
- **The default branch itself**: a schema load on the default branch has no parent to compare with, so the data it
  reads does not change.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: At merge, proposed-change merge and rebase, Infrahub MUST run the check of every migration-required
  schema change that has a check, for the changes made on the branch and the changes made on the default branch
  since the branch was created.
- **FR-002**: Those checks MUST read the data the operation would produce: the default branch's current data, with
  the branch's changes taking precedence.
- **FR-003**: Those checks MUST compare the data against the schema the operation would write: the default branch's
  current schema, plus only the changes the branch made since it was created.
- **FR-004**: At merge, the schema checks MUST run when either branch changed the schema since the branch was created,
  and MUST NOT run when neither did.
- **FR-005**: The check of a new mandatory attribute without a default value MUST flag only nodes that have no value
  for it, are not deleted, and are not of a NumberPool attribute.
- **FR-006**: When a check finds a violation, the merge, proposed-change merge or rebase MUST be refused; the branch
  MUST stay open; and neither branch's schema or data MUST change.
- **FR-007**: The refusal message MUST name the kind, each non-compliant node, the constraint and, where the check
  reads a value, the value.
- **FR-008**: A schema load or schema check on a branch MUST keep reading the data the branch sees today, so this
  feature does not change which schema loads are accepted.
- **FR-009**: The proposed-change schema check MUST use the same merged schema and the same data as the merge, and
  MUST report the same violations.
- **FR-010**: The regex, enum, length and choices checks MUST read the data the merge would produce when called from
  merge, proposed-change merge or rebase (user story 5, separate pull request).
- **FR-011**: The two suspected gaps in user story 6 MUST each be confirmed or ruled out with a test; a confirmed gap
  MUST be fixed or recorded as a follow-up with its reproduction.
- **FR-012**: The merge and rebase documentation MUST list the refusals this feature adds, and for a mandatory
  attribute added on the default branch without a default value it MUST give the two recovery paths: delete the
  nodes on the branch, or add a default value on the default branch.

### Key Entities

- **Default branch** and **branch**: the two sides of a merge or rebase. A branch reads the default branch as it was
  when the branch was created, plus its own changes.
- **Common ancestor schema**: the default branch's schema at the time the branch was created, which both sides
  changed from.
- **Merged schema**: the schema a merge or rebase would write, used to run the checks before the operation changes
  anything.
- **Migration-required schema change**: a change to a schema property that stored data must comply with, such as
  unique, optional, kind or uniqueness constraints, and that has a check run against that data.
- **Branch view** and **merge view**: the two ways a check can read the default branch's data from a branch. The
  branch view reads it as it was when the branch was created; the merge view reads its current data with the
  branch's changes taking precedence.
- **Proposed change**: a request to merge a branch, with checks that report the problems the merge would hit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In each of the ten refusal scenarios of user stories 1 and 2, run through merge, proposed-change merge
  and rebase, the operation is refused; none of the 30 runs is accepted.
- **SC-002**: In each of the six accepted scenarios of user story 3, run through the same three paths, the operation
  is accepted; none of the 18 runs is refused.
- **SC-003**: After every refusal, the branch is still open, the schema and data of both branches are unchanged, and
  a retry after fixing the data succeeds for merge and rebase.
- **SC-004**: After every accepted merge, every value of every changed kind on the default branch can be read.
- **SC-005**: For every refusal scenario, the proposed change's schema check lists the same nodes as the merge
  refusal.
- **SC-006**: A merge or rebase where neither branch changed the schema runs no schema check.

## Assumptions

- Every branch reads the default branch as it was when the branch was created. Code that creates a branch that reads
  the default branch's current data is no longer used.
- When both branches change the same schema property, the existing conflict resolution decides the merged value;
  this feature does not change conflict handling.
- The number pool scope check was designed to read both branches at merge, so running it at merge and rebase needs no
  change to the check itself.
- The work starts from the latest `release-1.12`. An earlier implementation of user stories 1 to 3 and part of user
  story 4 exists as a stash (`migration-validators-wip-2026-11-03`) and was validated on a local instance; it is a
  reference, not a commitment to its design.
- No graph migration, GraphQL schema change or CI change is expected.

## Out of Scope

- Making a schema load on a branch read the same data for every check (issue 10). The branch view is kept for the
  checks that use it today, and the checks that read the merge view keep doing so. This needs its own decision,
  because changing either side changes which branch schema loads are accepted.
- Re-running a proposed change's checks automatically after the data is fixed.
- Warning, when a schema change is loaded on the default branch, about open branches whose merge it would block.
- Changing how schema conflicts between the two branches are detected or resolved.
- Keeping the default branch's changes to the profile and template kinds of a kind that the branch renamed. In that
  case the merged schema takes the branch's profile and template kinds whole. Project F2 of
  [INFP-719](https://opsmill.atlassian.net/browse/INFP-719) plans to build the merged schema by replaying the stored
  schema changes, matched by kind and name, instead of comparing the schemas of the two branches.

## Behavior Changes

- A rebase can now be refused when the branch's data breaks a schema change made on the default branch. When the
  default branch adds a mandatory attribute without a default value, the branch cannot add the value, because its
  schema does not have the attribute yet: the branch must delete those nodes, or the default branch must add a
  default value.
- The number pool scope check now runs at merge and rebase for attribute and relationship removals and renames.
- The proposed-change schema check reads the data the merge would produce.
