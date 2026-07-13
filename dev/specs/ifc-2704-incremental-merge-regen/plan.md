# Implementation Plan: Incremental generator & artifact execution on merge

**Branch**: `incremental-merge-regen-ifc-2704` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/ifc-2704-incremental-merge-regen/spec.md`

## Summary

Post-merge follow-up currently regenerates every artifact and runs every eligible generator
regardless of what the merge changed. This plan makes that execution selective by (1)
capturing the enriched merge diff in the merge orchestrator before the diff is frozen,
serialized into the same `NodeDiff` summary shape the proposed-change pipeline consumes and
stored in cache under a merge-scoped key; (2) threading only that cache key through the
follow-up chain; and (3) replacing the two blanket trigger submissions with a selection step
that reuses the proposed-change definition-level predicates and member-level impact analysis,
translating the result into the merge/manual dispatch workflows' member filters. Every
uncertain path falls back to full regeneration, preserving the no-under-execution invariant.
Behavior is gated behind a new `selective_execution_after_merge` config flag.

See [research.md](./research.md) for the verified findings and design decisions (D1–D9)
that this plan is built on.

## Technical Context

**Language/Version**: Python 3.14 (backend)

**Primary Dependencies**: FastAPI, Prefect (workflow orchestration), Pydantic 2.12, Neo4j
driver 6.2, Redis-backed `InfrahubCache`

**Storage**: Neo4j (graph + enriched diff persistence); Redis (`InfrahubCache`) for the diff
summary payload

**Testing**: pytest — unit (`tests/unit/`), functional (`tests/functional/`), integration
Docker (`tests/integration_docker/`)

**Target Platform**: Linux server (backend workers + task-worker)

**Project Type**: Backend service (single project; no frontend surface for this feature)

**Performance Goals**: Reduce post-merge dispatched-task count from O(all definitions × all
members) to O(affected definitions × affected members) for typical small merges; eliminate the
~20-minute post-merge unresponsiveness window (IFC-2306)

**Constraints**: No under-execution (INFP-409 invariant — every affected artifact/generator
regenerates); no new core-schema or GraphQL-schema changes (reuse IFC-2844 `fingerprint` and
IFC-2738/INFP-409 `dependencies` fields); only string data may cross the Prefect parameter
boundary; branch-safe and temporal-correct (constitution II)

**Scale/Scope**: Backend-only; touches the merge orchestrator, post-merge dispatcher, the two
merge trigger tasks, the proposed-change selection helpers (generalized to a second caller),
two workflow message models, and one config flag

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.0.0.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | ✅ PASS | No new schema; reuses existing `fingerprint` / `dependencies` / `execute_after_merge` fields. No generated schema files edited. |
| II. Branch-Safe by Default | ✅ PASS | Core of the feature is merge behavior; diff captured on the source branch pre-freeze; selection runs against the target (destination) branch via the threaded `target_branch`, not a hardcoded default lookup. Merge behavior is specified and will be tested (FR-001..FR-011). |
| III. Type Safety & Explicit Contracts | ✅ PASS | New converter and selection routine fully typed; the `NodeDiff` TypedDict and Pydantic message models are the boundary contracts; `str | None` for the threaded key. |
| IV. Test Discipline | ✅ PASS | Unit (converter, predicates on merge summary, limit-trap filter), functional (selective dispatch end-to-end inline), integration Docker (full stack — this feature is a triggered-action path, so integration coverage is required). |
| V. Query Performance & Efficiency | ✅ PASS | The definition-level gate adds no Cypher (the diff is already loaded). Member reconciliation performs bounded per-selected-definition group/subscriber fetches — the same fetches the proposed-change CHECK flow already runs, and required for correct new-member coverage (research D4a). Net effect is still far fewer dispatched tasks. |
| VI. Security & Input Boundaries | ✅ PASS | No new external input; cache payload is internally produced; no user-supplied Cypher. |
| VII. Simplicity & Maintainability | ✅ PASS | Reuses existing predicates/impact analysis rather than reimplementing; the one extraction serves two callers (PC + merge); over-execution fallback chosen over complex cross-workflow sequencing (D7). |

**Ask-First items** (per AGENTS.md): none triggered — no DB schema/migration change, no
GraphQL schema change, no new dependency, no CI/CD workflow change, no auth change. The new
config flag is not on the Ask-First list. (This is the planning phase; the user reviews
`tasks.md` before implementation.)

No violations → Complexity Tracking section omitted.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2704-incremental-merge-regen/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 — decisions D1–D9
├── data-model.md        # Phase 1 — entities & payloads
├── quickstart.md        # Phase 1 — validation scenarios
├── contracts/           # Phase 1 — interface contracts
│   ├── merge-diff-summary.md
│   ├── branch-merge-post-process.md
│   └── artifact-generate-members.md
└── tasks.md             # Phase 2 — /speckit-tasks (not created here)
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/
│   ├── merge/
│   │   ├── orchestrator.py        # D1: capture branch_diff → summary → cache; D3: pass key to run_follow_ups
│   │   ├── post_merge.py          # D3: thread merge_diff_cache_key into BRANCH_MERGE_POST_PROCESS params
│   │   ├── selective_regen.py     # NEW — D4/D4a: definition gates + live-group member reconciliation on target branch
│   │   └── diff_summary.py        # NEW — D2: EnrichedDiffNode → NodeDiff converter (target-branch tag) + merge-scoped cache fns
│   └── branch/
│       └── tasks.py               # D4/D6/D7/D9: post_process_branch_merge — flag gate, selective dispatch, fallbacks, observability
├── proposed_change/
│   ├── tasks.py                   # D4: generalize predicates + get_field_level_impacted_subscribers to accept a resolved summary + explicit query branch
│   └── branch_diff.py             # reference for cache shape / get_modified_kinds (reused)
├── git/
│   ├── models.py                  # D5: add `members: list[str]` to RequestArtifactDefinitionGenerate
│   └── tasks.py                   # D5: consume `members` in generate_request_artifact_definition
├── generators/
│   ├── models.py                  # reference — RequestGeneratorDefinitionRun.target_members (reused)
│   └── tasks.py                   # reference — run_generator_definition / target_members filter (reused)
└── config.py                      # D9: selective_execution_after_merge flag on MainSettings

docker-compose.yml                 # D9: regenerated (release.gen-config-env)
docs/docs/reference/configuration.mdx  # D9: regenerated (docs.generate)

backend/tests/
├── unit/core/merge/              # converter, cache round-trip, limit-trap filter, selection gates on a merge summary
├── functional/                   # selective merge dispatch end-to-end (inline async tasks)
└── integration_docker/           # full-stack: single-kind change, new target, conflict-to-base, repo-code change, fallbacks, baseline count
```

