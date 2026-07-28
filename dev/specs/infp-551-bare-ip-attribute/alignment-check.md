# Spec / Ask Alignment Check

**Feature**: `specs/infp-551-bare-ip-attribute` | **Date**: 2026-07-28

## Source

| Source | Type | Status |
|--------|------|--------|
| `bare-ip-attribute-prd.md` (repository root) | Inline PRD — the ask passed to `/speckit-opsmill-prep` | ✅ Used as source of truth |
| `bare-ip-attribute.md` (repository root) | Companion idea brief, named by the PRD as its code-confirmed evidence base | ✅ Used as supporting source |

**No web fetch was performed, and none was needed.** The PRD contains no URLs; it is a complete local
document (≈330 lines with headings, 16 user stories, FR-001–FR-013, SC-001–SC-006, edge cases,
assumptions, out-of-scope, and open questions), which is decision path 2 in the Phase 5a rules.

The companion brief does carry URLs — [INFP-551](https://opsmill.atlassian.net/browse/INFP-551),
PR #9970, SDK PR #1190, issue #8896 — but these are **references**, not alternative PRD locations. The
Jira item in particular is the *seed idea*, which the PRD explicitly supersedes: it proposed a new
`IPAddress` attribute kind, and the PRD reverses that solution shape. Comparing the spec against the
superseded seed would manufacture false drift findings, so it was deliberately not used as the
baseline.

## Verdict

⚠️ **MINOR DRIFT (proceeding)**

Two deliberate, documented deviations from the PRD text. Neither removes, softens, or contradicts a
requirement, goal, non-goal, or acceptance criterion. Both are recorded below with their justification.

## Coverage

Mechanically verified, not asserted:

| Element | PRD | Spec | Status |
|---------|-----|------|--------|
| Functional requirements | FR-001 … FR-013 | FR-001 … FR-013 | ✅ All 13, numbering preserved 1:1 |
| Success criteria | SC-001 … SC-006 | SC-001 … SC-006 | ✅ All 6, numbering preserved 1:1 |
| User stories | 16 | 16 (traceability table, each mapped to its FR) | ✅ Complete |
| User journeys | P1 / P2 / P3 | User Story 1 / 2 / 3, same priority labels and ship-order notes | ✅ Complete |
| Key entities | 5 (incl. "Not created") | 5 | ✅ Complete |
| Edge cases | 9 | 12 (9 PRD + 2 from the brief + 1 from critique) | ✅ Superset |
| Assumptions | 5 | 5 + 3 open-question resolutions | ✅ Superset |
| Out of scope | 6 | 6 | ✅ Complete |
| Governance gates | 2 crossed, 3 not | Identical | ✅ Complete |
| Constitution alignment | 5 principles | 5 principles, same verdicts incl. the Principle III push-back | ✅ Complete |
| Open questions | 3 | 3, all resolved with recorded rationale | ✅ Resolved, not dropped |

PRD "Implementation Decisions" module sketch — 6 modules:

| Module | Disposition |
|--------|-------------|
| `IPHost` attribute parameters type | ✅ tasks T003–T004 |
| `IPHost` attribute schema type | ✅ tasks T005–T007 |
| `IPHost` attribute class (the deep module) | ✅ tasks T017–T018 |
| IPHost input, display, and filter handling (frontend) | ⚠️ **Dropped** — see D2 |
| SDK attribute value coercion | ✅ task T028 |
| SDK protocol generator attribute renderer | ✅ task T029 |

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| Minor (D1) | changed | SC-001 "three of those five"; SC-004 "the three separate workarounds" | `spec.md` § Success Criteria SC-001, SC-004 | Baseline workaround count corrected from **three to four**, and the spec now names all four explicitly plus notes that the fifth surface (UI display) has no workaround available at all. |
| Minor (D2) | changed | Implementation Decisions → "IPHost input, display, and filter handling (frontend, extends): reads the declaration and suppresses the prefix control and mask rendering" | `plan.md` § Summary and Phase E; `tasks.md` Phase 5 | No frontend **source** change is planned. The frontend contribution is a regression test only. |
| Minor (D3) | added | FR-004 (values only) | `spec.md` FR-004 extension + new edge case | FR-004's rules are extended to cover an attribute's declared `default_value`. |
| Minor (D4) | added | — (absent from PRD) | `spec.md` § Dependencies; `contracts/sdk-contract.md` § Version skew | An SDK version floor is documented: an *older* SDK reading a bare stored value re-attaches the host mask. |
| — | none | — | — | **No requirement, goal, non-goal, or acceptance criterion is missing, softened, or contradicted.** |

### D1 — SC-001 / SC-004 baseline corrected (changed)

**Why this is not drift to revert.** The PRD's own count is internally inconsistent with its own
Problem Statement. That statement enumerates **four** workarounds — GraphQL `mgmt_ip { ip }`,
`display_label: "mgmt_ip__ip"`, `human_friendly_id: ["mgmt_ip__ip"]`, and SDK `node.mgmt_ip.value.ip`
— across five read surfaces, and the fifth surface (UI display) has no workaround at all. The idea
brief compounds the confusion with a third figure ("3 of 6"). A success criterion whose baseline
contradicts its own source document cannot be verified at review time.

The corrected wording preserves the criterion's **intent** exactly (one declaration replaces N
workarounds) while making it checkable, and it states a *stronger* claim than the PRD did. Raised as
critique finding P2 and applied deliberately.

