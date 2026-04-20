# Tooltip Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Radix tooltip (`ui/tooltip.tsx`) with the React Aria tooltip (`aria/tooltip.tsx`) across all 41 frontend consumers.

**Architecture:** Extend the existing aria tooltip with a `placement` prop, then mechanically migrate every consumer. Non-focusable trigger elements get a `<Focusable>` wrapper (React Aria requirement). Wrapper components (`ButtonWithTooltip`, etc.) drop the `tooltipEnabled` prop — presence of `tooltipContent` signals whether to render.

**Tech Stack:** React 19, react-aria-components (TooltipTrigger, Tooltip, Focusable), Tailwind CSS, CVA

**Spec:** `docs/superpowers/specs/2026-04-20-tooltip-migration-design.md`

---

## Key migration patterns

Reference these patterns throughout the tasks below.

### Pattern A: Simple rename (focusable trigger)

```tsx
// BEFORE
import { Tooltip } from "@/shared/components/ui/tooltip";
<Tooltip enabled content="Edit"><Button>Edit</Button></Tooltip>

// AFTER
import { Tooltip } from "@/shared/components/aria/tooltip";
<Tooltip message="Edit"><Button>Edit</Button></Tooltip>
```

### Pattern B: Non-focusable trigger (add Focusable)

```tsx
// BEFORE
import { Tooltip } from "@/shared/components/ui/tooltip";
<Tooltip enabled content="Label"><span>text</span></Tooltip>

// AFTER
import { Tooltip } from "@/shared/components/aria/tooltip";
import { Focusable } from "react-aria-components";
<Tooltip message="Label"><Focusable><span>text</span></Focusable></Tooltip>
```

For components that may not forward ref/spread props (like `<Icon>` from @iconify-icon/react), wrap in an extra `<span>`:

```tsx
<Tooltip message="Status">
  <Focusable>
    <span className="inline-flex"><Icon icon="mdi:check" /></span>
  </Focusable>
</Tooltip>
```

### Pattern C: Conditional enabled → conditional rendering

```tsx
// BEFORE
<Tooltip enabled={showTooltip} content={text} side="right"><Child /></Tooltip>

// AFTER
{showTooltip ? (
  <Tooltip message={text} placement="right"><Focusable><Child /></Focusable></Tooltip>
) : (
  <Child />
)}
```

### Pattern D: Disabled-button tooltip (PC action buttons)

The disabled-button tooltip pattern (tooltip wrapping a button with `disabled` + `pointer-events-none`) never actually showed the tooltip in the old implementation either. Migration preserves this same behavior. The PC action button pattern also uses `className="whitespace-pre"` which passes through via `AriaTooltipProps`.

```tsx
// BEFORE
<Tooltip content={tooltipContent} enabled={tooltipEnabled} className="whitespace-pre">
  <Button disabled={tooltipEnabled || isPending}>...</Button>
</Tooltip>

// AFTER — conditional rendering: tooltip only when needed
{tooltipEnabled ? (
  <Tooltip message={tooltipContent} className="whitespace-pre">
    <Focusable>
      <span className="inline-flex h-full grow">
        <Button className="..." disabled isLoading={isPending}>...</Button>
      </span>
    </Focusable>
  </Tooltip>
) : (
  <Button className="..." disabled={isPending}>...</Button>
)}
```

---

### Task 1: Extend `aria/tooltip.tsx` with `placement` prop

**Files:**
- Modify: `src/shared/components/aria/tooltip.tsx`

- [ ] **Step 1: Add `placement` to the Tooltip component**

```tsx
import { cva } from "class-variance-authority";
import type React from "react";
import {
  Tooltip as AriaTooltip,
  type TooltipProps as AriaTooltipProps,
  composeRenderProps,
  OverlayArrow,
  TooltipTrigger,
} from "react-aria-components";

export interface TooltipProps extends Omit<AriaTooltipProps, "children"> {
  children: React.ReactNode;
  message: React.ReactNode;
}

const styles = cva(
  "group box-border rounded-xl border border-neutral-800 bg-neutral-700 px-2 py-1 font-sans text-white text-xs drop-shadow-lg will-change-transform",
  {
    variants: {
      isEntering: {
        true: "fade-in placement-bottom:slide-in-from-top-0.5 placement-top:slide-in-from-bottom-0.5 placement-left:slide-in-from-right-0.5 placement-right:slide-in-from-left-0.5 animate-in duration-200 ease-out",
      },
      isExiting: {
        true: "fade-out placement-bottom:slide-out-to-top-0.5 placement-top:slide-out-to-bottom-0.5 placement-left:slide-out-to-right-0.5 placement-right:slide-out-to-left-0.5 animate-out duration-150 ease-in",
      },
    },
  }
);

export function Tooltip({ children, message, ...props }: TooltipProps) {
  return (
    <TooltipTrigger delay={200} closeDelay={300}>
      {children}

      <AriaTooltip
        {...props}
        offset={10}
        className={composeRenderProps(props.className, (className, renderProps) =>
          styles({ ...renderProps, className })
        )}
      >
        <OverlayArrow>
          <svg
            width={8}
            height={8}
            viewBox="0 0 8 8"
            className="block fill-neutral-700 stroke-neutral-800 group-placement-bottom:rotate-180 group-placement-left:-rotate-90 group-placement-right:rotate-90"
          >
            <path d="M0 0 L4 4 L8 0" />
          </svg>
        </OverlayArrow>
        {message}
      </AriaTooltip>
    </TooltipTrigger>
  );
}
```

