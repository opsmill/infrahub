# Alignment Check: spec.md vs. source PRD

**Date**: 2026-09-08

## Source

- **Engineering Epic**: [IFC-3065 — Number pool improvements - part 1 - Weighted Ranges per pool](https://opsmill.atlassian.net/browse/IFC-3065).
- **Primary**: Confluence page 870514689 — "Number Pools - PRD, simple as possible" (revises product JPD INFP-308; derived from `POOL-RANGES-PRD.md` / `POOL-ASSIGNMENT-PRD.md` / `SCOPED-POOLS-PRD.md`), fetched in full for this check.
- **Governing scope from the user's ask**: "first part" → the PRD's **P1 slice** (weighted ranges). P2, P3, P4 are separate parts on their own branches.
- **In-session maintainer direction** (mid-turn message): "we can make P1 and P2 disjoint and not related if we update NumberGetTaken at the end of P1." This authorises the one deliberate divergence below.

## Verdict

⚠️ **MINOR DRIFT (proceeding)** — one deliberate, maintainer-authorised semantic divergence (FR-011), fully documented in the spec; everything else P1 aligns. Scoping P2/P3/P4 out is intentional narrowing, not drift.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| ⚠️ Authorised divergence | changed | FR-011 ("`NumberPoolGetTaken` and the `attribute.unique` scan in `get_next()` are **deleted**"; "Deliberate regression: reverts 1.11 #10180"; changelog entry 3) | Scope → P1/P2 decoupling; FR-011; Assumptions; Dependencies & Risks; research D7; tasks T014 | PRD deletes the taken-value scan in P1 and reverts #10180. Spec instead **keeps and updates** the scan over the range set and **defers the deletion/#10180 revert to P2**, per the in-session maintainer direction, to make P1 independently releasable. Direction of change is intentional and reverses a specific PRD decision — recorded here so it is not mistaken for silent drift. Re-running prep to "correct" this would be wrong. |
| ✅ Intentional scope | (narrowing) | Slices P2, P3, P4; FR-043 (PRD assigns to P3) | Scope; Out of Scope | P2 (provide/attach/detach, provenance, lifecycle), P3 (scoped allocation), P4 (SDK identifier) are deliberately excluded; the spec builds shared mechanisms P1-safe only. FR-043 correctly deferred to P3 (the PRD itself reassigns it there). Narrowing to the requested part, not drift. |
| ✅ Aligned | — | P1 mechanism: `CoreNumberPoolRange`, ranges relationship, effective-space calculator, single-range migration, range-set read queries | FR-001, FR-005/005a, FR-006–008, FR-042; data-model; research D1–D6, D10 | P1 capabilities carried faithfully. |
| ✅ Aligned | — | FR-002, FR-002a, FR-004, FR-007 | FR-002, FR-002a, FR-004, FR-007 | Range-edit-never-refuses, out-of-range retention, intra-pool-only non-overlap, fullness — all carried. |
| ✅ Aligned | — | FR-039, FR-041; "Open questions → Zero ranges" default | FR-039, FR-041; Edge Cases (zero ranges); research D8/D11 | Schema-created validation over the range set, `None` defaults for shorthand detection, and the zero-ranges legal/0%/exhausted default all carried. |
| ✅ Aligned (added detail) | — | Behaviour-changelog list (P1 items 4, 5) | Behaviour changes; SC-003/SC-007; critique P1/X2 | Utilization min/max sensitivity and nullable shorthand read carried. Spec adds an explicit API-consumer-tolerance note (from critique) — a necessary clarification, not off-scope addition. Changelog item 3 (#10180 revert) moved to P2 with the FR-011 divergence. |

## Action

Proceed to completion. No remediation loop: the single divergence (FR-011) is intentional, maintainer-authorised, and thoroughly documented; treating it as drift and re-running would revert an approved decision. No P1 PRD requirement is missing, contradicted, or silently changed. Remediation counter: 0 (not entered).
