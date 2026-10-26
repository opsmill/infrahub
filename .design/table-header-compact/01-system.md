# System inventory — table-header-compact

## Covered

- `Button` from `@infrahub/ui` (`sm`, `xs`, `ghost`, `outline`, `shape="square"`) for Add, Columns and the icon-only Columns trigger.
- `PopoverTrigger` and `Popover` from `@infrahub/ui`, with the existing `ColumnsEditor` as the popover body.
- `ColumnsPicker` (the labelled Columns button with its customised-column count badge).
- `DataTable`, `InfiniteScroll`, `getObjectTableColumns`, `getRelationshipActionsColumn`, `ObjectTableEmpty`: the table is the production table, unchanged.
- `Card`, `CardHeader` from `@infrahub/ui` for the repository cards; `FieldSchemaIcon` for field icons; the `grid-cols-detail-row` token (200px label column).
- Page precedent: the object list toolbar (`objects-manager-toolbar.tsx`) puts table controls on the left and the primary create button on the right (`ml-auto`), in one row.

## Close

- `ObjectDetailsCard` takes `title` and `caption` but always renders the caption on a second line.
- `ObjectDataRow` renders the label in a react-aria `Button`, which centres wrapped text, inside a fixed `h-8` cell.
- `RelationshipTable` renders its own toolbar row and has no slot for actions from its host.

## Missing

- No slot for actions in the detail-page tab strip. The "In the tab strip" direction needs one; the tab strip already scrolls horizontally, so the slot would have to sit outside the scroll area.

## Where the prototype mounts

Inside the app layout (real sidebar and header), at `/_proto/table-header-compact`, with the history panel's `frame` set to the measured content area. Every direction changes only what sits inside the content area. The object header and tab strip are static replicas (`chrome.tsx`) because two directions move controls into them; the table, its data and its permissions are real.
