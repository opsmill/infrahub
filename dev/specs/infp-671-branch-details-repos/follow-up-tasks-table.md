# Follow-up ticket: one tasks table across the app

Filed as [IFC-3245](https://opsmill.atlassian.net/browse/IFC-3245) (Draft).

**Type:** Story (frontend). **Epic:** INFP-671, or the Tasks area if there is one.
**Depends on:** INFP-671 branch details (ships `TasksTable` and IFC-3130's `TablePagination`).

## Problem

The app lists tasks in two ways:

- **`TaskItems`** is used on /tasks, the object Tasks tab and the proposed change Tasks tab. It
  has the columns Title, Branch, State, Related nodes, Progress, Workflow and Updated at, and a
  search filter. It uses the older `Table` and a URL-driven `Pagination`.
- **`TasksTable`** is the branch details page's table. It has the columns Title, State, Workflow,
  Related and Updated. The column set is configurable, it uses IFC-3130 pagination at a fixed
  height, and it shows short workflow labels ("Import", "Generator", "Proposed change").

The same task looks different depending on the page, and improvements land in one place only.

## Proposal

Move the three `TaskItems` pages onto `TasksTable`, and improve it once:

1. **Columns per page:**
   - /tasks: all columns.
   - Object Tasks tab: no Related column (the page is the related node).
   - Proposed change Tasks tab: no Branch column.
   - Branch details: no Branch column (already done).
2. **Pagination:** IFC-3130 `TablePagination` everywhere, server-side (`limit`, `offset`, `count`).
   Each table keeps its own page parameter, so two tables on one page don't share it.
3. **Filters on /tasks:** keep the search and the existing **state filter** (`TaskFilters` →
   `TasksFilterForm`'s State dropdown, read from the `state__value` URL filter) through the
   `TasksTable` migration; the branch page's "N failed" link relies on it. Consider a workflow
   filter based on the short labels.
4. **Progress:** show it only for running tasks, inside the State cell, instead of as a column that
   is empty most of the time.
5. **Related column:** make it stable. It shows the first related node's kind, and the backend's
   order changes: generator runs show "Generator Instance" on some rows and "Device" on others.
   Prefer a fixed priority (repository, then definition, then target), and link to the node.
6. **States:** use the same loading skeleton, empty state and "couldn't load" state as the branch
   page.
7. **Workflow labels:** extend `getWorkflowLabel`. Unknown ids fall back to humanized text. List
   the ids still humanized, taken from a real instance's task list.
8. **Remove `TaskItems`** once nothing imports it.

## Acceptance

- /tasks, the object Tasks tab, the proposed change Tasks tab and the branch details page all
  render through `TasksTable`. `TaskItems` is deleted.
- A task shows the same state badge, workflow label and Related label on every page.
- The state filter on /tasks works, and the branch page's "N failed" link opens /tasks
  filtered to that branch and state.
- Pagination: exactly 10 tasks shows no pager, and 11 shows one. A page past the end falls back to
  the last page.
- Component tests for each column preset. The e2e tests that use the old table's selectors are
  updated.

## Out of scope

- Task details page redesign.
- Backend changes (task ordering, `last_import_task`). Those are in `follow-ups.md`.

## Suggested

A short design pass on /tasks itself: filters bar, density, the Progress display. Run it before
implementation, because it's the page people land on from every "Open in Tasks" link.
