# Spec/Ask Alignment Check: IFC-2886

**Date**: 2026-07-10 | **Feature dir**: `specs/ifc-2886-priority-api-backpressure/`

## 1. Source

- **Source PRD**: Jira Story [IFC-2886](https://opsmill.atlassian.net/browse/IFC-2886) — "Priority-aware API backpressure (server-side)". The full PRD was fetched from the ticket's `description` field via the Atlassian MCP integration (not a web-fetch fallback); the complete text was used as the source-of-truth view. No auth gate or truncation.
- **Compared against**: `spec.md` (post-critique state).

## 2. Verdict

**⚠️ MINOR DRIFT (proceeding)**

The spec faithfully carries every PRD requirement. All 9 functional requirements (FR-001…FR-009), all observability requirements (FR-OBS-1…7, plus the "all through `/metrics`" clause split out as FR-OBS-8), all five success criteria (SC-001…SC-005), every Key Entity, Edge Case, Assumption, Out-of-Scope item, and Governance Gate are present and semantically intact. The only deltas are **consolidations and justified additive refinements** — nothing from the PRD is missing, softened, semantically changed, or contradicted.

## 3. Findings

| Severity | Category | PRD reference | Spec reference | Description |
|----------|----------|---------------|----------------|-------------|
| Minor | changed (consolidated) | PRD User Story 6 ("operator … see how much traffic arrives with no priority header") | spec US5 Acceptance Scenario 2 + FR-OBS-7 | The dedicated "adoption tracking" user story is folded into US5 (observability) rather than kept as a standalone story. The requirement itself (a no/invalid-priority counter for adoption) is fully retained as FR-OBS-7 and an US5 acceptance scenario. No loss of substance. |
| Minor | changed (consolidated) | PRD User Story 7 ("developer … shedding algorithm and concurrency primitive covered by deterministic unit tests") | spec Requirements FR-003/FR-004/FR-008 *Verify* clauses + `checklists/requirements.md` notes; tasks T012/T015/T016 | The "developer wants deterministic tests" story is expressed as per-FR verification clauses and realized in the tasks (fake-clock CoDel, slot-pool cancellation) rather than as a separate user-story section. Requirement retained; no distinct story block. |
| Minor | added (justified) | PRD Assumptions ("ships inert until callers set the header … all traffic defaults to `normal`") | spec SC-006 | SC-006 ("admission layer is inert on a default deployment") makes the PRD's existing "ships inert" assumption a measurable success criterion. This is an elaboration of a PRD statement, not new scope. |
| Minor | added (justified) | PRD SC-001 (discovery-measured); PRD Constitution Alignment V | spec SC-001 (sharpened) + Assumption "slot contention is the binding constraint" | The critique (E1) added a requirement that the SC-001 discovery scenario also confirm the sojourn signal actually rises under overload (so the mechanism sheds rather than admitting into a slow DB). This refines — does not weaken — the PRD's own discovery-measured SC-001 and serves PRD Constitution principle V. |
| Minor | added (justified) | PRD Solution Overview + Assumptions ("frontend → high … until then all traffic defaults to normal") | spec Assumption "rollout is kill-switch-guarded and sequenced with the frontend" | The critique (X1) surfaced the implication that, before the frontend sends `X-Priority: high`, interactive traffic is `normal` and shed like background under overload. This documents a consequence of the PRD's own rollout assumption; it adds no new build scope (the kill-switch is an implementation detail in plan.md, not a new spec FR). |
| Minor | added (clarifying) | PRD Constitution Alignment VII ("per-worker, coordination-free") | spec Assumption "per-worker, coordination-free" | Promotes a PRD design principle to an explicit assumption. Consistent with the PRD. |
| Info | added (bounding) | PRD "No GraphQL schema change"; "Data/persistence: none" | spec Out of Scope (last bullet) | Spec restates these as explicit out-of-scope items. Pure clarification. |

**No 🛑 significant-drift findings.** Specifically checked and clear:
- Nothing missing: every FR, FR-OBS, SC, entity, edge case, assumption, and out-of-scope item from the PRD appears in the spec.
- No semantic changes: `X-Priority` classes, default-`normal`, sojourn/CoDel mechanism, `429 + Retry-After`, per-class gradient (`low`→`normal`→`high`), per-worker capacity-from-pool-size, and the cooperative trust model are all preserved verbatim in meaning.
- No softened acceptance criteria: SC-002…SC-005 are intact; SC-001 was made stricter, not looser.
- No contradicted constraints: server-side-only scope, no-DB-schema/no-GraphQL/no-new-dependency, and the deferred fast-follows all match.

## 4. Action

**Proceed to completion.** The drift is limited to two PRD user stories being consolidated into functional/observability requirements + tasks (substance retained) and a handful of additive refinements that are all derived from the PRD's own assumptions/criteria or from the Must-Address critique finding. No remediation pass required (remediation counter unused: 0/2). `tasks.md` stands.
