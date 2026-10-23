# Commits tab pending badge: inventory

Read from `develop` at the start of the run. Paths are relative to `frontend/app/src/` unless
they start with `frontend/packages/`.

## Covered

### Tab bar and tab primitives

- `LinkTab` (`shared/components/ui/link.tsx`): `NavLink` with `inline-flex h-11 items-center gap-2
  truncate border-b-2 px-3 py-2 font-medium text-sm`. The active tab is
  `border-custom-blue-600 text-custom-blue-600`; an inactive tab is `text-foreground-muted`. Any
  child (label, badge, icon, spinner) sits in the `gap-2` row. `scrollIntoViewOnActive` scrolls the
  active tab into view. Active state comes from `useMatch({ path: to, end: true })`, so it needs a
  router and a real `to`.
- `ObjectDetailsTabs` (`entities/nodes/object/ui/object-details/object-details-tabs.tsx`):
  `ScrollArea scrollX scrollY={false} scrollBarClassName="hidden"` around
  `<nav aria-label="Tabs"><Row className="items-end gap-4 px-4">`. Order on a repository:
  Details, one `RelationshipTab` per visible relationship, Tasks (`ObjectTaskTab`), Objects
  (`RepositoryObjectsTab`), Commits (`RepositoryCommitsTab`). Commits is always the last tab.
- Tab with a count, the pattern every other tab uses (`entities/nodes/object/ui/object-tabs.tsx`,
  `entities/repository/ui/repository-objects-tab.tsx`):
  `<Badge className="rounded-full font-medium text-subtle">{count}</Badge>`, and `<Spinner />` from
  `@infrahub/ui` while loading. `ProposedChangeTab`
  (`entities/proposed-changes/ui/tabs/proposed-change-tab.tsx`) uses the same pill with
  `text-foreground-muted`.
- Tab with a leading icon and a coloured count: `ObjectDetailsTab`
  (`entities/nodes/object/ui/object-details/object-details-tab.tsx`, IPAM) renders a schema
  `Icon`, the label, then `<Badge variant="blue" className="rounded-full font-normal">`. This is
  the only tab in the app with an icon or a non-grey count.
- The Commits tab today (`entities/repository/ui/repository-commits-tab.tsx`): the grey count pill
  plus `<span className="sr-only"> pending import</span>`. The count comes from
  `getPendingImportCount` (`entities/repository/domain/rules/get-pending-import-count.ts`): 0 under
  `IN_SYNC`, `pending_count` under `BEHIND`, `null` (no badge) for every other condition. The
  spinner shows while `isLoadingFirstPage` is true.

### Badge and count variants

- `Badge` (`shared/components/ui/badge.tsx`), CVA `badgeVariants`, base
  `rounded-md border px-1.5 py-0.5 font-semibold text-xs`. Variants: `white`, `gray` (default),
  `dark-gray`, `green`, `red`, `blue`, `yellow`, `purple`, `gray-outline`, `lightgray-outline`,
  `blue-outline`, `yellow-outline`, `green-outline`, `red-outline`.
- `CountBadge` (`shared/components/buttons/count-badge.tsx`): raised cyan pill
  (`h-5 min-w-5 rounded-full tabular-nums inset-shadow-raised`) used on the sort, filter and
  column pickers to count active settings. It is the only count in the app that uses
  `tabular-nums`.
- `formatNumberDisplay` (`shared/utils/number.ts`): `Intl.NumberFormat("en-EN")`, so 1284 becomes
  "1,284". No tab uses it today.

### Attention and status signals already in the app

- Status tokens (`frontend/packages/ui/src/styles/theme.css`): `warning` (amber) with
  `-surface`, `-strong` and `-border`; `info` (sky) with `-surface`; `success`, `danger`. Theming
  doc rule: warning is amber, not yellow; info is sky, not blue or cyan (cyan belongs to `accent`
  and `ring`, blue-violet to `active`).
- `Pulse` (`shared/components/ui/pulse.tsx`): absolutely positioned 8px dot with a ping
  animation, tones `info` and `danger`. Used on the header's `RepositorySyncStatus` button
  (`entities/repository/ui/repository-sync-status.tsx`), where a red pulse at the corner of the
  Git icon means "repositories failed to import on this branch".
- Static dots: `size-2 rounded-full` markers in
  `entities/repository/ui/repository-activity-card/activity-markers.tsx`,
  `shared/components/ui/timeline-border.tsx`.
- Inline warning icon with a tooltip: `repository-row.tsx`
  (`entities/repository/ui/branch-repositories/`) renders lucide `AlertTriangleIcon`
  `size-3.5 text-warning` inside `Tooltip nonInteractiveTrigger`, with `role="img"` and an
  `aria-label`.
- Warning band: `repository-error-band.tsx` and the commits header notice
  (`border-warning-border bg-warning-surface text-warning`).
