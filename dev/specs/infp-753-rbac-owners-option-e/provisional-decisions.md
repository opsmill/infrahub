# Provisional decisions for the comparison build

Date: 2026-11-12.

The branches of options B and E exist to compare the two storage options. They stay local.
No review made these decisions. Each value below is the proposal that the spec or the research already holds.
Both branches use the same values, so that only the storage differs.
The decision tasks T001 to T005 stayed open in tasks.md until the decisions of 2026-11-16.
The section "Decisions of 2026-11-16" says which values are now decisions.

| ID | Open point | Provisional value | Source |
|---|---|---|---|
| PD-1 | Conflicts between owner changes (FR-030) | A conflict exists when the default branch and another branch both change the owner state of the same holder to different values. The diff compares the whole list of owners of the holder. | research R-9 |
| PD-2 | Two writes at the same time (FR-032) | A mutation that writes owners or sources takes a lock for the node with `InfrahubMultiLock`. The lock name holds the node ID and no branch name. The state of the last write stays. | research R-21 |
| PD-3 | Depth limit of the walk to the parents (E-16) | 16 parents. Beyond the limit, the node gets no inherited owner. | research R-3 |
| PD-4 | Audit metadata of an owner change (FR-053) | A change of owners or sources updates `updated_at` and `updated_by` of the changed node only. | spec FR-053 |
| PD-5 | Storage details (task T004) | Option B: `field` holds the field name, so the migration for a relationship rename applies. The "from template" mark is a separate edge from the holder vertex to the template, with `field` for a field. Option E: two branches reuse the same `OwnerSet` vertex, through the node lock of PD-2. | research R-1, R-21 |
| PD-6 | Names of fields, filters and object file keys (task T005) | The names of `contracts/graphql-schema.graphql` and `contracts/object-file.md`, plus the field `name` on `MetadataNodeInput` that the implementation added (task T140). | contracts |
| PD-7 | Product decisions (task T002) | The owner and source filters are in Community. D-6 stays. The reference data set is the one of the spec. E-15 stays as written: the field shows the origin "node" and its own node. | spec, research R-22 |
| PD-8 | Owner filter and SC-003 (spike) | The filter starts from the owner and goes down to the nodes that inherit. No index of the owners that apply is built, because it needs approval. If SC-003 is not met, `measurements.md` records the numbers. | research R-6 |
| PD-9 | Governance approvals (task T001) | Not available. The branches are not pushed and open no pull request. | plan.md |
| PD-10 | Python SDK change | A local commit in the `python_sdk` submodule. No push and no pull request on the SDK repository. | user request |

## Decisions of 2026-11-16

Guillaume Mazoyer, maintainer and owner of the two branches, made these decisions on 2026-11-16.

- The provisional values PD-1, PD-2, PD-4, PD-5, PD-6, PD-7 and PD-8 are now decisions.
- PD-3 stays provisional. The engineering review decides the depth limit, so task T003 stays open.
- The approval of T001 replaces the "not available" of PD-9. The branches are still not pushed and open no pull request.
- No decision of 2026-11-16 changes PD-10.

| ID | Point | Decision |
|---|---|---|
| D-A | Storage option | No choice in these answers. Decided later on 2026-11-16: option E. Option B is not chosen. See "Storage decision of 2026-11-16". |
| D-B | Deprecated attribute input `owner: null` | It changes nothing. A client uses `owners: null` to set the attribute to inherit. |
| D-C | Stored permission with a value that only Infrahub Enterprise knows | A permission that allows is dropped. A permission that denies stays, and denies for every node of its kind and action. |
| PD-1 | Conflict rule (FR-030) | Confirmed: the diff compares the whole list of owners of each holder. |
| PD-2 | Two writes at the same time (FR-032) | Confirmed: a lock for the node, and the state of the last write stays. |
| PD-3 | Depth limit (E-16) | Not decided. The engineering review decides. The value of 16 parents stays provisional. |
| PD-4 | Audit metadata (FR-053) | Confirmed: the change updates `updated_at` and `updated_by` of the changed node only. Two gaps stay as known limits of this phase: on a branch other than the default branch, and after a merge of an owner change alone. |
| PD-5 | Storage details (T004) | Confirmed as built: two branches reuse the same `OwnerSet` vertex, through the node lock of PD-2. |
| PD-6 | API names (T005) | Confirmed: the names of the two contract files, plus the field `name` on `MetadataNodeInput` that the code added. |
| PD-7 | Product decisions (T002) | Confirmed, all four: the owner and source filters are in Community (Q-23); D-6 stays; the reference data set is the one of the spec; E-15 stays as written. |
| PD-8 | Owner filter (SC-003) | Confirmed: the filter stays as built, with no index of the owners that apply. SC-003 is met up to about 60,000 matches and not met above. This limit is accepted for this phase. |
| T001 | Governance gates | Approved: each governance gate of plan.md ("Post-Phase 1 re-check"). E2E tests through the API meet principle IV of `dev/constitution.md`. User story 7 needs no E2E test. |
| Docs | Wording of the user documentation | The user pages about owners and sources say "object", as `docs/AGENTS.md` asks. Developer docs (`dev/`), specs and code keep "node". |

