# Spec / Ask Alignment Check: Retirement of branch-agnostic property edges

**Date**: 2026-08-12
**Feature**: [spec.md](./spec.md)
**Verdict**: 🛑 SIGNIFICANT DRIFT → ✅ ALIGNED after one remediation pass
**Remediation passes used**: 1 of 2

---

## 1. Source

Three sources were resolved and concatenated into the source-PRD view:

| Source | Access | Contribution |
|---|---|---|
| `IFC-2843-prd.md` (local, inline) | Read directly | The 249-line PRD the pipeline was seeded with — requirements, user stories, edge cases, implementation and testing decisions |
| [GitHub issue #9762](https://github.com/opsmill/infrahub/issues/9762) | `gh issue view` — public, fetched | The original bug report: Current Behavior, **Expected Behavior**, Steps to Reproduce, quantified dataset measurements, the orphan-detection Cypher signature, and the stopgap workaround |
| [IFC-2843](https://opsmill.atlassian.net/browse/IFC-2843) | Atlassian MCP (authenticated) — fetched | Same description as the issue, **plus a comment carrying the full hand-written Cypher used to unblock the affected production deployment**, and the note that "the migration to clean this up once the bug is fixed should have roughly the same shape" |

The Jira comment is the decisive source. It is a *validated* remediation — it ran against the real
database and fixed the real problem — and it therefore functions as a reference implementation that
the PRD summarised but did not fully transcribe.

Both URLs were reachable; nothing was gated or skipped.

---

## 2. Verdict

**Initial: 🛑 SIGNIFICANT DRIFT.** One requirement present in the source was missing from the spec,
and one claim the spec inherited from the PRD is contradicted by the source's own measurement.

**After remediation: ✅ ALIGNED.**

---

## 3. Findings

| Severity | Category | PRD / source reference | Spec reference | Description |
|---|---|---|---|---|
| 🛑 **Significant** | **missing** | Jira comment, production Cypher: `MATCH (n)-[attr_e:HAS_ATTRIBUTE {branch:"-global-", status:"active"}]->(attr) … SET attr_e.to = latest_delete_time` | FR-001 (pre-fix) listed only `HAS_VALUE`, `IS_PROTECTED`, `HAS_SOURCE`, `HAS_OWNER` | The validated fix closes **the global `HAS_ATTRIBUTE` edge as well as the property edges**. The spec closed only the four property edges. Compounding the omission: FR-011 makes that same edge the *candidate anchor*, so leaving it open would keep every retired vertex a candidate on every future pass, forever. |
| 🛑 **Significant** | **missing** | Jira comment: *"use a subquery to ensure we properly handle the case where `HAS_ATTRIBUTE` is deleted, but `HAS_VALUE` is not, or vice versa"* | Absent entirely | **Half-closed vertices exist in the real data.** The source explicitly calls this out as a case requiring deliberate handling. The spec had no requirement for it, and — worse — FR-011's open-edge anchor structurally *cannot reach* such a vertex, so they would have survived the migration untouched. |
| ⚠️ Minor | **contradicted** | Issue: ~512 effectively-live vs **~6,400 effectively-deleted nodes still holding an active global value**, measured with a query anchored on `(:Node)-[:HAS_ATTRIBUTE]->(:Attribute)` | US2 "Why this priority": branch-deletion orphans "are the dominant shape in the reported incident" | The only quantified evidence describes the **still-linked** shape. The measuring query is anchored on a node→attribute path and so *structurally cannot see* the fully-detached shape it is being cited as evidence for. The claim is unsupported, not disproven — but it was carrying weight it should not: it justified the plan's sequencing and the Complexity Tracking argument for hard-deleting. |
| ⚠️ Minor | **dropped (deliberate)** | Issue, Expected Behavior bullet 2: *"Uniqueness-constraint validation … should not scan attribute values belonging to nodes that are effectively deleted in the relevant branch view"* | Out of Scope | Declined by the PRD with a reasoned argument, and the spec followed the PRD faithfully — so this is **not** spec-vs-PRD drift. But it *is* an Expected Behavior item from the filed issue that this feature will not deliver, and it was recorded only as a bare scope exclusion. A reviewer should knowingly accept it. |
| ✅ None | — | Jira comment: latest-delete-time computed across every branch the object was created or merged on, requiring none still active | FR-015, FR-004 | **Confirms** the spec. The production logic and the spec's predicate agree, independently derived. |
| ✅ None | — | Jira comment: `IN TRANSACTIONS` used explicitly "to be safe with TRANSACTIONS than OOM" | FR-016 batching, the 500-row cap | **Confirms** the spec's batching requirement, and the motivation matches. |
| ✅ None | — | Issue: one value attached to 32 distinct mostly-deleted node objects | FR-017 shared-`AttributeValue` handling | **Confirms** that value sharing is real and at scale, not hypothetical. |

Not drift: the spec generalises the production script from per-kind/per-attribute-name to
label-anchored, and extends it from attributes to relationships with the two-peer form. Both are
expansions of correctness, which the alignment rules explicitly permit.

---

## 4. Action

One remediation pass, applied surgically rather than by regenerating the artifacts.

**Why surgical.** The prescribed loop re-invokes specify → plan → critique → tasks. Here the drift
was two precisely-located missing requirements and one overclaimed sentence, while the artifacts
already carried grounded research and four applied critique fixes. Regenerating would have risked
discarding verified work to re-derive it — a worse outcome than a targeted edit. The loop's
purpose (fix the drift, then re-verify) is met; step 5c was re-run against the same source view
after editing.

### Requirements added

| New | Content |
|---|---|
| **FR-001** (revised) | Closure covers the owning global `HAS_ATTRIBUTE` edge and **every** open global edge of the vertex, not only the four named property edges |
| **FR-002** (revised) | For relationships, closure covers **both** global `IS_RELATED` edges as well as the property edges |
| **FR-002a** (new) | Owning edge and property edges closed **independently**, each only where still open, so half-closed vertices end fully closed |
| **FR-011** (revised) | Open-edge anchor scoped explicitly to the **runtime** enforcement points |
| **FR-011a** (new) | The **migration** widens the anchor to `status: "active"` regardless of `to`, with same-UUID protection moved from the anchor into the predicate |
| **FR-016** (revised) | Migration closes owning edges too, and covers the half-closed shapes |
| **SC-004** (revised) / **SC-004a** (new) | Zero *open global edges* including the owning edge; re-running the migration reports zero |

### The design tension this surfaced, and how it was resolved

FR-002a and the original FR-011 were in direct contradiction: an anchor restricted to **open**
owning edges can never reach a vertex whose owning edge is **already closed**. Widening the anchor
globally would have broken the same-UUID protection that FR-011 exists to provide.

Resolved by splitting the anchor by caller, since the two callers have genuinely different needs:

- **Runtime** keeps the open-edge anchor. It is selective (on the node-delete hot path) and no
  *new* half-closed state can arise once FR-001/FR-002 close both groups in one pass.
- **The migration** widens the anchor and takes its same-UUID protection from the predicate
  instead — retained if *any* linked node vertex is live with an active owning edge, which is what
  the invariant literally says and is strictly stronger than the anchor-based protection. Safe
  there because it is batched and off every hot path.

### Corrections

- US2's "dominant shape" claim replaced with the actual measurement, an explicit statement that it
  covers only the still-linked shape, and a note that the detached shape is **unquantified** and
  the migration must not be sequenced on either dominating.
- The declined uniqueness-validation Expected Behavior item promoted from a bare scope exclusion to
  a quoted, argued divergence flagged for reviewer confirmation.
- Prior-art section added to `plan.md` recording the production Cypher's shape and the three ways
  this design generalises it.

### Files updated

`spec.md`, `plan.md`, `data-model.md`, `contracts/retirement-component.md`, `quickstart.md`,
`tasks.md` (7 tasks added: T009a, T010a, T012a, T012b, T031a, T040a, and T014/T042 revised).

### Carried forward for maintainer input

- The critique's open question **P1** is now partly answered and partly sharpened: the still-linked
  shape is confirmed at ~6,400 nodes; the detached shape remains unmeasured. The hard-delete branch
  of `m076` is still needed, but its Complexity Tracking justification can no longer lean on
  "dominant shape".
- The declined validator-filtering Expected Behavior item needs explicit acceptance, since the
  filed issue asks for it.
