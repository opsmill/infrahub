# Spec/Ask Alignment Check

**Date**: 2026-09-07

## Source

The source-of-truth PRD is the **inline feature description** passed to this run, which is a
structured brief (Context / Required change / Required tests / Definition of done / Hard
constraints) derived from Jira card **INBOX-162**. It was treated as the authoritative ask.

Supporting material, read but **not** treated as the PRD:

- <https://github.com/opsmill/infrahub/issues/10127> — fetched via `gh issue view`. This is a
  *reference*, not the PRD: its primary subject is the unbounded related-resource list on the
  **group** event path, and the `limits.py` divergence appears in it only as a noted "related
  divergence". The inline ask explicitly scopes this work to the divergence alone.
- The Jira card's own Overview / Suggested solution / scorecard fields.

## Verdict

⚠️ **MINOR DRIFT (proceeding)** — one genuine inconsistency found and fixed. No requirement from the
ask is missing, no scope was added, and no acceptance criterion was dropped or softened.

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|---|---|---|---|---|
| Minor | changed | "Preserve the existing defensive behaviour (non-positive / **unparseable** → fallback)" | FR-005, Edge Cases | **Fixed.** The ask asks for a fallback on an unparseable value. Empirically that fallback is unreachable: Prefect raises `pydantic_core.ValidationError` while *constructing* its settings, at import, before any Infrahub code runs (research.md R5). Infrahub cannot catch it and cannot fall back — the process does not start. The spec originally restated the ask's wording ("absent, non-positive, or unreadable → fallback"), which contradicted plan.md D2's decision to delete the guard. Reconciled by splitting FR-005 (absent / non-positive → fallback) from new **FR-005a** (non-numeric → rejected at startup, no masking fallback), and rewriting the corresponding Edge Case. |
| Info | changed | "keep a test-time override hook" | FR-008 | No drift, recorded for clarity. The ask allows either a dedicated hook or reliance on live reads. Reading the setting per call makes Prefect's own `temporary_settings` the override mechanism, so no bespoke hook is added — the ask's own parenthetical anticipated this ("reading the live setting on every call already makes `temporary_settings` work as the override hook"). |
| Info | added | — | spec "Out of Scope" | Not drift. The section names things the spec deliberately excludes (the group-event fix, changing the image's value, chunking instead of truncation). It bounds scope rather than expanding it, and the exclusions match the ask's single-repo, single-module framing. |

### Deviation from the ask, accepted deliberately

The FR-005/FR-005a split is a **considered deviation from the letter of the ask**, not an oversight.
The ask instructs preserving an unparseable-value fallback; the verified behaviour of the pinned
Prefect version makes that instruction impossible to implement — there is no point at which
Infrahub code could observe the malformed value. Implementing it anyway would mean shipping an
unreachable `except` clause advertising a fallback that cannot occur.

The resulting behaviour is also *better aligned with the ask's own intent*: the card exists to
eliminate a silent misconfiguration failure, and failing loudly at startup on a typo removes
another instance of exactly that. Flagged here, in plan.md D2, in critique E3, and required in the
changelog (T008) so it reaches reviewers rather than surprising them.

## Requirement coverage

| Ask item | Spec / plan | Status |
|---|---|---|
| Read the effective Prefect setting, not raw env | FR-001, plan D1 | ✅ |
| Correct, non-deprecated accessor, verified against installed source | research R1 (mirrors Prefect's own validator), R3 | ✅ |
| Fallback 100, never 500 | FR-002, FR-003 | ✅ |
| Preserve non-positive defensiveness | FR-005 | ✅ |
| Preserve unparseable defensiveness | FR-005a | ⚠️ deliberate deviation, above |
| Test-time override hook | FR-008, plan D3 | ✅ |
| Dockerfile untouched | FR-006, task T010 | ✅ |
| Helpers keep semantics + signatures | FR-007 | ✅ |
| Migrate existing env-driven tests to whichever mechanism really drives it | plan D3, task T003 (answer: `temporary_settings`, research R4) | ✅ |
| Node-action tests at 100 and at 500 | task T006 | ✅ |
| Fallback test (unset → 100) | task T005 | ✅ |
| Changelog fragment | FR-009, task T008 | ✅ |
| DoD: no 500 in module | FR-003, tasks T004/T010 | ✅ |
| DoD: named pytest suites pass | SC-005, tasks T002/T007 | ✅ |
| DoD: format + lint clean | task T009 | ✅ |
| Hard constraints (no schema/API/auth/deps/CI/generated) | plan Constraints, task T010 | ✅ |

## Action

**Proceed.** The single inconsistency was corrected in `spec.md` (FR-005 split, Edge Case
rewritten) without re-running plan / critique / tasks: the change *aligned the spec with what
plan.md D2, critique E3 and tasks.md T004 already specified*, so those artifacts required no edit.
No remediation pass was consumed.

**Remediation passes used**: 0 of 2.