### D2 — Frontend source change dropped (changed)

**Why this is not a scope reduction.** FR-010 ("Users MUST be able to edit a bare-address attribute
through a form with no prefix-length control") is retained **verbatim** in the spec, and User Story 2
is retained in full with all four acceptance scenarios. What changed is the *implementation decision*
about how to satisfy it, on the strength of code evidence gathered in Phase 0:

- `IP_HOST` appears nowhere in the form-field dispatch, table cell, filter input, or form field types
  (grep across all five files: zero matches).
- An `IPHost` attribute falls through every kind branch to `basicFormFieldProps` — a plain text input
  — at `frontend/app/src/shared/components/form/utils/getFormFieldFromAttribute.ts:196`.
- `prefixlen` / `prefixLength` appear nowhere in `frontend/app/src` outside generated types.

There is no prefix control to suppress and no mask rendering to intercept: the UI already displays the
raw `value` string, so it shows a bare address the moment the backend stores one. FR-010 is satisfied
**by construction**, and the UI half of FR-005 follows from bare storage.

Because it is satisfied only incidentally, the requirement is now guarded by a regression test
(task T034), explicitly labelled a requirement guard rather than optional polish, so a future dedicated
IPHost input cannot violate FR-010 silently. Task T036 additionally requires the implementer to stop and
record the contradiction in `plan.md` if any frontend source change does turn out to be necessary.

Net effect: the PRD's requirement is fully met and better protected; only the PRD's guess about which
module needed editing was wrong.

### D3 — FR-004 extended to declared default values (added)

Phase 5c permits the spec to "flesh out implicit requirements". This is that case, and leaving it
implicit would have produced a user-visible inconsistency:
`SchemaBranch.validate_default_values()` (`backend/infrahub/core/schema/schema_branch.py:1048-1066`)
routes an attribute's `default_value` through the same `validate_format` this feature modifies. So the
PRD's rules already applied to defaults whether or not anyone specified them — but only half-way: a
non-host-prefix default would start failing at schema load (unspecified), while a `/32` default would be
accepted and stored **unnormalised**, leaving the schema advertising `10.0.0.1/32` as the default for an
attribute whose every node stores `10.0.0.1`.

The extension applies FR-004's existing rule (accept a redundant host mask, store bare) to the one place
the PRD did not consider. It adds no new user-facing capability and no new scope. Raised as critique
finding E1.

### D4 — SDK version floor documented (added)

Documentation of an unavoidable consequence of FR-005 and FR-011, not new scope. An SDK predating this
change cannot know a bare value is meant to stay bare, so it coerces `"10.0.0.1"` with `ip_interface`
and re-attaches `/32`. The PRD covered only the safe skew direction (a newer SDK against a server that
does not publish the declaration). Raised as critique finding E4.

## Action

**Proceed.** No remediation pass required; the retry budget (2) is untouched and unused.

All four deviations are minor, deliberate, and disclosed. D1 corrects a defect in the PRD. D2 satisfies
a retained PRD requirement by a cheaper route proven by code evidence. D3 and D4 flesh out consequences
the PRD did not reach. None narrows the deliverable.

**For the PRD author's attention** — two items are worth folding back into the source PRD so the
inconsistency does not propagate to the next feature:

1. The SC-001 / SC-004 workaround count (three vs the four enumerated in the same document, vs the
   brief's "3 of 6").
2. The module sketch's frontend entry, which assumed an IPHost input component that does not exist.