- Icon chip with a tooltip: `BranchGitSyncBadge`
  (`entities/branches/ui/branch-list-item/branch-git-sync-badge.tsx`), a `rounded-full
  bg-custom-blue-700/10 p-1.5` circle holding `mdi:source-branch`, tooltip "Synced with Git".
- `GitStatePill` (`entities/repository/ui/branch-repositories/git-state-pill.tsx`): a
  `ColorDisplay` pill for the repository sync status.

### Overlays and icons

- `Tooltip` (`frontend/packages/ui/src/components/tooltip/tooltip.tsx`): react-aria, 200 ms open
  delay, `nonInteractiveTrigger` for a span or badge. A trigger inside a `LinkTab` must use
  `nonInteractiveTrigger`, or the tooltip trigger and the link compete for focus.
- Icons: two systems. `lucide-react` in about 112 files (current default); iconify through
  `Icon` (`shared/components/display/icon.tsx`, `mdi:*` names) in about 27 files. The repository
  and branch Git signals use `mdi:source-branch`.
- `@infrahub/ui` exports used here: `ScrollArea`, `Spinner`, `Tooltip`, `Popover`, `Card`.
  `@infrahub/ui` has no `Badge`, no `Tabs` and no indicator component; those live in the app's
  `shared/components/ui/`.

## Close

- `Badge` colour variants use fixed palette classes (`yellow` is `bg-yellow-100 text-yellow-900`
  plus `dark:` overrides; `blue` is `custom-blue-700`), not the status tokens. A warning-toned
  count drawn with `variant="yellow"` breaks the theming rule that warning is amber through
  `--warning`. Missing: a `warning` (and `info`) variant built on `bg-warning-surface
  text-warning border-warning-border`.
- `Pulse` has only `info` and `danger` tones, is absolutely positioned and always animated.
  Missing: a `warning` tone and a static (no ping) form that sits in a flex row next to a label.
  A permanent ping on a tab that stays behind for days is noise.
- `CountBadge` has the right number treatment (`tabular-nums`, fixed height) but its cyan tone
  means "settings applied", and it carries no state colour.
- `Tooltip` works on a badge, but a tooltip alone cannot carry the "import" or "rebase" meaning:
  a reader who glances at the tab bar does not hover. The tooltip can only add detail.
- `ObjectDetailsTab` proves an icon and a coloured count fit in a `LinkTab`, but its blue count
  still means "number of items", which is the reading this design must avoid.
