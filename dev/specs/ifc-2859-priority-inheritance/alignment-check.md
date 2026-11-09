# Spec/Ask Alignment Check: Priority Inheritance for Task Trees

**Date**: 2026-07-04
**Spec**: [spec.md](spec.md)

## Source

Inline PRD: the idea brief "Priority Inheritance via InfrahubContext" produced and confirmed section-by-section in the grilling session of 2026-07-04, passed verbatim as the feature description to `/speckit-specify`. No external URLs.

## Verdict

⚠️ MINOR DRIFT (proceeding)

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| Minor | changed | P2 journey example list ("e.g. … core/diff/branch_differ.py:159, core/merge/repository_merge_dispatcher.py:65,92") | US2 + FR-004; research.md D5 | The brief's illustrative list of in-flow audit sites named six sites; per-site code verification during planning showed three of them (`branch_differ.py:159`, `repository_merge_dispatcher.py:65,92`) plus `profiles/tasks.py:51` have **no context in scope** — passing one would require flow/class signature changes. The brief's operative definition ("passes the **in-scope** context") supports exempting them; the audit narrows to 4 fix sites + 7 documented exemptions. Example-list correction, not a requirement change. |
| — | verified | FR-001–FR-006 | FR-001–FR-006 | All six requirements carried over with matching semantics (optional field + payload compat; exact-inheritance precedence chain; effective-priority stamping; call-site audit with optional context; event/SDK boundary exclusion; local-adapter parity). |
| — | verified | Edge cases (5), SC-001–003, governance gates, out-of-scope (6 items) | Edge Cases, Success Criteria, Scope Boundaries | Complete and semantically unchanged; SC-003 reworded from "11 known gaps → in-flow ones fixed" to "all known in-flow gaps fixed; root-level sites explicitly exempt", consistent with the verified classification. |

## Action

Proceed. The single minor drift is a verified-against-code correction of an illustrative site list, recorded in research.md D5 with the full classification table; no remediation pass required.