Changes from current:
- `TooltipProps` interface now includes `message` directly (not as separate `&` intersection)
- Removed `isOpen` and `onOpenChange` from `TooltipTrigger` (they were never used, and controlled open state is an edge case — can be re-added via `AriaTooltipProps` passthrough if needed)
- Removed `shouldCloseOnPress={false}` (default React Aria behavior is fine)
- `placement` is already part of `AriaTooltipProps` and passes through via `{...props}`

- [ ] **Step 2: Verify existing aria tooltip consumers still work**

Run: `cd frontend/app && pnpm build`
Expected: Build succeeds (the 5 existing `aria/tooltip` consumers use `message` prop which is unchanged)

- [ ] **Step 3: Commit**

```bash
git add src/shared/components/aria/tooltip.tsx
git commit -m "refactor(tooltip): extend aria tooltip with placement support"
```

---

### Task 2: Migrate wrapper components

**Files:**
- Modify: `src/shared/components/ui/button.tsx`
- Modify: `src/shared/components/ui/dropdown-menu.tsx`
- Modify: `src/shared/components/aria/menu.tsx`
- Modify: `src/entities/nodes/object/ui/object-table/toolbar/toolbar-button.tsx`

- [ ] **Step 1: Migrate `ButtonWithTooltip` in `button.tsx`**

Replace the import and update the component:

```tsx
// Replace import line
import { Tooltip, type TooltipProps } from "@/shared/components/aria/tooltip";

// Replace interface + component
interface ButtonWithTooltipProps extends ButtonProps {
  tooltipContent?: React.ReactNode;
  tooltipPlacement?: TooltipProps["placement"];
}

export const ButtonWithTooltip = forwardRef<HTMLButtonElement, ButtonWithTooltipProps>(
  ({ tooltipContent, tooltipPlacement = "top", disabled, className, ...props }, ref) => {
    if (!tooltipContent) {
      return <Button ref={ref} {...props} className={className} disabled={disabled} />;
    }

    if (disabled) {
      return (
        <Tooltip message={tooltipContent} placement={tooltipPlacement}>
          <span className="inline-flex">
            <Button ref={ref} {...props} className={className} disabled />
          </span>
        </Tooltip>
      );
    }

    return (
      <Tooltip message={tooltipContent} placement={tooltipPlacement}>
        <Button ref={ref} {...props} className={className} />
      </Tooltip>
    );
  }
);
```

Note: the `<span>` wrapper for disabled buttons is needed because native `disabled` buttons have `pointer-events: none`. The `<span>` receives hover events instead. `<Focusable>` is NOT needed here because the `<span>` receives pointer events naturally and React Aria's `TooltipTrigger` handles it.

Actually — correction: React Aria's `TooltipTrigger` requires a focusable first child. The `<span>` is not focusable. We need `Focusable`:

```tsx
import { Focusable } from "react-aria-components";

// In the disabled branch:
<Tooltip message={tooltipContent} placement={tooltipPlacement}>
  <Focusable>
    <span className="inline-flex">
      <Button ref={ref} {...props} className={className} disabled />
    </span>
  </Focusable>
</Tooltip>
```

And for the non-disabled branch, `<Button>` renders a native `<button>` which is focusable — no wrapping needed.

Full replacement for button.tsx import block:

```tsx
import { Focusable } from "react-aria-components";

import { Spinner } from "@/shared/components/ui/spinner";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { Tooltip, type TooltipProps } from "@/shared/components/aria/tooltip";
import { classNames } from "@/shared/utils/common";
```

Full replacement for `ButtonWithTooltip`:

```tsx
interface ButtonWithTooltipProps extends ButtonProps {
  tooltipContent?: React.ReactNode;
  tooltipPlacement?: TooltipProps["placement"];
}

export const ButtonWithTooltip = forwardRef<HTMLButtonElement, ButtonWithTooltipProps>(
  ({ tooltipContent, tooltipPlacement = "top", disabled, className, ...props }, ref) => {
    if (!tooltipContent) {
      return <Button ref={ref} {...props} className={className} disabled={disabled} />;
    }

    if (disabled) {
      return (
        <Tooltip message={tooltipContent} placement={tooltipPlacement}>
          <Focusable>
            <span className="inline-flex">
              <Button ref={ref} {...props} className={className} disabled />
            </span>
          </Focusable>
        </Tooltip>
      );
    }

    return (
      <Tooltip message={tooltipContent} placement={tooltipPlacement}>
        <Button ref={ref} {...props} className={className} disabled={disabled} />
      </Tooltip>
    );
  }
);
```

- [ ] **Step 2: Migrate `DropdownMenuItemWithTooltip` in `dropdown-menu.tsx`**

Replace import:

```tsx
import { Tooltip, type TooltipProps } from "@/shared/components/aria/tooltip";
```

Add import:

```tsx
import { Focusable } from "react-aria-components";
```

Replace interface + component:

```tsx
export interface DropdownMenuItemWithTooltipProps
  extends ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> {
  tooltipContent?: React.ReactNode;
  tooltipPlacement?: TooltipProps["placement"];
}

export const DropdownMenuItemWithTooltip = forwardRef<
  ElementRef<typeof DropdownMenuPrimitive.Item>,
  DropdownMenuItemWithTooltipProps
>(({ tooltipContent, tooltipPlacement = "left", disabled, children, ...props }, ref) => {
  if (!tooltipContent || !disabled) {
    return (
      <DropdownMenuItem ref={ref} disabled={disabled} {...props}>
        {children}
      </DropdownMenuItem>
    );
  }

  return (
    <Tooltip message={tooltipContent} placement={tooltipPlacement}>
      <Focusable>
        <div>
          <DropdownMenuItem ref={ref} disabled={disabled} {...props}>
            {children}
          </DropdownMenuItem>
        </div>
      </Focusable>
    </Tooltip>
  );
});
```

