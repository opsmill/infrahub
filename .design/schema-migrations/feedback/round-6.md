# Round 6 feedback: schema-tab rev 3

Source: notes written by the owner in the design-jam session on 2026-11-17, copied word for
word.

1. ensure to have proper empty srceens for each cases so it's clear what is happening, maybe
   provide actions if available
2. i don't understand why we have the same banner in both schama changes view and staged
   view, is it correct, is there something to change
3. schema differences are difficult to read and not very clear
4. also it looks quite inconsistent between the different views, the ui is never the same,
   what can be done, do we have common data that should look the same, are there ui
   components we can reuse across the different views and from the current app

## Triage, 2026-11-17

1. Empty screens: **addressed** in schema-tab rev 4. One empty state component for every
   case; the list is in `03-decisions.md`, "Empty and waiting screens".
2. Same banner in Schema changes and Staged: **addressed** in rev 4. It was the revision
   block. It is removed; the revision is the header of the Schema changes list.
3. Schema difference hard to read: **addressed** in rev 4. It reuses the Diff tab's rows and
   badges: Change, Before, After, one card per kind.
4. Inconsistent views: **addressed** in rev 4. One component per kind of data, from the app
   where one exists; the table is in `03-decisions.md`, "Same data, same component".

Awaiting the owner's review of rev 4.
