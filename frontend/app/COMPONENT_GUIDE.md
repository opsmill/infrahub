# Infrahub Frontend Component Guide

This document captures the established patterns and conventions for building React components in the Infrahub frontend.

## Tech Stack

| Category | Technology |
|----------|------------|
| Framework | React 19.2 |
| Styling | Tailwind CSS v4 + CVA |
| UI Primitives | Radix UI + React Aria |
| Forms | react-hook-form |
| Icons | Iconify + Lucide React |
| Build | Vite |
| Formatting | Biome |

## Directory Structure

```
src/shared/components/
├── ui/           # Base UI components (Button, Card, Input, Badge)
├── buttons/      # Button variants and composed buttons
├── form/         # Form system with field components
│   └── fields/   # Specific field implementations
├── inputs/       # Input components (Dropdown, DatePicker, etc.)
├── aria/         # React Aria wrapped components
├── display/      # Presentation components (Avatar, Slide-over)
├── layout/       # Layout components
├── table/        # Table components
├── modals/       # Modal implementations
├── loading/      # Loading/skeleton components
└── filters/      # Filter components
```

## Core Utilities

### Class Merging

Always use the `classNames` utility for combining Tailwind classes:

```typescript
import { classNames } from "@/utils/common";

// Combines clsx + tailwind-merge for intelligent class merging
const className = classNames(
  "base-classes",
  conditional && "conditional-class",
  props.className
);
```

### Focus Styles

Use established focus utilities for consistent focus rings:

```typescript
import { focusVisibleStyle, focusWithinStyle } from "@/utils/common";

// focusVisibleStyle includes:
// "transition-colors focus-visible:outline-hidden focus-visible:ring-2
//  focus-visible:ring-custom-blue-600/25 focus-visible:border-custom-blue-600"
```

### Input Base Style

Use the preset input style for form inputs:

```typescript
import { inputStyle } from "@/shared/components/ui/input";

// inputStyle includes:
// "min-h-10 flex items-center w-full rounded-md border border-gray-300
//  bg-white p-2 text-sm placeholder:text-gray-400 focus-visible:outline-hidden
//  focus-visible:ring-2 focus-visible:ring-custom-blue-600/25
//  focus-visible:border-custom-blue-600 disabled:cursor-not-allowed disabled:bg-gray-100"
```

## Component Patterns

### Basic Component with CVA

```typescript
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type HTMLAttributes } from "react";
import { classNames } from "@/utils/common";

const componentVariants = cva(
  // Base styles (always applied)
  "inline-flex items-center justify-center rounded-md",
  {
    variants: {
      variant: {
        default: "bg-white border border-gray-200",
        primary: "bg-custom-blue-700 text-white",
        danger: "bg-red-600 text-white",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-2 text-sm",
        lg: "h-10 px-6",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ComponentProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof componentVariants> {}

export const Component = forwardRef<HTMLDivElement, ComponentProps>(
  ({ className, variant, size, ...props }, ref) => (
    <div
      ref={ref}
      className={classNames(componentVariants({ variant, size }), className)}
      {...props}
    />
  )
);

Component.displayName = "Component";
```

### Compound Component Pattern

```typescript
const CardRoot = forwardRef<HTMLDivElement, CardProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={classNames("rounded-xl border border-gray-200 bg-white p-3", className)}
      {...props}
    />
  )
);

const CardTitle = ({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) => (
  <h3 className={classNames("font-semibold text-gray-900", className)} {...props} />
);

const CardContent = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div className={classNames("text-sm text-gray-600", className)} {...props} />
);

export const Card = Object.assign(CardRoot, {
  Title: CardTitle,
  Content: CardContent,
});

// Usage:
// <Card>
//   <Card.Title>Title</Card.Title>
//   <Card.Content>Content</Card.Content>
// </Card>
```

### Button with Tooltip