- [ ] **Step 3: Migrate `MenuItemWithTooltip` in `aria/menu.tsx`**

Replace import:

```tsx
import { Tooltip, type TooltipProps } from "@/shared/components/aria/tooltip";
```

Replace interface + component:

```tsx
export interface MenuItemWithTooltipProps extends Omit<MenuItemProps, "children"> {
  tooltipContent?: React.ReactNode;
  tooltipPlacement?: TooltipProps["placement"];
  children?: React.ReactNode;
}

export function MenuItemWithTooltip({
  tooltipContent,
  tooltipPlacement = "left",
  isDisabled,
  children,
  ...props
}: MenuItemWithTooltipProps) {
  if (!tooltipContent || !isDisabled) {
    return (
      <MenuItem isDisabled={isDisabled} {...props}>
        {children}
      </MenuItem>
    );
  }

  return (
    <MenuItem isDisabled={isDisabled} className="data-disabled:pointer-events-auto" {...props}>
      <Tooltip message={tooltipContent} placement={tooltipPlacement} className="z-100001">
        <Focusable>
          <span className="flex w-full items-center gap-[inherit]">{children}</span>
        </Focusable>
      </Tooltip>
    </MenuItem>
  );
}
```

Note: `Focusable` is already available from `react-aria-components` which is already imported in this file. Just add it to the import destructuring.

- [ ] **Step 4: Migrate `ToolbarButtonWithTooltip` in `toolbar-button.tsx`**

Replace import:

```tsx
import { Focusable } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { Tooltip, type TooltipProps } from "@/shared/components/aria/tooltip";
import { classNames } from "@/shared/utils/common";
```

Replace interface + component:

```tsx
export interface ToolbarButtonWithTooltipProps extends ToolbarButtonProps {
  tooltipContent?: React.ReactNode;
  tooltipPlacement?: TooltipProps["placement"];
}

export function ToolbarButtonWithTooltip({
  tooltipContent,
  tooltipPlacement = "top",
  isDisabled,
  ...props
}: ToolbarButtonWithTooltipProps) {
  if (!tooltipContent) {
    return <ToolbarButton isDisabled={isDisabled} {...props} />;
  }

  if (isDisabled) {
    return (
      <Tooltip message={tooltipContent} placement={tooltipPlacement}>
        <Focusable>
          <span className="inline-flex">
            <ToolbarButton isDisabled {...props} />
          </span>
        </Focusable>
      </Tooltip>
    );
  }

  return (
    <Tooltip message={tooltipContent} placement={tooltipPlacement}>
      <ToolbarButton isDisabled={isDisabled} {...props} />
    </Tooltip>
  );
}
```

Note: `ToolbarButton` uses `AriaButton` from react-aria-components which IS focusable, so no `Focusable` needed for non-disabled case.

- [ ] **Step 5: Build check**

Run: `cd frontend/app && pnpm build`
Expected: Type errors from wrapper consumers (they still pass old props like `tooltipEnabled`, `side`). This is expected — we fix them in Task 3.

- [ ] **Step 6: Commit**

```bash
git add src/shared/components/ui/button.tsx src/shared/components/ui/dropdown-menu.tsx src/shared/components/aria/menu.tsx src/entities/nodes/object/ui/object-table/toolbar/toolbar-button.tsx
git commit -m "refactor(tooltip): migrate wrapper components to aria tooltip"
```

---

### Task 3: Update wrapper consumers

These files use `ButtonWithTooltip`, `DropdownMenuItemWithTooltip`, `MenuItemWithTooltip`, or `ToolbarButtonWithTooltip` and need prop updates.

**Files:**
- Modify: `src/entities/navigation/ui/sidebar/collapsed-sidebar-menu-item.tsx`
- Modify: `src/entities/branches/ui/branch-selector.tsx`
- Modify: `src/shared/components/form/object-create-form-trigger.tsx`
- Modify: `src/shared/components/form/object-edit-slide-over-trigger.tsx`
- Modify: `src/entities/proposed-changes/ui/proposed-changes-manager-toolbar.tsx`
- Modify: `src/entities/proposed-changes/ui/proposed-change-edit-trigger.tsx`
- Modify: `src/entities/groups/ui/add-group-trigger-button.tsx`
- Modify: `src/entities/tasks/ui/task-filters.tsx`
- Modify: `src/shared/components/table/table.tsx`
- Modify: `src/entities/navigation/ui/search-anywhere/search-anywhere-trigger.tsx`
- Modify: `src/entities/schema/ui/schema-selector.tsx`
- Modify: `src/entities/nodes/object/ui/object-details/object-data-display/object-relationship-row.tsx`
- Modify: `src/entities/nodes/object/ui/object-details/object-data-display/object-attribute-row.tsx`
- Modify: `src/entities/nodes/object-item-details/action-buttons/details-buttons.tsx`
- Modify: `src/entities/nodes/object-item-details/action-buttons/relationships-buttons.tsx`
- Modify: `src/entities/nodes/relationships/ui/relationship-table/relationship-actions-cell.tsx`
- Modify: `src/entities/nodes/relationships/ui/relationship-table/toolbar-dissociate-action.tsx`
- Modify: `src/entities/nodes/object/ui/object-details/object-details-menu.tsx`
- Modify: `src/entities/nodes/object/ui/object-table/toolbar/actions/groups/toolbar-add-to-groups-action.tsx`
- Modify: `src/entities/nodes/object/ui/object-table/toolbar/actions/groups/toolbar-remove-from-groups-action.tsx`
- Modify: `src/entities/nodes/object/ui/object-table/toolbar/actions/objects/toolbar-delete-action.tsx`
- Modify: `src/entities/nodes/object/ui/object-table/toolbar/actions/objects/toolbar-edit-action.tsx`

