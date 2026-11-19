# Round 18 feedback: the details panel orders

Source: two notes written by the owner in the design-jam session on 2026-11-18, copied word
for word.

> what about collapsible sections for schema differences and runs on this branch

> and sticky headers

## Triage, 2026-11-18

1. and 2. **Addressed** with a fifth direction, "Collapsible sections"
   (`collapsible-sections` rev 1), made from one-list rev 4:
   - every section title of the details panel opens and closes its section, with a plain
     chevron, distinct from the boxed chevron of a kind card and the caret of a row;
   - a closed section shows a summary: "19 kinds", the last run and its status, or the
     migrations and nodes changed;
   - a section title stays under the details header while its section scrolls, and the
     header of an applied change or a failed load now stays in view too;
   - what the viewer opens or closes stays so when they select another schema change;
   - a "Schema difference starts" knob compares three defaults: collapsed when it has more
     than 5 kinds, open, or collapsed;
   - "would fail" on a kind opens the Would fail section when it is closed.