```typescript
import { Tooltip, type TooltipProps } from "@/shared/components/ui/tooltip";
import { Button, type ButtonProps } from "@/shared/components/ui/button";

interface ButtonWithTooltipProps extends ButtonProps {
  tooltipContent?: TooltipProps["content"];
  tooltipEnabled?: TooltipProps["enabled"];
  side?: TooltipProps["side"];
}

export const ButtonWithTooltip = forwardRef<HTMLButtonElement, ButtonWithTooltipProps>(
  ({ tooltipContent, tooltipEnabled, side, ...props }, ref) => (
    <Tooltip enabled={tooltipEnabled} content={tooltipContent} side={side}>
      <Button ref={ref} {...props} />
    </Tooltip>
  )
);
```

## Color Palette

### Brand Colors (custom-blue)

| Token | Hex | Usage |
|-------|-----|-------|
| `custom-blue-50` | Light tint | Hover backgrounds |
| `custom-blue-100` | - | Light backgrounds |
| `custom-blue-200` | - | Avatar backgrounds |
| `custom-blue-600` | - | Focus rings, borders |
| `custom-blue-700` | - | Primary buttons, links |
| `custom-blue-800` | - | Hover states |
| `custom-blue-900` | - | Active states |

### Semantic Colors

| Token | Usage |
|-------|-------|
| `custom-blue-green` (#0B6581) | Secondary accent |
| `custom-blue-gray` (#0D3F54) | Dark accent |
| `custom-gray` (#0B1829) | Near-black |

### Gray Scale (Tailwind defaults)

| Token | Usage |
|-------|-------|
| `gray-50` | Page backgrounds |
| `gray-100` | Disabled inputs, hover |
| `gray-200` | Borders, dividers |
| `gray-300` | Input borders |
| `gray-400` | Placeholder text |
| `gray-500` | Secondary text |
| `gray-600` | Body text |
| `gray-700` | Emphasized text |
| `gray-900` | Headings |

### Status Colors

| State | Background | Text | Border |
|-------|------------|------|--------|
| Success | `green-50` | `green-700` | `green-200` |
| Warning | `yellow-50` | `yellow-700` | `yellow-200` |
| Error | `red-50` | `red-700` | `red-200` |
| Info | `blue-50` | `blue-700` | `blue-200` |

## Spacing Conventions

### Component Internal Spacing

| Context | Value | Tailwind |
|---------|-------|----------|
| Tight | 4px | `gap-1`, `p-1` |
| Default | 8px | `gap-2`, `p-2` |
| Comfortable | 12px | `gap-3`, `p-3` |
| Spacious | 16px | `gap-4`, `p-4` |

### Form Field Spacing

```typescript
// Standard form field wrapper
<div className="space-y-2">
  <Label />
  <Input />
  <FormMessage />
</div>

// Form sections
<div className="space-y-4">
  <FieldGroup />
  <FieldGroup />
</div>
```

### Layout Spacing

| Context | Value | Tailwind |
|---------|-------|----------|
| Section gap | 24px | `gap-6` |
| Card padding | 12px | `p-3` |
| Modal padding | 16-24px | `p-4` to `p-6` |

## Typography

### Font

- Family: `InterVariable` (variable weight 100-900)
- Base size: 14px (`--base-font-size`)

### Text Sizes

| Size | Tailwind | Usage |
|------|----------|-------|
| Extra small | `text-xxs` (0.625rem) | Badges, labels |
| Small | `text-sm` | Body text, inputs |
| Base | `text-base` | Default |
| Large | `text-lg` | Subheadings |
| XL+ | `text-xl`, `text-2xl` | Headings |

### Text Colors

| Purpose | Class |
|---------|-------|
| Primary | `text-gray-900` |
| Secondary | `text-gray-600` |
| Muted | `text-gray-500` |
| Placeholder | `text-gray-400` |
| Inverse | `text-white` |
| Link | `text-custom-blue-700` |

## Border & Radius

### Border Radius

| Size | Tailwind | Usage |
|------|----------|-------|
| Small | `rounded-sm` | Buttons, small elements |
| Medium | `rounded-md` | Inputs, dropdowns |
| Large | `rounded-lg` | Cards |
| XL | `rounded-xl` | Large cards, modals |
| Full | `rounded-full` | Avatars, icon buttons |

### Border Colors

| State | Class |
|-------|-------|
| Default | `border-gray-200` |
| Input | `border-gray-300` |
| Focus | `border-custom-blue-600` |
| Error | `border-red-500` |

## Accessibility Patterns

### Required Attributes

```typescript
// Interactive elements
<button
  type="button"
  aria-label="Close dialog"
  aria-expanded={isOpen}
  aria-controls="menu-id"
/>

// Form inputs
<input
  id={id}
  aria-invalid={!!error}
  aria-describedby={`${id}-error`}
/>

// Error messages
<span id={`${id}-error`} role="alert">
  {error}
</span>
```

### Keyboard Navigation

- All interactive elements must be focusable
- Use `tabIndex={0}` for custom interactive elements
- Implement arrow key navigation for lists/menus
- Support Escape to close modals/dropdowns

### Semantic HTML

```typescript
// Tables
<table>
  <thead>
    <tr>
      <th scope="col">Header</th>
    </tr>
  </thead>
  <tbody>...</tbody>
</table>

// Navigation
<nav aria-label="Breadcrumb">
  <ol>...</ol>
</nav>

// Sections
<section aria-labelledby="section-heading">
  <h2 id="section-heading">Title</h2>
</section>
```

## Form Field Pattern

### Standard Field Structure

```typescript
import { FormField, FormInput, FormMessage } from "@/shared/components/form";
import { LabelFormField } from "@/shared/components/form/fields/common";

const CustomField = ({ name, label, description, rules, ...props }) => {
  return (
    <FormField
      name={name}
      rules={rules}
      render={({ field }) => (
        <div className="space-y-2">
          <LabelFormField
            label={label}
            required={!!rules?.required}
            description={description}
          />
          <FormInput>
            <Input {...field} {...props} />
          </FormInput>
          <FormMessage />
        </div>
      )}
    />
  );
};
```

## Icons

### Usage

```typescript
// Iconify (preferred for MDI icons)
import { Icon } from "@iconify-icon/react";
<Icon icon="mdi:account" className="text-gray-500" />

// Lucide (for common UI icons)
import { ChevronDown, X, Search } from "lucide-react";
<ChevronDown className="h-4 w-4 text-gray-500" />
```

### Icon Sizes

| Context | Size | Class |
|---------|------|-------|
| Inline | 16px | `h-4 w-4` |
| Button | 20px | `h-5 w-5` |
| Large | 24px | `h-6 w-6` |

## Common Component Classes

### Cards

```typescript
// Basic card
"rounded-xl border border-gray-200 bg-white p-3"

// Card with shadow
"rounded-xl border border-gray-200 bg-white p-3 shadow-sm"

// Interactive card
"rounded-xl border border-gray-200 bg-white p-3 hover:border-gray-300 hover:shadow-sm transition-all cursor-pointer"
```

### Buttons

```typescript
// Primary
"bg-custom-blue-700 text-white hover:bg-custom-blue-700/90"

// Secondary/Outline
"border border-gray-200 bg-white hover:bg-gray-100"

// Ghost
"hover:bg-gray-100"

// Danger
"bg-red-600 text-white hover:bg-red-700"
```

### Inputs

```typescript
// Base input
"min-h-10 w-full rounded-md border border-gray-300 bg-white p-2 text-sm"

// Focus state
"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-custom-blue-600/25 focus-visible:border-custom-blue-600"

// Disabled
"disabled:cursor-not-allowed disabled:bg-gray-100"

// Error
"border-red-500 focus-visible:ring-red-600/25 focus-visible:border-red-500"
```

### Badges

```typescript
// Default
"inline-flex items-center rounded-full px-2 py-1 text-xs font-medium"

// Variants
"bg-gray-100 text-gray-700"      // default
"bg-green-100 text-green-700"    // success
"bg-yellow-100 text-yellow-700"  // warning
"bg-red-100 text-red-700"        // error
"bg-blue-100 text-blue-700"      // info
```

## Animation

### Transitions

```typescript
// Color transitions
"transition-colors"

// All properties
"transition-all"

// Duration
"duration-150"  // fast
"duration-200"  // default
"duration-300"  // slow
```

### Loading States

```typescript
// Spinner animation
"animate-spin"

// Pulse (skeleton)
"animate-pulse bg-gray-200 rounded"
```

## Testing

Components should have corresponding test files:

```
component.tsx
component.test.tsx
```

Use Vitest for unit tests and Playwright for E2E tests.
