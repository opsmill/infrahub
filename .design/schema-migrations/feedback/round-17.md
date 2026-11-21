# Round 17 feedback: one-list rev 4

Source: notes written by the owner in the design-jam session on 2026-11-18, copied word for
word.

> it looks great

> in the schema schanges view, if we have a lot of changes,would fail or runs are at the
> bottom which is not ideal, what could be done here, provide different solutions

> remove old prototypes and add new ones for those solutions

## Triage, 2026-11-18

1. One-list rev 4 approved (version chips, red chip for failed loads, the app's font).
2. Would fail and Runs at the bottom of the details panel: **answered** in the session with
   five solutions:
   - short sections first;
   - links to the sections in the header that stays in view;
   - tabs in the details panel;
   - kinds collapsed by default;
   - counts as links.
3. Prototypes: **addressed**. Four new directions, each made from one-list rev 4:
   - "Short sections first" (`short-first`), with the count link;
   - "Section links" (`section-links`);
   - "Section tabs" (`section-tabs`);
   - "Collapsed kinds" (`collapsed-kinds`).

   "One list" stays at rev 4 as the current order. Staged tab, Review page and One list
   revs 1 to 3 are removed from the panel; git keeps them at `ec383abdf9`.
