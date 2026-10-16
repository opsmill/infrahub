# Alignment Check: spec.md against the INFP-739 brief

**Date**: 2026-10-07

**Spec**: [spec.md](spec.md)

**Verdict**: ⚠️ MINOR DRIFT (proceeding)

## Source

The user's input was "use brief in INFP-739". The source document is [INFP-739](https://opsmill.atlassian.net/browse/INFP-739), fetched on 2026-10-07 through the Atlassian connector:

- the card description: summary, goals of the first version, open questions, use case, needs and solution overview
- the comment "Idea brief: estimated and actual cost of GraphQL queries", from the grilling session on 2026-10-07: user journeys P1 to P3, FR-001 to FR-018, key entities, cases where the estimate is less reliable, SC-001 to SC-003, governance gates, assumptions, out of scope, open questions and sources

## Method

Each goal, need, functional requirement, success criterion, key entity, assumption, out-of-scope item and open question of the brief was looked up in `spec.md`. Then each item of `spec.md` with no counterpart in the brief was checked to see whether it is a necessary clarification or an addition. Wording, structure and added detail are not counted as drift.

## What matches

- **Goals and needs**: all four goals of the card and all four needs are covered. They map to FR-001, FR-005, FR-007, FR-016, FR-003, FR-010, SC-001, FR-011 and FR-002.
- **Functional requirements**: FR-001 to FR-018 keep the brief's numbers, wording and tests. The "[CLAUDE RECOMMENDED]" note under FR-008 is carried over with its label.
- **User journey P1**: all four acceptance scenarios are kept. They are split into User Story 1 (scenario 1) and User Story 2 (scenarios 2 to 4), and both stay P1.
- **P2 and P3**: listed as out of scope, as in the brief.
- **Other sections**: the key entities, the six cases where the estimate is less reliable, the assumptions, the out-of-scope list, the governance gates, the open questions and the three items decided during planning all match.
- **Success criteria**: SC-001 to SC-003 are unchanged. Their "[CLAUDE RECOMMENDED]" labels are kept.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
| --- | --- | --- | --- | --- |
| Minor | added | P1 acceptance scenario 1, second bullet | SC-004 | A success criterion was added: an engineer finds the field that multiplies the rows from one request's cost details. It restates the brief's acceptance scenario as a measurable outcome, and is labelled "[CLAUDE RECOMMENDED]". |
| Minor | added | FR-001 ("actual nodes, resolver calls and database rows") | "Terms used in the requirements" | Definitions of nodes, resolver calls and database rows were added. The brief uses the terms without defining them, and the tests need them. Labelled "[CLAUDE RECOMMENDED]". |
| Minor | changed (clarified) | FR-005 ("when variable values are given"), FR-006 | FR-006, sub-bullet | A clarification was added: `/graphql` and `/api/query` always count the first step, and the report counts it only when `variables` is given. It follows FR-005 and the FR-006 test, and comes from critique finding E1. Labelled "[CLAUDE RECOMMENDED]". |
| Minor | added (fixed during this check) | Open question "How old may the statistics be?" | Assumptions | The spec stated that the refresh interval is a setting. The brief does not say that, and the plan uses a daily schedule fixed in code. The line now says only that the brief leaves the schedule open and the plan proposes a daily default. |
| Minor | added (plan, not spec) | Key entities, statistics store | `data-model.md`, `research.md` D5 | The plan stores two values the brief does not list: the number of nodes active on main, used to scale by label counts (FR-017), and the total peers for each concrete peer kind, used to follow peers through a generic (FR-005). The second is labelled "[CLAUDE RECOMMENDED]". Neither changes a requirement. |

No requirement, goal or acceptance criterion of the brief is missing, softened or contradicted.

## Action

Proceed. The one inconsistency, the refresh interval assumption, was fixed in `spec.md` during this check. No remediation pass was needed.
