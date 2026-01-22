# Styling Guidelines

> Part of: `dev/guidelines/frontend/`

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

## Forbidden

| Don't | Do |
|-------|-----|
| Inline `style={{}}` | Tailwind classes |
| CSS modules | Tailwind utilities |
| `bg-[#1e40af]` | `bg-custom-blue-700` (use theme) |
