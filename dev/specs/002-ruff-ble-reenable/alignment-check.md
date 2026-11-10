# Spec/Ask Alignment Check

**Date**: 2026-07-22 | **Spec**: [spec.md](spec.md) | **Checked after**: tasks.md generation (commit 9c42b3d12)

## 1. Source

- **Inline ask** (primary requirements): Engineering Inbox card INBOX-19 text passed to `/speckit.opsmill.auto` — context, suggested solution, acceptance criteria, scorecard, hard constraints.
- **Referenced URL** (context/evidence): Patrick Ogenstad's 2026-02-18 Slack thread, channel `C051C8WQ4C9`, ts `1771428456.822439` — **fetched successfully via the Slack connector**. The thread contains the full suppression-impact analysis; it ranks "Re-enable BLE (32 violations)" as priority #1 (Tier 1 — Direct Bug Risk, effort Low) and endorses the fix-in-small-chunks / agent-in-background workflow. It adds *evidence*, not requirements, beyond the inline ask.

## 2. Verdict

**✅ ALIGNED**

## 3. Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| none | — | "Remove BLE from the global ruff ignore list (~line 511)" | FR-001, tasks T015 | Present, exact. |
| none | — | "replace the blind except with the specific exception type(s) the guarded code can actually raise" | FR-003(a), US2 | Present; per-site analysis (data-model.md) determines where this is achievable. |
| none | — | "where a broad catch is genuinely required… keep `except Exception` with a targeted `# noqa: BLE001` and a brief justification comment" | FR-003(b), FR-010, US3 | Present, verbatim policy. |
| none | — | "never a bare `except:` that also swallows KeyboardInterrupt/SystemExit" | FR-004, SC-004 | Present; E722 backstop added. |
| none | — | House method `/fix-ruff-rule` (understand rule, minimal changes, preserve functionality) | research R1/R6, FR-005 | Followed, including ~10-file batching. |
| none | — | Acceptance: `ruff check --select=BLE .` clean; BLE out of ignore; `invoke backend.lint` passes; touched-module tests pass | SC-001, FR-001, SC-002, SC-005 | All present; spec **adds** the stricter CI-equivalent gate (`ruff check . --exclude python_sdk`) — necessary elaboration, not scope creep (CI must pass for the card to be done). |
| none | — | Hard constraints (no DB schema/migration changes, no API contract changes, no auth changes, no new deps, no CI workflow changes, no generated-file edits; STOP if required) | FR-006, FR-009, plan Constitution Check | Respected structurally: constraint areas are suppression-only/annotation-only; no stop-condition triggered. |
| info | interpretation (documented) | "no DB schema or migration changes… no auth changes" | spec Assumptions ¶2, FR-006 | 30 violations live *inside* migration files and 8 inside auth files; fixing "all violations" while never touching those files is unsatisfiable. Spec resolves this as "no *semantic* changes" — comment/`noqa` additions only, byte-equivalent runtime behavior, verified by diff audit (SC-007, T021). This is the only reading under which the card is internally consistent, and it is the conservative one. |
| info | superseded detail | "~32 sites" (card + Slack thread, measured 2026-02-18) | spec Context, Assumptions ¶1 | Measured ground truth on this branch is 78 sites / 46 files (migrations m043–m074 added since February). Scope follows the card's operative clause ("fix **all** of its violations"), not the stale count. |
| minor | added (convention) | — | spec Assumptions (changelog), research R7, T016 | Spec/plan add a towncrier `housekeeping` changelog fragment. Not requested by the PRD, but repo-convention compliance with existing precedent; zero scope risk. |

No PRD requirement is missing, no requirement semantics changed, no acceptance criterion dropped or softened (two were strengthened), and no spec addition contradicts a PRD constraint.

## 4. Action

**Proceed.** No remediation passes needed (0 of 2 budget used). The two `info` rows are documented interpretations already carried in spec Assumptions; the `minor` addition is deliberate and reversible.
