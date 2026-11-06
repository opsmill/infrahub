# The gate model

- [Four properties](#four-properties-of-a-gate) — what makes a checkpoint a gate
- [Trust tiers](#trust-tiers) — T0/T1/T2 and which gate each calls for
- [Ship vs verify checkpoints](#ship-vs-verify-checkpoints) — which skill to invoke where
- [R-codes glossary](#r-codes-glossary)

Since the split recorded in `DECISION.md` ADR-005, gates are **standalone skills invoked on
purpose**: `opsmill-dev-judging-changes` (the independent judge) and
`opsmill-dev-verifying-changes` (the in-context re-read). The code/PR skills do not embed gate
procedure; a shipping skill may point at the judge in one line, and the opt-in hook can require a
receipt, but the decision to pay for a second reading belongs to the user or the workflow.

## Four properties of a gate

1. **Pass definition** — an unambiguous statement of what "passes" means here.
2. **Independent verification** — judged by something other than the reasoning that produced
   the artifact.
3. **Required evidence** — the actual command output / artifact, pasted, not asserted.
4. **STOP-on-fail** — a failed gate halts the workflow; it never warns-and-continues.

## Trust tiers

More trust → more layers. Classify a step by its most consequential action.

| Tier | The step does | Fitting gate |
|---|---|---|
| **T0** | advisory / read-only output | evidence in the output itself; self-review |
| **T1** | mutates a branch, does not ship | `opsmill-dev-verifying-changes` at the checkpoint |
| **T2** | ships / opens a PR / merges / force-pushes / stamps a "complete" marker | `opsmill-dev-judging-changes` before the irreversible action (`--majority` for high blast radius) |

## Ship vs verify checkpoints

- **Ship checkpoint** — irreversible or outward-facing: open a PR, merge, force-push, stamp
  `AGENT_*_COMPLETE`, open drift PRs/issues, declare CI resolved, cross a spec-kit or PoV cut.
  → `opsmill-dev-judging-changes`. One judge by default; `--majority` (three judges, 2+ FAIL →
  FAIL) when the user or workflow asks for it. On PASS the skill writes the commit-bound receipt.
- **Verify checkpoint** — intermediate and reversible: a test passes, pre-CI checks are clean,
  mechanical conflicts resolved before a push. → `opsmill-dev-verifying-changes`. Single in-context
  judgment with pasted evidence; no receipt.

The hook enforces receipt **presence** only (any PASS or DEGRADED receipt for the current HEAD
unblocks the ship action). Majority judging and per-criterion rigour are prose discipline in the
judge skill, not hook-verified.

## R-codes glossary

| Code | Meaning |
|---|---|
| **R1** | Independent verbatim criteria — the judge receives the original source (issue body, `.bug-analysis-<key>.md`, spec/PRD, or pre-fix CI log) fetched fresh, not a summary. |
| **R2** | Degrade-to-re-read — when no subagent can be dispatched, fall back to the in-context procedure of `opsmill-dev-verifying-changes` AND declare the judgment degraded (DEGRADED receipt). |
| **R3** | *Retired.* Formerly the canonical-copy rule for the synced `opsmill-repo` copy; there is one copy now (`DECISION.md` ADR-006). Kept so the numbering reads complete. |
| **R4** | Human-approval-as-judge — when a mandatory human-approval step already exists before the irreversible action, that approval IS the independent judgment; no subagent is dispatched. |
