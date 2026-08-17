# Alignment Check: Dark Theme Completion

**Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md) | **Remediation passes used**: 0

## Revision — 2026-08-17, after edge-case review

The requester reviewed the Edge Cases section and directed six changes. All are applied across
`spec.md`, `research.md`, `data-model.md`, `contracts/rest-config.md`, `plan.md`, `quickstart.md` and
`tasks.md`. They do not change the seven-item coverage below.

| Direction | Effect |
|---|---|
| "By default we should respect the user's browser/system config" | **Production default changed from `light` to `system`** (FR-011). The deployment default is now three-valued; non-production still forces `dark`. |
| "Couldn't we store something in localStorage?" | Confirmed — already the design. The three cache-related edge cases (pre-sign-in, preference-unavailable, first paint) are now stated as one problem with one mechanism rather than three bullets. |
| "Multiple tabs — ignore this" | Moved to Out of Scope; the `storage` listener is dropped from the provider. |
| "System theme changes — react, only if easy" | Kept (FR-007). It is a subscribable browser event, so the cost is small. |
| "Content that carries its own colors — tackle separately" | Moved to Out of Scope. Former FR-021 (semantic distinguishability) removed; contrast promoted to FR-021 with an explicit boundary. `badge.tsx` becomes migrate-without-degrading rather than a palette redesign. |
| "Existing automated tests — let's tackle this" | Confirmed in scope; T035 unchanged. |
| "Build this as a stacked PR on the existing one" | Branch bases on `bab-dark-theme-app` and the PR targets it, not `develop`. Recorded that #10284's failing checks are inherited. |

**Consequence worth noting**: making the production default `system` removed a limitation rather than
adding one. The earlier design accepted a first-visit flash because an empty cache fell back to
light while the deployment default might be dark. With `system` as both the cold-start fallback and
the production default, those two agree, so a first-ever visit to production is now correct from the
first frame. The only residual flash is a non-production deployment on a light system.

**Trade recorded**: on production, a user whose system is dark now reaches the alpha palette without
explicitly choosing it. This was raised before the decision and confirmed; it is documented in the
spec's Assumptions so a later reviewer sees the trade rather than rediscovering it.

## Source

The source of truth is the **inline handover list** supplied by the requester: seven numbered
"Known limitations / follow-ups" recorded by the author of the dark-theme series, together with the
framing statement about taking over PR
[#10284](https://github.com/opsmill/infrahub/pull/10284).

It qualifies as a substantive PRD: structured, requirement-bearing, and well over the length
threshold. No external PRD document was linked, so nothing needed fetching — the only URL in the ask
is the pull request itself, which was read for context rather than as a requirements source.

Two clarifications were obtained directly from the requester during specification and count as part
of the source:

- Scope confirmed at **all seven items**, including the separate schema-visualizer repository, after
  being challenged as four.
- PR #10284's failing end-to-end checks: **explicitly deferred**, out of scope.

## Verdict

**⚠️ MINOR DRIFT (proceeding)**

All seven items are present and traceable. No requirement was dropped, softened, or reversed. The
drift is entirely in one direction — the spec adds material the handover did not ask for — and every
addition is either a necessary consequence of the chosen approach or a recorded judgement call. One
finding was a genuine fidelity loss and has been corrected.

## Coverage of the source ask

| # | Handover item | Spec location | Status |
|---|---|---|---|
| 1 | No user preference to switch themes; `@custom-variant` is a dev-only crutch; "alpha" tag next to dark | US1, FR-001–FR-009, FR-019 | ✅ |
| 2 | GraphiQL has its own dark theme, bind it to the app theme | US3, FR-014 | ✅ |
| 3 | Mermaid only partially dark, bind to selected theme | US4, FR-015 | ✅ |
| 4 | Schema visualizer is in another repo, not dark-compatible | US7, FR-016 | ✅ |
| 5 | DataViewer uses a colder (neutral) tone than the warmer theme | US6, FR-018 | ✅ |
| 6 | Legacy pages (e.g. Proposed Changes) have hardcoded `dark:` variants and raw colors | US5, FR-017 | ✅ |
| 7 | "Make canary enabled by default" so non-production versions default to dark | US2, FR-010–FR-013 | ✅ |
| — | Take over #10284; ignore its failing E2E | Context, Out of Scope | ✅ |

## Findings

| Severity | Category | Source reference | Spec reference | Description |
|---|---|---|---|---|
| Corrected | changed | Item 1 — "add an *alpha* tag" | FR-008, T024 | The spec had generalised the label to "pre-release". The requester named "alpha" specifically; a synonym is a small but real loss of fidelity in the one string users read. **Fixed** — FR-008 and T024 now require the literal word. |
| Minor | added | not in source | FR-001, `Theme.SYSTEM` | A match-system option was added. The handover implies a light/dark toggle. Recorded in Assumptions: it is the conventional expectation, and adding it later would change the meaning of an already-stored value. Reviewer-overturnable. |
| Minor | added | not in source | FR-003 | An organisation-wide default. Not requested, but it falls out of reusing the existing preference store, which is already two-layer — excluding it would have meant *removing* behaviour the machinery provides. |
| Minor | added | not in source | FR-006, SC-002 | First-paint correctness. Not requested, but shipping an account-backed theme setting without it produces a visible flash on every load; treated as inherent to item 1 rather than new scope. |
| Minor | added | critique | FR-021, SC-009 | A contrast requirement, added by the engineering/product critique. Justified for a feature whose entire subject is color. (Numbered FR-022 when added; renumbered to FR-021 in the revision above, when semantic-color distinguishability moved out of scope.) |
| Minor | added | not in source | T047 | An automated guard so the token cleanup does not regress. Follows from SC-004's "standing property" wording rather than from the ask. |
| Minor | added | house rules | T057, T058 | Changelog fragment and user-facing documentation. Required by `AGENTS.md` for a user-facing feature, not by the handover. |
| Open | unresolved | Item 7 — "for the coming weeks" | SC-008 | The dogfooding period has no stated length and no exit criterion, and nothing says where the defects it surfaces are collected. Raised in the critique as P2/P3 and deliberately **not** invented — it is a product decision for whoever owns the period. |

### On item 7's mechanism

The handover asked to "make canary enabled by default". No `canary` concept exists anywhere in the
repository, so the term had no referent to implement. Rather than guess silently, the mechanism was
chosen with evidence and documented in [research.md](./research.md) §R1: PEP 440 pre-release status
on the running version, verified against the actual build (`1.11.0b2.dev134+geb5acb009` →
pre-release; `1.11.0` → not).

This is recorded as a **resolution of an underspecified item**, not as drift — the intent ("the
non-production versions we usually run default to dark") is met exactly. But it is the single
decision in this spec most worth a reviewer's attention, because the requester may have had a
specific existing concept in mind that this analysis did not find.

## Action

Proceed. The one fidelity loss is corrected; the remaining drift is additive, documented, and
individually reversible by a reviewer. No remediation pass was required.
