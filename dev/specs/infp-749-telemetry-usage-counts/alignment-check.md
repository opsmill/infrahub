# Spec/Ask Alignment Check

**Date**: 2026-11-26

## Source

The prep input was the path of one file: the full text of the design doc for INFP-749 (usage counts in the telemetry report for 1.12, and a framework for adding metrics for 1.13), as updated on 2026-11-26. The file is the source PRD for this check.

- The file is a detailed PRD: behaviour rows, decisions with rejected alternatives, scope boundaries, a payload example and the results of checks. The check was run (rule 2 of the prep skill).
- The file links to its own sources: chat threads, call notes, a Jira card, Notion pages and files on GitHub. They are the evidence behind the design doc and not a second PRD, and most of them need a sign-in. They were not fetched. The comparison uses the text of the file.
- The design doc page in Notion ([link](https://app.notion.com/p/423228b83025817eb529daa8c8912843)) still held the text of 2026-11-25 when this check ran, so the file, not the page, is the current text.
- Scope: the file covers a 1.12 change and a 1.13 proposal. The specification covers the 1.12 change only, as the file's own follow-up list asks ("Speckit specification for the 1.12 change, then for the 1.13 framework"). The 1.13 rows (18 to 21) and decisions (D11 to D13) are listed under Out of Scope in the specification and are not counted as missing.

## Verdict

MINOR DRIFT (proceeding).

The specification carries every behaviour row, decision, cost and out-of-scope item of the 1.12 change. It differs from the design doc in one place on purpose: the design doc states a fact about the code that is wrong, and the specification states the corrected fact (finding 1). The other differences add detail or a check and change no requirement.

No remediation pass was run. A remediation pass makes the specification match the design doc, and for finding 1 that would put a false statement back into the specification. The design doc is the document to correct.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| High for the reader, and not drift to revert | changed | Section 2, rows 1, 3 and 4; D9 | User Story 1 (the paragraph about end states, acceptance scenarios 2 and 3, the second computed figure), SC-001, Out of Scope | The design doc says that a failed artifact generation is a run "with a failed end state" for both artifact generation workflows, and that the reader counts generator runs "succeeded and failed" from the rows. In the code, the three workflows that run inside a proposed change (`run-generator-as-check`, `git-repository-check-artifact-create`, `git-repository-run-user-check`) record failed work as a check with the conclusion `failure` and end in `COMPLETED` ([research R5](research.md)). The specification states this, calls the unchanged figure "the largest possible number", and lists the failed counts inside a proposed change as out of scope. The requirement (rows per workflow and end state) is the same; what the rows mean for three workflows is corrected. |
| Low | changed | D15, "Costs us" (a failed call can wait 60 seconds; the report is late by the wait of 8 calls) | Edge Cases, "The run history or the event count of the task manager does not answer" | The specification gives the wait computed from the client's default settings: about 7 minutes for one unanswered read, 14 new reads, about 100 minutes. It also says that the report is not stored when the task manager answers no call, as before the change. |
| Low | added | Section 4, the open question about whether the telemetry endpoint accepts the larger request body | Assumptions; [research.md](research.md), "Checks before the pull request is merged" | The specification keeps the question open and adds that it is checked before the pull request is merged, for the shape of the new values as well as the size. The design doc sets no time for the check. |
| Low | added | D18, "Costs us" (a generator that ran only on another branch is not counted) | Edge Cases, "A generator ran only on another branch" | The specification adds one case of the same cost: the nodes of a generator definition with `execute_after_merge: false` are never counted. |
| Low | added | Section 6, sizes of the request body; D1, D2, D17 and D18, numbers of calls | SC-006, SC-007 | The specification turns the measured sizes and the numbers of reads into success criteria. SC-006 states the sizes as measured and sets no limit. SC-007 counts four reads of the graph database, which is what the design makes: the design doc counts them in three places. |
| Low | added | Section 5, rules for `validators_started` and the `node_count` keys, marked as a proposal | FR-014, FR-023 | The specification states the proposed rules as requirements and records under Assumptions that they were proposed and not separately decided. |
| None | missing, by scope | Section 2, rows 18 to 21; D11 to D13 | Out of Scope | The 1.13 framework gets its own specification, as the design doc's follow-up list says. |
| None | missing, by scope | Section 2, row 6; section 4, the points for the owner of the data warehouse and the follow-up to reply in the chat thread | Assumptions ("The owner of the data warehouse adds a table ... outside this repository"); [contracts/telemetry-payload.md](contracts/telemetry-payload.md) | The work in the data warehouse and the messages to people are not requirements on this repository. The contract lists what the data warehouse needs for the new keys. It does not list the existing `features` keys that have no column. |
| None | missing, by choice | Section 1 and the "Because" lines that name people, chat threads and observations about customers | Sources line; [checklists/requirements.md](checklists/requirements.md), Notes | The repository is public. The specification links to the Jira card and to the design doc, and names roles. |

Checked and found aligned: the 8 workflows and the row shape (D1); the four end states, no row for a workflow with no run, the row with null figures and no limit on failed reads (D15); whole seconds, no average and no median (D6); the previous full UTC day and no earlier day (D5); the validator kinds read from the schema with no namespace filter (D17 and section 8); the three definition counts on the default branch, null together (D16); the five node totals and the test on `storage_id` (D2, D4, D18); no customer-defined name (D3); the payload format version (D7); the 1.12 patch release on `stable` with no backport (D8); the new values inside the existing blocks and the unchanged report code (D10, D14); every item of the out-of-scope list of section 4.

## What was compared

- Behaviour rows 1 to 17, 22 and 23 of section 2 against the user stories and acceptance scenarios.
- Decisions D1 to D10 and D14 to D18 of section 3, with their costs, against the functional requirements, the edge cases and the assumptions.
- The out-of-scope list and the note for a later release of section 4 against the Out of Scope section.
- The rules for `null`, `0` and an empty list of section 5 against FR-009, FR-014, FR-016, FR-023 and FR-027.

## Action

Proceed. `tasks.md` is generated and stands.

Two follow-ups come from finding 1:

- Correct the design doc: rows 1, 3 and 4 of section 2, D9, the list "Which rows make one figure" in the points for the owner of the data warehouse, and "What one run means" in section 6. Task T040 covers writing the corrected text to the design doc page.
- The owner of the telemetry code answers whether the 1.12 change needs the number of failed generators, failed artifact generations and failed checks inside a proposed change ([research.md](research.md), "Questions for the owner of the telemetry code"). If the answer is yes, the design needs a new decision and this specification changes.

Remediation passes used: 0 of 2.
