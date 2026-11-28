# Round 12 feedback: schema-tab rev 9

Source: notes written by the owner in the design-jam session on 2026-11-18, copied word for
word.

1. on hover
2. operation order seems ok, the one that would fail are in the tab right ? what is the goal
   of the tab, is it only to highlight or is it a dedicated view ?
3. for columns i want visual consistency, the dash character seems not right though, a
   simple - could do the trick or find another alternative
4. can you try to have change / before / after a bit lighter so it's less present in the ui

## Triage, 2026-11-18

1. Schema viewer link on hover: **addressed** in schema-tab rev 10.
2. Order and the Would fail tab: order **kept**. The tab is a separate view, the list of
   nodes to fix; answered in the session and recorded in `03-decisions.md`. Rev 10 makes
   "would fail" open the tab on the matching group.
3. Empty value: **addressed** in rev 10 with "-", as on the Diff tab; the Before column
   stays on every row.
4. Lighter column labels: **addressed** in rev 10; the colour is below the WCAG contrast for
   text, noted in `03-decisions.md`.
