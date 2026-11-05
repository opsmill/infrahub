# Lift sheet: instance badge and bar

Approved revision: `frontend/app/src/_proto/instance-badge/directions/header-left/rev-01.tsx`, with
`instance-badge.tsx` and `fixtures.ts` in the same folder.

## Lift as is

- `InstanceBadge` from `_proto/instance-badge/instance-badge.tsx`: `Badge` variant per color,
  `inline-block max-w-48 truncate`, `Tooltip nonInteractiveTrigger` with the full label. Destination:
  `frontend/app/src/entities/preferences/ui/instance-badge.tsx`.
- `InstanceBar` from the same file: a `div` with `h-0.75 w-full shrink-0` and the bar class,
  `aria-hidden`, rendered only with a color. Destination:
  `frontend/app/src/entities/preferences/ui/instance-color-bar.tsx`.
- The preset → classes map from `fixtures.ts` (badge variant, bar class). Destination:
  `frontend/app/src/entities/preferences/domain/rules/instance-color.ts`, the single owner.
- Placement: badge right before `TaskStatus` in `entities/navigation/ui/app-header.tsx` (owner's decision, right side);
  bar as the first child of the outer column in `pages/app-layout.tsx`, the row becoming
  `flex-1 min-h-0`; on `pages/login.tsx`, bar as the first child of the full-screen container and
  the badge as the first child of the centered column.

## Replace

- Knob values and fixtures with `useConfig().instance` (`label`, `color`) from `/api/config`.
- The local indigo override (`bg-active-surface text-active` through `twMerge`) with a real
  `indigo` variant in `shared/components/ui/badge.tsx`.
- The fake shell with the real `AppHeader`, `AppLayout` and login page.

## Resolve

- `BAR_HEIGHT`: `h-0.75` (3 px). `BADGE_MAX_WIDTH`: `max-w-48`. `stripHeight`: dropped.

## Do not lift

- `design-history-panel.tsx`, `design-annotations.tsx`, `notes-store.ts`, `shell.tsx`,
  `route.tsx`, the other three `directions/*/rev-01.tsx`, the router line, the knip ignore.

## Tests still to write

See `dev/specs/007-instance-badge-ifc-3232/tasks.md`.

## Teardown

Before the implementation PR opens (compressed jam, the prototype is on the implementation branch):
delete `frontend/app/src/_proto/`, the router entry and the knip ignore; search for
`PROTOTYPE design-jam instance-badge` and confirm nothing is left; keep `.design/instance-badge/`
with its screenshots.