**Structure Decision**: Single backend project. The merge-specific new code lives under
`backend/infrahub/core/merge/` (converter + cache in `diff_summary.py`, selection in
`selective_regen.py`) to keep the merge path cohesive; the reused selection primitives stay in
`proposed_change/` and are generalized in place to accept a resolved summary, so both callers
share one implementation.

## Phase 0 — Research

Complete. See [research.md](./research.md). All spec open questions resolved: OQ1 →
Decision 7 (over-execution fallback on direct merges with generator runs, plus a validation
spike); OQ2 → Decision 8 (no design change, explicit no-double-trigger test); OQ3 →
Decision 6 (null-fingerprint over-execution fallback).

## Phase 1 — Design & Contracts

Complete. Artifacts:

- [data-model.md](./data-model.md) — the merge diff summary entity, the reused
  `RegenerationDefinition` inputs, `ImpactedSubscribers`, and the dispatch payloads.
- [contracts/merge-diff-summary.md](./contracts/merge-diff-summary.md) — the
  `EnrichedDiffNode → NodeDiff` converter contract and the merge-scoped cache key/value.
- [contracts/branch-merge-post-process.md](./contracts/branch-merge-post-process.md) — the
  threaded `merge_diff_cache_key` parameter and the fallback contract.
- [contracts/artifact-generate-members.md](./contracts/artifact-generate-members.md) — the new
  `members` filter on `RequestArtifactDefinitionGenerate` and its member-id semantics.
