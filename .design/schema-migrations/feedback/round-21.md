# Round 21 feedback: the four ways to make both sections known

Source: notes written by the owner in the design-jam session on 2026-11-18, copied word for
word.

> short first wont work all the time
>
> i like fixed version of links in the header + a for collapsible and always displayed
> sections titles
>
> we can make the titles a bit more visible to better understand the different sections

> the diff icon (changed, removed, etc) is above the accordion title when scrolling, it must
> remain below

## Triage, 2026-11-18

1. Short sections first: **declined by the owner**, because the short section is not always
   short.
2. Header links (rev 3) with always-visible collapsible titles (edge-titles): **addressed**
   in collapsible-sections rev 4. A header link and a title stacked at an edge both open
   the section, scroll to it and highlight its title for 1.2 seconds. Merge into main is a
   section like the others in a proposed change.
3. More visible titles: **addressed** in rev 4. Each section title is a 44 px bar with the
   card header's grey background, a border above and below, and 16 px semibold text.
4. Diff icon above the section title: **addressed** in rev 4. Parts of the kind cards use
   the same z-index as the titles and come later in the page, so they were drawn on top.
   Each section's content now has its own stacking context, which keeps it below the
   titles.
5. Found while checking rev 4: in a proposed change, the details card clipped its content,
   so the header and the titles did not stick to the area that scrolls. Rev 4 lets the card
   grow there; its header and titles now stay in view.
