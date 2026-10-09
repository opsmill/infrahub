# Alignment Check: spec.md against the source design

## Source

- [Licensing in Infrahub Enterprise](https://app.notion.com/p/3ef228b830258130b788d4e2d9c2d357), the design doc, read through the Notion connector on 4 Oct 2026 (the page is not reachable through a plain web fetch).
- The inline ask: the first delivery part, for this repository only. The Enterprise checker and accepted issuers are out of scope, and the SDK and MCP warnings are follow-ups.

Only the parts of the design that land in this repository are compared. Decisions that live in opsmill/infrahub-private (signature verification, accepted issuers, key rotation, the license command, the daily log) are checked only for being listed as out of scope.

## Verdict

⚠️ MINOR DRIFT (proceeding)

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
| --- | --- | --- | --- | --- |
| Minor | dropped (by scope) | D12 rollout gates and signals (every paying customer issued, install in under 15 minutes, 80% of connected deployments report a license ID, renewals 30 days early) | Success Criteria SC-001–SC-006 | The design's success criteria belong to the first and second licensing releases. The spec's criteria cover only this delivery, as the ask scopes it. Not drift in substance, but readers of the spec do not see the rollout gates |
| Minor | added | D11 "the cloud telemetry processor has to accept it" | Assumptions, release gate | The spec turns the design's cost into an explicit release gate. A necessary clarification raised by the critique, consistent with the design |
| Minor | added | D9 banner audience | Edge cases, User Story 3 | No banner meant for super-admins until the permission check answers. A clarification of how D9 applies in the UI, not a new requirement |
| Minor | added | Behaviour row "A licence set on Community is ignored, and Infrahub logs that once" | FR-009, User Story 1 scenario 5 | Extended to Enterprise with no license service registered, which follows from the activation gate in D7 |
| Minor | added | D8 "days left" | data-model.md (rounding rule) | Rounding direction for days remaining and days since expiry; detail the design did not specify |

No requirement, goal or non-goal from the in-scope part of the design is missing:

- every behaviour row that applies to this repository has a matching requirement or edge case;
- D1, D2, D3, D4, D5, D8, D9, D10 and D11 are covered;
- D6 and D7 are reflected as the explicit dependency (FR-024) and the activation gate (Assumptions);
- D12 is covered as the release mode.

No semantics changed, and no PRD constraint is contradicted.

## Action

Proceed. No remediation pass needed. The rollout gates stay in the design doc, and are carried by the first and second licensing releases.
