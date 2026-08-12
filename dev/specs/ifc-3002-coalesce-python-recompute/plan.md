# Implementation Plan: Coalesce Python transform computed attributes on merge and rebase

**Branch**: `coalesce-python-recompute-ifc-3002` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/ifc-3002-coalesce-python-recompute/spec.md`

**Revision**: second pass. The first pass was rejected by [critiques/critique-20260811.md](./critiques/critique-20260811.md). Two of its decisions were wrong and are corrected below; the corrections are called out inline so the reasoning is not lost.

## Summary

Add Python transform computed attributes as a fourth family of the coalesced merge and rebase recompute, so the background work after a merge scales with the number of derived values that changed rather than with the number of changed nodes.

The pipeline gets one new step. The existing builder stays pure and synchronous: it derives which attribute-and-kind pairs a change set could affect, from the schema alone, without filtering. A new injected collaborator then narrows that result using data only the database has, and hands the same value object onward to the existing planner and submitter. Both axes flow through it.

**Correction from the first pass.** That draft resolved only the reader axis and took a schema-only over-approximation on the owner axis. That was wrong: today's owner automation already filters on the transform's read fields, so dropping the filter refreshes *more* nodes than today and makes merges slower on the common shape where a merge touches fields no transform reads. It violated the spec's own FR-005. Both axes need the read-field filter, both need the same lookup, so both belong in the same collaborator. This turned out to simplify the design rather than complicate it: one collaborator, one round of I/O, one place that owns the widen-on-failure policy.

Suppression comes last, and behind a switch. Until the coalesced pass covers Python, the per-node triggers are the only thing keeping the values correct.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: Prefect (task orchestration and event automations), Pydantic 2.12, `infrahub-sdk` (the client used for the lookups), FastAPI 0.131

**Storage**: Neo4j 2026.05 via driver 6.2. No schema change, no migration.

**Testing**: pytest 9.0. Unit for the pure builder and the resolver's failure table. Component with testcontainers for the deleted-peer case, the schema-merge overlap and the end-to-end submission shape. Two `integration_docker` tests: the cross-family chain, and a flow-run count assertion that the origin filter actually suppresses.

**Target Platform**: Linux server, distributed stack (API server plus task worker plus Prefect).

**Project Type**: Backend service. No frontend, SDK or documentation-site change.

**Performance Goals**: job count per pair bounded by the submission chunk limit rather than by the changed-node count (SC-001). Trailing window at 1000 changed nodes reduced by at least 90% against a measured baseline (SC-002). Transform execution count no higher than today (SC-004).

**Constraints**: never under-recompute. A bounded number of lookups per pass, independent of the changed-node count. No unbounded work while the global merge lock is held. No public contract change: no schema, no GraphQL, no REST, no new dependency. One new feature switch.

**Scale/Scope**: synthetic datasets at 100, 1000 and 2000 changed nodes. Roughly 10 production files touched, plus the restoration of a timing harness from an unmerged branch.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1. Both passes clean.*

| Principle | Assessment | Verdict |
|---|---|---|
| **I. Schema-Driven Integrity** | No node, attribute or relationship added. No migration. No generated file changes. | Pass, not engaged |
| **II. Branch-Safe by Default** | The principle the feature exists to serve. Merge and rebase are both specified (FR-003) and both tested. Cross-branch effects are the subject matter. | Pass |
| **III. Type Safety & Explicit Contracts** | New internal values are frozen dataclasses, matching the existing coalescer types. The resolver gets a Protocol because a second implementation exists from day one (the in-memory test adapter). Full type hints. | Pass |
| **IV. Test Discipline** | Requires `integration_docker` for computed attributes. Met with two new tests, and two is the floor rather than the ceiling: the first pass proposed one and the critique showed the suppression itself would then be untested at the only tier that can observe trigger matching. Everything else drops a tier. Adapter and protocol patterns, no mocks. | Pass |
| **V. Query Performance & Efficiency** | The feature is an N+1 removal at the dispatch layer. The lookups it adds are bounded and chunked, must return only the fields needed, and are benchmarked before the design is committed. | Pass |
| **VI. Security & Input Boundaries** | No new user input path, no new endpoint, no query built from user input. | Pass, not engaged |
| **VII. Simplicity & Maintainability** | One new enum literal, one new collaborator, one new setting. No new dependency. Three deviations recorded in Complexity Tracking. | Pass with recorded deviations |

**Governance gates from `AGENTS.md`**: none crossed. No database or migration change, no GraphQL change, no new dependency, no CI workflow change, no auth change. CI wall-clock grows by two `integration_docker` tests.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-3002-coalesce-python-recompute/
├── spec.md              # Feature specification (revised)
├── plan.md              # This file (revised)
├── research.md          # Phase 0 output: R1-R4 decisions
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── python-target-resolution.md
├── critiques/
│   └── critique-20260811.md   # the review that forced this revision
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output, created by /speckit-tasks
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/
│   ├── merge/
│   │   ├── recompute_coalescing.py     # 4th family; per-family self/cross choice;
│   │   │                               #   whole-kind target; depth bound; chain holds coordinator
│   │   ├── python_target_resolution.py # NEW: the resolver protocol and its client implementation
│   │   ├── post_merge.py               # subtract schema-covered pairs; wire the resolver
│   │   └── builder.py                  # construct and inject the resolver
│   ├── branch/
│   │   └── tasks.py                    # rebase flow: inject the resolver
│   ├── query_group/
│   │   └── subscribers.py              # NEW: the shared subscriber query, extracted from its two copies
│   └── recompute/
│       └── dispatch.py                 # chain wiring follows the coordinator change
├── computed_attribute/
│   ├── models.py                       # origin filter on both triggers; delete leg on the reader trigger
│   ├── tasks.py                        # recompute_depth + explicit coalesced flag; honour the target kind
│   └── scoping.py                      # NEW pure function: pairs a schema change is expected to cover
└── config.py                           # NEW setting: the feature switch

backend/tests/
├── unit/{core/merge,computed_attribute}/    # builder derivation; depth bound; resolver failure table;
│                                            #   trigger shape; the new scoping function
├── component/
│   ├── computed_attribute/                  # deleted peer; schema convergence
│   │                                        #   (existing package, has _base.py and conftest.py)
│   └── merge_recompute_coalescing/          # schema-merge overlap; submission shape; scoping logs
├── integration_docker/
│   ├── test_merge_recompute.py              # + a flow-run count assertion (suppression)
│   ├── test_merge_recompute_chain.py        # NEW: cross-family chain, both directions
│   └── test_merge_recompute_timing.py       # RESTORED from an unmerged branch, extended for Python
└── helpers/merge_recompute/{dataset,metrics,scales}.py
```

