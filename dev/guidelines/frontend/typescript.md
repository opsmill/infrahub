# TypeScript Coding Standards

> Part of: `dev/guidelines/frontend/`

## Exports

- **Named exports** for components, hooks, utilities
- **Default exports** only for form field components (`.field.tsx`)

## Components

### Props

```tsx
// Extend HTML attributes for primitives
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary";
}

// Discriminated unions when behavior differs
type LinkProps =
  | { href: string; onClick?: never }
  | { href?: never; onClick: () => void };
```

## Hooks

- Prefix: `use*`
- Let TypeScript infer return types (annotate only when complex)
- Include all deps in useEffect/useCallback/useMemo arrays

## Type Safety

| Forbidden | Use Instead |
|-----------|-------------|
| `any` | `unknown` + type guards |
| `!` (non-null assertion) | Null check first |
| `as` (type assertion) | Type guard validation |

```tsx
// Type guard pattern
if (isUserData(response)) {
  const data = response; // TS knows type
}
```

## Inference

| Annotate | Let Infer |
|----------|-----------|
| Function parameters | Local variables |
| Public API return types | Internal return types |
| Component props | Derived values |

## Imports

- Use `@/` alias: `import { Button } from "@/shared/components/buttons/button"`
- Biome handles import order (`npm run biome:fix`)

## Constants

- Module-level: `SCREAMING_SNAKE_CASE`
- Object/array constants: `PascalCase` with `as const`
