# Migrate `popover` to `@infrahub/ui`

**Date:** 2026-06-15
**Status:** Approved

## Goal

Move the popover primitive from `frontend/app/src/shared/components/aria/popover.tsx` into the
`@infrahub/ui` package (`frontend/packages/ui`), following the established pattern from the tooltip
(#9548) and checkbox migrations. Styling stays pixel-identical; this is a relocation, not a redesign.

## Current state

`aria/popover.tsx` exports four symbols, all in use across **18 consumer files**:

| Symbol | Usages |
|--------|--------|
| `Popover` | 18 |
| `PopoverDialog` | 5 |
| `PopoverTrigger` | 3 |
| `PopoverProps` (type) | 1 |

It is a low-level primitive: `aria/select.tsx` composes `Popover` into its own `SelectPopover`.

`@infrahub/ui` already provides everything required — `react-aria-components`, `tw-animate-css`
(the `animate-in` / `fade-in` / `slide-in-from-*` / `data-entering` / `data-exiting` utilities), and a
`composeAriaClassName(className, tw)` helper that replaces the current
`composeRenderProps(className, (c) => classNames(...))` pattern.

## Decisions

- **Old file:** delete `aria/popover.tsx` and repoint all 18 consumers to `@infrahub/ui` (mirror tooltip).
- **Styling:** keep pixel-identical; no token migration.
- **Story:** add `popover.stories.tsx`, consistent with tooltip/checkbox.

## Changes

### 1. New component — `frontend/packages/ui/src/components/popover/popover.tsx`

Port all four exports. The styling classes are copied verbatim from the original (lines 22–25). The
`Popover` className uses `composeAriaClassName`; `PopoverDialog` uses `cn` (its `AriaDialog` className is
a plain string, not render props).

```tsx
import {
  Dialog as AriaDialog,
  type DialogProps as AriaDialogProps,
  DialogTrigger as AriaDialogTrigger,
  Popover as AriaPopover,
  type PopoverProps as AriaPopoverProps,
} from "react-aria-components";
import { cn } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";

export const PopoverTrigger = AriaDialogTrigger;

export interface PopoverProps extends AriaPopoverProps {}

export function Popover({ className, offset = 4, ...props }: PopoverProps) {
  return (
    <AriaPopover
      offset={offset}
      className={composeAriaClassName(
        className,
        cn(
          "z-50 rounded-xl border border-neutral-300 bg-stone-100/70 shadow-md outline-hidden backdrop-blur-lg duration-50",
          "data-entering:fade-in-0 data-entering:zoom-in-95 data-entering:animate-in",
          "data-exiting:fade-out-0 data-exiting:zoom-out-95 data-exiting:animate-out",
          "data-[placement=bottom]:slide-in-from-top-2 data-[placement=left]:slide-in-from-right-2 data-[placement=right]:slide-in-from-left-2 data-[placement=top]:slide-in-from-bottom-2"
        )
      )}
      {...props}
    />
  );
}

export function PopoverDialog({ className, ...props }: AriaDialogProps) {
  return <AriaDialog className={cn("outline-hidden", className)} {...props} />;
}
```

### 2. Story — `frontend/packages/ui/src/components/popover/popover.stories.tsx`

Title `Components/Popover`, mirroring `tooltip.stories.tsx`. Demonstrate the
`PopoverTrigger > Button > Popover > PopoverDialog` composition.

### 3. Export — `frontend/packages/ui/src/index.ts`

```ts
export {
  Popover,
  PopoverDialog,
  type PopoverProps,
  PopoverTrigger,
} from "./components/popover/popover";
```

### 4. Update consumers and delete the old file

Delete `frontend/app/src/shared/components/aria/popover.tsx` and repoint these 18 files from
`@/shared/components/aria/popover` to `@infrahub/ui`:

- `app/src/entities/artifacts/ui/artifact-details-menu.tsx`
- `app/src/entities/branches/ui/branch-selector.tsx`
- `app/src/entities/ipam/ip-namespaces/ui/ip-namespace-selector.tsx`
- `app/src/entities/navigation/ui/breadcrumbs/breadcrumb-branches.tsx`
- `app/src/entities/navigation/ui/breadcrumbs/breadcrumb-proposed-changes.tsx`
- `app/src/entities/navigation/ui/breadcrumbs/breadcrumb-resource-manager.tsx`
- `app/src/entities/navigation/ui/breadcrumbs/items/breadcrumb-item-object.tsx`
- `app/src/entities/nodes/object-template/object-template-form.tsx`
- `app/src/entities/nodes/object/ui/filters/filter-condition-select.tsx`
- `app/src/entities/nodes/object/ui/filters/filter-picker.tsx`
- `app/src/entities/nodes/object/ui/object-details/object-details-menu.tsx`
- `app/src/entities/nodes/object/ui/object-help-button.tsx`
- `app/src/entities/nodes/object/ui/object-table/toolbar/actions/groups/toolbar-add-to-groups-action.tsx`
- `app/src/entities/nodes/object/ui/object-table/toolbar/actions/groups/toolbar-remove-from-groups-action.tsx`
- `app/src/entities/nodes/object/ui/object-table/toolbar/actions/objects/toolbar-edit-action.tsx`
- `app/src/entities/schema/ui/schema-help-menu.tsx`
- `app/src/shared/components/aria/select.tsx`
- `app/src/shared/components/filters/active-filter-tags.tsx`

Where a file already imports other symbols from `@infrahub/ui`, merge the popover symbols into that
existing import line.

`aria/select.tsx` stays in `aria/` (not part of this migration) but imports `Popover`/`PopoverProps`
from `@infrahub/ui`.

## Non-changes

- **No `package.json` change.** Unlike the tooltip migration (which removed `@radix-ui/react-tooltip`),
  popover has no dedicated dependency to drop — it is pure `react-aria-components`, already present in
  both packages.

## Verification

- `pnpm biome:fix` — formatting, lint, and import ordering.
- App build (`cd frontend/app && pnpm build`) is the source of truth. The `@infrahub/ui` package's own
  build is independently broken (pre-existing), so do not rely on it.
- Confirm `.betterer.results` — popover is not currently tracked there (grep returns 0 matches), so no
  change is expected; verify after the move.
