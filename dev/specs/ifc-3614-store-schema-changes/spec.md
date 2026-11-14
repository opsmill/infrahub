# Feature Specification: Store schema changes and query the schema change history of a branch

**Feature Branch**: `ajtmccarty/ifc-3614-store-migrations`

**Created**: 2026-11-14

**Status**: Draft

**Input**: Jira task [IFC-3614](https://opsmill.atlassian.net/browse/IFC-3614), "Store each schema
change, its applications and its migrations, and query the schema change history of a branch". It
is project B of the design document
[INFP-719 Make schema migrations visible](https://app.notion.com/p/opsmill/INFP-719-Make-schema-migrations-visible-402228b830258193b43ed097d965f633).
Parent epic: [IFC-3590](https://opsmill.atlassian.net/browse/IFC-3590).

## Context

A schema owner loads schema changes on a branch. Today they cannot view which migrations ran on
the branch, or what the migrations did. When a load fails, the error is in the response of that
one request and nowhere else.

A merge and a rebase also cannot apply a branch's schema loads one after the other, in the order
the schema owner made them, because the loads are not stored. Infrahub calculates one combined
change instead.

This feature stores every schema change, every time it is applied, and every migration that the
application runs. It also changes how a schema is built from user input: one applier builds the
schema from the stored operations, for every schema load, every dropdown or enum mutation and
every schema check. Later tasks of the same epic use the stored records and the applier to report
the progress of a load, to stage a schema change, and to apply schema changes in order at rebase
and merge.

## Terms

- **Schema change operation**: one change to the schema: add, remove or change a node, an
  attribute or a relationship. Example: add `serial` to `DcimGenericDevice`.
- **Schema change**: the schema change operations from one schema load, or from one dropdown or
  enum mutation.
- **Application**: one time a schema change is applied to a branch. Each application has its own
  migrations.
- **Migration**: one data operation on the nodes of one kind, or of the kinds that inherit from a
  generic, during an application. Example: `node.attribute.add` on `DcimCloudDevice.serial`.
- **Schema change history**: the applied schema changes of a branch, in order of version.
- **Processing**: the step that calculates the parts of a schema the user did not write, such as
  the attributes a kind inherits from a generic, generated relationships, and profile and template
  kinds.
- **Main**: the default branch.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A schema load gives the same schema and the same migrations as before (Priority: P1)

A schema owner loads a schema file on a branch, changes a dropdown or enum through a mutation, or
checks a schema file before loading it. Infrahub now builds the schema from the operations it
records, with one applier. The branch ends with the same schema, and the nodes go through the same
migrations, as a load gave before this feature.

**Why this priority**: every schema load, mutation and check goes through the applier. A case that
the applier handles wrongly breaks ordinary schema loads, not only the history. The source design
makes this the first task for that reason, and the format of the stored operations stays open
until it passes.

**Independent Test**: for each case in the equivalence list (FR-024), build the schema twice from
the same starting schema: once by laying the schema file over the branch schema as a load does
today, once by recording the operations and applying them with the applier. Compare the processed
schemas and the lists of migrations.

**Acceptance Scenarios**:

1. **Given** a branch schema and a schema file from the equivalence list, **When** the operations
   recorded from the file are applied with the applier, **Then** the processed schema equals the
   processed schema of a direct load of the same file.
2. **Given** the same branch schema and file, **When** the migrations are calculated from the
   schema before and after the applier, **Then** they are the same migrations, on the same paths,
   as a direct load calculates.
3. **Given** a case where today's load has one of the four known bugs listed in FR-025, **When**
   the applier applies the recorded operations, **Then** the expected result is the fixed
   behaviour that the bug's ticket describes, not today's result.
4. **Given** a schema file sent to the schema check, **When** the check ends, **Then** the diff it
   returns is the diff between the branch schema and the schema that the applier built, and no
   schema change is stored.
5. **Given** an operation that names a node, attribute or relationship that the target schema does
   not have, **When** the applier applies it, **Then** the applier refuses the schema change and
   the error names the operation and the missing element.

---

### User Story 2 - A schema owner views the schema change history of a branch (Priority: P1)

A schema owner loads several schema changes on a branch. They then query the schema change history
of the branch. For each schema change they view its name, its version, its status, its time and
its operations. For each application of the schema change they view its status and the migrations
it ran, each with its path, status, result and errors.

**Why this priority**: this is the value the task delivers to the schema owner. The records are
also what the later tasks of the epic read.

**Independent Test**: on a branch with nodes, load three schema files that each change the schema.
Query the schema change history of the branch. Compare the versions, the names, the operations and
the migrations with what each load did.

**Acceptance Scenarios**:

1. **Given** a branch created from main when main's version was 7, **When** the schema owner loads
   a schema file that adds `serial` to `DcimGenericDevice`, **Then** the branch's history holds one
   schema change with the version 8, the status `applied` and a name that starts with `00008_`.
2. **Given** that schema change, **When** the schema owner views its operations, **Then** they view
   one operation that adds the attribute `serial` to `DcimGenericDevice`, with the definition they
   wrote. They do not view an operation for each kind that inherits `serial`.
3. **Given** that schema change, **When** the schema owner views its application, **Then** the
   application has the status `applied` and one migration for each kind the load migrated, each
   with its path, migration name, status, result and time.
4. **Given** three loads on the branch that each changed the schema, **When** the schema owner
   queries the history, **Then** the three schema changes are returned in order of version, and
   each one after the first has the one before it as its parent.
5. **Given** a schema file that was already loaded on the branch, **When** the schema owner loads
   it again, **Then** the history still holds one schema change for that file.
6. **Given** a schema file that only changes the label of an attribute, **When** the schema owner
   loads it, **Then** the schema change is stored, and its application has no migrations.
7. **Given** a history longer than one page, **When** a client requests a page, **Then** it
   receives at most the number of schema changes it asked for and the total number of schema
   changes.
8. **Given** a schema change with more operations than one page, **When** a client requests its
   operations, **Then** it receives them in pages, in the order they apply.

---

### User Story 3 - A schema owner views why a schema load failed (Priority: P2)

A schema owner loads a schema file, and one of its migrations fails. The load rolls back, as it
does today. The schema owner queries the history of the branch and views the failed schema change,
the error, and the migrations that ran before the failure.

**Why this priority**: today the error exists only in the response of the failed request. A stored
record lets the schema owner, or a colleague, view it later. It depends on the records of user
story 2.

**Independent Test**: make one migration of a schema load fail. Query the history of the branch.
The failed schema change is listed with its application, the error and the migration records, and
the branch schema and data are as they were before the load.

**Acceptance Scenarios**:

1. **Given** a schema load whose migration fails, **When** the load ends, **Then** the schema
   change has the status `failed` and no version, and its application has the status `failed` and
   holds the error.
2. **Given** that failed load, **When** the schema owner views the application's migrations,
   **Then** they view each migration that ran with its status, result and errors.
3. **Given** that failed load, **When** the schema owner queries the history, **Then** the applied
   schema changes are listed by version, and the failed schema change is listed by the time it was
   created.
4. **Given** a failed schema change on a branch, **When** the schema owner loads a corrected file
   that succeeds, **Then** the new schema change gets the next version, and its parent is the last
   applied schema change, not the failed one.
5. **Given** a failed load on main, **When** time passes and other loads succeed, **Then** the
   failed schema change is still listed. Infrahub does not delete it automatically.

---

### User Story 4 - A dropdown or enum mutation is part of the history (Priority: P2)

A schema owner adds or removes a choice of a dropdown attribute, or a value of an enum attribute,
through the GraphQL mutations. The change is stored as a schema change, as a schema load is.

**Why this priority**: these mutations change the schema without a schema file. A change that is
not stored would be missing from the history, and the later task that applies schema changes in
order at merge would lose it.

**Independent Test**: add a choice to a dropdown attribute through the mutation. Query the history
of the branch. One schema change holds one operation that changes the choices of that attribute.

**Acceptance Scenarios**:

1. **Given** a dropdown attribute, **When** the schema owner adds a choice through the mutation,
   **Then** the branch's history holds one new schema change with the status `applied`, with an
   operation that changes the attribute's choices and holds the choices before the change.
2. **Given** an enum attribute, **When** the schema owner removes a value through the mutation,
   **Then** the branch's history holds one new schema change for it.
3. **Given** a mutation that Infrahub refuses, for example a choice that already exists, **When**
   the mutation returns its error, **Then** no schema change is stored.

---

### User Story 5 - Deleting a branch deletes its records (Priority: P3)

A user deletes a branch. Infrahub deletes the schema changes of that branch, with their operations,
their applications and their migration records. The records of main and of other branches stay.

**Why this priority**: the records are internal and are not removed with the branch's data, so
without this step each deleted branch leaves its records in the database for ever.

**Independent Test**: load schema changes on a branch, including one that fails, then delete the
branch. Count the records of that branch and of main before and after.

**Acceptance Scenarios**:

1. **Given** a branch with applied and failed schema changes, **When** the branch is deleted,
   **Then** no schema change, operation, application or migration record of that branch remains.
2. **Given** schema changes on main and on a second branch, **When** the first branch is deleted,
   **Then** the records of main and of the second branch are unchanged.

---

### Edge Cases

- **One load with several schema files**: a load request can hold several files. It is one schema
  load, so it stores one schema change.
- **A file that states values the branch already has**: only the paths that differ after processing
  are recorded. A file that changes nothing stores nothing.
- **A rename**: a schema file renames an element by its ID, as it does today. The operation names
  the element by the name it had before the load, and holds the new name as the value.
- **A list field that a load replaces whole**, such as `human_friendly_id` or `inherit_from`: one
  operation holds the whole new list and the whole list before the change.
- **`state: absent`** on a node, attribute or relationship is recorded as a removal.
- **A node extension** is recorded as operations on the kind it extends.
- **A calculated field that the user writes**, such as `human_friendly_id`: the operation holds the
  user's value.
- **Two branches created from the same version of main** can each hold a schema change with the
  same version. A version is unique only within one branch.
- **A version above 99999**: the name becomes longer than five digits. Pages are ordered by
  version, not by name, so the order stays correct.
- **A branch created before this feature is deployed**, or main with no stored schema change:
  main's version is 0, so the branch's first schema change has the version 1.
- **A worker that stops during a load**: the schema change and its application keep the status
  `running`. They have no version and are not part of the history that later tasks apply. Recovery
  after a worker stops during a schema load is out of scope, as in the source design.
- **A migration that is waiting when another migration fails**: its record keeps the status
  `waiting`. The status `failed` of the application tells the reader that it did not run.
- **A load that Infrahub refuses before it writes anything**, for example an invalid file or a
  constraint that existing nodes fail: no schema change is stored. See decision 1.
- **A query on a branch with no schema change** returns an empty page and a count of 0.
- **A merge or a rebase** stores and changes no record in this feature. See "Dependencies".

## Requirements *(mandatory)*

### Functional Requirements

#### Recording a schema change

- **FR-001**: Infrahub MUST store one schema change for each schema load that changes the schema
  of a branch.
- **FR-002**: Infrahub MUST store one schema change for each dropdown or enum mutation that changes
  the schema of a branch. Its operations are built from the mutation's input, because the mutation
  has no schema file.
- **FR-003**: A schema load or a mutation that changes nothing MUST store nothing. Loading the same
  file twice stores one schema change.
- **FR-004**: A schema change whose operations need no migration, such as a changed label, MUST
  still be stored. Its application has no migration records.
- **FR-005**: A schema change MUST hold:
  - its schema change operations, in the order they apply;
  - its name and its version (FR-030 to FR-035);
  - its parent, its branch and its status;
  - the version of the format its operations are stored in;
  - the time it was created, and the time it was applied.
- **FR-006**: The status of a schema change MUST be one of `staged`, `running`, `applied` and
  `failed`. A schema load creates its schema change with the status `running` before its migrations
  run, and sets it to `applied` or `failed` when the application ends. A dropdown or enum mutation
  runs no migration, and its schema change is stored as `applied` together with the schema
  (decision 7). No workflow in this feature sets `staged`; the staging task of the same epic does.
- **FR-007**: Infrahub MUST NOT store the schema file or the mutation input, only the operations.
- **FR-008**: The following writes MUST create no schema change in this feature:
  - the number pool sync that sets `number_pool_id` after a NumberPool attribute is added;
  - graph migrations;
  - the core schema update during an upgrade, a merge and a rebase, which other tasks of the same
    epic cover.

#### Schema change operations

- **FR-010**: Each operation MUST be one of six: add a node, remove a node, change a property of a
  node, and the same three for an attribute or a relationship.
- **FR-011**: A schema change MUST hold only the changes the user made: the paths of the processed
  diff that exist in what the user loaded, with the user's values. The paths that processing
  produced MUST be left out, such as:
  - the inherited copies of an attribute;
  - the kinds that inherit a changed generic;
  - profile and template kinds;
  - `human_friendly_id` or `uniqueness_constraints` calculated from a unique attribute.
- **FR-012**: An operation that adds a node, an attribute or a relationship MUST hold the full
  definition as the user wrote it, without `id` and without `parameters.number_pool_id`, because
  both are specific to one instance.
- **FR-013**: A calculated field that the user writes MUST be recorded with the user's value.
- **FR-014**: Each operation MUST identify the node, attribute or relationship it changes by kind
  and name, never by vertex ID. A rename names the element by the name it had before the load.
  Operations apply in order, so a name identifies one element at each step.
- **FR-015**: An operation that changes a property MUST also hold the value before the change.
- **FR-016**: Each schema change MUST record the version of the format its operations are stored
  in, so that stored operations stay readable after an upgrade that changes the format.

#### One applier

- **FR-020**: One applier MUST apply one schema change to the processed schema of a target branch
  as follows, and MUST NOT clear any stored value:
  - set the recorded paths;
  - for the renames and removals in the schema change, rewrite the paths in
    `uniqueness_constraints`, `human_friendly_id`, `display_labels`, `order_by` and
    `default_filter`, as a load does today;
  - run processing.
- **FR-021**: A direct schema load, a dropdown or enum mutation and the schema check MUST each
  build their operations and apply them with the applier. The schema that a load saves, the
  migrations it runs and the diff that the check returns MUST come from the applier's result. A
  load still lays the file over the branch schema to find what changed, because the operations are
  built from that diff.
- **FR-022**: Each application MUST calculate its migrations and its constraint checks after
  processing, from the difference between the target branch's schema before and after the applier.
  The changes that processing produces therefore still get their own migrations and checks.
- **FR-023**: The applier MUST refuse a schema change that holds an operation on a node, attribute
  or relationship that the target schema does not have. The error MUST name the operation and the
  missing element.
- **FR-024**: An equivalence test suite MUST exist before any workflow uses the applier. For each
  case, the processed schema and the migrations that the applier builds from the recorded
  operations MUST match those of a direct load. The cases are:
  - adding an attribute to a generic;
  - turning on `generate_profile`;
  - making an attribute unique;
  - removing an attribute;
  - renaming an attribute on a node and on a generic;
  - adding a node;
  - relationship changes;
  - kind renames, namespace changes and `inherit_from` changes;
  - removing a generic;
  - dropdown choices;
  - `state: absent`, node extensions, and list fields that a load replaces whole, such as
    `human_friendly_id` and `inherit_from`;
  - an attribute kind change within one load.
- **FR-025**: Where today's load has one of these known bugs, the expected result of the case MUST
  be the fixed behaviour:
  - [IFC-3085](https://opsmill.atlassian.net/browse/IFC-3085): `unique` cannot be turned off;
  - [IFC-3599](https://opsmill.atlassian.net/browse/IFC-3599): `on_delete` after a relationship
    kind change;
  - [IFC-3601](https://opsmill.atlassian.net/browse/IFC-3601): a rename on a generic and profile
    nodes;
  - [IFC-3602](https://opsmill.atlassian.net/browse/IFC-3602): an attribute kind change on a
    generic.

  Decision 2 says what happens to a case whose bug is still open.

#### Versions, names and parents

- **FR-030**: The version of a schema change MUST be its position in the schema change history of
  its branch. Main starts at version 0, and its first schema change has the version 1.
- **FR-031**: A branch MUST number its schema changes after main's version at the branch's
  `branched_from`. A branch created from main at version 7 numbers its first schema change 8. A
  version is unique only within one branch.
- **FR-032**: A schema change MUST get its version when it is applied. A staged or running schema
  change has no version, and a failed schema change never gets one. A schema change without a
  version is not part of the history and is never the parent of another schema change.
- **FR-033**: The name MUST be `<version>_<summary>`, with the version padded to five digits. The
  summary comes from the first operation (kind, field, operation), with a count when the schema
  change has more operations. Example: `00008_dcimgenericdevice_serial_add`. A schema change
  without a version is shown with its summary only. The version stays an integer.
- **FR-034**: The parent of a schema change MUST be the schema change that precedes it in the
  history of its branch. See decision 4 for the first schema change of a branch.
- **FR-035**: A schema change MUST NOT hold a fingerprint in this feature.

#### Applications

- **FR-040**: Infrahub MUST store one application each time a schema change is applied to a
  branch. In this feature, that is the original load or mutation. An application MUST hold its
  status, the branch it was applied to, its time, and the error when it failed.
- **FR-041**: The status of an application MUST be one of `running`, `applied`, `failed`,
  `rolled back` and `skipped`. This feature sets `running`, `applied` and `failed`. The task that
  applies schema changes in order at rebase and merge sets `rolled back` and `skipped`.

#### Migration records

- **FR-050**: Infrahub MUST store one record for each individual migration that runs during an
  application, for example `node.attribute.add` on `InfraDevice.serial`. The record MUST hold the
  path, the migration name, the status, the result, the errors and the time.
- **FR-051**: The status of a migration record MUST be one of `waiting`, `running`, `applied`,
  `failed` and `rolled back`.
- **FR-052**: The migration records of an application MUST exist, with the status `waiting`,
  before its migrations run, and MUST be updated as each migration ends, so that a client can read
  the state of a running load.
- **FR-053**: A migration that finds no nodes MUST be recorded as `applied`.
- **FR-054**: Migration records MUST be created each time a schema change is applied, because the
  list of migrations depends on the schema that the schema change is applied to.

#### Records after a failure

- **FR-060**: When a schema load fails after its application started, Infrahub MUST set the schema
  change and its application to `failed`, and the application MUST hold the error and keep its
  migration records. A migration record that was `applied` becomes `rolled back` (decision 6). A
  dropdown or enum mutation whose save fails stores nothing (decision 7).
- **FR-061**: The records MUST state the result of the load even though the load rolled back. The
  rollback of the graph does not revert these records, so the code that handles the failure MUST
  update them.
- **FR-062**: Failed schema changes MUST be kept, on main as well, with no automatic deletion.

#### Querying the history

- **FR-070**: A GraphQL query MUST return the schema change history of a branch in pages. For each
  schema change it MUST return:
  - its name, version, status and time;
  - its operations, in pages;
  - its applications with their status;
  - each application's migrations with their status, result and errors.
- **FR-071**: The query MUST return applied schema changes in order of version, and failed schema
  changes, which have no version, in order of the time they were created.
- **FR-072**: The query MUST return the total number of schema changes that match, and a page MUST
  hold at most the number of schema changes the client asked for.
- **FR-073**: Anyone who can read the schema of a branch MUST be able to query its schema change
  history. See decision 3.

#### Storage and deletion

- **FR-080**: Schema changes, applications and migration records MUST be stored as internal
  records linked by edges, not as a core kind. They are not part of the schema, they are not
  versioned by branch, and a diff, a merge or a rebase of data does not read or copy them.
- **FR-081**: Deleting a branch MUST delete its schema changes, with their operations,
  applications and migration records. The deletion is explicit, because internal records are not
  deleted with the branch's data.
- **FR-082**: Deleting a branch MUST NOT change the records of main or of another branch.

### Key Entities *(include if feature involves data)*

- **Schema change**: the operations from one schema load or one dropdown or enum mutation. It has
  a name, a version, a status, a branch, a parent, the version of its operation format, the time
  it was created and the time it was applied. It has an ordered list of operations and one or more
  applications.
- **Schema change operation**: one change to the schema. It has the kind of operation (one of
  six), the kind of the node, the name of the attribute or relationship when it changes one, the
  property when it changes one, the new value, and the value before the change. For an addition it
  holds the full definition as written.
- **Application**: one time a schema change was applied to a branch. It has a status, the branch,
  a time, the error when it failed, and its migration records.
- **Migration record**: one migration that an application ran. It has the schema path, the
  migration name, a status, the result, the errors and the time.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every case in the equivalence list, the schema built from the recorded operations
  equals the schema of a direct load, and the lists of migrations are the same. The four known-bug
  cases are compared with the fixed behaviour.
- **SC-002**: The existing tests of the schema load, the schema check and the dropdown and enum
  mutations pass with the same expected results as before this feature.
- **SC-003**: After N schema loads that each change the schema of a branch, the history of the
  branch lists N applied schema changes with N consecutive versions. Loading one of the files a
  second time adds none.
- **SC-004**: After a failed schema load, a schema owner reads the error and the status of each
  migration from the history of the branch, without the response of the failed request and without
  access to the server logs.
- **SC-005**: After a branch is deleted, no record of that branch remains, and the number of
  records of main and of every other branch is unchanged.
- **SC-006**: A client reads a history of any length, and the operations of a schema change of any
  size, page by page. No page holds more than the number of items the client asked for.

## Assumptions

- All tasks of the epic except the optional view in the proposed change ship together in one
  release. No release therefore records schema changes while merges and rebases still use today's
  combined calculation, and this feature does not need to keep records correct across a merge or a
  rebase.
- Schema loads on one branch do not run at the same time, as today, so two schema changes of one
  branch never get the same version.
- The format of the operations can still change until the equivalence test suite passes. The
  source design states that it stays open until then.
- The sources set no limit on the time that recording adds to a schema load. The plan states how it
  is kept small.
- A Git repository that imports a schema loads it through the same schema load as a user, so its
  loads are recorded in the same way.

## Dependencies

- This feature has no dependency on another task of the epic.
- These tasks depend on this feature and read or change its records:
  - [IFC-3619](https://opsmill.atlassian.net/browse/IFC-3619): the progress of a running load, as
    the count of its migration records by status;
  - [IFC-3620](https://opsmill.atlassian.net/browse/IFC-3620): a schema change for the core schema
    update;
  - [IFC-3621](https://opsmill.atlassian.net/browse/IFC-3621): staging, which creates schema
    changes with the status `staged`;
  - [IFC-3623](https://opsmill.atlassian.net/browse/IFC-3623): applying schema changes in order at
    rebase and merge, which numbers a branch's schema changes again at rebase, copies them to main
    at merge, and sets the statuses `rolled back` and `skipped`.
- The fixes of the four known bugs in FR-025 are separate tickets of the same epic.

## Out of Scope

- **The upgrade migration for schema loads made before the upgrade.** The source design decides
  that it is built with the task that applies schema changes in order at rebase and merge, because
  only that task needs it.
- **Applying a series of schema changes at rebase and merge**, main's copies of a branch's schema
  changes, and renumbering at rebase.
- **Staging a schema change**, its impact and its violations.
- **The count of migrations by status for an application and the progress artifact in the task
  list.** This feature stores the status of each migration; the progress task adds the counts.
- **Node counts for each migration.**
- **A schema change for the core schema update.**
- **Recovery after a worker stops during a schema load.**
- **Front-end work**, and SDK and CLI commands for stored schema changes.
- **Export and import of schema changes between instances.** Operations name elements by kind and
  name so that this stays possible later.
- **Warnings for deleted data in the response of a schema load**
  ([IFC-3204](https://opsmill.atlassian.net/browse/IFC-3204)).
- **Fixing the four known bugs in FR-025**, unless the applier fixes one as a result of how it sets
  the recorded values.

## Decisions Taken During Specification

The sources do not answer these points. Each was decided without asking, and each can be changed in
review.

1. **A load that is refused before it writes anything stores no schema change.** The sources say
   that a load creates its schema change "before its migrations run", and that a failed schema
   change is kept with "the error and the migrations that ran". They do not say whether a load
   refused at validation is stored. Such a load changes nothing, and the caller receives the
   reason in the response. Storing each refused file would also fill main's history, which is never
   deleted automatically.
2. **A known-bug case whose fix has not landed is an expected failure.** The sources say that the
   expected result is the fixed behaviour, and the four bugs are separate tickets that are not
   fixed yet. Each such case states the fixed behaviour and is marked as an expected failure that
   names its bug, so the suite reports it when the fix lands. A case that the applier fixes is a
   normal passing case.
3. **Reading the history needs the same access as reading the schema.** The sources say this for a
   staged schema change in the staging task. They do not say it for the history query.
4. **The parent of the first schema change of a branch is main's last schema change applied at or
   before the branch's `branched_from`.** When main has none, the schema change has no parent. The
   sources say that a schema change has a parent and that a branch numbers its schema changes after
   main's version at `branched_from`. They do not name the parent of a branch's first schema
   change.
5. **The query returns the schema changes stored for the queried branch only.** A branch's history
   in the sense of the source design also includes main's schema changes up to `branched_from`. A
   client reads those by querying main.
6. **A migration record that is `applied` when the load fails becomes `rolled back`.** The sources
   list `rolled back` as a status of a migration record and say that a failed load rolls back
   completely. They do not say which status the migrations of a failed load get. The record then
   states that the data change was reverted.

7. **A dropdown or enum mutation stores its schema change as `applied`, in the same transaction as
   the schema.** The sources say that a mutation, like a load, creates its schema change with the
   status `running` before its migrations run, so that the progress of the migrations can be
   reported. These mutations run no migration today, and they save the schema in one database
   transaction. Storing the records in that transaction means that the schema and its records are
   saved together or not at all, and that a mutation retried after a database error leaves no
   failed schema change in the history.

## Sources

- [IFC-3614](https://opsmill.atlassian.net/browse/IFC-3614): the task, with its scope, acceptance
  criteria and risks.
- [INFP-719 Make schema migrations visible](https://app.notion.com/p/opsmill/INFP-719-Make-schema-migrations-visible-402228b830258193b43ed097d965f633):
  the design document, read on 2026-11-14 as last edited on 2026-11-13. Sections used: "Terms used
  in this document", "B: stored schema changes and migrations", "C1: progress of a running load",
  "D1: staging", "F2: ordered replay at rebase and merge", "L: records for the core schema update",
  "Assumptions" and "Out of scope".
- [IFC-3590](https://opsmill.atlassian.net/browse/IFC-3590): the parent epic.
- The Jira tickets linked in "Dependencies" and in FR-025, read on 2026-11-14. All had the status
  Draft.
