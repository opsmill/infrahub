# Alignment Check: spec.md vs. the source ask

**Date**: 2026-07-16

## Source

The source ask is the feature seed handed to `speckit-specify` — a substantive,
structured brief derived from the IFC-2804 epic plus a code-verified investigation
(current over-regeneration path, the merged fingerprint foundation, the event/trigger
infrastructure, and a confirmed integration test). No external URL; the inline brief is
the PRD. It stated: the goal (stop recomputing every transform attribute on every commit;
recompute only the attributes fed by changed transforms), the trigger replacement
(create / update-on-fingerprint / delete), selective recompute via
`python_attributes_by_transform`, the live-edit-only filter, the over-regenerate-never
invariant with null/no-watch handling, four open questions, and an explicit out-of-scope
list.

## Verdict

**✅ ALIGNED** — no missing, softened, or contradicted requirement; the additions are
necessary corrections that serve the ask's own stated invariant.

## Findings

| Severity | Category | Ask reference | Spec reference | Description |
|---|---|---|---|---|
| — | preserved | goal: replace commit sweep | FR-001, FR-003, FR-004, FR-009 | Trigger replacement + selective recompute encoded exactly as asked. |
| — | preserved | live-edit-only | FR-012, FR-013, SC-006 | Merge/rebase and recompute-write exclusion kept. |
| — | preserved | invariant (over- not under-regenerate) | FR-014, FR-016, FR-017, non-neg. section | Null=changed, no-watch per-commit-scoped, all fallbacks recompute. |
| — | preserved | out-of-scope list | Out of Scope section | Fingerprint foundation, artifact/generator consumers, `.infrahub.yml` drop, Jinja2, USER attrs all excluded as asked. |
| — | preserved | open question 1 (API query edit) | FR-020, Edge Cases | Deferred limitation, documented. |
| — | preserved | open question 3 (read-only repos) | FR-019 | Parity required. |
| — | preserved | open question 4 (rollout) | FR-021, FR-022, US6 | One recompute per transform at first import; release-noted. |
| Necessary addition | added (in-intent) | open question 2 (delete teardown) + the invariant | FR-005, FR-006, FR-010 | The critique's code analysis showed the commit trigger also reconciled the node-input automations; preserving that on the transform lifecycle (FR-006), plus name-or-id resolution (FR-010), are **necessary to honor the ask's non-negotiable under-regeneration invariant** and to answer open question 2 (what to tear down on delete). Not scope creep — enforcement of a stated requirement. |

## Action

Proceed. The spec faithfully covers the ask; the two requirements added during critique
(FR-006 node-input reconciliation, FR-010 name-or-id resolution) are in-intent corrections
grounded in the code that uphold the ask's explicit invariant and resolve its open
question 2. No remediation pass required.
