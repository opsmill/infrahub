# Round 20 feedback: collapsible-sections rev 2

Source: notes written by the owner in the design-jam session on 2026-11-18, copied word for
word.

> it's just weird if both sections are collapsed that only the first link is active even if
> we can see both, same if the runs are already visible nothing changes after clicking the
> link
>
> what could be done, do you have a fix or we cold also start from scratch to solve this
> issue where we have a panel, with 2 sections and both are important and we need to ensure
> that the user is aware of the existance of those sections

> build those as prototypes so i can compare

## Triage, 2026-11-18

1. The highlighted link and the link that does nothing: **answered** in the session. The
   highlight shows where the viewer is, which means nothing when every section is in view;
   the owner's need is to know which sections exist and what they hold. The links also
   repeat the section titles when the sections are closed.
2. Prototypes to compare: **addressed**.
   - The fix: collapsible-sections rev 3. No link is highlighted; a link opens its section,
     scrolls to it when needed and highlights its title for 1.2 seconds.
   - Titles at the edges (`edge-titles` rev 1): no links row; every section title is
     always on screen, in place, stacked under the header once passed, or stacked at the
     bottom edge until reached. A title at an edge takes the viewer to its section; a title
     in place opens or closes it.
   - Short sections first rev 2 (`short-first`, rev 1 restored from `e0dc74065a`): Would
     fail shows its first 2 fields and "Show all 48 nodes in 4 fields".
   - Section tabs rev 1 (`section-tabs`), restored from `e0dc74065a` unchanged.
