# Feature Specification: Number Pools — Several Weighted Ranges per Pool

**Feature Branch**: `pmi-number-pools-part1`

**Created**: 2026-09-08

**Status**: Draft

**Input**: Number Pools PRD revision "simple as possible" (Confluence 870514689, revising INFP-308), slice **P1** only — several weighted ranges per pool with schema-declared ranges. Derived from `POOL-RANGES-PRD.md`.

## Scope

This specification covers **P1 only**: a number pool draws from several weighted numeric ranges instead of a single span, ranges are declarable in schema, and pool size / utilization / allocation order / fullness are all computed from one consistent effective-space calculation. P2 (provide / attach / detach hand-set numbers, provenance, record lifecycle) and P3 (scoped allocation) are separate parts and are out of scope here, except where a shared mechanism must be built so that P1 is correct on its own.

### P1 / P2 decoupling decision

The source PRD ships P1 and P2 together because it **deletes** the hand-set-value scan (`NumberPoolGetTaken` and the `attribute.unique` scan inside allocation) in P1, and only P2's attachment mechanism restores skipping of hand-set numbers — so P1 alone would regress. This spec **does not delete that scan in P1**. Instead P1 **updates** the existing scan to operate over the new range set, preserving today's "skip hand-set values on a unique attribute" behaviour within P1. This makes P1 self-consistent and **independently releasable** without P2. The eventual deletion of the scan (the deliberate #10180 revert) moves to P2, where the attach mechanism replaces it. FR-011 below reflects this.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Allocate across several ranges with gaps (Priority: P1)

An operator configures a number pool that draws from more than one numeric range (for example VLAN IDs 100–200 and 205–300, skipping the reserved 201–204 gap). As objects consume numbers, allocation fills the first range, then falls through the gap to the next range without the pool ever reporting itself full prematurely or dividing by zero.

**Why this priority**: This is the core capability of the slice — a pool that models real-world numbering plans, which are almost never one contiguous span. Without it the feature delivers nothing.

**Independent Test**: Create a pool with two ranges separated by a gap, exhaust the first range, request the next number, and confirm the first free number of the second range is returned and the pool is not reported full.

**Acceptance Scenarios**:

1. **Given** a pool with range 100–200 fully allocated and range 205–300 untouched, **When** the next number is allocated, **Then** 205 is returned.
2. **Given** a pool with ranges 100–200 and 205–300, all of both ranges allocated, **When** the next number is requested, **Then** allocation reports the pool full (raises the pool-exhausted error), and only then.
3. **Given** a pool with two ranges each carrying an allocation weight, **When** numbers are allocated repeatedly, **Then** the range chosen for each allocation respects the configured weights, and within the chosen range the lowest free number is returned.

---

### User Story 2 - Edit ranges without ever being refused, including removing a range that holds numbers (Priority: P1)

An operator adds, removes, or edits the ranges on an existing pool as their numbering plan evolves. A range edit is never refused by the pool, even when a range being removed still contains numbers that objects currently hold. Numbers left outside all ranges are retained and remembered but are neither handed out again nor counted as available; if a covering range is added back, those numbers count as in use again.

**Why this priority**: Numbering plans change over time. Refusing a range removal because a number inside it is in use would trap operators; silently dropping the record would corrupt the pool's accounting. This behaviour is what makes ranges safe to edit in production.

**Independent Test**: Allocate a number inside a range, remove that range, confirm the removal succeeds, the number is no longer allocatable and no longer counts toward utilization but remains associated with the pool, then re-add a covering range and confirm the number counts as in use again.

**Acceptance Scenarios**:

1. **Given** ranges 100–200 and 205–300 with 250 currently allocated, **When** range 205–300 is removed, **Then** the removal succeeds, 250 stays associated with the pool, utilization reports 101 of 101, and 250 is never handed out.
2. **Given** the state after scenario 1, **When** range 205–300 is re-added, **Then** 250 counts as in use again and utilization reflects it.
3. **Given** a pool with any ranges, **When** an operator removes the last remaining range, **Then** the edit succeeds, the pool is legal with zero ranges, utilization reports 0 of 0 (0%), and any allocation request reports the pool full rather than erroring on a division by zero.

---

### User Story 3 - Consistent size, utilization, and fullness across the pool's whole surface (Priority: P1)

An operator inspecting a pool sees a single, consistent answer for how big the pool is, how full it is, and whether it can still allocate — regardless of which read path produced it. That answer honours the attribute's own value domain: its minimum, maximum, and excluded values are all reflected in the pool's effective space, and only the excluded values that actually fall inside a range are subtracted.

**Why this priority**: Today the pool computes its exclusion and size arithmetic in several places that disagree, which produces inconsistent utilization figures and a divide-by-zero crash in a known edge case. A pool operators cannot trust the numbers of is not shippable.

**Independent Test**: Configure a pool whose ranges partly overlap the attribute's min/max and excluded values, read size and utilization, and confirm they equal the effective space (ranges intersected with the attribute domain, minus only the intersecting exclusions), consistently across size, utilization, allocation order, and fullness.

**Acceptance Scenarios**:

1. **Given** a pool whose attribute defines a minimum and maximum, **When** size and utilization are read, **Then** they reflect only the portion of the ranges lying within `[min_value, max_value]`.
2. **Given** a pool whose attribute defines excluded values, some inside a range and some outside every range, **When** size is read, **Then** only the excluded values that fall inside a range reduce the size; those outside every range do not.
3. **Given** a pool whose attribute's excluded values lie entirely outside the pool's ranges, **When** size and utilization are read, **Then** the read succeeds and returns a correct non-zero size (no divide-by-zero failure).

---

### Edge Cases

- **Zero ranges**: A pool with no ranges (for example after the last range is removed) is legal. Utilization is 0 of 0, reported as 0%. Allocation reports the pool full (raises the pool-exhausted error) rather than dividing by zero.
- **Range clamped to empty by the attribute domain**: A range that, after intersecting with `[min_value, max_value]` and removing intersecting exclusions, contains no allocatable value counts as exhausted for fullness purposes.
- **Number held outside every range** (record retention): A held number that falls outside all current effective ranges is retained, hidden from allocation, and excluded from utilization until a covering range is re-added or the number is explicitly unlinked.
- **Excluded values entirely outside the ranges**: Do not reduce size and must not cause a divide-by-zero.
- **Single-range shorthand round-trip**: A pool written with the single start/end shorthand and holding exactly one range reads that value back through the shorthand; a pool holding more than one range reads the shorthand fields as null.
- **Both spellings supplied**: An object that sets both the single start/end shorthand and an explicit list of ranges is refused, and the conflict is detectable (the shorthand fields must have no implicit default that would mask the conflict).
- **Overlapping ranges within one pool**: Refused (intra-pool ranges must not overlap).
- **Two pools over the same kind and attribute with overlapping ranges**: Allowed; nothing pool-side arbitrates a collision between two pools — only a uniqueness constraint on the attribute would.
- **Weight change on a partially drained pool**: Deterministic — the newly heaviest range is drawn from next, at its lowest free value.
- **Existing pools after upgrade**: Every pool that exists today keeps working unchanged, now modelled as a single range covering its former span.

## Requirements *(mandatory)*

Functional-requirement numbers follow the Confluence PRD. Requirements from the PRD not listed here stand as written there; P2- and P3-only requirements are out of scope for this slice.

### Ranges

- **FR-001**: A number pool MUST be able to draw from several numeric ranges, each with a start, an end, and an allocation weight, all belonging to exactly one pool.
- **FR-002**: Range edits (add, remove, change) MUST never be refused by the pool, including removing a range that still holds numbers objects currently hold.
- **FR-002a**: A held number whose value falls outside every effective range MUST be retained and stay associated with the pool: invisible to allocation, excluded from utilization, removed only by explicit unlink or re-link. Re-adding a covering range MUST make the number count as in use again.
- **FR-003**: Allocation MUST return the lowest free number available, falling through gaps between ranges and across ranges, honouring range weights when choosing which range to draw from.
- **FR-004**: Ranges within a single pool MUST NOT overlap. Two different pools over the same kind and attribute MAY overlap; the pool MUST NOT arbitrate a collision between two pools — only a uniqueness constraint on the attribute refuses such a collision, the same rule as for a hand-set duplicate.
- **FR-005**: Existing pools MUST continue to function after upgrade, each represented as a single range covering its previous span (weight absent, counting as zero).
- **FR-005a**: The single start/end range fields MUST remain available as an optional write-shorthand that creates or replaces one range. On read they MUST return a value only when the pool holds exactly one range, and null otherwise.
- **FR-006**: Pool size and utilization MUST be computed from the pool's **effective space**: the union of the ranges, intersected with the attribute's `[min_value, max_value]`, minus the excluded values that intersect that space. Excluded values that fall outside every range MUST NOT be subtracted. Sensitivity of utilization to `min_value` / `max_value` is intended and is a change from prior behaviour, which ignored them.
- **FR-007**: A pool MUST be reported full only when every effective range is exhausted. A range that clamps to empty (after intersecting the attribute domain and removing intersecting exclusions) counts as exhausted.
- **FR-008**: Size, utilization, allocation order, and fullness MUST all derive from the same single effective-space calculation, producing consistent answers across every read path. This calculation MUST NOT fail (for example by dividing by zero) when the attribute's excluded values lie entirely outside the pool's ranges.

### What a pool tracks (P1 portion of the record boundary)

- **FR-011**: Within P1, the mechanism that skips hand-set values on a unique attribute MUST continue to work — updated to operate over the new range set rather than a single span. **P1 does NOT delete this scan.** (The source PRD deletes it in P1 and relies on P2 to restore skipping; this slice instead keeps and updates it so P1 is independently releasable. The deletion — the deliberate revert of #10180 — is deferred to P2, where attachment replaces it. See *Scope → P1 / P2 decoupling decision*.)

### Pools the schema creates

- **FR-039**: A schema-created pool's ranges MUST be validated against the attribute's own value domain, not against the pool's held records: a schema change that would leave values objects currently hold outside the declared ranges MUST be refused, and the offending objects MUST be identified. The asymmetry with FR-002 (user range edits never refuse; schema range edits can) is intended: a value must sit inside the attribute's domain, whereas a pool's ranges only decide where allocation draws from.
- **FR-041**: The single start/end fields in the schema-side pool parameters MUST default to "unset" rather than the whole numeric span, so that supplying both the single shorthand and an explicit list of ranges is detectable and refused. (This is one parameter-contract change; the scope-parameter addition from P3 rides the same contract change but is out of scope for this slice.)

### Compatibility and lifecycle

- **FR-042**: Upgrading MUST NOT require operator action for pools to keep allocating: the range data migration converts each existing pool to a single-range pool automatically.
- **FR-043 (referenced, not built here)**: Held-number lifecycle across branch and object deletion is owned by P2; P1 relies on the existing liveness behaviour and does not change it.

### Key Entities *(include if feature involves data)*

- **Number pool**: A source of numbers for a specific attribute on a specific kind. Now owns a set of ranges rather than a single span. Retains the single start/end fields as an optional shorthand for the one-range case.
- **Number pool range**: One numeric interval a pool draws from — a start, an end, and an allocation weight. Belongs to exactly one pool. Branch-agnostic (the same on every branch).
- **Effective space**: The derived set of allocatable numbers for a pool — the union of its ranges intersected with the attribute's min/max, minus the excluded values that intersect it. Not stored; computed. The single source for size, utilization, allocation order, and fullness.
- **Held number record**: The association between a pool and a number an object holds. Retained even when the number falls outside all current ranges (FR-002a). Lifecycle semantics beyond retention are owned by P2.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can define a pool with two or more ranges and allocation correctly falls through gaps — the first free number of the next range is returned once earlier ranges are exhausted — in 100% of allocation requests until the whole effective space is consumed.
- **SC-002**: Removing a range that still holds numbers succeeds in 100% of cases, the held numbers remain associated with the pool, are never re-allocated, and are excluded from utilization until a covering range returns.
- **SC-003**: Size and utilization returned by every read path agree with the effective-space definition for the same pool configuration — no read path disagrees with another.
- **SC-004**: A pool whose attribute's excluded values lie entirely outside its ranges returns a correct size and utilization with zero failures (the prior divide-by-zero case no longer occurs).
- **SC-005**: 100% of pools that exist before the upgrade continue to allocate afterward with no operator action, each behaving as a single-range pool covering its former span.
- **SC-006**: A pool with zero ranges reports 0% utilization and, on an allocation request, reports itself full rather than failing with an internal error.
- **SC-007**: Reading the single start/end shorthand returns the range bounds for a one-range pool and null for a multi-range pool, in 100% of reads.

## Assumptions

- **"First part" = the P1 (ranges) slice.** The branch is named `pmi-number-pools-part1`; P2 and P3 are separate parts delivered on their own branches.
- **P1 is made independently releasable** by updating rather than deleting the hand-set-value scan (FR-011), per the maintainer's direction during specification. This diverges deliberately from the source PRD, which couples P1 and P2 through that deletion.
- The attribute value domain (`min_value`, `max_value`, `excluded_values`) and uniqueness constraints remain the authority on whether a *value* is valid; the pool only decides where allocation *draws from* and only refuses a provided number outside its own ranges. (P1 builds the effective-space arithmetic that this rests on; the provide/attach surface is P2.)
- The number pool range is a new core kind reusing the existing weighted-pool-resource generic; it is the first core kind to do so.
- Range records and the pool's held-number records are branch-agnostic (identical on every branch), consistent with today's behaviour.
- Gap detection within a range set stays in the database read path; the effective-space arithmetic in application code governs size, fullness, and allocation order.
- The single parameter-contract change that makes the shorthand fields default to "unset" (FR-041) is coordinated with the P3 scope-parameter addition as one schema-contract review, even though P3 is out of scope for this slice.
- Existing frontend and API consumers of `start_range` / `end_range` tolerate a null value on those fields; the nullable-read change (SC-007) lands in P1 even though the frontend work is deferred, so the changelog upgrade note must address API consumers, not only pool authors.
- Range-validity rules (start ≤ end, intra-pool non-overlap per FR-004) are enforced on every write path — both the GraphQL mutation and schema-created pools via `NumberPoolParameters` — not only the interactive mutation.

## Dependencies & Risks

- **Not independently *shippable as the whole feature* — but independently *releasable*.** With FR-011 keeping and updating the scan, releasing P1 without P2 does not regress hand-set-number skipping. This is the explicit divergence from the source PRD's P1/P2 coupling; if FR-011 were instead built as a deletion, P1 could not ship without P2.
- **Deliberate future regression deferred to P2**: the #10180 revert (allocation no longer skipping hand-set values on a unique attribute) and its upgrade note ("attach your hand-set numbers") land with P2, not here.
- **Database change**: a new core kind (number pool range) and a data migration converting every existing pool to a single-range pool. The single start/end fields are kept (not removed) and become nullable on read.
- **Schema contract change**: the ranges relationship is added and the single start/end scalars become nullable on read — one published-schema-contract review, coordinated with the P3 parameter addition.
- **Behaviour changes needing changelog entries (P1 portion)**: utilization becomes sensitive to `min_value` / `max_value` and to which excluded values intersect the ranges; the single start/end fields read as null on a pool with more than one range. (The #10180-revert changelog entry belongs to P2 under this decoupling.)

## Out of Scope (this slice)

- Providing, attaching, or detaching hand-set numbers; provenance on held-number records; the full record-lifecycle test matrix (P2).
- Scoped allocation, allocation scope on the pool or in schema parameters, per-scope utilization (P3).
- Deleting the hand-set-value scan / the #10180 revert (moves to P2 under the decoupling decision).
- SDK caller-supplied identifier (P4).
- Bulk attach and its dedicated mutation (deferred with the frontend).
