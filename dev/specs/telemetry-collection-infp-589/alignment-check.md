# Spec/Ask Alignment Check: Phase 1 Telemetry Collection

**Date**: 2026-06-28
**Remediation passes used**: 0

## 1. Source

Inline PRD: `INFP-589-phase1-handoff.md` (the feature-description block + Functional
Requirements + Success Criteria + Code pointers + Governance gate + Parked decision). No URLs
present in the ask — Jira/JPD items are referenced by ID only, so no web fetch was needed.

## 2. Verdict

✅ **ALIGNED** — no *unintended* drift. The spec is a faithful, expanded restatement of the
PRD. Additions are either necessary clarifications or one **sanctioned, user-directed scope
expansion** (checks/artifacts metrics — see §6), explicitly recorded rather than silently
folded in.

## 3. Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| ✅ none | — | FR-001..003, 005..011 | FR-001..003, 005..011 | All in-scope FRs present verbatim in intent; FR-004 correctly omitted (blocked). Numbering matches the PRD exactly. |
| ✅ none | — | "Success" SC-001/002/003 | SC-001/002/003 | All three success criteria carried over with the same meaning (presence+null-on-failure, exact 24h window, corenode ±0). |
| ✅ none | — | "Governance gate" | GR-001 | Receiving-end confirmation captured as a release gate. |
| ✅ none | — | "Out of scope" | Out of Scope section | user_node_count, Phase 2 items, dashboards, redefining node_count.total, persisting logins — all preserved. |
| ℹ️ info (added, justified) | added | FR-011 + Governance gate | SC-004 | Spec adds SC-004 (additive-only + format-bump consumer compatibility). This is a measurable restatement of FR-011 + the governance gate, not new scope. |
| ℹ️ info (added, justified) | added | — (engineering clarification) | GR-001(c), SC-004, contract | Critique added explicit "consumer tolerates `null` values (incl. corenode in node_count)" tolerance. This clarifies the additive contract implied by FR-010/FR-011 + the `node_count.corenode` requirement; it does not change scope. |
| ℹ️ info (expansion) | — | "Facts" / best-effort note | Edge Cases + Assumptions | PRD's best-effort/retention facts expanded into edge cases and assumptions. Expansion of detail, allowed. |

No `missing`, `changed`, `dropped`, or `contradicted` findings.

## 4. Action

Proceed. `tasks.md` is generated and aligned with the source PRD. No phases re-run.

## 5. Post-review refinements (2026-06-28, reviewer feedback)

Two design refinements applied after the user reviewed the prep output. Both keep the spec
aligned with the PRD — they make existing requirements precise, they do not add/drop scope:

1. **24h window anchoring (sharpens SC-002).** The daily flow runs at a per-deployment-random
   minute (`cron=f"{random.randint(0, 59)} 2 * * *"`, `workflows/catalogue.py`). Anchoring the
   window to gather-time `now` would make consecutive daily windows overlap or gap under
   execution drift — violating SC-002's "no overlap/leakage". The window is now anchored to a
   deterministic boundary: the **previous full UTC calendar day** `[midnight-24h, midnight)`.
   Updated in spec (SC-002, edge cases, assumptions, `activity_24h` entity), plan (constraints),
   research (Decision 3 + 4), data-model, contract, and tasks (new T009b helper + T007/T010/T012).
2. **Node-metric definitions pinned at the namespace level (sharpens FR-009).** Verified via
   `get_labels()` that `corenode` = all `CoreNode`-labelled nodes (`Core` + `Builtin` +
   user-defined namespaces), which always includes the non-empty `Core` management namespace;
   the future `user` metric excludes `Core`, so `user ⊆ corenode ⊆ total` strictly and they can
   never become synonyms (relevant because FR-011 forbids removing a shipped field). Updated in
   spec (FR-009), research (Decision 1), data-model, contract, and tasks (T021).

## 6. Sanctioned scope expansion — checks, artifacts & branch lifecycle (2026-06-28, user-directed)

| Category | PRD reference | Spec reference | Description |
|----------|---------------|----------------|-------------|
| added (approved) | **not in PRD** (came from the JPD card's Phase 2 list, not the handoff) | FR-012, FR-013, FR-014, US5, `activity_24h.checks_*` / `artifacts_*` / `branches_*` | Pulled `validator.started/passed/failed` → `checks_*`, `artifact.created/updated` → `artifacts_*`, and `branch.created/merged/deleted` → `branches_*` into Phase 1. |

**Why this is NOT unresolved drift**: The user explicitly directed this across two review
rounds (checks/artifacts, then branch-lifecycle counts after challenging the cost). It is a
deliberate, recorded expansion — the alignment phase exists to surface exactly this kind of
divergence rather than let it pass unnoticed, and here it is surfaced and approved.

**Why it is safe / cheap**: All three event families are **already emitted and counted today**
(verified via `get_all_events()`), so they reuse the US1 windowed event path unchanged (one more
event name per metric + a parametrized test). They serve the already-stated Phase 1
"depth-of-adoption" goal; branch create/merge/delete activity is an especially direct adoption
signal for the branch-based workflow.

**Boundary discipline applied** — events that exist but were deliberately **held in Phase 2**,
to keep permanent (FR-011) contract surface to clean standalone signals:
- **PR "merged-without-review"** (`proposed_change.*`) — needs per-PR review↔merge correlation.
- **Branch *lifetime*** (create→merge duration) — needs durable per-branch correlation. (The
  lifecycle *counts* are in scope; only the duration is deferred.)
- **Node churn** (`node.*`) — `node.updated` fires on every attribute mutation incl. automated
  writes, so the count is machine-dominated (held on signal quality, not cost).
- **Branch `rebased`/`migrated` counts** — maintenance/automation-driven, lower-signal.

Recorded in spec "Out of Scope", research Decision 9, and tasks Notes.
