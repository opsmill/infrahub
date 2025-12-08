# Tailwind CSS Usage Guide

Patterns extracted from the actual Infrahub frontend codebase.

## Color Palette

### Custom Blue (Primary Brand)

| Token | Hex | Usage |
|-------|-----|-------|
| `custom-blue-1` | #E4F3F7 | Very light backgrounds |
| `custom-blue-10` | #a7d9e6 | Light tints |
| `custom-blue-50` | #23a1c1 | Lighter interactive |
| `custom-blue-100` | #3babc8 | Light |
| `custom-blue-200` | #54b6cf | Medium-light |
| `custom-blue-500` | #0B97BB | Primary interactive, icons, hover |
| `custom-blue-600` | #0987a8 | Focus rings, borders |
| `custom-blue-700` | #087895 | **Primary buttons**, links |
| `custom-blue-800` | #076982 | Dark text/icons |
| `custom-blue-900` | #065a70 | Darkest shade |

```tsx
// Primary button
"bg-custom-blue-700 text-custom-white hover:bg-custom-blue-500"

// Focus ring
"focus-visible:ring-custom-blue-600/25 focus-visible:border-custom-blue-600"

// Badge tint
"bg-custom-blue-700/10 text-custom-blue-700"

// Icon
"text-custom-blue-500"
```

### Gray Scale

| Token | Usage |
|-------|-------|
| `gray-50` | Section backgrounds, table alternation |
| `gray-100` | Disabled inputs, hover backgrounds |
| `gray-200` | **Borders**, dividers, hover states |
| `gray-300` | Input borders |
| `gray-400` | Placeholder text, secondary icons |
| `gray-500` | Secondary/muted text |
| `gray-600` | Tertiary text |
| `gray-700` | Table headers |
| `gray-900` | **Primary text** |

```tsx
// Primary text
"text-gray-900"

// Secondary text
"text-gray-500"

// Placeholder
"placeholder:text-gray-400"

// Border
"border-gray-200"

// Input border
"border-gray-300"

// Hover background
"hover:bg-gray-100"
```

### Status Colors

#### Green (Success/Active)

```tsx
// Badge
"bg-green-700/10 text-green-900"

// Avatar
"bg-green-300 text-green-700"

// Solid
"bg-green-500 text-white"

// Border indicator
"border-2 border-green-500"
```

#### Red (Error/Danger)

```tsx
// Badge
"bg-red-100 text-red-900"

// Button
"bg-red-600 text-white hover:bg-red-700"

// Error text
"text-red-600"

// Error border
"border-red-500"

// Modal icon background
"bg-red-100"
```

#### Yellow (Warning)

```tsx
// Badge
"bg-yellow-100 text-yellow-900"

// Indicator
"bg-yellow-400"
```

---

## Spacing

### Padding

| Class | Value | Common Usage |
|-------|-------|--------------|
| `p-1` | 4px | Tight spacing |
| `p-2` | 8px | **Table cells**, small components |
| `p-3` | 12px | **Cards**, medium components |
| `p-4` | 16px | **Modals**, large containers |
| `p-6` | 24px | Modal content |

```tsx
// Card
"p-3"

// Table cell
"p-2"

// Modal content
"p-6" or "px-4 pt-5 pb-4"

// Dropdown menu
"p-2"
```

### Margin

| Pattern | Usage |
|---------|-------|
| `ml-auto` | Push element right |
| `mr-2` | Small right spacing |
| `my-1` | Vertical spacing |
| `mx-auto` | Center horizontally |
| `-mb-px` | Tab underline offset |

### Gap (Flexbox/Grid)

| Class | Value | Usage |
|-------|-------|-------|
| `gap-0.5` | 2px | Minimal spacing |
| `gap-1` | 4px | Tight |
| `gap-1.5` | 6px | **Table cells**, dropdown items |
| `gap-2` | 8px | **Standard spacing** |
| `gap-4` | 16px | Section spacing |

```tsx
// Standard flex container
"flex items-center gap-2"

// Table cell content
"flex items-center gap-1.5"

// Grid layout
"grid grid-cols-3 gap-4"
```

### Space (Children Spacing)

```tsx
// Form fields
"space-y-4"

// Accordion items
"space-y-2"

// Navigation tabs
"space-x-8"

// Menu items
"space-y-0.5"
```

---

## Typography

### Text Sizes

| Class | Size | Usage |
|-------|------|-------|
| `text-xxs` | 10px | Ultra-small labels |
| `text-xs` | 12px | Badges, metadata, table headers |
| `text-sm` | 14px | **Body text**, inputs |
| `text-base` | 16px | Normal text |
| `text-lg` | 18px | Section titles |
| `text-xl` | 20px | Major headings |
| `text-2xl` | 24px | Large headings |