What the branch holds for the decisions that changed a file outside this directory:

- D-B: commit `257ec7fe98` restores the behavior. The owner input parser returns no state for `owner: null`.
- D-C: the code already had this behavior (commit `478beeb65c`). `counted_permissions` of `backend/infrahub/permissions/change_check/community.py` applies it. The tests are in `backend/tests/unit/permissions/change_check/test_community.py`.
- PD-4: the code records `updated_at` and `updated_by` only for a write on the default branch or the global branch. No test of this branch reads them after a merge of an owner change alone.
- PD-8: the measured numbers are in [measurements.md](measurements.md), "Success criteria": met for 59,900 interfaces that match, not met for 101,462 or more.
- Docs: commit `471b3e9aa1` changes the user pages.

## Storage decision of 2026-11-16

Decided on 2026-11-16, after the decisions of the table above: the team builds storage option E. Guillaume Mazoyer, maintainer, recorded the decision. This branch builds option E.

The engineering design has the same decision as D17: <https://app.notion.com/p/401228b830258034af14d485d00b0314>. Jira tracks the work in IFC-3625, and IFC-3626 lists the work to do before the first pull request merges.

Reasons. They come from a comparison of the two local builds on 2026-11-16: three experiments and one review of the code.

- The two options have the same speed.
  - The slow "no owner" filter on devices of option B comes from its query, not from its storage. One more predicate on the kind of the parent cuts the database hits of the page query from 1,147,611 to 84,055 at 1,000 devices, with the same result. At 3,000 devices, the page with the count goes from 1,444 ms to 152 ms.
  - With 50,005 `OwnerSet` vertices at 1,000 devices, the owner diff of option E takes 1.6 ms. Its owner merge takes 34.4 ms, and 88.6 ms when each set is a template copy.
- Option B puts several `HAS_OWNER` edges between the same two vertices. Existing code expects one edge of a type between two vertices.
  - The build of option B changed the graph validation, the kind migration and the node removal for this.
  - The patch `delete-duplicated-edges` of `infrahub db patch` (`backend/infrahub/patch/queries/delete_duplicated_edges.py`) is not changed. On the data of option B, it deletes field owner edges.
- In option B, a query that does not filter on `field` and `given` returns node owners, field owners, given owners and the marker together. In option E, the plain `HAS_OWNER` pattern returns the own owners.
- Option B stores field owners by field name, so the rename of a relationship needs a migration. Option E stores them by identifier and direction, and the schema refuses an update of both (`UpdateSupport.NOT_SUPPORTED` in `backend/infrahub/core/schema/definitions/internal.py`).
- The engineering design sets the criterion (2026-11-03): the database structure matters more than the amount of diff and merge code.

Costs of option E:

- Two new vertex labels and four new edge types. The owner merge of option E has about 15 patterns. The owner merge of option B has 5.
- Infrahub keeps one `OwnerSet` for each key with a lock, not with the database. Two sets with the same key read as the owners of both, with no error. Nobody reproduced this state in real use.

Work to do before the first pull request merges, with its state on 2026-11-16:

- Close the two gaps of the lock. Done.
  - The write query now takes a write lock on the node vertex in the database before it looks for the set (`SET n.uuid = n.uuid` in `backend/infrahub/core/ownership/queries.py`). The lock lasts until the commit, so it also covers a mutation inside an outer transaction and the merge write of resolved owner conflicts.
  - The attribute rename migration, the only other code that creates a set, takes the same lock.
  - Proof: `test_two_first_writes_in_open_transactions_create_one_set` in `backend/tests/component/core/ownership/test_owner_sets.py`. Before the change, it gave two sets.
