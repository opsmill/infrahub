# Feature Specification: Retirement of branch-agnostic property edges

**Feature Branch**: `retire-agnostic-edges-ifc-2843`

**Created**: 2026-08-12

**Status**: Draft

**Ticket**: [IFC-2843](https://opsmill.atlassian.net/browse/IFC-2843) — High, epic IFC-2710 "Targeted bugs within the 1.11 release cycle"

**Issue**: [#9762](https://github.com/opsmill/infrahub/issues/9762)

**Target branch**: `release-1.11`

**Input**: PRD at `IFC-2843-prd.md` — "Retirement of branch-agnostic property edges"

## Problem Statement

An operator whose data model puts a `branch: agnostic` attribute or relationship on a
branch-aware node — canonically an allocated `NumberPool` value — accumulates dead
values that the system still treats as live. Every property edge of such a field is
written on the global branch, and only one path closes them today: deleting a branch
drops the agnostic attributes and relationships of the nodes that existed on no other
branch. Every other path leaks.

Deleting a node, or removing the field from the schema, tombstones the field at branch
level and leaves the global edges open, so repeated create/delete cycles pile up values
with no owner. Uniqueness validation counts them, so an unrelated data-only proposed
change fails with conflicts naming node UUIDs that resolve to nothing, and a schema
update introducing a uniqueness constraint on that field cannot load. There is no
user-accessible recovery: the reported occurrence required hand-written Cypher against
the production database.

## Solution Overview

A branch-agnostic field's global property edges are retired once no branch can still
legitimately reach them, and an upgrade migration retires the ones already leaked. The
rule is one invariant, enforced at each point where a field stops being reachable:

> An `Attribute` vertex's global property edges are open (`status: "active"`,
> `to IS NULL`) **iff** there exists a branch on which that vertex is reachable from a
> live node vertex over an active `HAS_ATTRIBUTE` edge.
>
> A `Relationship` vertex's global property edges are open **iff** there exists a branch
> on which **both** of its peer node vertices are live and **both** of its `IS_RELATED`
> edges are active.

"Live" means an active existence edge on that branch under that branch's own branch and
time filter, so a branch that forked between the object's creation and its deletion still
counts. Such a branch is a **retaining branch**; while at least one exists, retirement is
deferred.

A deferred retirement resolves as soon as the retaining set becomes empty. Several
unrelated events can empty it — the object being deleted on the retaining branch itself,
a rebase moving the branch's fork point past the deletion, a merge, or the branch being
deleted — and none of them empties it unconditionally, since the object may still be live
on the branch afterwards. The predicate is therefore re-evaluated at each of those events
rather than any of them being treated as a release trigger in its own right.

Stating the invariant on the `Attribute` / `Relationship` vertex rather than on the owning
node is what lets one predicate cover every leak path, because every path already
tombstones or closes the `HAS_ATTRIBUTE` / `IS_RELATED` edge at branch level — node
deletion, attribute removal, relationship removal, and branch deletion alike.

Operators see three changes: deletes and schema removals stop leaking reserved values,
proposed changes and schema updates stop failing on values with no owner, and upgrading
clears the backlog.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The invariant is enforced wherever a field stops being retained (Priority: P1)

On every path by which a branch-agnostic field stops being reachable from a live node on
any branch, its global property edges are retired; while a retaining branch exists,
retirement is deferred and re-evaluated whenever an event could have emptied the retaining
set.

**Why this priority**: Without it the reported failure recurs — the migration clears the
existing backlog but nothing stops the next one accumulating.

**Independent Test**: Exercise each enforcement point against a branch-aware kind carrying
a branch-agnostic attribute under a uniqueness constraint, asserting the graph shape after
each operation.

**Acceptance Scenarios**:

1. **Given** a node holding branch-agnostic value `V` with no branch forked during its
   lifetime, **When** it is deleted on the default branch, **Then** every global property
   edge of that field carries a `to` timestamp and a uniqueness check for `V` reports no
   violation.
2. **Given** a node holding `V` that exists only on branch `B`, so no other branch can
   reach it, **When** it is deleted on `B`, **Then** its global edges are closed
   immediately.
3. **Given** a node holding `V` that exists on both branch `B` and the default branch,
   **When** it is deleted on `B`, **Then** its global edges stay open, and **When** it is
   subsequently deleted on the default branch too, **Then** they are closed.
4. **Given** a node with branch `B` forked between its creation and its deletion, **When**
   it is deleted on the default branch, **Then** the global edges stay open, the value
   stays reserved, and the object remains readable on `B`.
5. **Given** that deferred state, **When** the retaining set is emptied — by deleting the
   object on `B`, by rebasing `B` past the deletion, by merging `B`, or by deleting `B` —
   **Then** the global edges are closed.
6. **Given** that deferred state, **When** `B` is rebased or merged but the object is
   still live on `B` afterwards, **Then** the global edges stay open.
7. **Given** a branch-agnostic relationship whose two peers are both live, **When** one
   peer is deleted such that no branch has both peers live, **Then** the relationship's
   global property edges are closed even though the other peer survives.
8. **Given** a branch-agnostic attribute that no branch retains, **When** it is removed
   from the schema, **Then** its global property edges are closed. Likewise for a
   branch-agnostic relationship.
9. **Given** a branch-agnostic field whose schema removal has a branch that forked
   beforehand, **When** the removal migration runs, **Then** retirement is deferred and
   the field stays readable on that branch.
10. **Given** a node whose kind or inheritance has changed, **When** any enforcement point
    or the repair migration runs, **Then** the surviving vertex keeps its value.
11. **Given** a node created and deleted on branch `B`, **When** `B` is rebased, **Then**
    the invariant still holds and no vertex is left with open global edges.
12. **Given** a value freed by retirement, **When** the pool next allocates, **Then** that
    value is allocatable again.

---

### User Story 2 - Existing damage is repaired on upgrade (Priority: P1)

Upgrading retires the global property edges of every branch-agnostic field that no branch
retains, covering both the still-linked orphans left by node deletion and schema removal and
the fully detached ones left by branch deletions that predate the existing agnostic-peer
cleanup.

**Why this priority**: This is what unblocks a customer who is stuck today. No enforcement
change can clear an existing backlog.

**Evidence on shape distribution**: the reported dataset was quantified at ~512
effectively-live nodes against **~6,400 effectively-deleted nodes still holding an active
global value**, and 13,378 active global value edges across 6,949 node objects for only
1,139 distinct values — one value attached to 32 distinct, mostly deleted node objects. That
measurement was taken with a query anchored on `(:Node)-[:HAS_ATTRIBUTE]->(:Attribute)`, so
it counts **only** the still-linked shape and structurally cannot see the fully detached one.
The still-linked shape is therefore confirmed at scale; the detached shape is known to exist
but is **unquantified**. The migration must handle both and must not be sequenced on the
assumption that either dominates.

**Independent Test**: Build the orphan shapes as fixtures, run the migration, assert the
edges are closed or the vertices removed and the reported counts are correct. Delivers
value with no other part of the feature present.

**Acceptance Scenarios**:

1. **Given** a database containing a node with open global `HAS_VALUE` edges and no active
   existence edge on any branch, **When** the repair migration runs during upgrade,
   **Then** those edges carry a `to` timestamp, the count is reported to the upgrade log,
   and a subsequent data-only proposed change validates clean.
2. **Given** an `Attribute` or `Relationship` vertex with no linked node vertex at all,
   **When** the repair migration runs, **Then** the vertex is hard-deleted and the count
   is reported.
3. **Given** two attributes sharing one `AttributeValue` vertex, one of them orphaned,
   **When** the repair migration runs, **Then** the orphan is detached and the surviving
   attribute keeps its value.
4. **Given** a state the migration cannot repair, **When** the upgrade runs, **Then** it is
   reported and the upgrade completes.

---

### User Story 3 - The deletion semantics are documented (Priority: P2)

An operator reading the user-facing documentation can predict what happens to a
branch-agnostic attribute or relationship when its object is deleted or the field is
removed from the schema, including deferral and what a branch that forked earlier will
see.

**Why this priority**: Independently shippable and valuable, but the behaviour must exist
first.

**Independent Test**: Documentation review against the enforcement points.

**Acceptance Scenarios**:

1. **Given** the published documentation, **When** an operator looks up deletion behaviour
   for branch-agnostic fields, **Then** it states when the value is released, when release
   is deferred and what resolves the deferral, and what a branch forked before the
   deletion sees.

---

### Priority Rationale

User Stories 1 and 2 are both **P1**. Shipping either alone leaves the reported failure
reachable: without the migration an affected deployment stays stuck, and without the
enforcement it becomes stuck again. They are listed enforcement-first because that is the
invariant the migration is the unbounded form of, but neither depends on the other and
each is independently developable, testable, and demonstrable.

### Edge Cases

- **A half-closed field vertex** — its global owning edge closed but its property edges still
  open, or the reverse. Present in the reported data, and the reason FR-002a closes the two
  independently rather than assuming they move together. The repair migration's widened anchor
  (FR-011a) is what makes the pre-existing ones reachable at all.
- **A retaining branch that is never touched again** holds its value reserved
  indefinitely. Accepted: it follows from the reservation semantics, and the existing
  backlog is cleared by the migration rather than by the enforcement points.
- **A branch-agnostic value updated after a branch forked, then its owner deleted.** The
  branch falls back to the value it knew at fork time — the same value an equivalent
  branch-aware attribute would show. Only reachable if the predicate misses a retaining
  branch, which is why retirement is a time-close rather than a status tombstone.
- **A relationship with one surviving peer.** Retiring on "either peer unreachable" rather
  than "both peers unreachable" is the correct reading, since a relationship with one peer
  is not a relationship. The predicate must therefore evaluate both `IS_RELATED` edges and
  both peers' existence on the same branch, not one peer at a time.
- **Isolation must not be overridden in the predicate.** Every branch is isolated — the
  create path drops any caller-supplied value — and several validators deliberately pass
  an isolation-ignoring flag to their branch filter so they can see across branches. The
  predicate must not do that: reading the default branch at current time makes a deleted
  object invisible, so every branch would look non-retaining and retirement would fire
  while branches still hold the object live.
- **Same-UUID node copies.** Name, namespace, and inheritance changes leave several node
  vertices sharing one UUID, each pointing at the *same* `Attribute` vertex over its own
  global edge, with the superseded vertex's edge closed as it is duplicated. Candidate
  traversal must therefore start from **open, active** global `HAS_ATTRIBUTE` /
  `IS_RELATED` edges, which excludes superseded copies for free. Traversing by
  reachability instead would close a shared vertex's value edges and strip a live object's
  value — the failure would only surface after the pre-migration branches were cleaned up.
- **Shared attribute values.** `AttributeValue` vertices are de-duplicated by value, so
  retirement must never delete one that any other attribute still references. Deleting one
  left with no references at all is permitted but not required.
- **Profiles and templates.** The predicate anchors on the `Node`, `Attribute`, and
  `Relationship` labels rather than enumerating schema kinds, so profile and template
  copies are covered without being listed — unlike the per-kind pattern the schema
  migrations follow.
- **Orphans with no existence edge at all.** Unreachable, un-diffable, and
  un-timetravellable. These are the vertices that get hard-deleted rather than closed.
- **Truly branch-agnostic nodes.** Their deletion already writes on the global branch and
  closes correctly. Out of scope, but must not regress.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST close an `Attribute` vertex's global property edges —
  `HAS_VALUE`, `IS_PROTECTED`, `HAS_SOURCE`, `HAS_OWNER` — **and its own global
  `HAS_ATTRIBUTE` edge** when no branch retains it. Closure MUST cover every open global
  edge of the vertex, not only the four property edges named here. *Verify: delete on the
  default branch with no branch forked during the object's lifetime; assert no open global
  edge remains, including `HAS_ATTRIBUTE`.*
- **FR-002**: The system MUST close a `Relationship` vertex's global property edges — and
  **both of its global `IS_RELATED` edges** — when no branch has both of its peers live
  with both `IS_RELATED` edges active, including when one peer survives. *Verify: delete
  one peer of a branch-agnostic relationship; assert closure of the property edges and both
  `IS_RELATED` edges.*
- **FR-002a**: The system MUST close the owning edge (`HAS_ATTRIBUTE` / `IS_RELATED`) and
  the property edges **independently**, so a vertex whose owning edge is already closed but
  whose property edges are still open — or the reverse — is fully closed rather than
  half-closed. Both mismatched states exist in the reported data. Because FR-001 and FR-002
  close both in a single pass, no *new* half-closed state can arise after this feature
  ships; the pre-existing backlog is the repair migration's responsibility (FR-016).
  *Verify: build each half-closed shape as a fixture and assert the migration closes the
  remaining open edge.*
- **FR-003**: The system MUST NOT close them while a retaining branch exists. *Verify:
  node created on a branch, merged, deleted on the default branch while that branch is
  open — edges stay open and the object is still readable there.*
- **FR-004**: The predicate MUST be governed by reachability from any branch, not by which
  branch the write happens on. *Verify: an object live on two branches is not retired when
  deleted on one of them, and is retired when deleted on the second.*
- **FR-005**: Node deletion MUST evaluate the predicate for the deleted node. *Verify: the
  default-branch, branch-only, and exists-on-two-branches cases.*
- **FR-006**: Branch merge MUST evaluate the predicate for the nodes whose deletion is
  being merged, using the diff already computed for the merge. *Verify: delete on a branch,
  merge it, assert closure.*
- **FR-007**: Branch rebase MUST evaluate the predicate for the nodes deleted on the
  default branch within the window the rebase closes, using the base-branch diff already
  computed before the rebase is applied and the same timestamp the rebase uses. *Verify:
  node deleted on the default branch while a branch is open, rebase that branch, assert
  closure.*
- **FR-008**: Branch deletion MUST evaluate the predicate for the nodes that were
  reachable on the discarded branch, using a query bounded by that branch's fork point
  rather than a stored diff, alongside the existing cleanup for branch-only nodes.
  *Verify: node deleted on the default branch, then delete the branch that was retaining
  it.*
- **FR-009**: Merge, rebase, and branch deletion MUST NOT treat their own occurrence as a
  release trigger; each MUST re-evaluate the predicate and leave the edges open when the
  object is still retained afterwards. *Verify: rebase and merge a branch on which the
  object is still live; edges stay open.*
- **FR-010**: Attribute-removal and relationship-removal schema migrations MUST evaluate
  the predicate for the field they remove. *Verify: remove a branch-agnostic attribute and
  a branch-agnostic relationship from the schema; assert closure when unretained and
  deferral when a branch forked beforehand.*
- **FR-011**: At the runtime enforcement points, candidate traversal MUST start from open,
  active global `HAS_ATTRIBUTE` / `IS_RELATED` edges, so a vertex shared with a live node
  copy is never reached. Because FR-001 and FR-002 close that same edge, a retired vertex
  stops being a candidate on subsequent passes. *Verify: rename a kind, then run every
  enforcement point; the surviving vertex keeps its value.*
- **FR-011a**: The repair migration MUST widen the anchor to global `HAS_ATTRIBUTE` /
  `IS_RELATED` edges with `status: "active"` regardless of whether they are open, so the
  pre-existing half-closed shapes of FR-002a are reachable. Same-UUID protection MUST then
  come from the predicate rather than the anchor: a vertex is retained when **any** node
  vertex linked to it is live with an active owning edge on some branch, so a vertex shared
  with a live copy is still never retired. This widening is confined to the migration, which
  is batched and off every hot path. *Verify: rename a kind, then run the migration; the
  surviving vertex keeps its value. Then re-run the migration and assert it reports zero.*
- **FR-012**: The predicate MUST evaluate each branch under its own branch and time filter
  with isolation applied, and MUST NOT use an isolation-ignoring filter. *Verify: an object
  retained only through a fork window is not retired.*
- **FR-013**: Retirement MUST be a time-close stamping `to` on the existing global property
  edge. The system MUST NOT express it as a `deleted`-status edge on the global branch.
  *Verify: with a deliberately unretired retaining branch, the object remains readable
  there rather than losing the field.*
- **FR-014**: Retirement MUST NOT register as a change on any branch that forked before it.
  *Verify: diff a pre-existing branch after a default-branch delete — no attribute or
  relationship change is reported for that node.*
- **FR-015**: Retirement MUST be stamped with the owner's latest deletion time where one
  survives, and the migration run time only where none does. *Verify: assert the stamped
  timestamp in both cases.*
- **FR-016**: The repair migration MUST close the global property edges **and the owning
  `HAS_ATTRIBUTE` / `IS_RELATED` edges** of vertices that no branch retains, including the
  half-closed shapes of FR-002a via the widened anchor of FR-011a, and MUST hard-delete
  `Attribute` and `Relationship` vertices that have no linked node vertex at all. It MUST anchor on graph labels rather than enumerating schema
  kinds, MUST cover attributes and relationships alike, MUST batch its writes, and MUST
  report both counts. It MUST NOT fail the upgrade on a state it cannot repair. *Verify:
  hand-built fixtures for both orphan shapes, asserting the reported counts.*
- **FR-017**: Retirement MUST NOT delete an `AttributeValue` vertex that any other
  attribute still references. *Verify: two attributes sharing one value, one orphaned — the
  surviving attribute keeps its value.*
- **FR-018**: Node deletion, branch merge, branch rebase, and branch deletion MUST NOT take
  substantially longer than they do today. "Substantially longer" is defined as a median
  duration more than 10% above the pre-change median for the same operation on the same
  dataset. The measurement MUST be taken at two open-branch counts — a low one and a
  realistic-high one — because the retaining-branch check grows with the number of open branches
  rather than with graph size, so a low-branch-count result is not evidence about a real
  deployment. *Verify: before/after timings on the existing benchmarks for all four
  operations at both branch counts, reported as numbers.*
- **FR-019**: The user-facing documentation MUST state the deletion semantics for
  branch-agnostic attributes and relationships on branch-aware objects, including deferred
  release, what resolves it, and what a branch forked before the deletion sees. *Verify:
  documentation review against the enforcement points.*

### Key Entities

No new entities, and no new persisted state — the diff-derived and query-derived candidate
sets remove any need for a marker or worklist.

- **Node** (branch-aware): its existence, evaluated per *vertex*, decides whether it is
  live on a given branch and therefore whether that branch retains a field.
- **Attribute** with `branch_support: "agnostic"`: its property edges live on the global
  branch and are the subject of the invariant. A single vertex can be shared across
  same-UUID node copies, which is why candidate traversal is constrained.
- **Relationship** with `branch_support: "agnostic"`: same, but with two peers, so its
  retention depends on both being live on the same branch.
- **AttributeValue**: shared across attributes by value de-duplication, so retirement
  detaches rather than deletes whenever another reference remains.
- **Branch**: its fork point defines the window that makes it a retaining branch. Every
  branch is isolated. Its lifecycle events — rebase, merge, deletion — are occasions to
  re-evaluate the predicate, not releases in themselves. The global branch is visible from
  every branch at current time, which is what makes an unclosed edge leak everywhere rather
  than staying local.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A data-only proposed change validates clean on a dataset carrying the pre-fix
  orphan shapes.
- **SC-002**: A schema update adding a uniqueness constraint on a previously-orphaned
  branch-agnostic attribute loads successfully.
- **SC-003**: The upgrade reports the number of edges closed and vertices removed, and
  completes without failing on unrepairable state.
- **SC-004**: After a create/delete cycle at any enforcement point with no retaining branch,
  zero global edges remain open for that field — property edges and the owning
  `HAS_ATTRIBUTE` / `IS_RELATED` edge alike.
- **SC-004a**: Re-running the repair migration on an already-repaired database reports zero
  edges closed and zero vertices removed.
- **SC-005**: With a retaining branch present, the object stays readable there and the value
  stays reserved; retirement occurs as soon as the retaining set is empty, by whichever
  event empties it.
- **SC-006**: A branch-agnostic relationship is retired when either of its peers becomes
  unreachable on every branch.
- **SC-007**: A value freed by retirement becomes allocatable again from its pool.
- **SC-008**: Node deletion, branch merge, branch rebase, and branch deletion show no median
  duration increase above 10% against current timings on the same dataset, at both a low and a
  realistic-high open-branch count.
- **SC-009**: An operator can determine from the published documentation what happens to a
  branch-agnostic value when its object is deleted or its field is removed, without reading
  the source.

## Assumptions

- Writing branch-agnostic values to the global branch from a branch remains intentional —
  that is what reserves a pool value across branches. The defect is lifecycle, not
  placement.
- Treating a branch-agnostic value as reserved on every branch is the correct semantics, so
  no branch-aware change to uniqueness validation is needed.
- Branches fork only from the default branch, so an object that exists only on one branch
  cannot be retained by another.
- Every branch is isolated in practice, since the branch-create path drops any
  caller-supplied isolation value.
- The base-branch diff computed during rebase is complete for the default-branch deletions
  in the window being closed, and is available before the rebase is applied and under the
  same lock.
- Both schema-removal migrations deliberately leave an inherited global edge open and
  shadow it with a branch-scoped tombstone. Retirement complements that pattern rather than
  replacing it.
- The reported orphans come predominantly from branch deletions predating the existing
  agnostic-peer cleanup, plus the schema-removal paths. One create/delete cycle under a
  uniqueness constraint reproduces the failure, so no large fixture is needed.
- Freed pool values becoming allocatable again is desired, user-visible behaviour and
  warrants a changelog entry.
- Releasing a reservation once no branch retains the field is accepted even though a value
  re-allocated afterwards would surface as a conflict at merge rather than at allocation.
  Blocking re-allocation while any branch could still reach the owner would require pool
  allocation to scan every open branch.
- The hand-written Cypher that unblocked the reported deployment is the closest thing to a
  validated reference implementation, and the retirement mechanism is expected to reproduce its
  shape: close the owning `HAS_ATTRIBUTE` edge and the property edges independently (each only
  where still open), stamp both with the owner's latest deletion time computed across every
  branch on which it was created or merged, and require that no branch leaves it still active.
  It differs in being label-anchored rather than per-kind and per-attribute-name, and in
  covering relationships as well as attributes.
- `release-1.11` is the right target: it carries the graph version this builds on, the
  existing agnostic-peer cleanup this extends, and the relationship-removal migration this
  depends on, and it reaches the development branch through the normal release merge.
- **Branch-deletion candidate selectivity** (resolved from the PRD's open question): the
  branch-deletion path bounds its candidate query by the discarded branch's fork point and
  anchors on the graph labels plus open, active global `HAS_ATTRIBUTE` / `IS_RELATED`
  edges, rather than scanning every node carrying a branch-agnostic field. Whether that is
  selective enough is a measured question answered during planning against a
  customer-sized graph; the FR-018 threshold is the gate. If the measurement fails the
  gate, the fallback is to narrow the bound further using the existence edge's `from`
  timestamp as an indexed filter.
- **Acceptable timing regression** (resolved from the PRD's open question): a median
  duration increase of no more than 10% for each of node deletion, branch merge, branch
  rebase, and branch deletion, measured against the pre-change build on the same dataset
  using the existing benchmark harness, at two open-branch counts.
- The number of branches open at once in a real deployment is materially higher than a test
  fixture's two or three. The retaining-branch check is evaluated against every open branch, so
  branch count — not graph size — is the dimension its cost grows in.
- Freed pool values become allocatable again through the existing used-value determination, which
  already requires an attribute's value edge to be open; no change to pool allocation itself is
  needed. This is verified by test rather than assumed, because the dependency spans three edges.

## Governance Gates Crossed

- [x] **Database schema or migration change** — a new graph migration plus a
  `GRAPH_VERSION` bump, mutating existing customer data during upgrade, including
  hard-deleting vertices with no linked node
- [ ] API / GraphQL / public interface change — none
- [ ] New dependency — none
- [ ] CI/CD workflow change — none
- [ ] Authentication / authorization change — none

## Out of Scope

- Any new persisted state — a node marker, a pending-retirement worklist, or a queue.
- Deleting `AttributeValue` vertices left with no references; permitted but not required,
  and not a deliverable.
- Post-filtering uniqueness violations by node existence. An open global edge means the
  value is retained somewhere, so the violation is legitimate; one naming an unretained
  value is a bug in the invariant.
- Adding node-existence filtering inside the uniqueness queries themselves. **Note**: the
  originating bug report lists this as one of two Expected Behavior items —
  *"uniqueness-constraint validation (and schema-migration constraint checks) should not scan
  attribute values belonging to nodes that are effectively deleted in the relevant branch
  view."* It is declined deliberately and with argument: every property edge of a
  branch-agnostic field is written on the global branch regardless of creating branch, so a
  branch-agnostic value is *already* reserved across every branch, which is the correct
  semantics for a cross-branch reservation. Fixing the lifecycle removes the symptom the
  reporter observed without weakening the validator, and leaving the validator unfiltered means
  a future leak fails loudly instead of being swallowed. This is a divergence from the filed
  issue that a reviewer should confirm they accept.
- Deferring retirement until no branch could ever see the object again by any path, rather
  than until no branch retains its field.
- A support-facing detector query as a separate deliverable; the migration's own predicate
  covers the need.
- End-to-end reproduction of the reported incident.
- Any change to deletion of branch-agnostic *nodes*, which already closes correctly.
- Reworking where branch-agnostic values are stored.
- The separate merge-time uniqueness race and the conflicted-value suppression behaviour,
  both tracked elsewhere.
