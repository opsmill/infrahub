# Round 16 feedback: one-list rev 2 and rev 3

Source: three notes written by the owner in the design-jam session on 2026-11-18, copied
word for word.

> it seems weird to have nothing for failed loads fi there is no number or badge

> what about the fonts changes for the numbers, or migrations names, we dont really do it in
> the rest of the app

> icon is not verticaly aligned for failed loads

## Triage, 2026-11-18

1. Failed loads with no chip: **addressed** in one-list rev 3. A failed load shows a red
   chip with a cross, the same width as a version chip, in its row and in its details
   header, and still says "no version" after its date. Every row of the list starts with a
   chip: a version (applied), the version it gets when applied (staged, dashed border) or a
   cross (failed, never gets one).
2. Monospace font: **addressed** in one-list rev 4. The app uses a monospace font in about
   10 places, for commit hashes, node IDs and error text. Rev 4 shows the names of schema
   changes, kinds and fields, and the version numbers, in the app's font, with tabular
   figures so the numbers line up. Commands to copy and node IDs stay monospace. Rev 3 keeps
   the monospace font, so the two can be compared.
3. Cross not centred vertically: **addressed** in rev 3 (the cross is centred with a flex
   box), before rev 4 was made from it.
