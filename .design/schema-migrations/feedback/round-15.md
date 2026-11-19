# Round 15 feedback: one-list rev 1, review-page rev 1, schema-tab rev 11

Source: two notes written by the owner in the design-jam session on 2026-11-18, copied word
for word.

> lets go with one list, it seems easier for user to understand where he is in the workflow
> instead of having another dedicated view

> in the list there is a dash instead of the revision number, why and how to change that to
> make it more clear what is happening

## Triage, 2026-11-18

1. Page structure: **addressed**. One list is the direction from now on. Staged tab and Review
   page stay in the panel unchanged, as the record of what was compared. The reasons are in
   `03-decisions.md`, "Page structure: one list".
2. The dash in the version column: **addressed** in one-list rev 2.
   - Why it was there: a schema change gets its version only when it is applied, so a staged
     change and a failed load have none. Rev 1 showed "-", the empty value of the Diff tab
     (round 12), which reads as missing data rather than as a step of the workflow.
   - Rev 2: the staged row shows the version it gets when applied, 00031, in a chip with a
     dashed border, and says "Becomes 00031 when applied" ("on the branch" in a proposed
     change). The details header shows the same dashed chip.
   - A failed load never gets a version: its row has no chip and says "no version" after its
     date.
