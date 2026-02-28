# File Naming Conventions

> Part of: `dev/guidelines/frontend/`

## File Suffixes

| Suffix | Purpose | Location | Example |
|--------|---------|----------|---------|
| `.tsx` | React component | ui/ or shared/components/ | `user-profile.tsx` |
| `.ts` | TypeScript module | any | `format-date.ts` |
| `.field.tsx` | Form field component | shared/components/form/fields/ | `input.field.tsx` |
| `.atom.ts` | Jotai atom | shared/stores/ | `time.atom.ts` |
| `.types.ts` | Domain types | domain/ | `branch.types.ts` |
| `.mappers.ts` | Transform functions (optional) | domain/ | `branch.mappers.ts` |
| `.query.ts` | queryOptions + useQuery hook | ui/queries/ | `get-branches.query.ts` |
| `.mutation.ts` | useMutation hook | ui/queries/ | `create-branch.mutation.ts` |
| `.query-keys.ts` | Query key factory | ui/queries/ | `branch.query-keys.ts` |
| `.test.ts(x)` | Test (colocated) | any | `button.test.tsx` |
| `.generated.ts` | Auto-generated | generated/ | `types.generated.ts` |

## Directory Patterns

| Directory | Pattern | Example |
|-----------|---------|---------|
| `shared/components/` | `kebab-case.tsx` | `button.tsx` |
| `shared/components/form/fields/` | `kebab-case.field.tsx` | `input.field.tsx` |
| `shared/hooks/` | `useCamelCase.ts` | `useDebounce.ts` |
| `shared/stores/` | `kebab-case.atom.ts` | `time.atom.ts` |
| `entities/{name}/api/` | `verb-noun-from-api.ts` | `get-branches-from-api.ts` |
| `entities/{name}/domain/` | `verb-noun.ts` | `get-branches.ts` |
| `entities/{name}/domain/` | `{noun}.types.ts` | `branch.types.ts` |
| `entities/{name}/domain/` | `{noun}.mappers.ts` (optional) | `branch.mappers.ts` |
| `entities/{name}/ui/queries/` | `verb-noun.query.ts` | `get-branches.query.ts` |
| `entities/{name}/ui/queries/` | `verb-noun.mutation.ts` | `create-branch.mutation.ts` |
| `entities/{name}/ui/queries/` | `{noun}.query-keys.ts` | `branch.query-keys.ts` |
| `entities/{name}/ui/` | `kebab-case.tsx` | `branches-table.tsx` |
| `pages/` | `kebab-case.tsx` | `login.tsx` |

## Rules

- All files: `kebab-case`
- Tests: colocate with source, never in `__tests__/`
- Types: `{noun}.types.ts` in entity `domain/`, or inline in component
- Avoid `index.ts` barrel exports; prefer direct imports
