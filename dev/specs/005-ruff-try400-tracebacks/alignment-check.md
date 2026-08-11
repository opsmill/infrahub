# Spec/Ask Alignment Check

**Date**: 2026-08-11 | **Feature**: `dev/specs/005-ruff-try400-tracebacks/`

## Source

The source-of-truth ask is the **inline PRD** passed to this run, composed from Jira card
**INBOX-29** (Engineering Inbox, Tech Debt) by the platform-health drain pipeline. It carries the
card's Overview, Suggested solution, the measured ground truth, the TRY400-only scope decision, a
4-item "WHAT TO BUILD", an acceptance list, and a hard-constraints block.

Two referenced URLs were **not** fetched:

- the card's provenance link (`opsmillworkspace.slack.com/...`) — an authenticated Slack
  permalink, not reachable; its substance is already quoted in the card and carried into the ask.
- the card itself was read directly via the Jira API before this run, not re-fetched here.

Neither is requirement-bearing beyond what the inline ask already states, so the check runs
against the inline ask.

## Verdict

**✅ ALIGNED** — 0 remediation passes used.

## Findings

| Severity | Category | Ask reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| info | expansion | WHAT TO BUILD #2 ("if `exception` would be wrong there, use a targeted `# noqa: TRY400`") | research.md §R4, FR-003 | The ask authorised per-site noqa in the abstract; the spec/research resolve it concretely into 28 conversions + 6 justified suppressions. Elaboration of an explicit instruction, not drift. |
| info | added | — | SC-007 | "Every remaining `# noqa: TRY400` carries a one-line justification" is a criterion the ask implied ("with a one-line reason") but did not list under ACCEPTANCE. Added as a verifiable gate. |
| info | added | — | research.md §R3 | The `TracebackSuppressionFilter` interaction was discovered during Phase 0, not present in the ask. It *narrows* scope at one site for a correctness reason and is documented. |
| info | changed | ask: "the 34 TRY400 violations ... EXCEPT auth/auth.py" | spec.md Context | The ask's own arithmetic (36 total, 2 in auth ⇒ 34 in scope) is preserved exactly; the spec additionally publishes the full 36-site distribution table. Presentation only. |

**No** missing requirements, **no** off-scope additions, **no** softened or dropped acceptance
criteria, **no** contradicted constraints. Specifically confirmed present in the spec:

- TRY004 out of scope, with the reason (spec "Out of Scope — TRY004", SC-003)
- `extend-select` mechanism and the TRY200-removed-rule warning (Assumptions, research.md §R1)
- no dependency-list edits (FR-002)
- `auth/auth.py` untouched, suppressed by file with a commented reason (FR-006)
- changelog fragment conditional on repo convention (FR-008)
- all four hard-constraint categories (FR-007, SC-005)
- structlog keyword-argument preservation (FR-004)
- test-assertion exposure for log records (research.md §R7)

## Action

Proceed to implementation. No phases re-run.
