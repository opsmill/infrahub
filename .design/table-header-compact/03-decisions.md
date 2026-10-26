# Decisions — table-header-compact

Direction chosen: **Where it acts** (owner, 2026-10-26). Other directions stay reachable in the prototype.

- **No toolbar row above relationship tables.** Each control moves to what it changes, so the table starts directly under the tabs.
- **Columns is an icon button in the table's top-right header cell**, the empty cell above the row menus. It changes the table's columns, so it sits on the table.
- **The icon shows a dot when columns differ from the defaults, and its tooltip and accessible name say how many** ("Columns · 2 changed"). Rev 1 used colour alone, which some readers cannot see.
- **Add sits in the object header, as the leftmost button of the right-hand group.** When Add appears or disappears on a tab change, Refresh, Edit, Schema and Actions keep their positions. Rev 1 placed it between Refresh and Edit, which moved Edit on every tab change.
- **Add appears without animation.** Users switch tabs many times a session; a transition would only delay the header.
- **Add keeps today's label, "Add <relationship label>", and today's disabled state and tooltip** when the user cannot create. No truncation: the object title already truncates first, so the header stays one line at 1440px.
- **The IPAM and repository hosts of the relationship table get only the header-cell Columns icon**; they have no Add button today.
- **Deferred:** the "On this branch" card header and the wrapping of long field labels (owner's call); see `00-brief.md`.

## Rejected directions

- **Today:** about 96px of mostly empty space above every relationship table.
- **One toolbar row:** still a mostly empty row while Columns is the only table control.
- **In the tab strip:** needs a new slot in a strip that already scrolls horizontally on objects with many tabs.