### Font Weights

| Class | Usage |
|-------|-------|
| `font-normal` | Body text |
| `font-medium` | Emphasized text, table headers |
| `font-semibold` | **Buttons**, strong emphasis |
| `font-bold` | Section titles |

### Common Combinations

```tsx
// Primary heading
"text-xl font-bold text-gray-900"

// Section title
"text-lg font-semibold text-gray-900"

// Body text
"text-sm text-gray-600"

// Table header
"text-xs font-medium text-gray-700"

// Button text
"text-sm font-semibold"

// Muted/secondary
"text-sm text-gray-500"

// Badge
"text-xs font-medium"
```

---

## Borders & Radius

### Border Radius

| Class | Size | Usage |
|-------|------|-------|
| `rounded-sm` | 4px | Checkboxes, small badges |
| `rounded-md` | 6px | **Inputs**, small components |
| `rounded-lg` | 8px | **Modals**, containers |
| `rounded-xl` | 12px | **Cards**, dropdown menus |
| `rounded-full` | 50% | Avatars, circular elements |

```tsx
// Card
"rounded-xl"

// Input
"rounded-md"

// Modal
"rounded-lg"

// Dropdown menu
"rounded-xl"

// Avatar
"rounded-full"

// Button
"rounded-sm"
```

### Borders

```tsx
// Standard border
"border border-gray-200"

// Input border
"border border-gray-300"

// Divider
"border-b border-gray-200"

// Tab underline (active)
"border-b-2 border-custom-blue-500"

// Tab underline (inactive)
"border-b-2 border-transparent"

// Status indicator
"border-2 border-green-500"
```

---

## Shadows

| Class | Usage |
|-------|-------|
| `shadow-xs` | **Buttons**, inputs, tooltips |
| `shadow-sm` | Primary buttons |
| `shadow-lg` | **Dropdown menus**, popovers |
| `shadow-xl` | **Modals**, slide-overs |

```tsx
// Button
"shadow-xs"

// Primary button
"shadow-sm"

// Dropdown
"shadow-lg"

// Modal
"shadow-xl"
```

---

## Layout

### Flexbox Patterns

```tsx
// Standard row with centered items
"flex items-center gap-2"

// Vertical stack
"flex flex-col gap-2"

// Space between
"flex items-center justify-between"

// Centered content
"flex items-center justify-center"

// Right-aligned
"flex justify-end"

// Full height centered (modals)
"flex min-h-full items-center justify-center"

// Reversed row (modal buttons)
"flex flex-row-reverse"
```

### Width & Height

```tsx
// Full width
"w-full"

// Icon sizes
"h-4 w-4"   // 16px - inline icons
"h-5 w-5"   // 20px - button icons
"h-6 w-6"   // 24px - larger icons
"h-8 w-8"   // 32px - prominent icons

// Input height
"min-h-10"  // 40px

// Button heights
"h-7"       // 28px - small
"h-8"       // 32px - default
"h-9"       // 36px - medium

// Fixed width panel
"w-[400px]"

// Modal max width
"max-w-lg"

// Dropdown min width
"min-w-32"
```

### Grid

```tsx
// 3-column grid
"grid grid-cols-3 gap-4"
```

---

## Interactive States

### Hover

```tsx
// Background hover
"hover:bg-gray-50"   // Subtle (table rows)
"hover:bg-gray-100"  // Standard
"hover:bg-gray-200"  // Stronger

// Primary hover
"hover:bg-custom-blue-500"

// Text hover
"hover:text-gray-700"

// Border hover
"hover:border-gray-300"

// Link
"hover:underline"
```

### Focus

```tsx
// Standard focus ring (inputs, buttons)
"focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-custom-blue-600/25 focus-visible:border-custom-blue-600"

// Focus within (form containers)
"focus-within:ring-2 focus-within:ring-custom-blue-600/25"

// Error focus
"focus-visible:border-red-500 focus-visible:ring-red-500/25"

// Dropdown item focus
"focus:bg-neutral-100"
```

### Disabled

```tsx
// Standard disabled
"disabled:cursor-not-allowed disabled:opacity-60"

// Input disabled
"disabled:cursor-not-allowed disabled:bg-gray-100"

// Button disabled
"disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-60"

// Primary button disabled
"disabled:bg-custom-blue-gray disabled:text-custom-white"
```

### Active/Selected

