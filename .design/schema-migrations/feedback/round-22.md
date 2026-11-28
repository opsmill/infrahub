# Round 22 feedback: collapsible-sections rev 4

Source: notes written by the owner in the design-jam session on 2026-11-18, copied word for
word.

> let's stick to the forst prototype with collapsible sections and links in the header
>
> should the Impact calculated 14 minutes ago banner be in the header too with the button
>
> improve the ui of the top banner with links and buttons to make it user friendly so it's
> easy to see all the different informations, we can also select what needs to be
> displayed and what can be removed

> it seems weird to have sections titles bigger than revision title at the top
>
> we can change all the different sizes everywhere to make it consistent now and easy to
> track the informations

## Triage, 2026-11-18

1. Keep only collapsible sections with links: **addressed**. Titles at the edges, Short
   sections first and Section tabs are removed from the panel; git keeps them at
   `bc67d20136`.
2. The impact line in the header: **addressed** in rev 5. The plain "Impact calculated 14
   minutes ago" line and Recalculate move to the header, next to Apply, because the
   numbers Apply relies on come from that calculation. "Data changed on the branch since
   then is not counted" moves to a tooltip. An out-of-date or failed calculation shows in
   the header in colour; the conflict and out-of-date banners stay in the panel, because
   they ask for an action before Apply. A knob puts the line back in the panel.
3. The header: **addressed** in rev 5, in three bands: the change with its actions, one line
   of facts, and the section links with an icon each (the same icon as on the section
   title). Header knobs choose what it shows: the impact calculation, when the change was
   staged and on which revision, View the staged schema, the number of operations (off by
   default, it repeats the Schema difference count) and the previous schema change (off
   by default). While applying, the facts line shows the progress text and View the task.
4. Sizes: **addressed** in rev 6 with one type scale (see `03-decisions.md`). Rev 6 also
   moves View the staged schema to the end of the links band, so the facts line no longer
   wraps at 1440 px, and removes the empty band above the first section title.
