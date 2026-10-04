# Alignment check: spec against the source PRD

**Feature**: `dev/specs/ifc-3220-writeback-failure-handling`
**Date**: 2026-10-02
**Verdict**: ⚠️ MINOR DRIFT (proceeding)
**Remediation passes used**: 0 of 2

---

## Source

Three documents, read in full through authenticated MCP tools, not a web fetch.

| Source | How | What it contributes |
|---|---|---|
| PRD "Git remote writeback failure handling" | Notion page `a81228b830258373bc5b81dbb878345c` | Problem statement, fifteen user stories, two journeys, nineteen functional requirements, key entities, twelve edge cases, six success criteria, implementation and testing decisions, two open questions. |
| The same PRD on Confluence | Confluence page 861896706, which the epic links | The same content as the Notion page. No difference found. |
| Jira epic IFC-3220 | Atlassian MCP, `opsmill.atlassian.net` | The "Done when" and "Out of scope" lists, the sequencing, and the two requirements inherited from IFC-3210. |
| PRD "Git history-rewrite reconciliation" | Notion page `992228b83025825990bc011568cc2f4b` | The text of its FR-015 and FR-016, which the epic says are built here. |

Where the PRD and the epic disagree, the epic wins. No disagreement was found. The epic adds the
two inherited requirements, which the spec carries as FR-020 and FR-021.

---

## Why the verdict is minor and not significant

Four findings change the meaning of a PRD statement (F1 to F4). By the letter of the check, a change
of semantics is significant drift. They are classed as minor here, as the sibling epic's check
classed its own reworded SC-006, for three reasons:

1. Each one is deliberate and recorded in the spec's "Decisions Taken During Specification" or in
   `research.md`, with its reason.
2. Each one corrects a statement that the code, as verified by the two critique passes, does not
   allow, or that would cost a regression on the success path.
3. A remediation pass would restore the PRD text and, with it, the defect that the change removes.

Each of the four needs the PRD owner's confirmation. If Patrick Ogenstad reads one differently, the
fix is local to the named section, not a redesign.

---

## Findings

| # | Severity | Category | PRD reference | Spec reference | Description |
|---|---|---|---|---|---|
| F1 | ⚠️ | changed | SC-001, epic "Done when" bullet 6 | SC-001 | **The first sentence of SC-001 is dropped.** The PRD says the reported commit "equals the commit on the remote". FR-023 pauses the import of the default branch while a delivery is pending, because a desired-state import would delete the merged objects that are not delivered yet. During such an outage the remote can advance, so the two commits differ by design. The spec keeps the PRD's second sentence and the epic's bullet, "never reports a commit the remote does not have". **To confirm.** |
| F2 | ⚠️ | changed | Implementation decision "Held work is identifiers, not targets"; FR-014 | FR-014, SC-008, `research.md` R9 | **Narrowing is kept for a short time.** The PRD drops member and target narrowing for every release. The coalesced recompute nearly always runs before the first attempt ends, so the hold is the normal path for a git-synced merge that carries content, and dropping narrowing there would turn every such merge into whole-kind recomputes. The spec keeps FR-014's persistence rule and its purpose, and adds a cache of the narrowed selection whose time to live is the length of the automatic retry chain. A long recovery never reads it. **To confirm.** |
| F3 | ⚠️ | changed | FR-016, decision "Blanket regeneration is the failsafe" | FR-016, `research.md` R10 | **The failsafe is scoped to the owning repository.** The PRD widens an unresolvable held set "to full branch regeneration". Held work is partitioned by repository, so every held item belongs to one repository's definitions. Regenerating all of that repository's definitions covers the whole held set and keeps the widen-never-skip invariant, without regenerating other repositories' definitions twice. **To confirm.** |
| F4 | ⚠️ | changed | FR-015, SC-004 "exactly one release" | FR-015, SC-004 | **"Exactly one" is stated honestly.** No step can be atomic across the graph and the orchestrator. The spec guarantees one release in the absence of a failure, never zero, and at most a repeat after a failure between the dispatch and the clear. SC-004 also states the fail-open exception of FR-016, which applies only after a bounded retry of the state read. |
| F5 | ℹ️ | added | none | FR-005a, FR-005b, FR-022 to FR-027 | Eight requirements added. Each one is a necessary clarification found against the code: the enqueue order the PRD states as a decision (FR-005a), no resurrection of an abandoned entry (FR-005b), no push of a discarded trunk history (FR-022, IFC-3210's FR-005b), no other import while pending and a durable import obligation (FR-023), an abandonment that never fails (FR-024), the default-branch read rule (FR-025), silent bookkeeping writes (FR-026, the PRD's ADR 0016 note), and liveness (FR-027). Recorded in spec decisions 5 to 12. |
| F6 | ℹ️ | added | FR-011, edge case "The remote source branch would be deleted after merge" | FR-011, US6, spec decision 15 | The PRD refuses the deletion. The spec also deletes the branch once the entry is delivered, keeps the synchronisation from importing it meanwhile, and, after an abandonment, lets it come back as a new Infrahub branch. Without these, a refused deletion leaves a branch that the default `git.import_sync_branch_names` imports again on some workers only. The behaviour after an abandonment is **to confirm** with the product owner. |
| F7 | ℹ️ | changed | FR-017 | FR-017, "Terms", spec decisions 14 and 16 | FR-017 adds the schema-scoped recompute, allows a wider hold at its two consultation points, and states that live per-node recomputes and transform webhooks are not held. The PRD's own decision "Barrier, not trigger" and its rejection of "gating inside the transform executor" support the exclusion. |
| F8 | ℹ️ | changed | FR-008, user story 8 | FR-024, US5 | The abandonment clears, records and releases. It does not re-import, and the repository then offers the existing reimport of the current commit. The PRD says only that an abandonment returns the repository "to a working state". |
| F9 | ✅ | missing, then fixed | Out of Scope, "Repository type naming (INFP-95)" | spec "Out of Scope" | The first spec omitted it. Added before this report was written. |
| F10 | ℹ️ | corrected | Decision "requests are already per definition and carry their owning repository" | `research.md` R0, R9 | True for generator requests only. `RequestArtifactDefinitionGenerate` carries no repository today, so the plan adds an optional `repository_id`. Not drift in the spec; a factual correction in the plan. |
| F11 | ℹ️ | changed | Module table, "`InfrahubRepository.merge()` — extends — Delegate the push to the service" | `research.md` R19, plan "What slice C changes" | The merge flow calls the service, which replays the queue, instead of `merge()` delegating its push. The intent is the PRD's: "one implementation, two callers". `merge()` stays for the no-remote path and the tests of #10465. |
| F12 | ℹ️ | expansion of detail | Decision "Status vocabulary" | data-model "Failure cause" | The PRD gives a status whose values name the action, and a verbatim message. The spec adds a closed cause enum beside the status, from which the required action is derived. It is needed because two causes with the same status need different actions: retry or abandon. |

