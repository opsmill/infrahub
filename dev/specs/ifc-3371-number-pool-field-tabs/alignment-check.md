# Spec/Ask Alignment Check

## Source

- Inline ask passed to the prep run (IFC-3371 description: two tabs, Value sends the number only,
  pool tab with an optional number; attach with a number, allocate without).
- Jira ticket [IFC-3371](https://opsmill.atlassian.net/browse/IFC-3371), created on 2026-10-09 from
  the same request; its content was already in this session, so it was not fetched again.

## Verdict

⚠️ MINOR DRIFT (proceeding)

## Findings

| Severity | Category | PRD reference | Spec reference | Description |
|---|---|---|---|---|
| Minor | changed | "a number input below the pool selector" | FR-003 | The number input appears once a pool is picked, not before. A number without a pool has no state to live in (critique E1); the user-visible journey is unchanged. |
| Minor | added | — | FR-010, US4 | The edit form opens on the pool tab for a tracked number. The ask does not cover edit mode; this is a needed clarification and differs on purpose from IFC-2764 FR-017. |
| Minor | added | "Value tab: no pool records it" | FR-009 | On an edit form, saving from the Value tab over a tracked number sends `from_pool: null` (detach). This is how "no pool records it" holds in edit mode. |
| Minor | added | — | FR-014 | Picking a pool pre-fills the number the node holds on an edit form, so an existing number is not replaced by accident. |
| Minor | added | — | FR-016, FR-017 | Value tab placeholder shows the current number; badge text says "recorded in the pool" for number pools. Small UI wording from the critique. |
| — | open | "Not decided yet: the labels of the two tabs" | FR-001 | The spec keeps the IFC-2764 labels "Value" and "From pool". Not a drift; the ticket's open question is answered by reuse. |

No requirement from the ask is missing, softened or contradicted.

## Action

Proceed. No remediation pass used.
