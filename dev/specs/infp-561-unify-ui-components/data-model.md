# Data Model: Unify UI Components

**Branch**: `infp-561-unify-ui-components` | **Date**: 2026-04-22

This feature is frontend-only and does not introduce new data entities, database changes, or API contracts. The "data model" here describes the component API surface — the props interfaces that form the contract between the unified components and their consumers.

## Component API Contracts

### Button (new — aria/button.tsx)

```typescript
interface ButtonProps extends AriaButtonProps {
  variant?: "primary" | "primary-outline" | "danger" | "warning" | "active" | "active-outline" | "outline" | "dark" | "ghost";
  size?: "default" | "sm" | "icon" | "square";
  className?: string;
  ref?: Ref<HTMLButtonElement>;
}

// Composed variants
interface LinkButtonProps extends ButtonProps {
  to: string; // React Router link
}

interface ButtonWithTooltipProps extends ButtonProps {
  tooltipContent: ReactNode;
  tooltipEnabled?: boolean;
}
```

### Badge (consolidated — aria/badge.tsx)

```typescript
interface BadgeProps {
  variant?: "white" | "gray" | "dark-gray" | "green" | "red" | "blue" | "yellow" | "purple" | "outline" | "green-outline" | "red-outline" | "blue-outline" | "yellow-outline";
  className?: string;
  children: ReactNode;
  onDismiss?: () => void; // replaces BadgeCircle's delete functionality
}
```

### Tabs (new — aria/tabs.tsx)

```typescript
interface TabsProps extends AriaTabsProps {
  className?: string;
}

interface TabProps extends AriaTabProps {
  className?: string;
}

interface TabPanelProps extends AriaTabPanelProps {
  className?: string;
}
```

### Accordion (new — aria/accordion.tsx)

```typescript
interface AccordionProps extends AriaDisclosureGroupProps {
  className?: string;
}

interface AccordionItemProps extends AriaDisclosureProps {
  title: ReactNode;
  className?: string;
}
```

### Existing aria/ Components (unchanged API)

The following components already exist in `aria/` and their APIs are stable:
- **Select**: SelectTrigger, SelectPopover, SelectList, SelectItem
- **Menu**: Menu, MenuItem, MenuSection, MenuItemWithTooltip
- **ListBox**: ListBox, ListBoxItem, ListBoxLoadMoreItem
- **Autocomplete**: Autocomplete, AutocompleteSearchField
- **Tooltip**: Tooltip (with CVA animation variants)
- **Popover**: Popover, PopoverDialog, PopoverTrigger
- **Modal**: Modal, ModalOverlay
- **Checkbox**: Checkbox
- **RadioGroup**: RadioGroup, Radio
- **Breadcrumbs**: Breadcrumbs, Breadcrumb, BreadcrumbItem
- **Label**: Label
- **Separator**: Separator
- **Tree**: Tree, TreeItem, TreeItemContent, TreeItemLoader

## Migration Mapping

### Files to Create

| File | Purpose | Based On |
|------|---------|----------|
| `aria/button.tsx` | Unified Button with CVA variants | `ui/button.tsx` API + react-aria Button |
| `aria/badge.tsx` | Unified Badge with CVA variants | `ui/badge.tsx` + `display/pill.tsx` + `display/badge-circle.tsx` |
| `aria/tabs.tsx` | react-aria Tabs | `tabs.tsx` query-param logic + react-aria Tabs |
| `aria/accordion.tsx` | react-aria Disclosure | `ui/accordion.tsx` + `display/accordion.tsx` |

### Files to Delete (after consumer migration)

| File | Replaced By |
|------|-------------|
| `ui/button.tsx` | `aria/button.tsx` |
| `ui/badge.tsx` | `aria/badge.tsx` |
| `ui/tooltip.tsx` | `aria/tooltip.tsx` (already exists) |
| `ui/popover.tsx` | `aria/popover.tsx` (already exists) |
| `ui/dropdown-menu.tsx` | `aria/menu.tsx` (already exists) |
| `ui/combobox.tsx` | `aria/autocomplete.tsx` (already exists) |
| `ui/command.tsx` | `aria/autocomplete.tsx` (already exists) |
| `ui/accordion.tsx` | `aria/accordion.tsx` (new) |
| `display/accordion.tsx` | `aria/accordion.tsx` (new) |
| `display/pill.tsx` | `aria/badge.tsx` (new) |
| `display/badge-circle.tsx` | `aria/badge.tsx` (new) |
| `inputs/checkbox.tsx` | `aria/checkbox.tsx` (already exists) |
| `buttons/info-button.tsx` | Compose from `aria/button.tsx` |
| `buttons/link-toggle-button.tsx` | Compose from `aria/button.tsx` |
| `buttons/copy-to-clipboard.tsx` | `aria/copy-to-clipboard-button.tsx` (already exists) |
| `buttons/clipboard.tsx` | `aria/copy-to-clipboard-button.tsx` (already exists) |
| `buttons/retry.tsx` | Compose from `aria/button.tsx` |
| `tabs.tsx` | `aria/tabs.tsx` (new) |
