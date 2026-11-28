# Alignment check: spec.md against the source request

## Source

- Jira epic [IFC-2167](https://opsmill.atlassian.net/browse/IFC-2167) "Refactor placeholder automations". The epic has no description.
- Discovery idea [INFP-441](https://opsmill.atlassian.net/browse/INFP-441), which IFC-2167 implements. Its description is the source PRD: summary, problem, impact, customer impact, proposed solution and note. Its only comment asks whether the work is still needed and has the right priority; the comment has no answer and adds no requirement.

## Verdict

⚠️ MINOR DRIFT

The spec covers every requirement of INFP-441:

- Placeholder automations for display labels and HFIDs are no longer created (FR-001).
- Infrahub records the fingerprints in its own database (FR-002). The plan and research use a `StandardNode` subclass, as INFP-441 asks.
- The automation count drops and no longer grows with kinds and branches (User Story 1, SC-001).
- Users notice no change except the lower automation count (FR-011, FR-012).
- The 200-automation display limit is treated as an edge case once the count drops, as the INFP-441 note states.

The spec adds one scope item that INFP-441 does not name: the placeholder automations of Jinja2 computed attributes. The spec records this choice and its reason in Assumptions, and it serves the PRD goal of removing every automation that only serves as a placeholder. The other additions (upgrade carry-over, branch lifecycle, concurrency) are details that the PRD goal needs, not new scope.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| Minor | added | INFP-441 Description: "placeholders to track when to trigger recalculation of display labels and HFIDs" | Background; User Story 1 scenario 2; FR-001; FR-009; Assumptions "Scope includes Jinja2 computed attributes" | The spec also removes the self-targeting placeholder automations of Jinja2 computed attributes. INFP-441 names only display labels and HFIDs. The spec states the reason (same placeholder pattern, epic title covers all placeholder automations) and records no fingerprint for them, because their recompute decision does not read one. This matches the PRD goal "Eliminate automations that only serve as placeholders", but it widens the work beyond the two families named in the PRD and beyond the 1-week estimate. |
| Info | added | INFP-441 Summary: "Keep large environments [...] stable through upgrades" | User Story 3; FR-009; SC-003 | The upgrade deletes the existing placeholder automations and carries their fingerprints over. INFP-441 does not describe a migration, but without it the first schema update after the upgrade would recompute every node of every kind on every diverging branch. This is a necessary clarification, not drift. |
| Info | added | INFP-441 Proposed Solution: "Track internally instead of in Prefect" | User Story 4; FR-008; Edge Cases | The spec removes recorded fingerprints when a branch, kind or template is removed. INFP-441 does not mention cleanup, but records that outlive their branch would grow without bound, which is the problem INFP-441 describes. Necessary clarification. |
| Info | changed | INFP-441 Proposed Solution: "Comes after placeholder automation refactor" | Not referenced | INFP-441 says the work comes after a placeholder automation refactor, but that refactor is the title of INFP-441 and IFC-2167 themselves, so the sentence names no separate prerequisite. The spec does not mention it. No action is needed unless a separate prerequisite exists; the sources do not say. |
| Info | changed | INFP-441 Problem: names the customer | Assumptions "Customer naming" | The spec does not name the customer because it is stored in a public repository. The facts (11,000 automations, failure during the 1.5 upgrade) are kept. Not drift. |