```tsx
// Data state (Radix UI)
"data-[state=open]:bg-neutral-100"

// Selected tab
"border-custom-blue-500 text-custom-blue-600"

// Unselected tab
"border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
```

---

## Transitions & Animations

### Transitions

```tsx
// Color transition (hover states)
"transition-colors"

// All properties
"transition-all"

// With duration
"transition-all duration-200"
"transition-colors duration-300"
```

### Animations

```tsx
// Spinner
"animate-spin"

// Pulse (notifications)
"animate-ping"

// Skeleton loading
"animate-[pulse_1s_ease-in-out_infinite]"
```

---

## Z-Index

| Class | Usage |
|-------|-------|
| `z-1` | Sticky headers |
| `z-10` | Modals, dialogs |
| `z-50` | Dropdown menus |

---

## Component Recipes

### Button (Primary)

```tsx
"inline-flex items-center justify-center gap-2 rounded-sm border border-transparent bg-custom-blue-700 px-4 py-2 text-sm font-semibold text-custom-white shadow-sm hover:bg-custom-blue-500 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-custom-blue-600/25 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-custom-blue-gray"
```

### Button (Secondary/Outline)

```tsx
"inline-flex items-center justify-center gap-2 rounded-sm border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-xs hover:bg-gray-100 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-custom-blue-600/25 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-60"
```

### Button (Ghost)

```tsx
"inline-flex items-center justify-center gap-2 rounded-sm px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-custom-blue-600/25"
```

### Button (Danger)

```tsx
"inline-flex items-center justify-center gap-2 rounded-sm border border-transparent bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-700 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-red-600/25"
```

### Input

```tsx
"min-h-10 w-full rounded-md border border-gray-300 bg-white p-2 text-sm placeholder:text-gray-400 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-custom-blue-600/25 focus-visible:border-custom-blue-600 disabled:cursor-not-allowed disabled:bg-gray-100"
```

### Card

```tsx
"rounded-xl border border-gray-200 bg-white p-3"
```

### Badge

```tsx
// Default
"inline-flex items-center rounded-md px-2 py-1 text-xs font-medium bg-gray-100 text-gray-700"

// Success
"inline-flex items-center rounded-md px-2 py-1 text-xs font-medium bg-green-700/10 text-green-900"

// Error
"inline-flex items-center rounded-md px-2 py-1 text-xs font-medium bg-red-100 text-red-900"

// Warning
"inline-flex items-center rounded-md px-2 py-1 text-xs font-medium bg-yellow-100 text-yellow-900"

// Primary
"inline-flex items-center rounded-md px-2 py-1 text-xs font-medium bg-custom-blue-700/10 text-custom-blue-700"
```

### Modal

```tsx
// Overlay
"fixed inset-0 bg-black/40 z-10"

// Container
"fixed inset-0 z-10 flex min-h-full items-center justify-center p-4"

// Panel
"relative w-full max-w-lg transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all"

// Content
"p-6"

// Footer
"flex flex-row-reverse gap-2 bg-gray-50 px-4 py-3"
```

### Dropdown Menu

```tsx
// Container
"z-50 min-w-32 overflow-hidden rounded-xl bg-white p-2 shadow-lg"

// Item
"flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-gray-700 cursor-pointer hover:bg-gray-100 focus:bg-gray-100 focus:outline-hidden"

// Divider
"-mx-1 my-1 h-px bg-gray-200"
```

### Table

```tsx
// Container
"overflow-hidden rounded-lg border border-gray-200"

// Header cell
"bg-gray-50 p-2 text-left text-xs font-medium text-gray-700"

// Body cell
"flex items-center gap-1.5 p-2 text-sm text-gray-900 bg-white"

// Row hover
"hover:bg-gray-50"
```

### Slide-over Panel

```tsx
// Overlay
"fixed inset-0 bg-black/40"

// Panel
"fixed inset-y-0 right-0 w-[400px] bg-white shadow-xl"
```

---

## Quick Reference

### Most Used Classes

**Spacing:** `p-2`, `p-3`, `p-4`, `gap-2`, `gap-1.5`

**Colors:** `custom-blue-700`, `custom-blue-500`, `gray-200`, `gray-500`, `gray-900`

**Radius:** `rounded-md`, `rounded-lg`, `rounded-xl`, `rounded-full`

**Shadows:** `shadow-xs`, `shadow-lg`, `shadow-xl`

**Text:** `text-sm`, `text-xs`, `font-medium`, `font-semibold`

**Layout:** `flex items-center`, `gap-2`, `justify-between`

**States:** `hover:bg-gray-100`, `disabled:opacity-60`, `focus-visible:ring-2`