- Add a check for duplicate `OwnerSet` vertices to the graph validation. Done: `GraphCheck.DUPLICATE_OWNER_SETS` in `backend/infrahub/database/validation.py`.
- Correct three points of the build of option E:
  - The attribute delete query reads only one owner edge. No change is needed: the node delete closes the other owner edges of its attributes and sets with a second query. `test_node_delete_closes_each_owner_edge_of_its_attributes_and_sets` proves it.
  - The lookup of a set by `properties(s) = $set_key`. Done: the lookup compares only the key properties (`owner_set_key_filter`).
  - The object conversion can lose field owners. Verified and done: a relationship of the new kind now takes the owners of the relationship that the mapping fills it from, and the owners of a relationship that fills no field are not copied.
- A person reviews the owner merge queries. Not done.

Not checked: no experiment ran at the full size of 10,000 devices. The files of the experiments are not in this repository.

## Decision of 2026-11-20: the lock of two writes at the same time

Guillaume Mazoyer, maintainer, made this decision on 2026-11-20. It replaces PD-2 for this build. The rows above keep the values of 2026-11-12 and 2026-11-16.

- Two writes of the same node at the same time run one after the other because of a write lock in the database on the node vertex (`SET n.uuid = n.uuid`). The lock lasts until the commit.
  - `Node._update` and `Node.delete` take it at their start (`NodeLockQuery`).
  - The owner queries take it inside the query, before they write: `OwnerStateWriteQuery` and its subclasses `NodeSourcesWriteQuery` and `NodeOwnerEdgesCloseQuery`, and the attribute rename migration (`OwnerSetKeyMigrationQuery`).
  - The cascade of `NodeManager.delete`, the profile refresh and the IPAM reconciler lock their nodes in the order of the node IDs.
- No mutation takes `InfrahubMultiLock` for owners. Task T021 is closed.
- The state of the last write stays, as in PD-2.
- PD-5 ("through the node lock of PD-2") now means this database lock: the owner write query locks the node vertex before it looks for the set, so two branches reuse the same `OwnerSet` vertex.

Reasons. The evidence is in the scratch files of the review of 2026-11-20 (`review8/lock-alternatives.md`, `probe3.jsonl`). Line numbers are at commit `7d2ce2969a`, unless the line says `origin/develop`.

- Without the node lock, an owner write and a node delete deadlock, and a delete can leave an open owner edge on a deleted node.
  - Probe of 2026-11-20: real GraphQL mutations, `TestPersonUpdate` that sets an owner on `height` (with or without a new value) and `TestPersonDelete` of the same node at the same time, 160 pairs on the default branch and on a branch. With the lock: 0 deadlocks and 0 open owner edges. Without `NodeLockQuery`: 9 `DeadlockDetected` retries and 1 open `HAS_OWNER` edge on a deleted node, which `verify_graph` reports.
  - Runs that pause one transaction at a fixed step (36 cases): with the lock, 0 cases with bad owner data and 0 deadlocks. Without `NodeLockQuery`: 7 cases with bad owner data and 3 deadlocks.
  - Cause: the owner write locks the node first (`backend/infrahub/core/ownership/queries.py:545`) and then the attribute (`:457-463`, on the default branch). Without `NodeLockQuery`, the delete locks the attribute first (`backend/infrahub/core/query/attribute.py:320`, on the default branch) and the node later (`NodeOwnerEdgesCloseQuery`, `queries.py:545`).
  - On Neo4j 2026.10.1, the create of an edge does not wait for a `SET` on either end vertex. So only the `SET` on the node vertex orders two writes of one node. `Node.delete` reads its time after this lock (`backend/infrahub/core/node/__init__.py:1473-1475`), so it also closes the owner edges of a write that commits while the delete waits.
- The writers that do not run through a mutation cannot take an application lock before they write. So the database lock in the owner queries must stay in all cases.
  - The IPAM reconciler runs inside the transaction of the create mutation, after `create_node` wrote, and gets its nodes from a read (`backend/infrahub/graphql/mutations/ipam.py:157-173`, `backend/infrahub/core/ipam/reconciler.py:89-148`).
  - The migrations write with Cypher over all the nodes of a kind (`backend/infrahub/core/migrations/query/owner_set_attribute.py:119` takes the node lock inside the Cypher).
  - The merge deletes nodes with Cypher.