**Structure Decision**: Backend only. The resolver joins `core/merge/` next to the coalescer it feeds. The subscriber query moves to a small dependency-free module, because it already exists in two copies and a third consumer in `core/merge/` would otherwise have to import the computed-attribute task module, closing an import loop through `core/recompute/`.

## Implementation Phases

Ordered so each phase leaves the tree green and the invariant intact.

| Phase | Work | Why this order |
|---|---|---|
| **0. Measure** | Restore the timing harness and the deterministic counting layer from the unmerged branch. Point them at the Python jobs. Add a Python-transform dataset with a real transform repository. Add a 2000-node scale. Record the baseline and the transform-execution count. | SC-002 and SC-007 are ratios against a baseline that does not exist. This is also the gate: if the numbers say the remaining pain is small, stop here. |
| **1. Resolve** | Extract the shared subscriber query. Add the resolver protocol, its client implementation and its in-memory adapter. Both axes: read-field narrowing and reader lookup. Not yet wired. | Pure addition, no behaviour change, unit-testable against the whole failure table on its own. |
| **2. Derive** | Add the Python family to the builder, unfiltered, with a per-family self/cross choice. Add an explicit whole-kind target that actually dispatches. Add the Python term to the depth bound. Wire the resolver into the coordinator, and make the chain submitter hold the coordinator. | The coalesced pass now produces correct Python targets while the per-node triggers still run. Duplicate work, no missing work. |
| **3. Plumb** | Give `process_transform` a `recompute_depth` and an explicit `coalesced` flag, and make it honour the target kind and attribute it is given rather than rederiving from the node kind. | Without this a coalesced submission is a silent no-op. Independent of everything above and safe to land alone. |
| **4. Deletes** | Add the delete leg to the reader trigger. Resolve subscribers at a pre-delete point in time, for deleted ids only. | Correct on its own merits: the same gap affects a plain delete outside any merge. Order against suppression does not matter, because the reader trigger has no delete leg today, so the case is already broken and suppression cannot worsen it. Kept separate so the bug fix is not blocked on the performance work. |
| **5. Subtract** | Filter schema-covered pairs out of the coalesced targets on a schema-carrying merge, after a successful send. Add a per-item guard and a `finally` to the schema flow's submit loop so a partial failure cannot skip the automation reconcile. | Needs phase 2 to have something to subtract from. |
| **6. Suppress** | Add the feature switch. Behind it: the origin filter on both Python triggers, and coalesced-mode writes so chains leave through the chain submitter. | The payoff, and reversible without a release. It needs phases 2 and 3: until the coalesced pass covers Python and the flows accept a depth and a coalesced flag, suppressing the per-node triggers loses data. Phases 4 and 5 are not prerequisites — without them a deleted peer stays as broken as it is today, and a schema-carrying merge does the work twice. Both are wasteful, neither is incorrect, so the task list orders them after suppression. |
| **7. Observe and prove** | Selection and widening logs. Re-run the harness. Publish before and after, including the transform-execution count. Update the knowledge docs. | Closes SC-001 to SC-007. |