The changes are mechanical. For each file apply:

| Old prop | New prop | Notes |
|----------|----------|-------|
| `tooltipEnabled` | (remove) | Tooltip renders when `tooltipContent` is truthy |
| `tooltipContent={x}` | `tooltipContent={x}` | No change |
| `side="right"` | `tooltipPlacement="right"` | Rename only |

For files that used `tooltipEnabled` conditionally:

```tsx
// BEFORE
tooltipEnabled={!isAllowed}
tooltipContent={message}

// AFTER (merge condition into content)
tooltipContent={!isAllowed ? message : undefined}
```

- [ ] **Step 1: Update `collapsed-sidebar-menu-item.tsx`**

Remove `tooltipEnabled` prop, rename `side` to `tooltipPlacement`:

```tsx
// BEFORE
<ButtonWithTooltip
  variant="ghost"
  size="square"
  side="right"
  tooltipEnabled
  className={classNames("h-10 w-10 p-2", className)}
  {...props}
>

// AFTER
<ButtonWithTooltip
  variant="ghost"
  size="square"
  tooltipPlacement="right"
  className={classNames("h-10 w-10 p-2", className)}
  {...props}
>
```

- [ ] **Step 2: Update `branch-selector.tsx`**

```tsx
// BEFORE
tooltipEnabled={!isAuthenticated}
tooltipContent="You need to be authenticated."

// AFTER
tooltipContent={!isAuthenticated ? "You need to be authenticated." : undefined}
```

- [ ] **Step 3: Update `object-create-form-trigger.tsx`**

Update the `Omit` type and the props:

```tsx
// BEFORE
extends Omit<ButtonProps, "disabled" | "tooltipEnabled" | "tooltipContent"> {

// AFTER
extends Omit<ButtonProps, "disabled" | "tooltipContent"> {
```

```tsx
// BEFORE
tooltipContent={message}
tooltipEnabled={!isAllowed}

// AFTER
tooltipContent={!isAllowed ? message : undefined}
```

- [ ] **Step 4: Update `object-edit-slide-over-trigger.tsx`**

```tsx
// BEFORE
tooltipEnabled={!permission.create.isAllowed}
tooltipContent={permission.create.message ?? undefined}

// AFTER
tooltipContent={!permission.create.isAllowed ? (permission.create.message ?? undefined) : undefined}
```

- [ ] **Step 5: Update `proposed-changes-manager-toolbar.tsx`**

```tsx
// BEFORE
tooltipEnabled={!permission.create.isAllowed}
tooltipContent={permission.create.message ?? undefined}

// AFTER
tooltipContent={!permission.create.isAllowed ? (permission.create.message ?? undefined) : undefined}
```

- [ ] **Step 6: Update `proposed-change-edit-trigger.tsx`**

```tsx
// BEFORE
tooltipEnabled={!permission.update.isAllowed}
tooltipContent={permission.update.message ?? undefined}

// AFTER
tooltipContent={!permission.update.isAllowed ? (permission.update.message ?? undefined) : undefined}
```

- [ ] **Step 7: Update `add-group-trigger-button.tsx`**

```tsx
// BEFORE
tooltipContent={permission.update.message ?? "Add groups"}
tooltipEnabled

// AFTER
tooltipContent={permission.update.message ?? "Add groups"}
```

(Just remove `tooltipEnabled`)

- [ ] **Step 8: Update `task-filters.tsx`**

```tsx
// BEFORE
tooltipEnabled
tooltipContent="Apply filters"

// AFTER
tooltipContent="Apply filters"
```

- [ ] **Step 9: Update `table.tsx`**

```tsx
// BEFORE
tooltipContent="Actions"
tooltipEnabled

// AFTER
tooltipContent="Actions"
```

- [ ] **Step 10: Update `search-anywhere-trigger.tsx`**

```tsx
// BEFORE
tooltipContent="Search anywhere"

// AFTER (no change needed — tooltipEnabled was not used)
tooltipContent="Search anywhere"
```

Verify: this file doesn't use `tooltipEnabled`. No changes needed.

- [ ] **Step 11: Update `schema-selector.tsx`**

```tsx
// BEFORE
tooltipContent={anyOpen ? "Collapse all" : "Expand all"}
tooltipEnabled

// AFTER
tooltipContent={anyOpen ? "Collapse all" : "Expand all"}
```

- [ ] **Step 12: Update remaining ButtonWithTooltip consumers**

