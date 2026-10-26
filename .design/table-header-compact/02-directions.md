# Directions — table-header-compact

Prototype: `http://localhost:8080/_proto/table-header-compact` (switch directions in the panel, or `?dj.variant=<id>`).

Shared knobs, read by every direction:

- `screen`: relationship tab, or the repository Details tab.
- `object`: device Interfaces (15 rows, generic relationship), country Site tab (5 children), country Site tab with no children (empty state).
- `deny`: render with no create permission (Add disabled).
- `branchHeader`: `two-lines` (today), `inline` ("On this branch · main"), `chip` (branch name in a bordered chip with a branch icon).
- `labelWrap`: `today` (centred, fixed height), `left` (left-aligned, minimum height, icon on the first line), `left-balanced` (as `left`, with balanced line lengths).

## Today (`baseline`)

Two right-aligned rows, one button each: Add, then Columns. About 96px between the tabs and the table header. Kept as the reference.

## One toolbar row (`one-row`)

- **Bet:** the relationship tab should look like the object list it is a filtered view of: table controls on the left, the primary Add on the right, one row.
- **Cost:** still one row (about 48px) of mostly empty space while the only table control is Columns.
- **Best for:** consistency with the list view, and room for search, sort and filters on the left later.

## In the tab strip (`tab-strip`)

- **Bet:** the tab strip has empty space on its right; using it removes the toolbar row, so the table starts directly under the tabs.
- **Cost:** needs a new slot in the tab strip, which scrolls horizontally on objects with many tabs (a repository has 9). The controls change with the selected tab, which is unusual for a tab strip. Requires `xs` buttons to fit the 44px strip.
- **Best for:** maximum vertical space for the table.

## Where it acts (`where-it-acts`)

- **Bet:** each control sits next to what it changes: Columns as an icon in the table's top-right header cell (above the row menus), Add in the object header next to Edit.
- **Cost:** Add in the object header reads as an action on the object, and it changes with the selected tab. The Columns icon has no text label and loses the visible customised-column count (shown as a colour change instead). The header cell is 40px wide, so the hit target is small.
- **Best for:** the densest layout; no new row and no tab-strip slot.

## Rejected before building

- **Both buttons right-aligned in one row** (Columns next to Add): differs from "One toolbar row" only in alignment, and contradicts the list-view precedent where table controls sit on the left.
- **Add in the table footer, next to the count:** `DataTable` owns its footer; the prototype cannot change it without editing production code, and an action under a long table is out of view.
