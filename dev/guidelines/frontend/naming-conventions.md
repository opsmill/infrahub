# File Naming Conventions

> Part of: `dev/guidelines/frontend/`

## File Suffixes

| Suffix | Purpose | Example |
|--------|---------|---------|
| `.tsx` | React component | `user-profile.tsx` |
| `.ts` | TypeScript module | `format-date.ts` |
| `.field.tsx` | Form field component | `input.field.tsx` |
| `.atom.ts` | Jotai atom | `time.atom.ts` |
| `.query.ts` | React Query options | `get-app-info.query.ts` |
| `.test.ts(x)` | Test (colocated) | `button.test.tsx` |
| `.generated.ts` | Auto-generated | `types.generated.ts` |

## Directory Patterns

| Directory | Pattern | Example |
|-----------|---------|---------|
| `shared/components/` | `kebab-case.tsx` | `button.tsx` |
| `shared/components/form/fields/` | `kebab-case.field.tsx` | `input.field.tsx` |
| `shared/hooks/` | `useCamelCase.ts` | `useDebounce.ts` |
| `shared/stores/` | `kebab-case.atom.ts` | `time.atom.ts` |
| `entities/{name}/domain/` | `verb-noun.ts` | `get-app-info.ts` |
| `entities/{name}/domain/` | `verb-noun.query.ts` | `get-app-info.query.ts` |
| `entities/{name}/ui/` | `kebab-case.tsx` | `config-provider.tsx` |
| `entities/{name}/` | `types.ts` | `types.ts` |
| `pages/` | `kebab-case.tsx` | `login.tsx` |

## Rules

- All files: `kebab-case`
- Tests: colocate with source, never in `__tests__/`
- Types: `types.ts` in entity root, or inline in component
- Avoid `index.ts` barrel exports; prefer direct imports
