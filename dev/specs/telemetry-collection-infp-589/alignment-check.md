# Spec/Ask Alignment Check: Phase 1 Telemetry Collection

**Date**: 2026-06-28
**Remediation passes used**: 0

## 1. Source

Inline PRD: `INFP-589-phase1-handoff.md` (the feature-description block + Functional
Requirements + Success Criteria + Code pointers + Governance gate + Parked decision). No URLs
present in the ask — Jira/JPD items are referenced by ID only, so no web fetch was needed.

## 2. Verdict

✅ **ALIGNED** — no significant drift. The spec is a faithful, expanded restatement of the
PRD. Additions are necessary clarifications, not scope creep.

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
