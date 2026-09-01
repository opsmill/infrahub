# Implementation Plan: Stop emitting value-intrinsic constraint validators on data-only diffs

**Branch**: `skip-value-intrinsic-validators-ifc-3096` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `dev/specs/ifc-3096-skip-value-intrinsic-validators/spec.md` · Jira [IFC-3096](https://opsmill.atlassian.net/browse/IFC-3096)

## Summary

Constraint validation on a data-only branch operation currently schedules checks that a data change is structurally incapable of violating, so the cost of rebasing, merging, or validating a branch scales with total database population rather than with the size of the change.

Eight constraint checker classes declare `triggered_by_data_change = False`, removing fourteen constraint identifiers from the data-diff producer's output. Those constraints continue to run at unrestricted scope whenever the guarded schema property genuinely changes, which the schema-diff producer already owns via a three-way comparison spanning the common ancestor and both branches. Cross-node constraints — uniqueness, cardinality, hierarchy, common parent — are untouched.

The mechanism already exists and is already honoured at both of the determiner's decision points; this feature changes declarations, not logic. The substantive work beyond the eight one-line edits is the test that stops the classification drifting, and the knowledge page that records why each entry is classified as it is.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: None added. Pydantic 2.12 (schema property metadata), Neo4j driver 6.2 (via the checkers being scheduled, not modified)

**Storage**: Neo4j 2026.05 — **no schema change, no migration, no new persisted state**

**Testing**: pytest 9.0 — unit (`backend/tests/unit/`) and component (`backend/tests/component/`)

**Target Platform**: Linux server (backend)

**Project Type**: Backend-only change within a graph-based infrastructure data platform

**Performance Goals**: For a data-only diff, scheduled value-intrinsic constraints drop to zero regardless of population size; total scheduled constraints fall by ~3K for K touched (kind, field) pairs (SC-001, SC-002). Wall-clock improvement measured and reported, not gated (SC-004)

**Constraints**: No user-visible behaviour change — same operations, same outcomes, faster. No loss of any constraint a merge can genuinely violate (SC-003)

**Scale/Scope**: 8 class-attribute edits across 8 files, 1 registry consistency fix, 1 new unit test, 1 extended component test file (6 edit sites), 1 new knowledge page, 1 changelog fragment

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design. Both passes recorded.*

| Principle | Assessment | Verdict |
|---|---|---|
| **I. Schema-Driven Integrity** | The change rests on schema validation at write time being the enforcement point for value-intrinsic rules. FR-005 requires each of the eight to have its enforcement site **traced and named** in the knowledge page, and research R8 makes an untraceable enforcement point a reason to drop that family from the flip list. The reliance is documented, not assumed. | ✅ Pass |
| **II. Branch-Safe by Default** | The load-bearing principle. Verified in research R3 that the schema-diff producer covers property changes originating on *either* branch (`get_3ways_diff_schema` sums ancestor→source and ancestor→destination), and that the rebase-path hash gate does not become a correctness gap. Merge behaviour is tested explicitly (FR-002, FR-003) rather than inferred. | ✅ Pass |
| **III. Type Safety & Explicit Contracts** | One typed `bool` class attribute per checker, on an existing typed interface. The registry key normalisation (R4) makes all 29 keys uniformly `str`, removing a mixed key type. No untyped dicts, no new API contract. | ✅ Pass |
| **IV. Test Discipline** | Unit tier for the classification pinning test (pure dict, no DB — cheapest tier per `.agents/rules/testing-python.md`); component tier for the behaviour, extending the established pattern in `test_determiner.py`. No mocks — the determiner component test already uses a hand-written `_NoDependentsResolver` adapter. **No E2E**: justified below. | ✅ Pass, with justification |
| **V. Query Performance & Efficiency** | The entire purpose. Removes work whose cost scales with population rather than with change size. No query is modified; queries simply stop being scheduled. | ✅ Pass |
| **VI. Security & Input Boundaries** | No boundary touched. No user input, no Cypher change, no authz change. | ✅ Not applicable |
| **VII. Simplicity & Maintainability** | One class attribute per checker, reusing decision points that already exist. No new abstraction, no new component, no new configuration, no new dependency. The rejected alternative (a new determiner-side property-comparison gate) is the more complex option and was rejected on correctness grounds as well as simplicity — see research R1. | ✅ Pass |

### E2E exemption (Principle IV)

Principle IV requires E2E tests "for all user-facing features". This feature has **no user-facing surface**: no API change, no frontend change, no CLI change, no change to which operations succeed or what they report. The same operations produce the same outcomes, faster. Adding an E2E test would assert behaviour this change does not alter, and would not detect the failure mode that matters (a constraint silently not running), which the component tests target directly.

Recorded as a deliberate, justified exemption rather than an omission.

### Governance gates (`AGENTS.md` "Ask First")

| Gate | Crossed? |
|---|---|
| Database schema or migration change | No |
| GraphQL schema modification | No |
| New dependency | No |
| CI/CD workflow change | No |
| Authentication / authorization change | No |

None crossed. A `housekeeping` changelog fragment is required.

### Post-Phase-1 re-evaluation

Re-checked after `research.md`, `data-model.md` and `quickstart.md` were written. No new violations. Two findings emerged during Phase 0 that *strengthen* the assessment rather than weakening it:

- Principle II: the rebase hash-gate question, carried out of the spec phase as a potential blocker, was settled as **not a gap** (R3), with the residual recorded as a follow-up rather than absorbed silently.
- Principle VII: the registry key normalisation (R4) was assessed against the "no drive-by refactors" rule in `.agents/rules/backend-component-design.md` and judged in-scope because the dict is the direct subject of the FR-004 deliverable — explicitly not a licence to touch anything else in that module.

No entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3096-skip-value-intrinsic-validators/
├── spec.md              # Phase: specify
├── checklists/
│   └── requirements.md  # Phase: specify — spec quality gate
├── plan.md              # This file
├── research.md          # Phase 0 — R1..R8, both open questions settled
├── data-model.md        # Phase 1 — in-memory model + the classification
├── quickstart.md        # Phase 1 — validation guide
└── tasks.md             # Phase 2 — NOT created by /speckit-plan
```

**No `contracts/` directory.** The feature exposes no external interface — no REST endpoint, no GraphQL field, no CLI command, no SDK surface. Per the plan workflow's guidance, contract generation is skipped for purely internal changes.

### Source Code (repository root)

```text
backend/
├── infrahub/core/validators/
│   ├── __init__.py                  # MODIFY: normalise 2 registry keys to .value
│   ├── interface.py                 # UNCHANGED: default stays True (FR-006)
│   ├── determiner.py                # UNCHANGED: already honours the declaration
│   ├── constraint_merge.py          # UNCHANGED: union, unrestricted scope wins
│   ├── attribute/
│   │   ├── kind.py                  # MODIFY: AttributeKindChecker
│   │   ├── optional.py              # MODIFY: AttributeOptionalChecker
│   │   ├── regex.py                 # MODIFY: AttributeRegexChecker
│   │   ├── length.py                # MODIFY: AttributeLengthChecker
│   │   ├── enum.py                  # MODIFY: AttributeEnumChecker
│   │   ├── choices.py               # MODIFY: AttributeChoicesChecker
│   │   ├── min_max.py               # MODIFY: AttributeNumberChecker
│   │   ├── unique.py                # UNCHANGED: cross-node, keeps its trigger
│   │   └── number_pool.py           # UNCHANGED: out of scope by decision
│   └── relationship/
│       └── peer.py                  # MODIFY: RelationshipPeerChecker only,
│                                    #         NOT RelationshipPeerParentChecker
└── tests/
    ├── unit/core/validators/
    │   └── test_constraint_classification.py   # NEW: FR-004 pinning test
    └── component/core/constraint_validators/
        └── test_determiner.py                  # MODIFY: 6 edit sites + new tests

dev/knowledge/backend/
└── constraint-validation.md         # NEW: FR-005

changelog/
└── +<slug>.housekeeping.md          # NEW
```

**Structure Decision**: Backend-only, following the existing `backend/infrahub/core/validators/` layout. Test files mirror source structure per Principle IV — the new unit test sits at `backend/tests/unit/core/validators/` mirroring `backend/infrahub/core/validators/`.

**Two files in the modify list carry a trap**, both flagged because a careless edit silently over-reaches:

- `relationship/peer.py` defines **two** checkers. `RelationshipPeerChecker` flips; `RelationshipPeerParentChecker` (guarding `relationship.common_parent.update`) is cross-node and must keep its data trigger.
- `attribute/length.py` and `attribute/min_max.py` are each registered under **multiple** identifiers, so one class attribute moves four and three identifiers respectively. Intended — see research R2.

## Implementation Approach

Ordered so that each step is independently verifiable and the safety property is proven before the optimisation is trusted.

### Step 1 — Pinning test first, against current behaviour

Write `test_constraint_classification.py` asserting full dict equality over all 29 identifiers with **today's** values (27 `True`, 2 `False`). It passes immediately. This establishes the baseline and proves the test is wired correctly before it is used to police a change.

### Step 2 — Trace the write-time enforcement points

Before flipping anything, confirm each of the eight families has a universal write-time enforcement site (research R8). This is the evidence for the classification, and Principle I depends on it. A family whose enforcement cannot be confirmed drops out of the flip list and the finding is recorded — the plan must not assume all eight survive tracing.

### Step 3 — Flip the eight declarations

One class attribute per checker. Update the pinning test's expected literal in the same commit — the two are a single logical change, and a pinning test updated in a separate commit is a pinning test that briefly did not pin.

### Step 4 — Update the six determiner test sites

Per research R5. Existing expected sets shrink; the suite must be green before new assertions are added.

### Step 5 — Add the intentional assertions

- A data-only-diff test naming the exclusion explicitly (FR-001) and asserting every cross-node constraint survives (FR-003), rather than relying on the shrunken sets from Step 4 to imply it by omission.
- A test that a genuine guarded-property change still yields the constraint **at unrestricted scope from the schema-diff producer** (FR-002). Assert the scope, not merely presence — presence alone would pass if the data-diff producer supplied it, which is the opposite of the requirement.

### Step 6 — Registry key normalisation

Two keys to `.value`. Behaviour-preserving under `StrEnum` (verified, R4). Kept as its own step so it is separable in review.

### Step 7 — Knowledge page and changelog

`dev/knowledge/backend/constraint-validation.md` (FR-005) carrying the two producers and their three differing gates, the determiner's decision points, the merger's union rule, and the classification with each entry's justification including the traced enforcement sites from Step 2. Plus a `housekeeping` changelog fragment.

### Step 8 — Measure

Before/after wall-clock for a data-only rebase and the scheduled-constraint counts, for the PR description (SC-004).

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| A value-intrinsic family has no universal write-time enforcement point, making its classification unsound | Low | Step 2 traces each one before flipping; an untraceable family drops out of the list rather than shipping on an assumption |
| Flipping a multi-identifier checker moves an identifier that should have kept its trigger | Low | The pinning test's full-dict equality makes every moved identifier visible in the diff of the expected literal |
| `RelationshipPeerParentChecker` flipped along with `RelationshipPeerChecker` (same file) | Medium | Called out explicitly in the structure section and covered by the pinning test — `relationship.common_parent.update` must stay `True` |
| The rebase hash-gate fail-open loses coverage that data-path scheduling incidentally provided | Low | Settled in R3: the cover was partial and coincidental, and the `None`-hash state is a startup-ordering edge. Follow-up ticket recommended, not a blocker |
| A reviewer cannot check the classification against its justification | Low | The expected literal in the pinning test and the knowledge page table are both explicit, reviewable lists — this is User Story 3's requirement |

## Follow-ups (not in scope)

1. **Align the rebase schema-diff gate with merge's.** Rebase uses the cached `Branch.schema_differs_from_default_branch`; merge uses the freshly-recomputed `MergeSchemaAnalyzer.has_schema_changes()`, with a code comment stating the choice is deliberate. The cached-hash form fails open when a schema hash is absent. Recommend rebase adopt the merge form. New ticket.
2. **Attribute uniqueness scheduling cost.** Scheduled for every attribute in a diff because its schema property defaults to `false` rather than being absent. The check exits cheaply, but each scheduling round-trips the validation dispatch. Folded into IFC-2797.
3. **Node-scope the remaining data-path constraints.** IFC-2797, whose scope this feature narrows.
4. **Attribute number pool range classification.** Deliberately untraced here; enforcement lives in pool allocation. Keeps its data trigger.

## Complexity Tracking

No constitution violations require justification. The single deviation — the E2E exemption under Principle IV — is documented in the Constitution Check above with its rationale, and is an exemption from a general rule rather than an unjustified complexity.
