# Feature Specification: Inherited-Attribute Migration Fix and Healing Migration

**Feature Branch**: `inherited-attr-migration-ifc-2619`

**Created**: 2026-07-31

**Status**: Draft

**Input**: PRD `inherited-attribute-migration-prd.md` — forward fix for inherited attributes not materializing on pre-existing nodes when a kind newly inherits a generic, plus a one-shot healing migration that repairs already-damaged installs. Related issue [#9284](https://github.com/opsmill/infrahub/issues/9284); Jira IFC-2619.

## Problem Statement

When an operator evolves their schema so that an existing node kind starts inheriting from a generic, the attributes gained through inheritance never materialize on pre-existing nodes. Those nodes read the new attributes back with `id: null` and `is_default: true`, update mutations report success but persist nothing, and attribute filters silently never match. The failure is invisible at schema-load time, easy to trigger through routine schema evolution, and any install that has performed such a change is carrying silent data damage today.

Two coordinated deliverables ship as two pull requests in the same release:

1. **Forward fix** — loading a schema where a kind newly inherits a generic creates real attribute rows on every pre-existing node of that kind (including its profile and template instances), with NumberPool attributes allocated. Schema-migration execution is also made race-free by ordering kind-update migrations before all others.
2. **Healing migration** — a one-shot upgrade-time graph migration repairs installs already damaged: every active node missing a row for a schema-defined attribute gets one backfilled, timestamped retroactively so that existing branches see the repaired data without a rebase. Damage that originated from schema changes made on a branch is repaired in the same pass with branch-scoped checks — no rebase or merge is required anywhere.

After both land, operators can add generics to existing kinds safely, and previously damaged installs are fully repaired by upgrading.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Forward fix: new inheritance creates attribute rows (Priority: P1)

An operator loads a schema version in which an existing kind newly inherits a generic, and all pre-existing nodes of that kind immediately have working inherited attributes — reads return real attribute identities, updates persist, and filters match. Profile and template instances of the kind gain the same attributes (where profiles/templates support them), and inherited NumberPool attributes receive allocated numbers. Simultaneous schema changes (a new generic plus a new inheritor in one load) migrate correctly without racing.

**Why this priority**: This stops new damage from occurring. Every schema evolution that adds a generic to an existing kind currently corrupts data silently; the forward fix is the prerequisite for the healing migration being a one-shot repair rather than a recurring chore.

**Independent Test**: Load a schema v1, create nodes, load a schema v2 where the kind newly inherits a generic, then read/update/filter the inherited attributes on the pre-existing nodes. Deliverable and testable entirely without the healing migration.

**Acceptance Scenarios**:

1. **Given** a loaded schema v1 with nodes created for a kind, **When** schema v2 adds a generic to that kind's `inherit_from` and is loaded, **Then** reading an inherited attribute on a pre-existing node returns a non-null `id`, an update to a non-default value persists across a re-read with `is_default: false`, and an attribute-value filter matches the expected nodes.
2. **Given** a kind with existing profile and template instances, **When** the kind newly inherits a generic, **Then** the profile and template instances gain the same inherited attributes, gated by the same support rules that govern which attributes profiles and templates carry.
3. **Given** a kind that newly inherits a generic defining a NumberPool attribute, **When** the schema is loaded, **Then** every pre-existing node of the kind receives an allocated number drawn from the pool registered against the generic's kind, with no duplicate pools and no duplicate allocations.
4. **Given** a single schema load introducing both a new generic and a new inheritor of it, **When** migrations execute, **Then** kind-update migrations run to completion before any other migration starts, and the result converges to the same state as sequential loads.

---

### User Story 2 - Healing: upgrade repairs damaged installs on the default branch (Priority: P2)

An administrator upgrades an install damaged before the fix existed, and the upgrade backfills every missing attribute row on the default branch without touching healthy data. The migration validates its own result and fails the upgrade loudly if the invariant still does not hold. Running it on healthy data — or running it a second time — performs zero writes.

**Why this priority**: Installs damaged before the forward fix carry silent data damage that no amount of future schema loading repairs. Healing is the only remediation path that does not require operators to identify and fix damaged data by hand.

**Independent Test**: Seed a damaged graph state (active nodes missing rows for schema-defined attributes), run the healing migration, and verify every active (node, schema-defined attribute) pair on the default branch has an active attribute row; rerun and verify zero writes.

**Acceptance Scenarios**:

1. **Given** an install where active nodes are missing rows for schema-defined attributes, **When** the upgrade runs the healing migration, **Then** every active (node, schema attribute) pair on the default branch has an active attribute row valued at the schema default (or a fresh NumberPool allocation), the migration's own validation passes, and a second run performs zero writes.
2. **Given** an undamaged install, **When** the healing migration runs, **Then** it performs zero writes.
3. **Given** a healing run whose validation finds the invariant still violated, **When** the migration completes, **Then** the upgrade fails loudly with actionable, per-kind error detail.
4. **Given** a pre-existing branch created before the upgrade, **When** default-branch data is healed with retroactive timestamps, **Then** the branch reads the healed default-backed attributes correctly without being rebased.

---

### User Story 3 - Healing: branch-side repair (Priority: P3)

A branch user whose branch introduced the damaging schema change gets repaired data from the same upgrade, without rebasing or merging. The healing migration repairs branch-originated damage on all existing branches during the same upgrade pass, using branch-scoped detection that considers only data changed on the branch.

**Why this priority**: Branch-originated damage is rarer than default-branch damage but forces the most disruptive manual remediation (organization-wide rebases). Same-pass repair removes that cost.

**Independent Test**: Seed a non-default branch where a kind gained inheritance on-branch before the fix, run the healing migration, and verify the branch-scoped pass creates the missing branch-level rows.

**Acceptance Scenarios**:

1. **Given** a non-default branch where a kind gained inheritance on-branch before the fix, **When** the upgrade runs the healing migration, **Then** the branch-scoped pass creates the missing branch-level rows and inherited attributes read back with non-null `id` on the branch.

---

### Edge Cases

- **Tombstoned attribute edges**: a node whose only row for a schema-defined attribute is deleted (the remove-then-re-add-`inherit_from` shape) counts as damaged; the healed row's timestamp must not resurrect history before the tombstone.
- **Deleted nodes**: skipped entirely — only nodes active at migration time are examined.
- **Mandatory attribute with no default gained via inheritance**: healed (and forward-migrated) as a null-valued row — visible and user-fixable rather than absent. No special-casing.
- **Generic changed after inheritance began**: attributes the generic gained after a kind inherited it were already handled by the generic-scoped path; per-attribute timestamp derivation from schema vertices distinguishes these from genuinely missing rows.
- **Simultaneous new-generic + new-inheritor in one schema load**: phase ordering guarantees the kind update completes before attribute-adds run; idempotency guards make the overlap converge.
- **Partial failure mid-heal**: all repair queries are idempotent; a rerun (or the retry policy) completes the remainder, and validation gates success.
- **Concurrent NumberPool usage across branches**: healing allocates at run time via the reservation-aware allocation path; the allocation path's branch- and time-scoping is verified during implementation before run-time allocations are trusted (see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Loading a schema in which a kind newly inherits a generic MUST create attribute rows for the newly-inherited attributes on all pre-existing nodes of that kind, including profile and template instances where the attribute supports them.
- **FR-002**: The forward fix MUST preserve the existing protection against duplicate rows when a generic gains an attribute (the generic-scoped migration remains the sole owner of that case).
- **FR-003**: Schema-migration execution MUST run all kind-update migrations to completion before any other migration starts, and MUST skip the second phase when the first phase reports errors.
- **FR-004**: Inherited NumberPool attributes MUST receive allocated numbers on pre-existing nodes, drawing from the pool registered against the generic's kind, without creating duplicate pools or duplicate allocations.
- **FR-005**: The healing migration MUST create an active attribute row for every (active node, schema-defined attribute) pair lacking one, on the default branch, regardless of how the row went missing.
- **FR-006**: Healed rows (other than NumberPool) MUST carry the schema default value and a retroactive timestamp derived per attribute from the schema graph — the later of "the kind began inheriting the generic" and "the generic gained the attribute" — and MUST never predate an existing tombstone for the same attribute.
- **FR-007**: Healed NumberPool attribute rows MUST be created at migration-run time with a pool allocation that cannot collide with any existing reservation.
- **FR-008**: The healing migration MUST be idempotent and a strict no-op on healthy data.
- **FR-009**: The healing migration MUST repair branch-originated damage on all existing branches during the same upgrade pass, using branch-scoped detection that considers only data changed on the branch.
- **FR-010**: The healing migration MUST validate the repaired invariant after execution and fail the upgrade with actionable errors when validation does not pass.
- **FR-011**: Detection and repair MUST operate as batched per-kind queries; per-node iteration is permitted only for NumberPool allocation.
- **FR-012**: The migration ordering rule (kind updates before everything else) MUST be expressed as a pure, unit-testable function, so that the two-phase behavior cannot regress unnoticed.
- **FR-013**: After the fix, attribute reads, updates, and filters MUST behave identically for inherited and locally-defined attributes — inheritance remains an implementation detail of the schema.

### Key Entities

- **Node kind / Generic (schema)**: the trigger — a kind's `inherit_from` gaining a generic. The schema's own graph representation (the generic's schema node and its attribute vertices) becomes the source of truth for retroactive timestamps.
- **Attribute row (graph vertex)**: the missing artifact; the invariant restored is "every active node has an active attribute row for every attribute its schema defines."
- **Schema migration**: the forward-fix surface — the kind-update migration gains responsibility for newly-inherited attributes; the attribute-add migration gains a controlled bypass of its inherited-attribute guard; the migration batch gains two-phase ordering.
- **Graph migration** *(new instance, existing framework)*: the healing migration — a one-shot upgrade-time migration with free-form orchestration that repairs the default branch and every existing branch in a single pass — flagged for governance review as a database migration.
- **NumberPool**: pool-backed inherited attributes require allocation, not defaults; healing allocates at run time to protect pool uniqueness.
- **Profile / Template instances**: concrete instances that must gain the same rows, gated by the same support predicates the schema generator uses.
- **Branch**: retroactive timestamps make default-branch repairs visible to pre-existing branches; branch-originated damage is repaired by the same upgrade pass via branch-scoped checks — no rebase or merge required.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After upgrade, an audit of the default branch finds zero active (node, schema-defined attribute) pairs without an active attribute row — enforced automatically as the healing migration's self-validation.
- **SC-002**: The #9284 reproduction (the issue's two schema files) passes end-to-end on a fresh install after PR 1, and on a pre-damaged install upgraded through PR 2: reads return non-null `id`, updates persist, filters match.
- **SC-003**: Running the healing migration twice produces zero writes on the second run; running it on an undamaged install produces zero writes on the first run.
- **SC-004**: A pre-existing branch (branched before upgrade) reads healed default-backed attributes correctly without being rebased.

## Assumptions

- No legitimately row-less attributes exist: every attribute a node's schema defines is supposed to have a row, so invariant repair is safe as a blanket rule.
- Writing retroactively-timestamped rows into default-branch history is acceptable and intended: time-travel reads and open-branch views will show rows as having always existed; this is the mechanism for branch visibility without rebase.
- Post-upgrade merges of damaged branches run the fixed forward-path migrations, providing a backstop on the default branch for any branch-originated damage the branch-scoped pass might miss.
- Both PRs land in the same release, so no install experiences the intermediate state (new damage stopped, old damage present).
- **NumberPool allocation scoping (resolved from PRD open question)**: the reservation-aware allocation path is assumed suitable for run-time healing allocations, subject to a mandatory implementation-time verification that its uniqueness check is correctly branch- and time-scoped before run-time allocations during healing are trusted (FR-007). If verification fails, the allocation path is fixed or wrapped before healing ships.
- **Self-validation scope (resolved from PRD open question)**: the healing migration's self-validation re-runs the batched per-kind damage-detection query and asserts zero remaining damaged pairs. Because detection is already batched per kind and must run anyway, the validation cost is one additional detection pass. If profiling during implementation shows this is prohibitive on very large installs, the fallback is scoping validation to the kinds touched by the repair — a plan-level decision that does not change the invariant being validated.

## Out of Scope

- Refactoring the migration-within-a-migration pattern (follow-up issue).
- Stale template-generic labels on existing template vertices — a pre-existing gap distinct from #9284 (follow-up issue).
- Continuous or scheduled invariant repair — healing is a one-shot upgrade migration; the forward fix prevents recurrence.
- API/interface surface: no GraphQL, REST, or SDK changes; no frontend changes; no CLI changes (the existing upgrade command picks up the new migration).

## Governance Gates

- [x] Database schema or migration change — both PRs: schema-migration behavior change plus a new numbered graph migration that every install executes at upgrade. **Requires governance review.**
- [ ] GraphQL schema modification — none.
- [ ] New dependency — none.
- [ ] CI/CD workflow change — none.
- [ ] Authentication / authorization change — none.

## Further Notes

- Related issue: [#9284](https://github.com/opsmill/infrahub/issues/9284); Jira: IFC-2619. Prior related work: the duplicate-row protection introduced by #7407, which the forward fix deliberately preserves.
- Source PRD: `inherited-attribute-migration-prd.md`, itself produced from a grilling session over `inherited-attribute-migration-plan.md` (the forward-fix implementation plan).
