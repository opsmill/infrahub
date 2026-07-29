# Spec/Ask Alignment Check

**Date**: 2026-07-29 | **Remediation passes used**: 0

## Source

The source-of-truth PRD is **Jira card [INBOX-8](https://opsmill.atlassian.net/browse/INBOX-8)**
(Overview + Suggested solution + Scorecard), plus the linked originating discussion it was filed
from: **[opsmill/infrahub#9977 review comment `discussion_r3614911929`](https://github.com/opsmill/infrahub/pull/9977#discussion_r3614911929)**
by reviewer `polmichel`, fetched via `gh api` (not paraphrased from the card).

Both were resolvable, so the check ran against the real sources rather than falling back to inline
text.

Card's stated ask, verbatim in substance:

> **Overview**: `RelationshipManager.update()`'s data parameter is typed as an invariant list, which
> forces a scoped `# type: ignore[arg-type]` at its caller in `core/manager.py`. Typing it as a
> covariant `Sequence` lets the suppression be removed and keeps mypy meaningful on that path.
>
> **Suggested solution**: In `backend/infrahub/core/manager.py`, type the `update()` method's
> collection parameter as `collections.abc.Sequence[...]` (non-mutating) and delete the `type:
> ignore` comment that was suppressing the warning.

Reviewer's guidance, verbatim:

> Since we are removing the warning, it's always better to properly fix the warning. […] Sequence is
> not mutable by default

## Verdict

✅ **ALIGNED**

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| — | (none: covered) | Suggested solution, clause 1 | FR-001 | Collection member re-typed as covariant `collections.abc.Sequence`. Present and faithful. |
| — | (none: covered) | Suggested solution, clause 2 | FR-002 | `type: ignore` deleted. Present, and the spec correctly extends it to the adjacent explanatory comment, which becomes false once the parameter is covariant. |
| — | (none: covered) | Reviewer: "Sequence is not mutable by default" | FR-004, research R2 | The spec makes non-mutation an explicit requirement and R2 *verified* it against the method body rather than assuming it. Faithful to the reviewer's actual rationale. |
| ℹ️ Info | elaboration (not drift) | Not in PRD | FR-003, US3 | The spec adds a requirement that `update()`'s **runtime narrowing** be widened in step with the annotation. This is a **necessary clarification**, not added scope: the PRD's literal instruction, applied alone, makes `tuple` statically valid while the unchanged `isinstance(data, list)` test mishandles it (research R3). Implementing only what the card says would introduce a latent bug, so this is the card's own ask done correctly. |
| ℹ️ Info | elaboration (not drift) | Not in PRD | T002, research R6 | Relocating the `Sequence` import from `typing` to `collections.abc`. Required to satisfy the PRD's own words (`collections.abc.Sequence`) and to make it a valid `isinstance` target. Two-line, contained. |
| ℹ️ Info | non-goal added | Not in PRD | FR-006 | Spec explicitly excludes `menu/repository.py:105`'s separate `arg-type` ignore. This **narrows** rather than expands scope, and prevents a plausible misreading of "remove the type: ignore" as "remove all of them". |
| ℹ️ Info | location precision | PRD says "In `backend/infrahub/core/manager.py`, type the `update()` method's collection parameter…" | plan D1/D3 | The card names `core/manager.py` as the edit site, but `update()` is **defined** in `backend/infrahub/core/relationship/model.py`; `core/manager.py` only *calls* it. The spec/plan split the change to the correct two files. This is a factual correction of an imprecise PRD, not drift — the card's intent (fix the signature, drop the ignore) is fully preserved. |

## Assessment

No requirement, goal, or non-goal from the PRD is **missing**, **softened**, **semantically
changed**, or **contradicted**. Every spec addition is either a necessary consequence of executing
the PRD correctly (FR-003, import relocation), a scope *reduction* (FR-006), or a factual correction
of a file-location imprecision in the card. Acceptance criteria are strengthened, not dropped: the
spec adds the revert-and-confirm verification (quickstart §2) because it discovered
`warn_unused_ignores` is off and a clean mypy run alone would not prove the fix.

Per the check's own rule, "cosmetic, structural, or expansion-of-detail differences are not drift;
the spec is allowed to be longer, more precise, and to flesh out implicit requirements."

## Action

**Proceed** to implementation. No remediation pass needed; `spec.md` and `plan.md` are unchanged by
this check.
