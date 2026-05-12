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
| `optional?.field!` (optional chain + non-null) | Narrow with a conditional render or early return |
| `useParams() as { foo: string }` | `useRequiredParams("foo")` for route-guaranteed params |

```tsx
// Type guard pattern
if (isUserData(response)) {
  const data = response; // TS knows type
}
```

### `optional?.x!` is always wrong

`?.` says "this might be undefined" and `!` says "this is definitely defined" — they contradict on the same expression. The `!` silences the compiler but leaves the runtime trap. Fix by narrowing first:

```tsx
// ❌ Bad — type lie
<Link to={getObjectDetailsUrl(metadata?.created_by?.__typename!, metadata?.created_by?.id)} />

// ✅ Good — narrow with a conditional
{metadata?.created_by ? (
  <Link to={getObjectDetailsUrl(metadata.created_by.__typename, metadata.created_by.id)} />
) : null}

// ✅ Good — early return guard at the parent
if (!proposedChangeData.source_branch?.value) {
  return <NoDataFound message="Proposed change is missing a source branch." />;
}
const sourceBranchValue = proposedChangeData.source_branch.value; // narrowed
```

### Reading route params

Use `useRequiredParams` from `@/shared/hooks/use-required-params.ts` for params the route guarantees. The hook throws with a clear message if the param is missing — no silent `undefined` propagating into URL builders or queries.

```tsx
// ✅ Route guarantees branchName — runtime-checked
const { branchName } = useRequiredParams("branchName");

// ✅ Param is genuinely optional (button used inside and outside the route) — typed generic, no cast
const { objectKind, objectId } = useParams<{ objectKind: string; objectId: string }>();
//   ^ inferred as string | undefined — narrow before use

// ❌ The type lie pattern
const { objectKind, objectId } = useParams() as { objectKind?: string; objectId?: string };
```

If a child component reads a param to do work but a parent already has the value, prefer **passing the value as a prop** instead of re-reading. The child becomes routing-agnostic and the type narrowing happens once at the parent.

See [route-architecture.md](route-architecture.md) for the full route + outlet-context pattern.

### Boy-scout rule on rewrites

When you rewrite a file (replacing the whole component, not just a small edit), audit it for type lies (`!`, `as`, implicit `any`) in the touched expressions and fix them. Inheriting an antipattern verbatim during a rewrite is its own decision — don't make it by default. The PR that rewrites the file is the cheapest place to fix the lie.

When the rewrite also **deletes** a consumer, run `pnpm knip` before you finish — TypeScript doesn't flag dead exports, but knip will. See [route-architecture.md → Verifying cleanup](route-architecture.md#verifying-cleanup-after-a-deletion-or-rewrite).

The audit applies to **every file the rewrite commit lands in**, not just the marquee files. A commit like "drop unsafe non-null assertions" that fixes 3 files but leaves `!` survivors in 2 sibling files touched by the same PR is a half-fix — reviewers won't catch it because the commit message claims the work is done.

Concretely, before declaring a `!`-cleanup commit done, run:

```bash
git diff <base>...HEAD --name-only -- '*.ts' '*.tsx' | xargs rg -nP '(?<=[\w\])])!(?!=)' --
```

The lookbehind anchors on an identifier, `)`, or `]` so the prefix-`!` (logical NOT) doesn't match, and `(?!=)` excludes `!=` / `!==`. This catches postfix non-null assertions regardless of what follows (`.`, `,`, `;`, `)`, `]`, `}`, whitespace, end of line, `&&`, `||`, etc.).

Resolve each remaining hit (or explicitly note it as out-of-scope in the PR description).

## Inference

| Annotate | Let Infer |
|----------|-----------|
| Function parameters | Local variables |
| Public API return types | Internal return types |
| Component props | Derived values |

## Imports

- Use `@/` alias: `import { Button } from "@/shared/components/buttons/button"`
- Biome handles import order (`pnpm biome:fix`)
- **React imports**: single `import React from "react"` (or `import type React` for type-only files). No named imports — use `React.useState`, `React.Ref`, etc.

## Constants

- Module-level: `SCREAMING_SNAKE_CASE`
- Object/array constants: `PascalCase` with `as const`
