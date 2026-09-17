# Feature Specification: Numbers you give the pool

**Feature Branch**: `pool-number-attach-ifc-3184`

**Created**: 2026-09-16

**Status**: Draft

**Epic**: [IFC-3184](https://opsmill.atlassian.net/browse/IFC-3184)

**Input**: `POOL-ASSIGNMENT-PRD.md` — "PRD: Numbers you give the pool", P2 of the Number Pools PRD
([INFP-308](https://opsmill.atlassian.net/wiki/spaces/Product/pages/854818817), as revised by
[Number Pools — PRD, simple as possible](https://opsmill.atlassian.net/wiki/spaces/Product/pages/870514689)).

**Ships with**: P1 (several ranges), one release. P1 deletes the attribute scan that this slice's
attachment replaces; shipping one without the other leaves a release where hand-set numbers are
neither skipped nor attachable.

---

## Problem

A number set by hand cannot be tracked by a number pool. There is no way to say "this number is
mine, and this pool should account for it", so a pool's utilization describes only the part of the
space it handed out itself, and the next number it offers may already be in use. The same gap blocks
bringing a pool onto infrastructure that already carries numbers — firewall rule IDs, VLANs, a
fabric being onboarded — because those numbers are just allocations made by hand earlier. One
prospect said the current behaviour could stop them adopting resource pools at all; one customer's
architect called reconciliation with existing data "more than mandatory".

## Solution Overview

A pool tracks two kinds of number: ones it handed out, and ones you gave it. Provide a number
together with the pool that should track it, or give the pool later for a number an object already
carries — one mechanism, two ways in. Either way the pool records it, counts it in utilization, and
never hands it out again. You can take a pool back off a number, and the number itself is unchanged.

The pool refuses nothing. Ranges decide where allocation *draws from*, never what may be tracked, so
any number can be attached — including one outside the pool's ranges. Such a number is tracked and
reported in a bucket of its own rather than in the utilization fraction, which turns it into the
operator's worklist for widening the pool. Whether a value is *valid* stays where it already lives:
uniqueness constraints and the attribute's own domain.

Creating a pool over populated data still adopts nothing. A pool knows exactly what it handed out
plus what you handed it, and nothing else.

Underneath, the pool's ledger is re-anchored: a record now points at the attribute it reserves for,
not at the value. That is invisible to users, but it is what makes the pool stay correct when a
number changes or a branch diverges. It is delivered as foundational work that merges ahead of the
feature (User Story 1).

The record also becomes the one place a pool's claim is recorded. The pool stops writing itself into
the attribute's `source`; that slot shows the pool only when the user has not set a source of their
own. Two things follow: moving an object from one pool to another is a single update, and a user may
record their own source on a pooled number without the pool noticing or caring.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The ledger stays honest as data moves (Priority: P1, foundational)

Before a user can hand a pool a number, the pool's ledger has to be anchored somewhere that survives
the things brownfield data does: numbers change, objects are converted, branches diverge and get
deleted. Today the ledger record points at the *value*, which makes several of those cases wrong —
two of them confirmed defects that silently hand out a number somebody still holds.

This story re-anchors each record from the shared value to the per-object attribute it reserves for,
migrates every existing record, moves the pool out of the attribute's `source` storage, and fixes
cross-branch liveness. No new user-facing capability ships with it: the user-visible outcome is that
every figure a pool reports is unchanged except where a known defect is corrected.

**Why this priority**: Nothing in User Stories 2 and 3 can be built on the old anchoring — attach
would inherit the same defects the moment it shipped, and detach could not be made correct at all.
It merges ahead of the feature work so that SC-022 (figures identical before and after) can be
measured at a point where nothing else has moved the numbers.

**Independent Test**: Run the existing number-pool suites plus the new lifecycle and migration
coverage against a database populated before the change; every reported figure matches, the two
confirmed defects (branch-delete liveness, object conversion) now behave, and the migration reports
its counts.

**Acceptance Scenarios**:

1. **Given** a pool with existing allocations recorded under the old anchoring, **When** the
   migration runs, **Then** utilization, the branch split and the in-use list report exactly the
   same figures as before, and the migration reports a count for each of its destructive behaviours.
2. **Given** an object holding a pooled number on the default branch and deleted on another branch,
   **When** the pool is asked for its next number, **Then** the held number is still reported in use
   and is never offered — on a non-unique attribute as well as a unique one.
3. **Given** an object holding a pooled number, **When** it is converted to another object type,
   **Then** the pool still reports the number, attributed to the converted object, and never offers
   it.
4. **Given** a tracked object, **When** a plain `value` update is sent naming no pool, **Then**
   nothing is written to the ledger and the pool reports the new number in use and the old one free.
5. **Given** an attribute whose number a pool allocated and which carries no user-set source,
   **When** the attribute is read, **Then** `source` still reports that pool, with no source edge
   stored behind it.
6. **Given** an attribute a pool tracks, **When** the user sets their own source, **Then** the
   reported source is the user's and nothing the pool reports changes.
7. **Given** a pool-tracked attribute, **When** the attribute is renamed in the schema, **Then** the
   ledger record is still branch-agnostic and the pool still reports the number.

---

### User Story 2 - Bring existing numbers under a pool (Priority: P1)

An operator points a pool at a populated range, sees it report nothing, attaches the objects that
already carry numbers, watches utilization jump to match reality, then allocates and receives the
first genuinely free number.

**Why this priority**: This is the slice. It is the only reason the feature exists, it unblocks
adoption of Resource Manager on populated estates, and it is the replacement for the hand-set-value
scan that P1 deletes in the same release.

**Independent Test**: Create a pool over a partly-used range, attach the objects holding numbers in
it, and assert what the pool reports in use, in the out-of-space bucket, and as its next number.

**Acceptance Scenarios**:

1. **Given** a pool over 1–100 with 1–5 handed out, **When** an object is created with `value: 50`
   and that pool named, **Then** the save keeps 50, the pool reports 50 in use, the next allocation
   returns 6, and 50 is never handed out.
2. **Given** an object created earlier holding 37 with no pool, **When** it is updated with
   `value: 37` and the pool named, **Then** 37 is unchanged and the pool now reports it.
3. **Given** a new pool over 1–100 and forty objects already holding 1–40, **When** the pool is
   queried, **Then** it reports nothing — creating a pool adopts nothing.
4. **Given** a tracked object holding 50, **When** a plain `value: 60` update is sent with no pool
   named, **Then** the pool releases 50 and tracks 60 with no second call.
5. **Given** a pool over 1–100, **When** an object is saved with `value: 500` and that pool named,
   **Then** the save succeeds, 500 is tracked and reported in the out-of-space bucket rather than in
   utilization, and widening a range to cover 500 moves it into the in-use fraction with no further
   action.
6. **Given** 50 allocated to object A and 50 attached on object B with no uniqueness constraint,
   **When** the pool is queried, **Then** the in-use list returns two rows for 50 — one `allocated`,
   one `provided`, each naming its holder — while utilization counts 50 once.
7. **Given** an attribute pool A tracks, **When** a write names pool B — with or without a value —
   **Then** A's record ends and B's begins in one operation, A reports nothing for that object, and
   A's out-of-space bucket does not acquire B's number.
8. **Given** an object holding a non-default number no pool tracks, **When** `from_pool` is sent
   alone, **Then** the save is refused with an error naming both ways forward: restate the value to
   attach it, or send `value: null` to discard it and allocate.
9. **Given** an object that already owns a number under a pool, **When** the same `value` and
   `from_pool` are re-sent, **Then** the write is a silent no-op.

---

### User Story 3 - Take a pool back off a number (Priority: P2)

An operator detaches a number from a pool; the pool stops reporting it and the object keeps it.

**Why this priority**: Small, separable, and it changes no contract — `from_pool: null` is existing
input with new meaning. It reuses the release query the foundational story introduces. Without it,
an attach made in error can only be undone by discarding the number.

**Independent Test**: Attach a number, detach it, and assert the object's value is unchanged, the
pool's in-use count dropped by one, and the number is offered again.

**Acceptance Scenarios**:

1. **Given** a number the pool tracks, **When** `from_pool: null` is sent, **Then** the number is
   unchanged, the pool's in-use count drops by one, and the number is allocatable again.
2. **Given** 50 held by two objects under one pool, **When** one of them is detached, **Then** only
   that record ends and the other object's record still reports 50 in use.
3. **Given** a detach performed on a branch, **When** that branch is deleted, **Then** no branch
   reports a pool source for that attribute and the pool reports nothing for it.

---

### Edge Cases

- Attach a number a uniqueness constraint rejects → refused by the constraint, not the pool.
- Attach a number outside the pool's ranges, or inside the attribute's excluded values → accepted,
  tracked, bucketed.
- Three objects hold the same number → three rows in the in-use list, one element of utilization.
- Detach one holder of a duplicated number → only that record ends; the others still report it.
- A duplicated number that is also out of the effective space → bucketed, and still consumes nothing.
- Re-send `value` + `from_pool` for a number the object already owns → silent no-op. Required for
  clients that resend every field.
- `from_pool` alone on an attribute holding a schema default → allocates, overwriting the default.
- One object holds different values on different branches → **every** value any live branch holds
  counts as taken, and a value becomes free only when no live branch holds it (FR-036a).
- Detach on a branch → the record ends globally and immediately, symmetric with allocating on a
  branch consuming immediately. This is about the *record*, not the value: a branch that still holds
  the number keeps it, and FR-036a governs whether the pool still sees it.
- Detach, then the object still holds the number → the pool may hand it out again, and the save
  fails if a uniqueness constraint exists. Accepted.
- Delete the object, or change the number without naming a pool → the record stops counting on its
  own, because every read requires the object to still hold the recorded value.
- `source` named alongside `from_pool` → accepted; the user's source is displayed and the pool keeps
  tracking the number.
- Attach onto an attribute that already carries a user-set source → accepted, nothing cleared.
  Common on the brownfield path, where imported objects routinely arrive with a source.
- Name pool B on an attribute pool A tracks → re-pool: A's record ends, B's begins, one update.
- One record straddles the effective-space boundary — in space on one branch, out of space on
  another → it appears in the utilization fraction and in the bucket at once, told apart by the
  branch on the row.
- A tracked value falls outside the effective space by two different paths — attached there, or a
  range removed under it → identical state; both must be tested.

### Record lifecycle

Every read requires the owning object to still hold the recorded value. That liveness join, not
record deletion, is what frees a number. `provenance` is irrelevant to every row.

| Event | Required behaviour | Status at spec time |
|---|---|---|
| Object deleted | Record retained; liveness join fails; the number stops counting. No cleanup write. | Already covered — node-delete suites. Extend if the attached case differs; do not duplicate |
| Branch deleted, object existed only on that branch | Same mechanism. | Likely covered — audit before writing |
| Branch deleted after an attach or detach made on it | Attach and detach are global and permanent, like allocation. | By design — test that it holds |
| Two branches allocate from one pool | Records are global and reads branch-agnostic; the second branch cannot receive the same number. | Believed to work — verify with a test |
| Two branches hand-set the same number, both attached | Both records exist. At merge a uniqueness constraint refuses; without one, both survive and the free-number query collapses them. | Follows from FR-028 — test the constraint path |
| Merge of a value change on a tracked attribute | The record follows the attribute. If conflict resolution reverts the value, the liveness join hides the record and the number is free again. | Test the conflict-revert path — shares a mechanism with FR-036a |
| Object deleted on a branch while another branch still holds it | The number must stay taken until no live branch holds it (FR-036a). | **Confirmed broken.** Reproduced: freed on every branch and reallocated into a collision |
| One object holds different values on different branches | Each value counts as taken while some branch holds it. | **Verified working** — must stay working |
| Object converted to another type | The record must follow to the new object's attribute. | **Confirmed broken post-move** — foundational work item 2 |
| Object re-pooled from A to B | A's record ends, B's begins; A reports nothing for it and A's bucket stays empty. | New — test, including that A's bucket does not acquire B's number |
| Detach on a branch, then delete that branch | No branch displays a pool source, because none was ever written. | Resolved by FR-030b — test it holds |
| A tracked value falls outside the effective space | Retained, invisible to allocation, reported in the bucket. Re-entering the space moves it to in use. | New state, two paths — test both |

One component test per row **that is not already covered** — several are. Audit first; extend an
existing test rather than adding a parallel one. Where a row's existing coverage exercises a
branch-agnostic attribute, the attached branch-aware case is still a genuine gap, because the two
are protected by different mechanisms.

If either of the first two rows fails for the attached case, the fix is a cleanup write on the
record — the same release the release query is introduced — not a change of shape. The FR-036a row
is different: a failure there is a read-query change, and it gates the slice.

---

## Requirements *(mandatory)*

Numbering follows the Confluence PRD so requirements stay traceable across slices. Requirements not
listed here stand as written there.

### Functional Requirements

- **FR-021**: `value` + `from_pool` on create MUST keep the provided number and track it. Works on a
  pool already in use. *(Today the value is discarded.)*
- **FR-022**: `value` alone MUST be accepted and tracked by no pool. No record, no pool claims it.
- **FR-023**: The named pool MUST be attached to the kind and attribute being written; any other
  pool is refused. Already enforced, including for a pool attached to a generic the kind inherits
  from.
- **FR-024**: `value` + `from_pool` on update MUST attach. `from_pool` alone on a non-default
  untracked value MUST be refused, naming the two ways forward: restate the value to attach, or send
  `value: null` to discard and allocate.
- **FR-024a**: A write naming pool B on an attribute pool A already reserves MUST **re-pool** — A's
  record ends and B's begins in one operation — whether the write allocates (`from_pool: B` alone)
  or attaches (`value` + `from_pool: B`). Not a refusal: re-homing objects between pools is the
  brownfield journey this slice exists for. "Tracked by a *different* pool" is therefore a dimension
  of the intent decision table, not an error case.
- **FR-024b** *(invariant)*: At most one live reservation record MUST exist per attribute. The
  create path MUST close any existing record on the target attribute before creating its own.
  This invariant holds today only as an emergent property of the value anchoring; the re-anchoring
  removes the accident, so it must be enforced by construction.
- **FR-025**: `from_pool: null` MUST detach. The number is unchanged. The release ends the single
  branch-agnostic record between the pool and that object's attribute; identifier matching is no
  longer needed, because the anchor is already per-object. No source is cleared, because under
  FR-030b the pool never wrote one.
- **FR-026**: Each record MUST carry `provenance` ∈ {`allocated`, `provided`}. Two values, not
  three. Absent means `allocated`, so the property itself needs no backfill. Under FR-021/FR-024,
  "provided" and "attached" are the same request made on create and on update.
- **FR-027**: A tracked number inside the pool's effective space MUST count in utilization and
  appear in the in-use list beside allocated ones. A tracked number outside the effective space MUST
  be reported in a separate bucket, not folded into the utilization fraction.
- **FR-027a**: Out-of-space rows MUST carry value, holder **and branch**, matching the in-use row
  shape. The bucket MUST NOT be split into per-branch buckets: the three utilization figures are
  split because a *fraction* cannot carry per-item detail, while the bucket is already a list of
  rows and can. Grouping by branch is a client concern, and the count stays derivable. The branch is
  load-bearing: under FR-028a one record can straddle the boundary, appearing in the utilization
  fraction and in the bucket at once, and without the branch on the row the operator reads a
  contradiction they cannot resolve.
- **FR-028**: The pool MUST have no duplicate rule. Two objects may hold the same number under one
  pool. A uniqueness constraint on the attribute is the only thing that refuses it, with the
  ordinary duplicate error.
- **FR-028a**: Utilization MUST count distinct elements of the effective space consumed, never
  records — a number held by three objects consumes one element. The in-use list MUST return one row
  per **(record, branch-resolved value)**, so every holder is visible with its own `provenance`.
  Because a record is anchored on the attribute, one record reserves whichever values its attribute
  holds across branches: a record whose object holds 1 on the default branch and 5 on another
  contributes two rows and consumes two elements. Both numbers are genuinely unavailable, so this is
  correct, not double-counting. Releasing one record MUST NOT affect another record holding the same
  number.
- **FR-029**: **Deleted.** The pool refuses no provided value. A number outside the pool's ranges,
  or inside the attribute's excluded values, MUST be accepted and tracked, behaving per FR-002a:
  invisible to allocation, reported in the bucket, and re-counted if the effective space later
  covers it.
- **FR-030**: Applies to plain writable number attributes only. The `NumberPool` attribute kind
  stays read-only and accepts no provided value. Templates remain refused.
- **FR-030a**: **Deleted.** A user MAY set `source` on an attribute a pool tracks. Both reasons
  earlier drafts gave for the refusal are dissolved by FR-030b: the two facts no longer share
  storage, so they cannot carry the same fact incompatibly, and they no longer contend for anything
  but the read slot. The refusal was in truth patching a query defect — the allocated-list query
  gates every row on the source edge being active, so a user-set source today removes an allocated
  number from the list while it stays reserved. FR-030c fixes the query instead of constraining the
  user.
- **FR-030b**: A pool MUST NOT be written to the attribute's source storage. `source` resolves to
  the user's stored source when one exists, and otherwise to the pool derived from the inbound
  branch-agnostic reservation record on the attribute. The output slot and its type are unchanged,
  so this is **not** a published-contract shape change, and display is unchanged for every attribute
  that has no user source. This is what makes detach correct: with no pool-owned source there is
  nothing to clear on detach, nothing to leave behind when a detaching branch is deleted, and the
  displayed source stops naming the pool on every branch at once.
  **Cost**: pool lineage leaves the diff. Allocating or attaching on a branch will show a value
  change with no accompanying source change. Defensible — the pool fact is branch-agnostic, so
  diffing it per branch was always a fiction — but user-visible, and it needs a changelog entry.
- **FR-030c**: The rewritten allocated-list query MUST NOT consult the source edge; membership of
  the allocated list is decided by the record and the liveness join alone. The rewritten
  reserved-list query MUST resolve forward through the value edge, so a record pointing at an
  abandoned attribute reports nothing rather than reporting the edge.
- **FR-031**: **Deleted — satisfied by construction.** The requirement was that changing a number on
  a pool-tracked attribute moves the record. Anchored on the attribute, a value change writes
  nothing to the ledger: the record already tracks the attribute, and what it reserves is whatever
  values that attribute holds. The record-move, its self-healing clause and its pool lock all go,
  taking with them the only hot-path regression this slice carried. It was also not correctly
  implementable under the old anchoring: a record is branch-agnostic but a value change is
  branch-scoped, so "release the old number" would free it for every branch while others still hold
  it.
- **FR-036a** *(confirmed by repro — release blocker)*: Liveness MUST be evaluated as a **union
  across branches**. A number MUST count as taken while any live branch holds an object carrying it,
  and MUST become free only once no live branch does. The error must stay one-sided: the pool may
  report a number taken that is free on some branch, never free when taken on any.
  **Confirmed defect.** Deleting an object on a branch while the default branch still holds it makes
  the pool report its number free on *every* branch, because liveness is resolved with a single
  cross-branch winner-takes-all and the deleting branch's tombstone wins. On a non-unique attribute
  the pool then hands the number to a second object while the first still holds it — reproduced.
  **P1 removes the mask**: today a unique attribute is protected by the 1.11 hand-set-value scan,
  which P1 deletes, converting a latent read defect into a live collision. This slice's remedy for
  the deletion — *attach your hand-set numbers* — does not help, because the number is already
  tracked. **Owned by this slice**; it cannot land after P1's deletion.
  **Required fix**: resolve liveness per branch and take the disjunction across branches, matching
  the shape the branch-agnostic retirement work already uses for its retaining-branch predicate. No
  migration, and it lands in queries P1 is rewriting anyway.

### Requirements inherited from P1 (several ranges)

- **FR-011**: The pool never inspects its attribute. The attribute scan is deleted in P1, which ships
  with this slice. This slice relies on the deletion but does not carry it.

  **Identifying which numbers to attach is the operator's job** (decided 2026-09-16). A pool adopts
  nothing, bulk attach is out of scope, and this slice ships no enumeration surface: an operator
  brings numbers under a pool by naming the values they want tracked, one object at a time. Making
  that easier — an enumeration query or a migration tool — is explicitly deferred, not forgotten; see
  *Out of Scope*.
- **FR-002a**: A record outside every effective range is retained and stays associated with the
  pool. This slice narrows "excluded from utilization" to "excluded from the utilization fraction" —
  such records are bucketed, not hidden.
- **Effective space**: union of ranges ∩ `[min_value, max_value]` minus intersecting excluded
  values. This slice consumes P1's calculator for membership and MUST NOT reimplement it.

### Foundational work (must merge ahead of the feature work)

None of this slice's feature work can start until these land. Each is a separate change with its own
review; the first three are one change set.

1. **Re-anchor the reservation record to the attribute, with a data migration.** Six pool queries
   are rewritten; the six IP-pool queries are untouched. The migration must resolve each record's
   node uuid to the *active* node vertex (duplicate-uuid aware), find the attribute by the pool's
   configured attribute name, create the branch-agnostic edge and close the old one. It carries four
   behaviours, and each of the last three **reports a count** rather than proceeding quietly:
   1. Re-anchor every record.
   2. **Drop orphaned records** whose object no longer exists.
   3. **Collapse multi-pool records onto one attribute** (FR-024b). Survivor is the record with the
      most recent `from`: a record is a claim, and the most recently made claim is the current one.
      *(The PRD justifies this as "matching the rule `m066` uses for schema pools". That is false —
      `m066` keeps the **earliest**, and it answers a different question: which pool **vertex**
      survives dedup, where the original is the one schema parameters already point at. The rule here
      stands on its own merits.)*
   4. **Delete every stored pool source edge** (FR-030b), unconditionally: every
      `(attr)-[:HAS_SOURCE]->(:CoreNumberPool)` edge goes, whatever state that pool's record for the
      attribute is in. FR-030b says the pool is never a stored source, so a stored one is legacy by
      construction. Left in place they win the read slot forever, so the derivation never fires for
      pre-upgrade data — and, being branch-aware edges carrying what is now a branch-agnostic fact,
      they reproduce the detach orphaning for exactly the objects most likely to be detached during
      brownfield cleanup. Scoping the sweep to a pool that still holds a live record would spare the
      worst cases: a released reservation, a collapsed-away loser, and an attribute renamed out from
      under its record each keep an edge naming a pool that no longer accounts for them.

   **Ordering is defence-in-depth.** Behaviour 4 runs before behaviour 3, though its predicate no
   longer reads the records, so no ordering of the two can leave an edge behind. The order holds the
   line if that predicate is ever narrowed back to a pool with a live record: the collapse would then
   kill a losing pool's record first, behaviour 4 would find no live record for it, and its legacy
   source edge would win the read slot forever.

   **The migration is irreversible.** Three of its four behaviours delete data and there is no
   reverse migration; the recourse after a bad upgrade is a database restore. Each destructive
   behaviour therefore reports its count twice — a pre-count of what it is about to act on, and a
   post-count of what it did — so an operator who stops the upgrade still has the figure.

   This is the heaviest item in the release and the most likely to stall review, so it merges on its
   own ahead of the feature work. That boundary is what makes SC-022 measurable.
2. **Re-target the pool-record-move query for object type conversion.** **Confirmed defect** on
   `develop` as of 2026-09-15: it closes the record and re-creates it against the *same* resource,
   while its only caller has already created the new node with its own attribute — so post-move the
   record points at the abandoned attribute, the liveness join fails, and the pool frees a number
   the converted object still holds. Three consequences: the fix must re-target the edge to the new
   node's attribute, matched by the pool's configured attribute name; the query is shared by all
   three pool shapes, so it must branch on shape or be split; and the existing conversion test will
   not catch it as written, because it asserts through a query with no liveness join — rewrite it to
   assert the value the pool reports.
3. **Fix the attribute-rename migration's branch-agnostic handling.** It copies every edge untyped
   without preserving the branch-agnostic marker, so renaming an attribute would silently relocate
   the ledger edge onto a branch. Port the conditional that node duplication already has. Silent if
   missed.
4. **Fix FR-036a.** Written *after* (1), against the post-move edge chain — doing it first means
   writing it twice.

### Untyped edge sweeps over attributes

Anchoring the record on the attribute puts it in the path of every untyped edge sweep over that
vertex. There are three, and each needs checking for correct branch-agnostic handling:

| Sweep | Effect once the record is anchored on the attribute |
|---|---|
| Attribute rename | **Bug** — copies edges without preserving branch-agnostic, relocating the ledger edge onto a branch |
| Attribute remove | **Likely a win** — schema attribute removal would close the reservation, which today it does not |
| Branch-agnostic retirement | **Intended** — this is the inheritance the move is for |

FR-030b raises the stakes on all three. The record is now the sole storage of the pool's claim, so a
sweep that relocates or drops it does not merely lose accounting — it silently changes what the
attribute reports as its `source`.

### Key Entities

- **Number pool record** (pool → **attribute**, branch-agnostic): **re-anchored by this slice**, and
  gains `provenance`. The attribute is per-object and survives value changes, so the record no
  longer needs an identifier to say whose it is. What it reserves is resolved forward through the
  value edge, per branch.
- **Attribute source** (attribute → user-chosen node): **no longer written by the pool** (FR-030b).
  It remains an ordinary branch-aware, user-settable lineage edge with its ordinary diff and merge
  semantics, and a user may now set it freely on a pooled attribute. The pool is no longer *in* it
  and is no longer *found* through it — the inbound record answers "which pool tracks this?" in one
  hop, and the read slot falls back to that pool when no user source exists.
- **Number pool**: no new attribute from this slice. Ranges come from P1.
- **Allocation scope**: not involved. Scope affects which number is picked next and nothing else, so
  this slice is scope-unaware and does not depend on P3.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A provided number and an allocated number appear together in one pool's in-use list,
  distinguishable by provenance, and both count toward utilization.
- **SC-002**: After attaching every object holding a number in a pool's range, utilization equals
  the share of the range actually held.
- **SC-003**: A new pool pointed at a fully populated range reports 0% used until something is
  attached.
- **SC-013**: An operator changes a tracked object's number naming no pool. The in-use count is
  unchanged, the new number is reported in use, the old one is free and is returned by the next
  allocation. No second call is needed.
- **SC-014**: An operator detaches a number. The in-use count drops by one, the number is
  allocatable again, and the object's value is unchanged.
- **SC-015**: An operator attaches numbers lying outside the pool's ranges and the pool lists exactly
  which. Widening a range to cover them moves them into the utilization fraction with no further
  action.
- **SC-016**: An object holding a pooled number is deleted on a branch while another branch still
  holds it. The number stays reported in use, is never offered by allocation, and becomes free only
  once no live branch holds it — on a non-unique attribute as well as a unique one. Verifies
  FR-036a.
- **SC-017**: **Withdrawn.** A numeric allocation-latency target was drafted and removed: the repo
  has no evidence for a realistic live-branch ceiling, the performance task runner is not
  parameterised on branch count, and "no worse than linear" is satisfied by construction. The
  performance obligation is real and moves to *Testing Decisions* as a benchmark requirement rather
  than a threshold nobody can justify.
- **SC-018**: An operator moves an object from pool A to pool B in a single update. A reports
  nothing for that object and A's out-of-space bucket is empty; B reports the number. No second
  call. Verifies FR-024a/FR-024b.
- **SC-019**: An attribute allocated from a pool reports that pool as its source with no stored
  source edge present. Setting a user source changes the reported source and changes nothing the
  pool reports. Verifies FR-030a's deletion and FR-030b.
- **SC-020**: An operator detaches on a branch and then deletes that branch. No branch reports a
  pool source for that attribute and the pool reports nothing for it.
- **SC-021**: An object holding a pooled number is converted to another type. The pool keeps
  reporting the number, attributed to the new object, and never offers it. Verifies foundational
  work item 2.
- **SC-022**: Every figure a pool reports — utilization, the branch split, the in-use list — is
  identical before and after the re-anchoring, except where FR-036a corrects a known defect. *(Only
  measurable at a boundary where nothing else has moved the numbers, so the foundational work must
  merge before P1's ranges and this slice's bucket land. It is the strongest available evidence the
  migration is safe.)*

*(Base PRD SC-005 and SC-006 are the ranges criteria and are not this slice's. SC-004, bulk attach,
is deferred with the frontend.)*

---

## Implementation Decisions

Carried from the PRD; the plan phase turns these into design, it does not reopen them.

- Modules to build or modify:
  - **`FromPoolIntentResolver`** (core, mutation path, new): maps a request — `value` sent,
    `from_pool` sent / explicit-null / absent — plus the attribute's current state to one intent:
    allocate, provide, attach, detach, discard-and-allocate, no-op, or refuse. Its inputs include
    whether the attribute is currently tracked by a *different* pool, which yields the re-pool
    intent (FR-024a). Encodes the whole contract, including its one refusal, as pure decision logic.
  - **`PoolRecordLedger`** (core, query layer, extends): creates and ends branch-agnostic records
    between a pool and an attribute, with `provenance`. Carries the new release query. No identifier
    scoping and no record-move — both disappear with the re-anchoring.
  - **`PoolUtilizationReporter`** (pools, new, pure): takes a record set and an effective space;
    returns the distinct-element count, the branch split, and the out-of-space bucket. Owns the
    FR-028a invariant.
  - **`NumberUtilizationGetter`** (pools, reduced to a seam): fetches and delegates, owning no
    arithmetic. Its three utilization properties are read directly by the pool query resolver, so
    the seam keeps this slice's contract diff limited to the two new fields. Its total-size property
    is deleted by P1.
  - **Pool query surface** (GraphQL, extends): adds `provenance` and the out-of-space bucket.
- **Consumed, not built**: P1's effective-space calculator. Membership must not be reimplemented
  here.
- **API surface**: no new input fields. `from_pool` changes meaning — explicit `null` is detach,
  `value: null` + `from_pool` discards and allocates — and absent versus explicit-null are
  distinguishable at the GraphQL input layer (verified on the pinned graphene). Two new output
  fields on the pool query: `provenance` per in-use row, and the out-of-space bucket as a list of
  rows carrying value, holder and branch (FR-027a). `source` keeps its existing field and type; only
  what populates it changes (FR-030b).
- **Errors**: **one** new refusal — `from_pool` alone on a non-default untracked value. The
  out-of-range refusal earlier drafts carried is deleted, and the two `source` refusals go with
  FR-030a. A duplicate reuses the existing uniqueness error.
- **Data**: the record edge is re-anchored from the value to the attribute; one property on the
  edge; one new release query. No new core kind. The pool stops writing the source edge and the
  source resolver gains a fallback to the record. The migration runs over every existing record and
  carries four behaviours, two of them destructive.
- **Frontend**: none. The backend must expose everything the deferred views need so they require no
  further backend change.
- **SDK/CLI**: none.

---

## Testing Decisions

- **What makes a good test here**: assert what a user can see — which number comes back, what the
  pool reports in use and in the bucket, which saves are refused. The two pure modules are the
  exception: they exist so the contract and the arithmetic can be pinned without a database, so they
  are tested directly.
- **Unit tests**: `FromPoolIntentResolver` — every cell of both decision tables, including the
  re-pool cells, the single refusal and the idempotent no-op. `PoolUtilizationReporter` —
  distinct-element counting with duplicates, the in-space/out-of-space partition, the branch split,
  and an empty effective space.
- **Regression tests for FR-036a (confirmed defect)**: delete a pooled object on a branch while the
  default branch still holds it, and assert the number stays in use and is not reallocated — **once
  with the attribute non-unique**, where the collision reproduces today, and once unique, which only
  starts failing when FR-011 lands. A working exploratory repro exists and should be promoted rather
  than rewritten. Keep the passing case as a regression too: a branch-level *value change* must not
  free the default branch's value.
- **Component tests**: the ledger against a database — attach, detach, and release with duplicates
  present; that a value change writes nothing to the ledger and the number tracked follows the
  attribute; that re-pooling from A to B ends A's record and leaves A's bucket empty; that a
  user-set source changes nothing the pool reports and that a pool with no user source is still
  returned in the slot; that object conversion keeps the number attributed to the converted object;
  the attribute-rename and attribute-remove sweeps leaving the record branch-agnostic; one test per
  row of the record-lifecycle matrix, in the existing number-pool lifecycle and branch test modules.
- **Integration (Docker)**: **required.** The re-anchoring migration needs Docker integration
  coverage per the repo's rule that schema migrations do, alongside P1's range migration. Cover the
  duplicate-uuid node case and each of the migration's four behaviours — in particular the
  multi-pool collapse and the legacy source-edge deletion (a pool-written edge removed, an unrelated
  user source left alone), with their reported counts.
- **Benchmark**: FR-036a replaces a single cross-branch resolution with a per-branch one inside the
  allocation path's pool-wide lock, so allocation cost gains a dependency on live branch count that
  it does not have today. Benchmark allocation against `develop` before and after the fix, vary
  branch count, and review the curve. No numeric gate is set — see SC-017 — but a superlinear curve,
  or a large constant from nesting per-branch resolution inside a query that already fans out over
  records, is a release decision rather than something to wave through.
- **E2E scenario**: an operator creates a pool over a populated range, sees it report nothing,
  attaches the existing objects, sees utilization jump to match reality, then allocates and receives
  the first genuinely free number. Playwright coverage travels with the deferred frontend.
- **Audit existing coverage before writing anything.** Several lifecycle rows are already tested and
  must not be duplicated. Known prior art: the functional number-pool lifecycle and branch suites
  (covering assign-in-branch, branch delete, node delete, and allocation over pre-existing nodes);
  the branch-merge suite under schema lifecycle; the branch-agnostic retirement suites, which carry
  one module per enforcement point and include a test asserting that a value freed by retirement is
  allocatable again from its pool. Extend these rather than adding parallel modules.
- **Reusable helpers already exist** for the graph-shape assertions this slice needs — enumerating
  an attribute's global edges, listing a pool's reservation edges, and asserting retirement
  timestamps — alongside the shared number-pool test helper. Use them; do not re-roll them.
- **The gap the audit will expose**: existing pool-lifecycle coverage exercises the *branch-agnostic*
  attribute configuration. This slice targets *branch-aware* plain number attributes, which a
  different mechanism protects. A row marked covered is covered for one configuration, not both.

---

## Constitution Alignment

- **I. Schema-Driven Integrity**: no new core kind, but **this slice carries a data migration**
  re-anchoring every existing record, in a release that also carries P1's range migration. The
  migration must preserve every allocation and every reported figure, and is the first to delete
  reservation data, so it reports a count. Four behaviours, two destructive — orphan drop, multi-pool
  collapse, legacy source-edge deletion — each reporting its own count. The two query fields change
  the published schema, so generated files are regenerated, not edited; `source` changes what
  populates it without changing its shape, so nothing is regenerated for it and it must be named in
  the contract review explicitly.
- **II. Branch-Safe by Default**: records stay branch-agnostic, so attach and detach take effect
  everywhere immediately — symmetric with allocation. The record-lifecycle matrix states and tests
  the branch behaviour this principle demands, including three "verify" rows that gate the slice.
  FR-036a is the sharpest test of this principle: a ledger that is branch-agnostic in storage must
  still be branch-*honest* in what it reports, and the read path fails that today.
- **III. Type Safety & Explicit Contracts**: `from_pool` changes meaning without changing shape, and
  `source` changes provenance without changing shape, so the single refusal and the intent table
  *are* the contract — which is why the resolver is extracted and unit-tested rather than left
  inline. Query results come back as typed structures, not raw records.
- **IV. Test Discipline**: two pure modules with their own suites; one component test per lifecycle
  row; Docker integration coverage for the migration; the E2E scenario named above.
- **V. Query Performance & Efficiency**: net improvement. P1's deletion of the attribute scan
  removes the in-memory taken-set built per allocation under the pool lock; re-anchoring removes the
  liveness traversal's fan-out over a globally shared value vertex and the uuid join with it; and
  FR-031's deletion removes the pool-lock contention on plain number edits that earlier drafts would
  have introduced. Costs to watch: the range filter now applies after a branch-resolved hop, and
  FR-036a's per-branch resolution multiplies edge resolution by branch count inside the allocation
  lock — this is the slice's one real performance risk, and the benchmark obligation covers it.
  FR-030b's derivation is not comparable: one further optional match inside a subquery already bound
  to the attribute, gated by the existing metadata flag. The reporting split must not reintroduce an
  N+1 over records.
- **VI. Security & Input Boundaries**: no new authentication or authorization surface.
- **VII. Simplicity & Maintainability**: one source for what a pool knows, one arithmetic for what it
  reports, and one edge behind both the ledger and the displayed lineage instead of two that had to
  be hand-synchronised across incompatible scopes. FR-024b is the same instinct: make an invariant
  that used to hold by accident hold by construction. The cost is that the pool is wrong whenever a
  user forgets to attach — accepted deliberately, with attaching as the remedy.

---

## Governance Gates Crossed

Using the "Ask First" list from `AGENTS.md`.

- [x] **Database schema or migration change** — the record edge is re-anchored to the attribute,
  with a data migration over every existing record. Plus one property on the edge and one new
  release query. No new kind. Two behaviours beyond the orphan drop are destructive: the multi-pool
  collapse (FR-024b) and the deletion of legacy pool source edges (FR-030b). This is by some
  distance the heaviest gate the slice crosses and it lands in a release that also carries P1's
  range migration. It merges ahead of the feature work so that SC-022 can be measured against it.
- [x] **GraphQL schema modification** — `from_pool` semantics, one new refusal, two new output
  fields on the pool query, and a change to what populates `source` with no change to its shape.
- [x] **Published schema contract (ADR 0010)** — the two output fields are a published-contract
  change. This slice must be named in the contract review alongside P1 and P3's attribute-parameter
  changes. FR-030b must be named there too: the generated schema will not show it, because the field
  and type are unchanged and only its provenance moves.
- [ ] New dependency
- [ ] CI/CD workflow change
- [ ] Authentication / authorization change

---

## Assumptions

- Keeping a pool honest about hand-set numbers is the user's job. The pool never looks at its
  attribute; attaching is the mechanism, not a convenience.
- The record no longer identifies its owner by uuid — the attribute it points at *is* the owner.
  This removes the duplicate-UUID hazard that uuid-joined queries carry, and it unblocks P4: a
  caller-supplied identifier can no longer break liveness, because liveness no longer depends on it.
- Strict schema validation is on by default, and attribute validation runs on read as well as write.
  An out-of-domain value therefore cannot sit on an object in a default deployment, and in a
  non-strict deployment attribute validation does not run at all — so deleting FR-029 delivers
  unrestricted attach without needing FR-024 to change its spelling.
- Duplicates within a pool are legitimate; the schema decides validity.
- Cross-branch liveness is a union, not a winner-takes-all resolution. **Verified false today** —
  see FR-036a, which this slice fixes.
- The record edge and the attribute source are **not** kept in sync, because the pool no longer
  writes the source at all (FR-030b). The record is the ledger and the sole storage of the pool's
  claim; the source edge is the user's lineage fact and nothing else. Hand-synchronising them was
  tried and rejected: their scopes differ, not just their semantics, so detach could not have been
  made correct.
- A user who sets their own source accepts that the read slot stops naming the pool until the
  deferred `from_pool` output field lands. Nothing the pool computes is affected.
- Per-attribute user sources on pooled number attributes are **rare**, which is what makes deferring
  that field safe. Automatic source assignment applies only to repository-managed core objects, not
  to the user data nodes FR-030 scopes this slice to. A deployment that sets lineage widely by hand
  will see the user's source and no pool on the object; its pool query is unaffected.
- At most one pool tracks an attribute at a time. True today only as an emergent property of the
  value anchoring, and made an enforced invariant by FR-024b.
- Bulk attach is out of scope, so brownfield adoption is one object at a time through the API. The
  base PRD's forty-object scenario is to be read as forty single attaches.

---

## Out of Scope

- Bulk attach and the pool-level mutations it would need. All-or-nothing cannot be built from N
  update calls, so it requires a dedicated mutation; deferred with the frontend.
- **Any tooling for discovering which numbers to attach** — an enumeration query over values already
  held on the pool's kind and attribute, or a migration tool that attaches them. Decided 2026-09-16:
  the operator names the values they want tracked. This is a real ergonomic cost on the brownfield
  path and it is accepted knowingly; a migration tool can be added later if adoption shows it is
  needed. It is deferred, not rejected.
- A dedicated `from_pool` output field. It is the end state and the only way to show a pool and a
  user source together, but FR-030b makes it cheaper to add later rather than harder — it would
  remove a branch in the source resolver, not change a contract.
- Discarding a hand-set number in favour of a pool-picked one on a **required** attribute —
  `value: null` is unavailable there. For brownfield the answer is to attach the number.
- Undoing a detach when the branch that performed it is deleted. Detach is permanent, like
  allocation.
- The SDK identifier (P4), several ranges (P1), allocation scope (P3).
- Frontend work: managing ranges, the attach action, and the pool detail view.

---

## Behaviour changes needing changelog entries

1. `value` + `from_pool` stops discarding the provided value.
2. `from_pool` alone on an object holding a non-default untracked number now errors instead of
   silently overwriting it.
3. **Deliberate regression**: allocation no longer skips hand-set values on a unique attribute. This
   shipped as a fix in 1.11 (#10180) and is reverted by P1 in the same release. The upgrade note —
   attach your hand-set numbers — belongs with this slice, because attaching is the replacement.
   Identifying which numbers those are is the operator's job; the note must say so plainly rather
   than implying a tool exists.
4. Pool lineage is derived from the reservation rather than stored as a `source` edge. Displayed
   source is unchanged, but branch diffs no longer show a source change when a number is allocated
   or attached on a branch.
5. A user may now set `source` on a pool-tracked attribute. Doing so hides which pool tracks it
   until the `from_pool` output field lands.
6. Moving an object between pools is a single update.
7. **Upgrade**: the migration removes legacy pool `source` edges, collapses records where more than
   one pool tracked the same attribute, and drops reservations whose object no longer exists. Each
   reports a count.

---

## Dependencies & References

- **Ships with**: P1 (several ranges). This slice consumes P1's effective-space calculator and
  relies on P1's deletion of the hand-set-value scan (FR-011).
- **Related ADR**: `dev/adr/0010-generated-user-facing-schema-contract.md` — the two new query
  fields are part of the schema we publish and generate from.
- **Related specs**: `dev/specs/ifc-1869-from-pool-prefix-mask`,
  `dev/specs/infp-431-ipam-closest-prefix`.
- **Handoff to P1**: FR-028a is an invariant P1's read-query rewrite must preserve. Today's
  distinct-counting is an emergent property of two Python set comprehensions in the utilization
  getter — code P1 replaces. Counting rows instead of distinct values would let utilization exceed
  100%.
