# Alignment check: spec against the source PRD

**Feature**: `dev/specs/ifc-3210-history-rewrite-reconciliation`
**Date**: 2026-09-29
**Verdict**: ⚠️ MINOR DRIFT (proceeding)
**Remediation passes used**: 0 of 2

---

## Source

Two documents, read in full through authenticated MCP tools, not a web fetch.

| Source | How | What it contributes |
|---|---|---|
| PRD "Git history-rewrite reconciliation" | Notion page `992228b83025825990bc011568cc2f4b`. Confluence page 896466945 carries the same content. | Problem statement, four journeys, 16 functional requirements, key entities, edge cases, seven success criteria, implementation and testing decisions, two open questions. |
| Jira epic IFC-3210 | Atlassian MCP, `opsmill.atlassian.net`. | The "Done when" and "Out of scope" lists, which the user named as the contract. |

Where the two disagree, the Jira epic wins. One disagreement was found. See F1.

---

## Findings

| # | Severity | Category | PRD reference | Spec reference | Description |
|---|---|---|---|---|---|
| F1 | ⚠️ | changed | PRD SC-006, epic "Done when" bullet 6 | `spec.md` SC-006 | **The epic contradicts itself, and the spec resolves it.** Both the PRD and the epic say the reason content cannot be re-derived must be "determinable from the repository **view** alone". Both also put "Display of any of this: repository page, branch list, status vocabulary (INFP-671)" out of scope. As written, no work inside this epic can satisfy the criterion, and nobody can verify it. The spec rewords SC-006 to the repository's stored state, readable through the repository API, and says the human-facing surface is INFP-671's. **Patrick must confirm this reading.** |
| F2 | ℹ️ | added | none | `spec.md` FR-017 | The PRD's FR-003 forbids the word "conflict" for a divergent history. The current classifier maps Git's divergent-branches text to a conflict message for **every** caller of `pull`, not only the sync. Removing the divergence case alone leaves the wrong message reachable. FR-017 states the message contract so a test can hold it. Recorded in the spec's "Decisions Taken During Specification". |
| F3 | ℹ️ | added | PRD edge case "a trunk reconciliation that fails badly enough to force re-initialisation... must be loud rather than retried blindly" | `spec.md` FR-018 | The PRD states this as an edge case, not as a requirement. Nothing in the PRD's FR list covers it, so the feature could ship with a silent retry loop and pass every stated requirement. FR-018 promotes the PRD's own sentence to a requirement. Not new scope. |
| F4 | ℹ️ | added | none | `spec.md` FR-019 | An observability requirement: each reconciliation logs the repository, the branch, the discarded commit and the new commit. Genuinely new, and small. It exists because the display surface is out of scope, so while INFP-671 is unbuilt the log line is the only way an operator learns a reconciliation happened. It also supports SC-006 under F1's reading. |
| F5 | ✅ | dropped by contract | PRD FR-015, FR-016, and user stories 9 and 10 | `spec.md` "Out of Scope" | Deferred to epic IFC-3220. Not drift: the Jira epic's "Out of scope" list says so explicitly, and the user confirmed the same default. The delivery queue both requirements read does not exist yet. |
| F6 | ✅ | expansion of detail | PRD user stories 3 and 6, edge cases, SC-005 and SC-007 | `spec.md` US3 and US6 | The PRD lists these as user stories and success criteria but gives them no journey of their own. The spec promotes them to first-class, independently testable journeys. Allowed: the spec may be longer and more precise. |
| F7 | ✅ | missing, then fixed | PRD "Testing Decisions" → "E2E scenario" | `tasks.md`, end-to-end task | The first `tasks.md` had no end-to-end task, although the PRD names the scenario and the constitution requires an E2E test for a user-facing feature. Added before this report was written. |

---

## What was checked and matched

| PRD element | Coverage |
|---|---|
| FR-001 to FR-014 | All fourteen present in `spec.md` with the same identifiers and the same meaning. |
| Journeys P1 to P4 | US1, US2, US4 and US5. |
| User stories 1 to 8 and 11 | All covered by a requirement or a journey. |
| User stories 9 and 10 | Out of scope, per F5. |
| SC-001 to SC-005, SC-007 | Verbatim in meaning. SC-006 changed, per F1. |
| Key entities | All six carried, plus the classification type the plan introduces. |
| Edge cases | The PRD lists eleven. Eight are carried as edge cases. Two (the orphaned delivery and the reverted delivery) are out of scope with the delivery work. One — a deliberate change of tracking target — is carried as a user story and a requirement instead of an edge case. Three are added: a non-trunk rewrite notifying nobody, a tracked ref that disappears from the remote, and an imported commit no longer present in the local object database. `spec.md` lists thirteen in total: eight carried, three added here, and two more added by the later review passes (a branch left ahead of its remote, and the deliberate change of tracking target restored as an edge case alongside its user story). |
| Assumptions | All five carried. |
| Out of scope | All eight carried. |
| Governance gates | Both crossed gates carried into `plan.md` and marked as needing sign-off. |
| Implementation decisions | All ten reflected in `plan.md` and `research.md`. The four rejected alternatives are named. |
| Testing decisions | Unit, live-remote integration, branch-safety and E2E all have tasks. The "prior art to extend, not duplicate" instruction is followed for both the Gogs harness and PR #10669. |
| Open question on FR-015/FR-016 | Resolved: defer to IFC-3220. |
| Open question on the FR-014 consumer | Resolved with a decision, marked "to confirm with Patrick". |

---

## Action

**Proceed.** No remediation pass was needed. F7 was fixed in place before this report. F2, F3 and
F4 are additions that the PRD's own text implies, or that make an existing statement testable. All
three are recorded in the spec's "Decisions Taken During Specification" or in this report.

**F1 needs Patrick's confirmation.** It is the only place where the spec states something the epic
does not. The epic asks for a view and forbids building one. The spec delivers the record that
makes the view possible and says so. If Patrick reads the epic differently, the fix is one sentence
in SC-006, not a redesign.
