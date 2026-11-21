# Round 14 feedback: schema-tab rev 11

Source: two notes written by the owner in the design-jam session on 2026-11-18, copied word
for word.

> if we challenge the way we built the different pages, do we find another good solution /
> use emil skills to assess this issue

> can you create 2 prototypes to see the differences, keep the current version aside since
> it still works

## Triage, 2026-11-18

1. Challenge the page structure: **addressed** with an assessment in the session, based on
   the `emil-design-foundations` information architecture rules and the `emil-ui-review`
   method. It found:
   - three levels of tabs before the impact: branch tabs, then "Schema changes | Staged |
     Diff", then "Schema difference | Would fail";
   - sub-tabs that mix a list of records, one pending change with actions, and a comparison
     with main;
   - the staged change and the applied changes in different sub-tabs, although the
     investigation describes one record whose status moves from staged to applied or failed;
   - "Diff" and "Schema difference" next to each other, comparing different things;
   - a different set of sub-tabs on the branch, the proposed change and main.
2. Two prototypes: **addressed** with two new directions in the panel. The current one stays
   as "Staged tab", unchanged at rev 11.
   - "One list" rev 1 (`dj.variant=one-list`).
   - "Review page" rev 1 (`dj.variant=review-page`).