- A Redis lock waits with no limit. `RedisLock.acquire` loops until it gets the key (`backend/infrahub/lock.py:188-209` on `origin/develop`), and a lock that is not an init lock gets no time to live (`lock.py:612-627` on `origin/develop`). The lock modes of pull request 11410 do not change this. Two writers that take two node locks in the reverse order wait without end. Neo4j finds a deadlock of database locks, and the mutation retries it (`retry_db_transaction`).

Update time, changed after the review of 2026-11-23: `Node._update` reads the update time after the lock when the caller gives no time. With the time read before the lock, an owner update that waited behind another owner update wrote at an earlier time, did not see the owners of the other update, and left both lists active. A value update that waits behind a delete wrote an active `HAS_VALUE` edge on a deleted attribute: the same probe saw it in 7 of 160 pairs with the lock and in 28 of 80 pairs on `develop`. With the update time read after the lock, it saw 0 of 80, and the update fails. `NodeLockQuery` now also reads, after the lock, whether the node is active, so such an update raises `NodeNotFoundError`. A write of owners with a time from before the lock fails when the holder has an owner edge with a later time. `develop` has the `HAS_VALUE` bug without this change.

## Decisions of 2026-11-26

Guillaume Mazoyer, maintainer, made these decisions on 2026-11-26, before pull request 2 (GraphQL API).

- The origin value of a field that takes the owners of its node is `NODE`, not `OBJECT`. This replaces the answer of 2026-11-16 to E-15 (spec.md) and the value of PD-6 for this one name.
  - Reason: the engineering design names it `NODE` (sections 2 and 3, and the GraphQL examples of 2026-11-09). Wim approved this shape at the status meeting of 2026-11-19, after PD-6.
  - The origin node does not change: it is the node of the field.
- Task T031 is dropped. Two tests of `backend/tests/component/core/ownership/test_owner_sets.py` already run two first writes of owners in two open transactions on one node. Task T021 was closed on 2026-11-20 for the same reason.
- No test asserts a count of database queries (decision of 2026-11-18, commit `259305a5c8`). Tasks T044 and T106 follow this rule: the benchmarks of T061 measure FR-009.
- An owner or a source given by `name` must also give `kind`. Infrahub refuses `{name}` without `kind`, and the error says to give the kind. `{kind, name}`, `{id}` and `{kind, hfid}` do not change.
  - Reason: not recorded with the decision. Before, a name without a kind was read as an account group, and refused only when an account had the same name. The object file loader of the SDK must send a plain name with the kind of an account group.
- A `field_owners` or `target_field_owners` entry that leaves out `owners` changes nothing. `owners: null` still gives inherit, and `[]` gives no owner.
  - Reason: not recorded with the decision. Before, an entry without `owners` was read like `owners: null` and set the field to inherit. A key left out at the node level already changes nothing (D-5).
- `target_field_ownership(fields: [...])` refuses a name that is not an attribute or a relationship of the nodes, with an error that names the field.
  - Reason: not recorded with the decision. Before, the query skipped the name and gave no error. The `field_owners` input already refused an unknown field name.
- When one attribute input gives both `owner` and `owners`, `owners` is written and `owner` is ignored. The owners are written once.
  - Reason: the save wrote `owner` and then `owners`, so the owners changed twice and the changelog showed the ignored owner (commit `b0ee2e28e4`).
- `ownership` is null on `ancestors` and `descendants`.
  - Reason: these fields share their types with `children`, but they are not relationships and have no owners. Separate types would add GraphQL types for each hierarchy (commit `cb2ee07f8b`).
- Decisions of pull request 1 on the same day:
  - The deprecated `owner` gives null for an owner that an object template copied. Reason: the owner code reads a copy as inherit, not as an own owner (commit `fb920e333d`).
  - The label of a deleted owner stays "deleted owner". Reason: an owner can be an account or an account group, so "deleted group" was not correct (commit `21927113bc`).
  - The test of a create from a template no longer asserts a count of owner reads. Reason: a count of queries fails when the query plan changes for a good reason (commit `1afb9166a7`).