## Complexity Tracking

| Deviation | Why needed | Simpler alternative rejected because |
|---|---|---|
| A new collaborator rather than extending the builder or the submitter | The lookups perform I/O, can fail, and must widen rather than skip. That needs its own logger and policy. | Extending the builder would make the one pure component in the pipeline async and cost 12 mock-free unit tests their independence. Extending the submitter would put a widen-on-failure policy inside a class whose existing failure policy is log-and-skip, which is how the fallback gets implemented as a skip by accident. |
| Refactoring the chain submitter to hold the coordinator | Otherwise the resolver must be injected twice and the merge path and chain path can silently diverge, which ships stale data. The two classes already run the identical build-then-submit pipeline. | Injecting into both is one line cheaper today and fragile forever. The rule against drive-by refactors does not apply: the chain path is directly in scope through FR-007. |
| A feature switch, against the YAGNI principle | The adjacent selective-regeneration work has one, and this feature's failure mode is silent stale data discovered in production. A code revert is not available to an operator at three in the morning. | No switch means the rollback is a release. The first pass claimed reverting two trigger changes would restore today's behaviour; it would not, because the coalesced family would still run, giving a double refresh. |

## Risks

| Risk | Mitigation |
|---|---|
| Suppression lands with a chain gap and values go stale silently | Phase order puts suppression last, behind a switch. Both chain directions tested end to end. The chain submitter holds the coordinator so the paths cannot diverge. |
| The coalesced pass executes more transforms than today | This is what sank the first draft. FR-004 requires the read-field filter, SC-004 measures execution count, and SC-007 reverts if it regresses. |
| A resolver failure silently skips every family | The pass sits inside a guard that swallows exceptions. The resolver must catch internally and return a widened value; a raising-adapter test asserts the other three families still ship. |
| The lookup becomes the bottleneck, or stalls the global merge lock | Benchmark at 2000 members in phase 0 before committing. Chunk the lookup, pass an explicit timeout, and record the merge critical path separately from the trailing window. |
| The restored harness is subtly wrong and the 90% claim is unfounded | It is a conflict resolution against a long-diverged branch, not an import fix. Restore the deterministic counting layer first: it is docker-free and answers SC-001 on its own. Report ratios, never absolute seconds. |
| CI time grows past what the team accepts | Two new `integration_docker` tests, and the existing suppression test is extended rather than duplicated. The class-scoped stack boots once. |