For these files, just remove `tooltipEnabled` if present (it's always `true`):
- `object-relationship-row.tsx`
- `object-attribute-row.tsx`
- `details-buttons.tsx`
- `relationships-buttons.tsx`

- [ ] **Step 13: Update DropdownMenuItemWithTooltip consumers**

Files: `relationship-actions-cell.tsx`, `object-actions-cell.tsx`

```tsx
// BEFORE
<DropdownMenuItemWithTooltip
  tooltipContent={permission.delete.message}
  tooltipEnabled
  disabled={!permission.delete.isAllowed}
>

// AFTER
<DropdownMenuItemWithTooltip
  tooltipContent={permission.delete.message}
  disabled={!permission.delete.isAllowed}
>
```

Remove `tooltipEnabled` and rename `side` to `tooltipPlacement` if present.

- [ ] **Step 14: Update MenuItemWithTooltip consumers**

File: `object-details-menu.tsx`

```tsx
// BEFORE
<MenuItemWithTooltip
  tooltipContent={permission.update.message}
  tooltipEnabled
  isDisabled={!permission.update.isAllowed}
>

// AFTER
<MenuItemWithTooltip
  tooltipContent={permission.update.message}
  isDisabled={!permission.update.isAllowed}
>
```

Remove `tooltipEnabled` from all 4 `MenuItemWithTooltip` usages.

- [ ] **Step 15: Update ToolbarButtonWithTooltip consumers**

Files:
- `toolbar-add-to-groups-action.tsx`
- `toolbar-remove-from-groups-action.tsx`
- `toolbar-delete-action.tsx`
- `toolbar-edit-action.tsx`
- `toolbar-dissociate-action.tsx`

```tsx
// BEFORE
<ToolbarButtonWithTooltip isDisabled tooltipEnabled tooltipContent={message}>

// AFTER
<ToolbarButtonWithTooltip isDisabled tooltipContent={message}>
```

Remove `tooltipEnabled` from all usages.

- [ ] **Step 16: Build check**

Run: `cd frontend/app && pnpm build`
Expected: Remaining errors are from direct `<Tooltip>` consumers (old import path). Fixed in Tasks 4-7.

- [ ] **Step 17: Commit**

```bash
git add -A
git commit -m "refactor(tooltip): update wrapper consumers to new tooltip props"
```

---

### Task 4: Migrate direct consumers — focusable triggers

These files wrap focusable elements (Button, LinkButton, button, PopoverTrigger) and only need import + prop rename.

**Files:**
- Modify: `src/shared/components/display/question-mark.tsx`
- Modify: `src/shared/components/buttons/clipboard.tsx`
- Modify: `src/shared/components/form/pool-selector.tsx`
- Modify: `src/entities/navigation/ui/search-anywhere/search-anywhere-input.tsx`
- Modify: `src/entities/schema/ui/schema-viewer.tsx`
- Modify: `src/entities/groups/ui/object-groups-list.tsx`
- Modify: `src/entities/tasks/ui/task-status.tsx`
- Modify: `src/entities/diff/ui/node-diff/thread.tsx`
- Modify: `src/shared/components/form/fields/common.tsx`

All follow Pattern A:

- [ ] **Step 1: Migrate each file**

For each file:
1. Replace `import { Tooltip } from "@/shared/components/ui/tooltip"` → `import { Tooltip } from "@/shared/components/aria/tooltip"`
2. Replace `content={x}` → `message={x}`
3. Remove `enabled` prop
4. Replace `side="x"` → `placement="x"` (if present)

Specific notes per file:

**question-mark.tsx:**
```tsx
<Tooltip message={message}><Button ...>?</Button></Tooltip>
```

**clipboard.tsx:**
```tsx
<Tooltip message={tooltip}><Button ...>...</Button></Tooltip>
```

**pool-selector.tsx:**
```tsx
<Tooltip message="select a pool"><PopoverTrigger ...>...</PopoverTrigger></Tooltip>
```

**search-anywhere-input.tsx:**
```tsx
<Tooltip message="Case sensitive"><Button ...>...</Button></Tooltip>
```

**schema-viewer.tsx:**
```tsx
<Tooltip message="View in graph"><LinkButton ...>...</LinkButton></Tooltip>
```

**object-groups-list.tsx:**
```tsx
<Tooltip message="Leave"><Button ...>...</Button></Tooltip>
```

**task-status.tsx** (2 usages):
```tsx
<Tooltip message={tooltipContent}><LinkButton ...>...</LinkButton></Tooltip>
```

**node-diff/thread.tsx** (2 usages):
```tsx
<Tooltip message="Add comment"><Button ...>...</Button></Tooltip>
```

**form/fields/common.tsx** (3 usages — ProfileSourceBadge, PoolSourceBadge, TemplateSourceBadge):
```tsx
<Tooltip message={<div className="max-w-60">...</div>}>
  <button type="button" ...>...</button>
</Tooltip>
```

- [ ] **Step 2: Build check**

Run: `cd frontend/app && pnpm build`

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor(tooltip): migrate direct consumers with focusable triggers"
```

---

### Task 5: Migrate direct consumers — non-focusable triggers

These files wrap non-focusable elements (`<span>`, `<div>`, `<Icon>`, `<Avatar>`) and need `Focusable` wrapping.

**Files:**
- Modify: `src/shared/components/display/date-display.tsx`
- Modify: `src/shared/components/display/duration-display.tsx`
- Modify: `src/shared/components/display/color-display.tsx`
- Modify: `src/entities/diff/ui/diff-empty.tsx`
- Modify: `src/entities/diff/ui/checks/validator.tsx`
- Modify: `src/entities/diff/ui/checks/check.tsx`
- Modify: `src/entities/events/ui/global-event.tsx`
- Modify: `src/entities/proposed-changes/ui/proposed-change-item.tsx`
- Modify: `src/entities/proposed-changes/ui/proposed-change-item-light.tsx`
- Modify: `src/entities/proposed-changes/ui/proposed-change-details.tsx`
- Modify: `src/entities/proposed-changes/ui/conversations/thread.tsx`
- Modify: `src/entities/resource-manager/ui/ResourcePoolUtilization.tsx`
- Modify: `src/entities/branches/ui/branch-list-item/branch-git-sync-badge.tsx`
- Modify: `src/entities/navigation/ui/breadcrumbs/breadcrumb-object-details-hierarchy.tsx`

All follow Pattern B. For each file:
1. Replace import path
2. Add `import { Focusable } from "react-aria-components"`
3. Replace `content={x}` → `message={x}`
4. Remove `enabled`
5. Wrap the non-focusable child in `<Focusable>`
6. For `<Icon>` children, add `<span className="inline-flex">` wrapper inside `<Focusable>`

- [ ] **Step 1: Migrate display components**

**date-display.tsx** (2 usages):
```tsx
import { Tooltip } from "@/shared/components/aria/tooltip";
import { Focusable } from "react-aria-components";

<Tooltip message={getDateDisplay(dateData)}>
  <Focusable>
    <span className={classNames("truncate font-normal text-xs", className)}>
      {format(dateData, newDateFormat)}
    </span>
  </Focusable>
</Tooltip>
```

**duration-display.tsx:**
```tsx
<Tooltip message={tooltip}>
  <Focusable>
    <span className="font-normal text-xs">...</span>
  </Focusable>
</Tooltip>
```

**color-display.tsx:**
```tsx
<Tooltip message={description}>
  <Focusable>
    <div className="inline-flex min-h-[24px] min-w-[24px] ...">
      {value}
    </div>
  </Focusable>
</Tooltip>
```

- [ ] **Step 2: Migrate diff components**

**diff-empty.tsx:**
```tsx
<Tooltip message={formatFullDate(lastRefreshedAt)}>
  <Focusable>
    <span className="font-semibold">{formatRelativeTimeFromNow(lastRefreshedAt)}</span>
  </Focusable>
</Tooltip>
```

**validator.tsx** (5 usages, all wrapping `<Icon>`):
```tsx
import { Tooltip } from "@/shared/components/aria/tooltip";
import { Focusable } from "react-aria-components";

<Tooltip message="Queued">
  <Focusable>
    <span className="inline-flex">
      <Icon icon={"mdi:timer-sand-complete"} className="text-yellow-500" />
    </span>
  </Focusable>
</Tooltip>
```

Apply same pattern to all 5 cases (Queued, In progress, Success, Failure, Unknown).

**check.tsx** (3 usages, all wrapping `<Icon>`):
```tsx
<Tooltip message="Success">
  <Focusable>
    <span className="inline-flex">
      <Icon icon={"mdi:check-circle-outline"} className="mr-2 text-green-500" />
    </span>
  </Focusable>
</Tooltip>
```

Apply same pattern to all 3 cases (Success, Failure, In progress).

- [ ] **Step 3: Migrate event/PC components**

**global-event.tsx** (2 usages):
Usage 1 wraps `<span>`:
```tsx
<Tooltip message={format(new Date(props.occurred_at), "yyyy-MM-dd HH:mm:ss (O)")}>
  <Focusable>
    <span>{format(new Date(props.occurred_at), "MMM dd, HH:mm:ss")}</span>
  </Focusable>
</Tooltip>
```

Usage 2 wraps `<Icon>`:
```tsx
<Tooltip message="Contains sub activities">
  <Focusable>
    <span className="inline-flex">
      <Icon icon={"mdi:subtasks"} className="absolute right-2 rounded-full bg-custom-blue-500/10 p-1.5 text-custom-blue-500" data-testid="activity-has-children-icon" />
    </span>
  </Focusable>
</Tooltip>
```

Note: The `absolute` positioning on the Icon may need the wrapper span to also be `absolute right-2`. Move positioning to the wrapper span:
```tsx
<Tooltip message="Contains sub activities">
  <Focusable>
    <span className="absolute right-2 inline-flex">
      <Icon icon={"mdi:subtasks"} className="rounded-full bg-custom-blue-500/10 p-1.5 text-custom-blue-500" data-testid="activity-has-children-icon" />
    </span>
  </Focusable>
</Tooltip>
```

**proposed-change-item.tsx** (1 usage):
```tsx
<Tooltip message="Comments">
  <Focusable>
    <span className="flex items-center gap-1">
      <Icon icon={"mdi:comment-outline"} /> {comments}
    </span>
  </Focusable>
</Tooltip>
```

**proposed-change-item-light.tsx** (2 usages):
Same pattern — wrap `<span>` in `<Focusable>`.

**proposed-change-details.tsx** (5 usages, all wrapping `<Avatar>`):
```tsx
<Tooltip message={getNodeLabel(metadata.created_by)}>
  <Focusable>
    <Avatar size="sm" name={getNodeLabel(metadata.created_by)} className="bg-custom-blue-green" />
  </Focusable>
</Tooltip>
```

`Avatar` uses `forwardRef<HTMLDivElement>` so `Focusable` can clone it directly (no extra span needed).

**conversations/thread.tsx:**
```tsx
<Tooltip message="The resolution will be done after submitting the comment">
  <Focusable>
    {MarkAsResolved}
  </Focusable>
</Tooltip>
```

- [ ] **Step 4: Migrate remaining entity components**

**ResourcePoolUtilization.tsx:**
```tsx
<Tooltip message={<ResourceUtilizationTooltipContent ... />}>
  <Focusable>
    <span className="w-8 text-right font-medium text-custom-blue-700">
      {roundNumber(utilizationOverall, 0)}%
    </span>
  </Focusable>
</Tooltip>
```

**branch-git-sync-badge.tsx:**
```tsx
<Tooltip message="Synced with Git">
  <Focusable>
    <span className="inline-flex shrink-0 items-center justify-center rounded-full bg-custom-blue-700/10 p-1.5 text-custom-blue-700">
      <Icon icon={"mdi:source-branch"} className="size-4" />
    </span>
  </Focusable>
</Tooltip>
```

**breadcrumb-object-details-hierarchy.tsx:**
```tsx
<Tooltip message={<div className="max-w-xs">...</div>}>
  <Focusable>
    <BreadcrumbItem href="..." target="_blank" rel="noopener noreferrer" className="gap-1 text-amber-600">
      <TriangleAlertIcon className="size-4" /> Depth limit reached
    </BreadcrumbItem>
  </Focusable>
</Tooltip>
```

Check: if `BreadcrumbItem` renders an `<a>` (focusable), `Focusable` may not be needed. Verify and adjust.

- [ ] **Step 5: Build check**

Run: `cd frontend/app && pnpm build`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(tooltip): migrate consumers with non-focusable triggers"
```

---

### Task 6: Migrate direct consumers — conditional enabled

These files use `enabled` conditionally (not always `true`) and need conditional rendering.

**Files:**
- Modify: `src/entities/navigation/ui/sidebar/sidebar-menu-section-object.tsx`
- Modify: `src/entities/homepage/ui/git-repository.tsx`
- Modify: `src/entities/proposed-changes/ui/proposed-changes-actions-cell.tsx`
- Modify: `src/entities/ipam/ip-addresses/ui/ip-address-available-create-form-trigger.tsx`
- Modify: `src/entities/ipam/ip-prefixes/ui/ip-prefix-available-identifier.tsx`

All follow Pattern C.

- [ ] **Step 1: Migrate `sidebar-menu-section-object.tsx`**

```tsx
import { Tooltip } from "@/shared/components/aria/tooltip";
import { Focusable } from "react-aria-components";

// BEFORE
<Tooltip enabled={isCollapsed} content={item.label} side="right">
  <span className="flex">
    <MenuItemIcon item={item} />
  </span>
</Tooltip>

// AFTER
{isCollapsed ? (
  <Tooltip message={item.label} placement="right">
    <Focusable>
      <span className="flex">
        <MenuItemIcon item={item} />
      </span>
    </Focusable>
  </Tooltip>
) : (
  <span className="flex">
    <MenuItemIcon item={item} />
  </span>
)}
```

- [ ] **Step 2: Migrate `git-repository.tsx`**

```tsx
// BEFORE
<Tooltip enabled={!!sync_status?.description} content={sync_status?.description}>
  <div ...>{sync_status.label}</div>
</Tooltip>

// AFTER
{sync_status?.description ? (
  <Tooltip message={sync_status.description}>
    <Focusable>
      <div ...>{sync_status.label}</div>
    </Focusable>
  </Tooltip>
) : (
  <div ...>{sync_status.label}</div>
)}
```

- [ ] **Step 3: Migrate `proposed-changes-actions-cell.tsx`**

```tsx
// BEFORE
<Tooltip enabled={!isDeleteAllowed} content={permission.delete.message} side="left">
  <div>
    <DropdownMenuItem disabled={!isDeleteAllowed} ...>...</DropdownMenuItem>
  </div>
</Tooltip>

// AFTER
{!isDeleteAllowed ? (
  <Tooltip message={permission.delete.message} placement="left">
    <Focusable>
      <div>
        <DropdownMenuItem disabled ...>...</DropdownMenuItem>
      </div>
    </Focusable>
  </Tooltip>
) : (
  <DropdownMenuItem ...>...</DropdownMenuItem>
)}
```

- [ ] **Step 4: Migrate `ip-address-available-create-form-trigger.tsx`**

```tsx
// BEFORE
<Tooltip enabled={!isCreationAllowed} content={!isCreationAllowed && permission.create.message} side="right">
  <IpAddressAvailableIdentifier ... />
</Tooltip>

// AFTER
{!isCreationAllowed ? (
  <Tooltip message={permission.create.message} placement="right">
    <Focusable>
      <IpAddressAvailableIdentifier ... />
    </Focusable>
  </Tooltip>
) : (
  <IpAddressAvailableIdentifier ... />
)}
```

- [ ] **Step 5: Migrate `ip-prefix-available-identifier.tsx`**

Same pattern as ip-address above:

```tsx
{!isCreationAllowed ? (
  <Tooltip message={permission.create.message} placement="right">
    <Focusable>
      <Button disabled ...>...</Button>
    </Focusable>
  </Tooltip>
) : (
  <Button disabled={!isCreationAllowed} ...>...</Button>
)}
```

Note: `<Button>` is focusable, but it has `disabled` which removes focusability. Use `Focusable` for the disabled case.

- [ ] **Step 6: Build check**

Run: `cd frontend/app && pnpm build`

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(tooltip): migrate consumers with conditional enabled"
```

---

### Task 7: Migrate PC action buttons and combobox lists

These files use the disabled-button-with-tooltip pattern and need special handling.

**Files:**
- Modify: `src/entities/proposed-changes/ui/action-button/pc-approve-button.tsx`
- Modify: `src/entities/proposed-changes/ui/action-button/pc-close-button.tsx`
- Modify: `src/entities/proposed-changes/ui/action-button/pc-merge-button.tsx`
- Modify: `src/entities/proposed-changes/ui/action-button/pc-reject-button.tsx`
- Modify: `src/entities/proposed-changes/ui/action-button/pc-draft-button.tsx`
- Modify: `src/entities/proposed-changes/ui/action-button/pc-action-combobox-list.tsx`
- Modify: `src/entities/proposed-changes/ui/action-button/pc-review-combobox-list.tsx`

- [ ] **Step 1: Migrate PC action buttons (5 files)**

All 5 action buttons follow the same pattern. Example for `pc-approve-button.tsx`:

```tsx
import { Tooltip } from "@/shared/components/aria/tooltip";
import { Focusable } from "react-aria-components";

// Replace the return JSX. BEFORE:
<Tooltip content={tooltipContent} enabled={tooltipEnabled} className="whitespace-pre">
  <Button
    className="flex h-full grow flex-wrap gap-2 rounded-r-none border-r-white"
    onClick={handleAction}
    variant={"primary"}
    isLoading={isPending}
    disabled={tooltipEnabled || isPending}
  >
    {hasApproved ? "Cancel Approve" : "Approve"}
  </Button>
</Tooltip>

// AFTER:
{tooltipEnabled ? (
  <Tooltip message={tooltipContent} className="whitespace-pre">
    <Focusable>
      <span className="flex h-full grow">
        <Button
          className="flex h-full w-full flex-wrap gap-2 rounded-r-none border-r-white"
          variant={"primary"}
          disabled
        >
          {hasApproved ? "Cancel Approve" : "Approve"}
        </Button>
      </span>
    </Focusable>
  </Tooltip>
) : (
  <Button
    className="flex h-full grow flex-wrap gap-2 rounded-r-none border-r-white"
    onClick={handleAction}
    variant={"primary"}
    isLoading={isPending}
    disabled={isPending}
  >
    {hasApproved ? "Cancel Approve" : "Approve"}
  </Button>
)}
```

Apply same transformation to `pc-close-button.tsx`, `pc-merge-button.tsx`, `pc-reject-button.tsx`, `pc-draft-button.tsx` (each has the same `<Tooltip>...<Button>` pattern, just different variant and labels).

Remove `const tooltipEnabled` local variables — replace with inline conditions where needed, or keep them for readability.

- [ ] **Step 2: Migrate combobox lists (2 files)**

**pc-action-combobox-list.tsx** and **pc-review-combobox-list.tsx** have the same pattern:

```tsx
import { Tooltip } from "@/shared/components/aria/tooltip";
import { Focusable } from "react-aria-components";

// BEFORE (inside the map):
<Tooltip enabled content={action.message} className="whitespace-pre" key={action.value}>
  <span className="ml-5 flex cursor-default select-none items-center gap-2 truncate rounded-md px-2 py-1.5 text-sm opacity-50 outline-hidden">
    {action.name}
  </span>
</Tooltip>

// AFTER:
<Tooltip message={action.message} className="whitespace-pre" key={action.value}>
  <Focusable>
    <span className="ml-5 flex cursor-default select-none items-center gap-2 truncate rounded-md px-2 py-1.5 text-sm opacity-50 outline-hidden">
      {action.name}
    </span>
  </Focusable>
</Tooltip>
```

- [ ] **Step 3: Build check**

Run: `cd frontend/app && pnpm build`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(tooltip): migrate PC action buttons and combobox lists"
```

---

### Task 8: Migrate progress bar

**Files:**
- Modify: `src/shared/components/stats/multiple-progress-bar.tsx`

This is a special case: conditional `enabled={!!tooltip}` with `className="max-w-48"` and the child is `<ProgressPrimitive.Indicator>` (non-focusable Radix component).

- [ ] **Step 1: Migrate `multiple-progress-bar.tsx`**

```tsx
import { Focusable } from "react-aria-components";

import { Tooltip } from "@/shared/components/aria/tooltip";
import { classNames } from "@/shared/utils/common";

interface ProgressBarItemProps extends ProgressPrimitive.ProgressIndicatorProps {
  value: number;
  color?: string;
  tooltip?: React.ReactNode;
}
```

Replace the map body:

```tsx
// BEFORE
{elements.map(({ className, color, style, tooltip, value, ...props }, index) => {
  return (
    <Tooltip key={index} content={tooltip} enabled={!!tooltip} className="max-w-48">
      <ProgressPrimitive.Indicator
        className={classNames("h-full transition-all", className)}
        style={{
          width: `${value}%`,
          backgroundColor: color ?? `rgba(9,135,168, ${1 - index * (1 / length)})`,
          ...style,
        }}
        {...props}
      />
    </Tooltip>
  );
})}

// AFTER
{elements.map(({ className, color, style, tooltip, value, ...props }, index) => {
  const indicator = (
    <ProgressPrimitive.Indicator
      className={classNames("h-full transition-all", className)}
      style={{
        width: `${value}%`,
        backgroundColor: color ?? `rgba(9,135,168, ${1 - index * (1 / length)})`,
        ...style,
      }}
      {...props}
    />
  );

  if (!tooltip) return <React.Fragment key={index}>{indicator}</React.Fragment>;

  return (
    <Tooltip key={index} message={tooltip} className="max-w-48">
      <Focusable>
        {indicator}
      </Focusable>
    </Tooltip>
  );
})}
```

Note: Remove `type TooltipProps` from imports since `tooltip` type is now just `React.ReactNode`.

- [ ] **Step 2: Build check**

Run: `cd frontend/app && pnpm build`

- [ ] **Step 3: Commit**

```bash
git add src/shared/components/stats/multiple-progress-bar.tsx
git commit -m "refactor(tooltip): migrate progress bar to aria tooltip"
```

---

### Task 9: Delete old tooltip and remove Radix dependency

**Files:**
- Delete: `src/shared/components/ui/tooltip.tsx`
- Modify: `package.json`

- [ ] **Step 1: Verify no remaining imports of old tooltip**

Run: `grep -r "shared/components/ui/tooltip" src/`
Expected: No results.

- [ ] **Step 2: Delete the old tooltip file**

```bash
rm src/shared/components/ui/tooltip.tsx
```

- [ ] **Step 3: Check if `@radix-ui/react-tooltip` is used elsewhere**

Run: `grep -r "@radix-ui/react-tooltip" src/`
Expected: No results (only was used in the deleted file).

- [ ] **Step 4: Remove the dependency**

```bash
cd frontend/app && pnpm remove @radix-ui/react-tooltip
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(tooltip): remove old Radix tooltip and dependency"
```

---

### Task 10: Final verification

- [ ] **Step 1: Full build**

Run: `cd frontend/app && pnpm build`
Expected: Build succeeds with no errors.

- [ ] **Step 2: Lint and format**

Run: `cd frontend/app && pnpm biome:fix`
Expected: No lint errors introduced.

- [ ] **Step 3: Run unit tests**

Run: `cd frontend/app && pnpm test`
Expected: All tests pass.

- [ ] **Step 4: Final commit (if lint/format changed anything)**

```bash
git add -A
git commit -m "style: format after tooltip migration"
```
