# Decisions — table-header-compact

Direction chosen: **One toolbar row** (owner, 2026-10-26), replacing the earlier pick of "Where it acts". Other directions stay reachable in the prototype.

- **One toolbar row above relationship tables**: Columns on the left, Add on the right (`ml-auto`). It matches the object list toolbar, where table controls sit on the left and the create button on the right.
- **The row keeps today's controls unchanged**: the labelled `ColumnsPicker` with its count badge, and `RelationshipsButtons` with its label, disabled state and tooltip.
- **The IPAM and repository hosts of the relationship table keep a row with only Columns**; they have no Add button today.
- **Deferred:** the "On this branch" card header and the wrapping of long field labels (owner's call); see `00-brief.md`.

## Rejected directions

- **Today:** two rows of one button each, about 96px of mostly empty space above every relationship table.
- **Where it acts** (picked, refined to rev 2, then reversed by the owner on 2026-10-26; reason not recorded): Add in the object header, Columns as an icon in the table's header corner. Its costs were already listed in `02-directions.md`: Add reads as an action on the object and changes with the tab, and the icon-only Columns hides the customised-column count behind a tooltip.
- **In the tab strip:** needs a new slot in a strip that already scrolls horizontally on objects with many tabs.
