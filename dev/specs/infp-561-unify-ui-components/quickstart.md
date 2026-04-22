# Quickstart: Unify UI Components

**Branch**: `infp-561-unify-ui-components` | **Date**: 2026-04-22

## Prerequisites

```bash
cd frontend/app && pnpm install
```

## Development

```bash
cd frontend/app && pnpm dev        # Start dev server
cd frontend/app && pnpm test       # Run unit tests
cd frontend/app && pnpm biome:fix  # Format and lint
```

## Migration Workflow (per component)

Each component migration follows this pattern:

### 1. Create the aria/ component (if it doesn't exist)

```bash
# Example: creating aria/button.tsx
# - Wrap react-aria-components primitive
# - Use CVA for variants
# - Use composeRenderProps for dynamic states
# - Use style tokens from style-rac.ts
# - Write colocated test: aria/button.test.tsx
```

### 2. Update all consumers in the same PR

```bash
# Find all consumers of the old component
cd frontend/app
grep -r "from.*ui/button" src/ --include="*.tsx" --include="*.ts" -l
```

Update imports:
```typescript
// Before
import { Button } from "@/shared/components/ui/button";

// After
import { Button } from "@/shared/components/aria/button";
```

Adapt any API differences (e.g., prop name changes).

### 3. Delete the old component file

```bash
# Only after ALL consumers are updated
rm src/shared/components/ui/button.tsx
```

### 4. Verify

```bash
pnpm build       # Must compile without errors
pnpm test        # All tests must pass
pnpm biome:fix   # No lint issues
```

## Component Pattern Reference

All aria/ components follow this structure:

```typescript
import { composeRenderProps, Button as AriaButton } from "react-aria-components";
import { cva } from "class-variance-authority";
import { classNames } from "@/shared/utils/common";
import { focusVisibleStyle } from "@/shared/components/aria/style-rac";

const buttonVariants = cva("inline-flex items-center justify-center rounded-md", {
  variants: {
    variant: {
      primary: "bg-custom-blue-700 text-custom-white ...",
      danger: "bg-red-600 text-custom-white ...",
    },
    size: {
      default: "h-8 px-3 text-sm",
      sm: "h-7 px-2 text-xs",
    },
  },
  defaultVariants: { variant: "primary", size: "default" },
});

export function Button({ variant, size, className, ...props }: ButtonProps) {
  return (
    <AriaButton
      {...props}
      className={composeRenderProps(className, (className, renderProps) =>
        classNames(
          buttonVariants({ variant, size }),
          renderProps.isFocusVisible && focusVisibleStyle,
          className
        )
      )}
    />
  );
}
```

## Migration Order (by PR)

1. **PR 1**: Tooltip + Popover (already exist in aria/, delete Radix versions, update 70 consumers)
2. **PR 2**: Button (create aria/button.tsx, update 120 consumers + delete specialized buttons)
3. **PR 3**: Badge (create aria/badge.tsx, absorb Pill + BadgeCircle, update 66 consumers)
4. **PR 4**: Combobox/cmdk → Autocomplete (update 35 consumers, remove cmdk dependency)
5. **PR 5**: Menu (Radix DropdownMenu → aria/menu, update 8 consumers)
6. **PR 6**: Checkbox (HTML → aria/checkbox, update 4 consumers)
7. **PR 7**: Tabs (custom → aria/tabs, update 21 consumers)
8. **PR 8**: Accordion (Radix + custom → aria/accordion, update 17 consumers)
9. **PR 9**: Modal/SlideOver consolidation
10. **PR 10**: Dependency cleanup (remove Radix + Headless UI + cmdk packages)