---

## What was checked and matched

| PRD element | Coverage |
|---|---|
| FR-001 to FR-019 | All nineteen present with the same identifiers. FR-001 to FR-003 kept as satisfied by #10465. FR-014 to FR-017 changed as F2, F3, F4 and F7 say. The others keep their meaning, with detail added. |
| IFC-3210 PRD FR-015 and FR-016 | FR-020 and FR-021. FR-020 detects at the next attempt; "reconcile the branch regardless" is IFC-3210's reconciliation, and a merged source branch is already excluded from synchronisation today. |
| User stories 1 to 15 | All covered. 1 to 3: US1. 4 and 5: US2. 6 and 7: US4. 8 and 9: US5. 10: FR-001, SC-001. 11 to 13: US3, FR-016. 14: US6 #5, FR-010. 15: FR-006. |
| Journey P1a | Recorded as delivered by #10465. FR-001 to FR-003 retained. |
| Journey P1b | US2 #1, US3 #2 and US6 #1 together carry its acceptance, clause by clause. |
| Key entities | All carried. The state lives on `CoreRepository` only (spec decision 17), since a read-only repository never delivers. |
| Edge cases | All twelve of the PRD carried. The spec lists thirty in total: those twelve and eighteen added from the code reviews. |
| SC-001 to SC-006 | All carried. SC-001 changed (F1), SC-004 sharpened (F4). SC-007 and SC-008 added. |
| Epic "Done when" | All six bullets map to SC-001 to SC-006. |
| Implementation decisions | All carried in `plan.md` and `research.md`. Two changed (F2, F3). The four rejected alternatives of the PRD stay rejected. |
| Testing decisions | Unit tests of the four named modules, live-remote integration tests, deferral tests, the branch-safety test, the E2E scenario and the prior-art harness all have tasks. |
| Governance gates | All three carried, plus the SDK submodule change, which the PRD does not list. |
| Assumptions | All carried. "P1a lands on stable" is now "on `develop` as `7d1bab3d1`". IFC-3018 is done. |
| Out of scope | All eleven carried, INFP-95 after F9. |
| Open questions | Both answered, each flagged for confirmation (spec decisions 1 and 2). |

---

## Action

**Proceed.** No remediation pass was run. F9 was fixed in place. F5 to F8 and F10 to F12 are
additions or corrections that the code requires, each recorded with its reason.

**Five items need a person**, all listed in `tasks.md`, "Gates before any code is written":

- F1, F2 and F3: the PRD owner confirms the changed statements.
- F6: the product owner confirms what a kept branch does after an abandonment.
- Spec decisions 1 and 2: whole-queue abandonment, and the status label with INFP-671.