- [quickstart.md](./quickstart.md) — runnable validation scenarios mapped to the spec's
  testing focus.

### Implementation phases (for /speckit-tasks to expand)

1. **Config flag + generated files** (D9) — add the setting, regenerate `docker-compose.yml`
   and `configuration.mdx`, verify the two CI validators pass locally.
2. **Diff capture + serialization** (D1, D2) — converter, merge-scoped cache functions,
   capture call in the orchestrator; unit tests for the converter (all element types, action
   uppercasing, conflict-resolved-to-base retained, membership/relationship changes).
3. **Thread the key** (D3) — extend `run_follow_ups` and `BRANCH_MERGE_POST_PROCESS`
   parameters and `post_process_branch_merge` signature.
4. **Generalize the selection primitives** (D4) — refactor the predicates and
   `get_field_level_impacted_subscribers` to accept a resolved `diff_summary`; keep the PC
   path passing its cached summary. No behavior change to the PC path (regression-tested).
5. **Merge selection routine — definition level** (D4, D6) — `selective_regen.py`: definition
   gates (query/definition/fingerprint/modified-kinds), the group-membership gate, the repo-code
   fingerprint signal + null-fingerprint fallback (with the E6 repo-signal verification).
6. **Merge selection routine — member level** (D4a, D5) — live-group reconciliation on the
   **target branch**: fetch group members + subscriber map, compute `managed_branch`, map
   impacted subscriber ids → member ids, force-render new members, emit member-id filters.
   Generalize `get_field_level_impacted_subscribers` + predicates to accept a resolved summary
   and an explicit query branch. Add the artifact `members` field + consumer (D5). **This is the
   safety-critical step (critique E1/E2/X1); it must land with its own tests.**
7. **Fallbacks + direct-merge cascade** (D6, D7) — full-regeneration fallback wiring in
   `post_process_branch_merge`. **Blocking spike first (E4)**: does the event machinery cover
   generator→artifact staleness on direct merges? If yes, drop the fallback; if no, the
   fallback must *await* generator completion (sequenced), never concurrent.
8. **Observability** (E8) — per-merge log/metric of selective-vs-fallback path + dispatch counts.
9. **Tests** — unit (converter, cache round-trip, limit-trap `members` filter, gates on a merge
   summary); functional (selective dispatch; the three member-reconciliation cases — new object
   in group, existing object added to group, SPECIFIC field change); integration Docker (full
   testing-focus matrix incl. baseline dispatched-task count flag on/off); no-double-trigger
   regression (D8).

### Agent context

The Spec Kit block in `CLAUDE.md` will be updated (via the `after_plan`
`speckit.agent-context.update` hook) to reference this plan.

### Revision: design tightening 2026-07-10

- Reason: Decision 1 diff-capture timing tightened. Serialization now runs against the
  already-loaded in-memory `branch_diff` before the freeze, but the cache write is deferred
  until after the merge's point of no return (post `MERGED` transition / write-block lift), so a
  failed or rolled-back merge writes no cache entry at all (previously it could leave a benign
  orphan that expired on TTL). Both steps are guarded so a capture failure degrades to the
  full-regeneration fallback and can never roll back a committed merge. Affects research.md D1,
  contracts/merge-diff-summary.md, contracts/branch-merge-post-process.md, and task T006.
  Reinforces Constitution II (Branch-Safe by Default).

### Revision: terminology 2026-07-13

- Reason: The branch the summary is tagged with and where selection runs its live lookups is the
  merge **target (destination) branch** (`self.destination_branch` / the threaded `target_branch`
  parameter), not a hardcoded `registry.default_branch` lookup. Infrahub merges always target the
  default branch today (`branch/tasks.py:298`), so target == default in practice; keying off the
  `target_branch` parameter keeps the design correct if that assumption ever changes. Wording
  aligned across research.md (D2/D4/D4a), contracts, and tasks (T004/T011). No behavior change.

## Post-Design Constitution Re-Check

Re-evaluated after design: no new violations. The design introduces no new schema, no new
dependency, and no new query on the hot path; it adds two typed module files and one message
field, and extracts one shared helper serving two callers. **PASS.**
