# Spec / Ask Alignment Check

**Date**: 2026-09-16
**Feature**: [spec.md](./spec.md)
**Verdict**: ✅ **ALIGNED** *(was ⚠️ MINOR DRIFT; the sole scope addition was withdrawn by the user 2026-09-16)*
**Remediation passes used**: 0 of 2

---

## 1. Source

| Source | Resolution | Used as source of truth? |
|---|---|---|
| `POOL-ASSIGNMENT-PRD.md` (repo root, 503 lines) | Read in full | **Yes — the sole requirement source** |
| [IFC-3184](https://opsmill.atlassian.net/browse/IFC-3184) | Fetched. Epic, *In Progress*, summary *"Number pool improvements - part 2 - Manual attaching values to pool"*, **`description: null`** | Title only — carries no requirements |
| `POOL-RANGES-PRD.md` (P1, ships together) | Read in full | Cross-slice dependency check only |
| Confluence: [Number Pools — PRD](https://opsmill.atlassian.net/wiki/spaces/Product/pages/854818817), [Number Pools — PRD, simple as possible](https://opsmill.atlassian.net/wiki/spaces/Product/pages/870514689) | **Not fetched** | Not required — `POOL-ASSIGNMENT-PRD.md` is the derived, slice-scoped, later document and states its own supersession |

The epic having an empty description is the material fact: nothing outside the PRD file carries a
requirement, so the comparison is exactly PRD ↔ `spec.md`.

---

## 2. Coverage

Every requirement-bearing element of the PRD is present in the spec.

| PRD section | In spec | Note |
|---|---|---|
| Problem Statement | ✅ | Substance preserved |
| Solution Overview | ✅ | |
| User Stories (17) | ✅ | Folded into three prioritised journeys with acceptance scenarios, per the spec template. **All 17 traced** — see §5 |
| User Journeys P1, P2 | ✅ | Spec US2, US3 |
| FR-021 … FR-036a (incl. the three **Deleted** entries) | ✅ | Numbering preserved for cross-slice traceability; deletions retained as explicit entries with their reasoning, because each deletion is itself a requirement |
| Depends on P1 (FR-011, FR-002a, effective space) | ✅ | Plus `contracts/effective-space.md` |
| Key Entities | ✅ | |
| Edge Cases (16) | ✅ | All carried |
| Record lifecycle matrix (13 rows) | ✅ | All rows, with status |
| Interaction with branch-agnostic retirement | ✅ | Condensed in spec; full treatment in `research.md` D1/D9 |
| Decision: record moves to the `Attribute` vertex | ✅ | `research.md` D1, incl. the rejected Option A |
| Prerequisites 1–4 | ✅ | Spec *Foundational work*, surfaced as User Story 1 |
| Source display decision | ✅ | FR-030b/c; rationale in `research.md` D5 |
| SC-001 … SC-022 (incl. withdrawn SC-017) | ✅ | |
| Implementation Decisions | ✅ | |
| Testing Decisions | ✅ | Three claims corrected — §4 |
| Constitution Alignment | ✅ | |
| Governance Gates (3 crossed, 3 not) | ✅ | |
| Assumptions (9) | ✅ | |
| Out of Scope (6) | ✅ | Plus one added by decision 2026-09-16: tooling for discovering which numbers to attach |
| Open Questions (4, all resolved) | ✅ | Resolutions carried |
| Behaviour changes needing changelog (7) | ✅ | Item 3 carries the PRD's wording plus a note that identifying the numbers is the operator's job |
| Further Notes / handoff to P1 | ✅ | |

**Nothing is missing, dropped, softened, or contradicted.**

---

## 3. Findings

| # | Severity | Category | PRD reference | Spec reference | Description |
|---|---|---|---|---|---|
| A1 | ~~Minor~~ **WITHDRAWN** | ~~added~~ | — | — | **The brownfield worklist.** Raised by the critique (X1/P2) and briefly added as FR-011a / SC-023 / a reporting task. **Reversed 2026-09-16 by the user: out of scope.** Operators name the values they want tracked; no enumeration surface ships. The cost is accepted knowingly and recorded in the spec's *Out of Scope*, with a migration tool deferred. **No longer a divergence from the PRD.** |
| A2 | ~~Minor~~ **WITHDRAWN** | ~~changed~~ | FR-011 | FR-011 | FR-011 was briefly narrowed to *"during allocation"*. **Reverted 2026-09-16** to the PRD's wording verbatim. No cross-slice sign-off needed; P1 owns FR-011 unchanged. |
| A3 | Minor | **added** | Prerequisites 1, behaviour 4 | Foundational work item 1 | Ordering constraint: behaviour 4's predicate must be evaluated against records live at migration start, or run before behaviour 3. The PRD specifies both behaviours but not their order; the order is load-bearing (critique E3). An implementation detail the PRD did not determine, not a scope change. |
| A4 | Minor | **added** | — (gap) | Foundational work item 1 | The migration is **irreversible** and reports a pre-count as well as a post-count. The PRD requires the counts but never states irreversibility (critique P7). |
| A5 | Informational | **corrected** | Prerequisites 1, behaviour 3 | Foundational work item 1 | The PRD's survivor justification — *"matching the rule `m066` uses for schema pools"* — is **factually false**: `m066` keeps the **earliest**. The **rule is unchanged** (most recent `from`); only the justification is replaced. |
| A6 | Informational | **corrected** | Testing Decisions | Spec Testing Decisions, `research.md` D15 | The PRD's stated coverage gap is **inverted**. All pool lifecycle coverage is branch-**aware**, not agnostic. Following the PRD literally would have produced tests for an already-covered configuration and missed the real gap. |
| A7 | Informational | **corrected** | Testing Decisions | `research.md` §0 item 7 | The named "branch-merge suite under schema lifecycle" **merges no branch** — all three of its classes assert pool identity across branches. The merge lifecycle row is a genuine gap, not an extension. |
| A8 | Informational | **corrected** | Testing Decisions | `artifacts/test_fr036a_repro.py` | *"A working exploratory repro exists"* — it existed only in a previous session's `/tmp` scratchpad, untracked and unstashed. Rescued into the spec directory during planning; it would otherwise have been lost. |
| A9 | Informational | **corrected** | Prerequisites, *"Every number-pool read query joins `res.identifier = n.uuid`"* | `research.md` §0 item 1 | Only two of five do. The PRD reaches the right conclusion (FR-030c) from a wrong premise. |
| A10 | Informational | **added** | — (gap) | `data-model.md` §6, T006 | `IS_RESERVED` is the only property edge type with no `branch` index, and FR-030b puts it on a read path serving every attribute of every kind (critique E7). |
| A11 | Informational | **added** | — (gap) | `contracts/reservation-ledger.md`, T011 | `get_resource` never receives the `Attribute` vertex, so the PRD's match-close-create is unimplementable as written (critique E2). |
| A12 | Informational | **clarified** | FR-026 | `contracts/reservation-ledger.md`, T047 | `provenance` updates to `provided` when a user hand-sets a number onto a record the pool originally allocated. The PRD leaves this undetermined (critique P5). |

### Not counted as drift

- **Format**: the PRD's 17 numbered user stories become three prioritised journeys with acceptance
  scenarios, per the spec template. All 17 are traced in §5 — none lost.
- **Expansion**: `research.md`, `data-model.md` and `contracts/` add code-grounded verification the
  PRD asserts at a higher level. The spec is allowed to be longer and more precise.
- **Foundational work as User Story 1**: the PRD makes it a hard gate (*"None of this slice's feature
  work can start until these land"*). Surfacing it as a schedulable, independently-testable story is
  presentation, not scope.

---

## 4. Assessment

The three **corrections** (A5–A9) are the significant category, and none is drift: each is a place
where the PRD asserts something about the codebase that turned out to be false. Three of them would
have caused real damage if followed — A6 would have aimed the test effort at an already-covered
configuration, A8 would have lost the only reproduction of the release-blocking defect, and A5 would
have written the wrong survivor rule into the migration. Correcting them is the spec doing its job.

A1/A2 was the only finding with genuine scope weight — the spec briefly required that the
enumeration query survive P1's deletion. **The user withdrew it on 2026-09-16**: operators name the
values they want a pool to track, and a migration tool is deferred. FR-011 is restored verbatim, and
the spec now records the ergonomic cost in *Out of Scope* rather than solving it.

With A1/A2 gone, every remaining finding is either a correction of a false PRD claim (A5–A9) or an
implementation determination the PRD left open (A3, A4, A10, A11, A12). None adds scope, changes a
requirement's semantics, or softens an acceptance criterion.

**Verdict**: ✅ **ALIGNED**. No PRD requirement is missing, softened, reversed, contradicted or
added to. No remediation pass needed.

---

## 5. User-story traceability

| PRD story | Spec |
|---|---|
| 1 — provide a number on create with the pool that tracks it | US2 AS1 |
| 2 — provide a number without naming a pool | FR-022; US2 AS4 |
| 3 — give the pool later for a number already carried | US2 AS2 |
| 4 — bring a pool onto a populated range | US2 journey; AS3 |
| 5 — take a pool back off a number | US3 AS1 |
| 6 — utilization matches what is really in use | SC-002; US2 AS1 |
| 7 — the next number is genuinely free | US2 AS1; SC-016 |
| 8 — allocated and provided side by side | US2 AS6; SC-001 |
| 9 — see which objects hold a given number | US2 AS6 ("each naming its holder") |
| 10 — attach outside the ranges and be shown | US2 AS5; SC-015 |
| 11 — out-of-range counts once a range is widened | US2 AS5; SC-015 |
| 12 — change the number the ordinary way | US2 AS4; US1 AS4; SC-013 |
| 13 — a new pool reports nothing | US2 AS3; SC-003 |
| 14 — attach/detach on every branch at once | Edge Cases; Constitution II |
| 15 — resending the same number and pool is a no-op | US2 AS9 |
| 16 — move between pools in a single update | US2 AS7; SC-018 |
| 17 — set my own `source` on a pooled number | Edge Cases; FR-030a deleted; SC-019 |

---

## 6. Action

**Proceed.** No phase is re-run. Both open items are resolved:

- ~~**OQ1**~~ — **RESOLVED 2026-09-16 by the PRD owner: P2 wins.** `source` can be cleared on
  pool-sourced attributes; P1's FR-030a / Decision 2 are superseded. No change to this slice —
  FR-030b/FR-030c were already written this way. Remaining action is mechanical: amend
  `POOL-RANGES-PRD.md` before P1 enters spec-kit.
- ~~**OQ2**~~ — **RESOLVED 2026-09-16: out of scope.** P1 deletes the hand-set-value scan outright
  per its unchanged FR-011; this slice adds no enumeration surface and needs no cross-slice
  agreement.