- The tab has only the count. The "pending import" or "not on this branch" distinction needs the
  branch's `sync_with_git` (on `currentBranch` from `useCurrentBranch`,
  `entities/branches/domain/model/branch.ts`) and the repository's read-only or read-write kind.
  Neither is read by `RepositoryCommitsTab` on `develop`; the "not on this branch" wording comes
  from [opsmill/infrahub#11189](https://github.com/opsmill/infrahub/pull/11189), not `develop`.
  The prototype mocks both.

## Missing

- A visual for "this tab needs your attention" that is not an item count. No tab in the app has
  one. It would take a new `Badge` variant or a small indicator component, built on the
  `warning` or `info` tokens and checked in both themes.
- A way to show that the tab bar has tabs scrolled out of view. `ScrollArea` hides the scrollbar
  (`scrollBarClassName="hidden"`) and draws no edge fade or overflow control, so a signal on a
  scrolled-away Commits tab is invisible. It would take a fade mask or an overflow control on
  `ObjectDetailsTabs`, or a second place for the signal (the page header).
- A prototype route. `app/router.tsx` has no `/_proto` or design route on `develop`. The run
  has to add one (see below).

- A tab bar that keeps its last tab visible when the tabs overflow (found in phase 3, pill rev 2).
  The prototype renders the Commits tab outside the horizontal `ScrollArea` and fades the cut
  edge with a CSS mask. In the product this belongs in `ObjectDetailsTabs` (or a shared tab bar
  component): a slot for a pinned trailing tab, and an edge fade on `ScrollArea` when it
  scrolls horizontally. `LinkTab` also carries `transition-all`, which the polish rules ask to
  replace with the exact properties.

## Prototype route and mount decision

- Routes are declared in `app/router.tsx` with `createBrowserRouter`. The tree is
  `ReactAriaRouterProvider` → `RequireAuth` + `BranchesProvider` + `SchemaProvider` → path `/`
  lazy `pages/app-layout` (`AppSidebar`, `AppHeader`, `<Outlet />`) → page routes. The object
  details route is `/objects/:objectKind/:objectId` (`pages/objects/object-details-page.tsx`),
  which renders `Content.Card` → `ObjectDetailsHeader` → `ObjectDetailsBody` →
  `ObjectDetailsTabs` + `Card variant="panel"` with the tab `<Outlet>`.
- Proposed route: `/_proto/commits-tab-pending-badge`, a child of the `/` app-layout route,
  with child paths for each fake tab (`details`, `commits`, and so on) so `LinkTab`'s `useMatch`
  marks one tab active.
- Mount decision: inside the app layout, with the history panel's `frame` passed. Every
  direction changes only the tab bar and the tab content inside the object details content
  area; none changes the sidebar, the header or the page frame. The one exception to watch:
  if a direction moves the signal into the page header (`ObjectDetailsHeader`), that is still
  inside `Content.Card`, so the decision holds.
- Do not render the real `ObjectDetailsTabs`. It needs a `ModelSchema` and a `NodeObject`, and
  each `RelationshipTab` and `ObjectTaskTab` runs its own GraphQL count query
  (`useGetRelationshipCount`, `useSchema`, `useGetTaskCount`); `RepositoryCommitsTab` runs
  `useGetRepositoryCommits`, keyed on `currentBranch.name`. Seeding all of that through the
  react-query cache is fragile. Render a faithful copy instead: the same `ScrollArea` props, the
  same `nav` + `Row className="items-end gap-4 px-4"`, real `LinkTab`s and the real grey
  `Badge` for the other tabs, and a variant-specific Commits tab fed by a scenario picker
  (the scenario matrix A1 to F2 in the brief). `BranchesProvider`, react-query and the router are
  already present under the app layout, so the copy needs no extra providers.

## Worst-case data notes

- Overflow: the tab row is `ScrollArea scrollX` with a hidden scrollbar and no fade. At 1200px
  the demo repository page already pushes Commits partly out of view. The only way the user
  reaches it is a horizontal trackpad scroll or Tab key focus; nothing tells them more tabs
  exist. Because Commits is always last, any signal on it is the first thing cut off. The
  prototype needs a "narrow" toggle (or a container width of about 900px for the content
  area) that reproduces this.
- `LinkTab` has `truncate`, but each tab is a flex item without `min-w-0`, so labels do not
  truncate in practice; the row grows and scrolls.
- Long counts: the badge is `px-1.5 py-0.5 text-xs` with no `tabular-nums`, no minimum width and
  no number formatting, so "1284" renders as a wider pill and the width jumps between
  scenarios. A design that keeps a number should use `formatNumberDisplay` ("1,284") and
  `tabular-nums`, or cap the display ("999+") with the full figure in the tooltip and the
  `sr-only` text.
- Loading: other tabs swap the badge for `Spinner`; Commits does the same. A design that adds an
  icon or dot must keep the tab width stable between the spinner and the final state, or the
  tab bar shifts when the query resolves.
- Every tab's `LinkTab` sits at `h-11`. A badge, dot or icon taller than about 20px changes the
  row height; anything added has to fit in that height.

## Built for the phase 2 prototype

Everything below lives in `frontend/app/src/pages/_proto/commits-tab-pending-badge/` and is
imported by nothing outside it. Each item is prototype-only until a direction is picked.

- The route `/_proto/commits-tab-pending-badge/*` in `app/router.tsx`, inside the app layout. The
  splat lets the fake tabs link to child paths so `LinkTab`'s `useMatch` marks one active; the
  route had no prototype home before (see Missing).
- `stage.tsx`: a copy of the `ObjectDetailsTabs` tab bar (same `ScrollArea` props, `nav`, `Row`,
  real `LinkTab` and grey `Badge`) and a simplified Commits tab with the wording of PR #11189.
  Justification: the real `ObjectDetailsTabs` needs a schema, an object and live count queries
  (see the mount decision above).
- A warning-toned count pill (`pill/rev-01.tsx`), built from `bg-warning-surface
  border-warning-border text-warning` plus a lucide icon. Justification: `Badge` has no
  token-based warning variant (see Close); building it in the prototype folder avoids adding a
  shared variant before a direction is picked.
- A static warning dot (`dot/rev-01.tsx`), `bg-warning`, no animation. Justification: `Pulse` is
  absolutely positioned, always animated and has no warning tone (see Close).
- A tooltip on a whole tab, opened by the tab's own hover, focus and Escape handlers and
  positioned with the `Tooltip`'s `triggerRef` (`pill`, `dot`, `words`). Justification: the
  `nonInteractiveTrigger` form puts a non-focusable trigger inside the link, so the tooltip never
  opens on keyboard focus and react-aria logs "Focusable child must have an interactive ARIA
  role".
- A status strip at the top of the Commits tab (`inside/rev-01.tsx`), on the warning tokens.
  Justification: the existing warning notice is a rounded box inside the header; a full-width band
  is a new placement that only the `inside` direction needs.
- The design-jam history panel (`design-history-panel.tsx`, `design-annotations.tsx`,
  `notes-store.ts`), copied from the design-jam skill's `reference/` folder. The frame it fills
  is measured from the app layout's content box, because the panel shell is fixed-positioned.
- Round 2 additions, same folder: a warning-icon pill with no number (`pill`, for warnings without
  a count), warning words in the tab label (`words`), a two-line status strip and a two-pill or
  two-word display for scenario B5, and a "Pending import on main" row badge (yellow `Badge`).
  Justification: the scenario matrix now covers every condition, and B5 shows a split the API
  does not return yet (see `03-decisions.md`); none of these exists in the app.
