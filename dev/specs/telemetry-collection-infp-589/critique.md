# Critique Report: Phase 1 Telemetry Collection

**Date**: 2026-06-28
**Lenses**: Product + Engineering
**Inputs**: `spec.md`, `plan.md` (+ research/data-model/contracts)
**Verdict**: ✅ PROCEED (Must-Address findings applied inline)

## Product lens

The spec is well-scoped and producer-only with crisp in/out-of-scope boundaries, prioritized
independently-testable user stories, measurable success criteria, and a governance gate
(GR-001). The blocked `user_node_count` (IFC-2825) and Phase 2 items are explicitly excluded.
No scope creep observed relative to the PRD. No product-level Must-Address items.

## Engineering lens

The plan is grounded in the actual telemetry module. Branch-safety (Constitution II) is honored
by routing node/account counts through `NodeManager.count` and explicitly avoiding raw label
counts for `corenode`. The existing unwindowed event tally is preserved (FR-007). Per-metric
graceful degradation is the right shape for FR-010/SC-001. Two Must-Address gaps were found and
fixed; two recommendations were applied.

## Findings

| # | Severity | Lens | Finding | Resolution |
|---|----------|------|---------|------------|
| 1 | 🎯 Must-Address | Eng | Test strategy for SC-001/SC-002 was an "open consideration" and didn't name a deterministic-time approach — risk of slipping into `unittest.mock`, which `testing-python.md` forbids. | Firmed up in `research.md` Decision 7: degradation helper unit-tested directly with raising/returning coroutines (no mock); `freezegun` pins time for windowing; Prefect `.fn`/logger handled via the allowed pattern. |
| 2 | 🎯 Must-Address | Eng/Prod | Widening `node_count` to `dict[str, int \| None]` means a previously all-integer map can carry a `null` on `corenode`. GR-001/SC-004 only mentioned "ignores unknown fields", not "tolerates null values". A strict consumer could choke. | GR-001 + SC-004 (spec) and the contract now explicitly require the consumer to tolerate `null` values, calling out the `corenode`-in-`node_count` case. |
| 3 | 💡 Recommendation | Eng | Behavior of in-window-but-non-terminal `webhook-process` runs was unspecified. | Documented in `data-model.md` + `research.md` Decision 8: non-terminal runs counted as neither success nor failure (trend-signal semantics). |
| 4 | 💡 Recommendation | Eng | `NodeManager.count(CoreNode)` cost on large deployments (Constitution V) unaddressed. | `research.md` Decision 8: single aggregate query, daily batch — acceptable; no benchmark required this phase, deliberate over per-label summation. |
| 5 | 🤔 Question | Prod | Does `branches.active` include open-but-merged branches lingering in the registry? | Resolved: registry membership already means "open" (closed/deleted branches are evicted), consistent with the existing `branches.total`. No change. |

## Constitution re-check (post-critique)

All seven principles still pass. The `node_count` type-widening is the only contract subtlety
and is now explicitly gated (GR-001) and documented as additive-in-practice (no existing key
ever `null`). No new entities, no new dependencies, no schema changes.
