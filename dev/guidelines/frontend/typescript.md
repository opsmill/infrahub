# TypeScript Coding Standards

> Part of: `dev/guidelines/frontend/` | Related: `dev/knowledge/frontend/architecture.md`

Coding standards for the TypeScript/React frontend.

## File Naming

- Components: `kebab-case.tsx`
- Atoms: `kebab-case.atom.ts`
- Tests: `*.test.ts` or `*.test.tsx` (colocated)
- Types: `types.ts` or inline

## Component Patterns

Follow React best practices and project conventions. See `frontend/app/AGENTS.md` for component-specific patterns.

## Type Safety

- Use TypeScript types for all props and state
- Avoid `any` - use `unknown` if type is truly unknown
- Prefer type inference where possible

## See Also

- `frontend/app/AGENTS.md` - Frontend-specific patterns and structure
- `dev/knowledge/frontend/architecture.md` - Frontend architecture overview
