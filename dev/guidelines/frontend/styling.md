# Styling Guidelines

> Part of: `dev/guidelines/frontend/`

## Layout Components

Use `Col` and `Row` components from `@/shared/components/container` instead of raw divs with flexbox classes.

```tsx
import { Col, Row } from "@/shared/components/container";

// ✅ Good: Use Row for horizontal layout
<Row>
  <span>Label</span>
  <input />
</Row>

// ✅ Good: Use Col for vertical layout
<Col>
  <header>Title</header>
  <main>Content</main>
</Col>

// ❌ Bad: Don't use raw divs with flex classes
<div className="flex items-center gap-2">
  <span>Label</span>
  <input />
</div>

// ✅ Good: Override with className when needed
<Row className="justify-between gap-4">
  <span>Label</span>
  <input />
</Row>
```

**Why**: Consistent layout primitives, less repetition, easier to maintain.

## classNames Utility

```tsx
import { classNames } from "@/shared/utils/common";

className={classNames("base", isActive && "active", className)}
```

Use for: conditionals, CVA merging, className prop override.
Skip for: static class strings.

## CVA (Class Variance Authority)

Use when component has 2+ predefined visual variants.

```tsx
const buttonVariants = cva("inline-flex items-center rounded-md", {
  variants: {
    variant: {
      primary: "bg-custom-blue-700 text-white",
      secondary: "bg-gray-100 text-gray-900",
    },
    size: { sm: "h-8 px-3", md: "h-10 px-4" },
  },
  defaultVariants: { variant: "primary", size: "md" },
});

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = ({ variant, size, className, ref, ...props }: ButtonProps) => (
  <button ref={ref} className={classNames(buttonVariants({ variant, size }), className)} {...props} />
);
```

## Theme tokens

Style with the semantic theme tokens (`bg-surface`, `text-foreground-muted`, ...) instead of raw
palette classes, so surfaces follow the active light/dark theme. When migrating a hard-coded color
to a token:

- **A token swap is a visual change unless the rendered value is identical.** Check the token's
  computed value in both themes against the class it replaces before claiming "light theme
  unchanged" in a PR, and list any deliberate visual change in the description. A solid fill
  replaced by a translucent overlay, or `neutral-100` replaced by a `stone-600/10` wash, is a
  user-visible change even though the diff looks mechanical.
- **Stay in the theme's palette family.** Don't map a surface to a `gray-*`-backed token when the
  surrounding theme uses `neutral`/`stone` — pick the token whose family and shade match what the
  surface rendered before.
- **Keep readable text at WCAG AA (4.5:1).** Secondary text (labels, badges, nav items, hints) takes
  the muted-foreground tier; the faintest tier is only for decorative or placeholder content that
  may fall below AA. Demoting readable text to the faintest tier is the most-repeated review finding.
- **Fixed-scheme surfaces don't take theme tokens.** A component hardcoded to one scheme (an
  always-dark code viewer) needs values readable on that surface; a token that flips with the theme
  is unreadable in one mode.
- **Identical sibling controls take identical tokens**, and a token added to `theme.css` needs a
  consumer in the same PR.

## Forbidden

| Don't | Do |
|-------|-----|
| Inline `style={{}}` | Tailwind classes |
| CSS modules | Tailwind utilities |
| `bg-[#1e40af]` | `bg-custom-blue-700` (use theme) |
| `<div className="flex items-center gap-2">` | `<Row>` from `@/shared/components/container` |
| `<div className="flex flex-col gap-2">` | `<Col>` from `@/shared/components/container` |
