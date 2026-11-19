# Round 2 feedback: combined rev 1, and one note on "In the review" rev 1

Source: a *Copy all notes* block pasted by the owner in the design-jam session on
2026-11-16. The block carries no reviewer name. The notes are copied word for word.

<!-- design-jam:schema-migrations -->
## design-jam feedback — schema-migrations

### Current knobs (In the review · rev 1)
- Screen (`view`): Staged schema change
- Impact calculation (`impact`): done

### Schema page + review · rev 1 — 1 note, 1 open
http://localhost:8097/_proto/schema-migrations?dj.variant=combined&dj.rev=1&dj.k.view=Staged+schema+change&dj.k.impact=done

1. **InfraDevice** — titles are not clear compared to content, corners are not displayed correctly for the rounded border
   `div > div > div > section:nth-of-type(2) > div > div > section:nth-of-type(1) > h4`

### In the review · rev 1 — 1 note, 1 open
http://localhost:8097/_proto/schema-migrations?dj.variant=review&dj.rev=1&dj.k.view=Staged+schema+change&dj.k.impact=done

1. **StagedHistory6** — it does not look very clear to have a side panel like that in the proposed changes, on small screens it wont work
   `div > aside > nav > div`

## Triage, 2026-11-16, agreed with the owner

1. Schema page + review, note 1 (kind titles not clear, rounded corners wrong): **addressed**
   in combined rev 2. Each kind is a heading with its operation count, the operations sit
   indented below it, and the box inside a box is removed.
2. In the review, note 1 (side panel unclear, does not work on small screens): **declined**.
   The side panel was rejected in round 1 for the same reasons, and the combined direction
   has no side panel.
