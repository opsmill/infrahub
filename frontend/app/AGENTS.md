# AGENTS.md - Frontend

> See [root AGENTS.md](../../AGENTS.md) for project-wide commands and guidelines.

## Overview

React TypeScript frontend built with Vite, using Tailwind CSS for styling.

## Commands

```bash
cd frontend/app && pnpm setup      # Init submodules + install all dependencies (run first)
cd frontend/app && pnpm install    # Install app dependencies only (submodule must already be initialized)
cd frontend/app && pnpm dev        # Start dev server
cd frontend/app && pnpm build      # Production build
cd frontend/app && pnpm test       # Run unit tests
cd frontend && pnpm biome:fix      # Format and lint the whole workspace (app + packages/*)
cd frontend/app && pnpm codegen    # Generate GraphQL types
```

## Before pushing (run the full CI gate locally)

`pnpm biome:fix` alone is **not** the CI gate. The `frontend-lint` job runs three checks and
`frontend-tests` runs the browser test suite. Run all of them before pushing — they each fail CI
independently. Note that Biome runs from `frontend/`, the pnpm workspace root, so that one
config and one command cover `app` and `packages/*` together:

```bash
cd frontend && pnpm exec biome ci .       # format + lint, whole workspace (same as CI)
cd frontend/app && pnpm knip              # unused exports/files/deps
cd frontend/app && pnpm exec betterer ci  # TypeScript-regression gate (NOT plain tsc)
cd frontend/app && pnpm test              # vitest (browser mode)
```

## See Also

### Guidelines (How to write code)

- `dev/guidelines/frontend/component-patterns.md` - Reuse-first checklist, early returns, layout extraction
- `dev/guidelines/frontend/page-architecture.md` - State ownership, URL sync, size budgets, backend-authoritative rule
- `dev/guidelines/frontend/route-architecture.md` - Detail-page nested routes, tab bars, outlet context, route param hooks
- `dev/guidelines/frontend/naming-conventions.md` - File naming patterns and query-key shape
- `dev/guidelines/frontend/typescript.md` - TypeScript and React patterns
- `dev/guidelines/frontend/styling.md` - Tailwind CSS and CVA
- `dev/guidelines/frontend/object-forms.md` - react-hook-form patterns and focus management
- `dev/guidelines/frontend/url-construction.md` - URL building utilities

### Knowledge (How the system works)

- `dev/knowledge/frontend/react.md` - React 19 and React Compiler patterns
- `dev/knowledge/frontend/architecture.md` - Project organization
- `dev/knowledge/frontend/entities-structure.md` - Entity layer pattern (api/domain/ui), GraphQL fetching, backend authority
- `dev/knowledge/frontend/shared-components.md` - **Reuse-first inventory** — look here before building anything generic
- `dev/knowledge/frontend/design-system.md` - `@infrahub/ui` package (Button, Card, Modal, Spinner)
- `dev/knowledge/frontend/theming.md` - **Read before touching colours** — theme tokens, the dark class, how to change a colour in one theme only
- `dev/knowledge/frontend/file-components.md` - DataViewer and file handling components
- `dev/knowledge/frontend/auth-methods.md` - Auth method registry, picker, token persistence boundaries
- `dev/knowledge/frontend/branches.md` - Read before writing code that depends on which branch is current, or on the default branch — the default branch name is deployment-configurable

### Guides (How to do X)

- `dev/guides/frontend/writing-unit-tests.md` - Unit tests for TypeScript functions
- `dev/guides/frontend/writing-component-tests.md` - React component tests
- `dev/guides/frontend/writing-e2e-tests.md` - E2E tests (pytest-playwright)
- `dev/guides/frontend/adding-an-auth-method.md` - Step-by-step recipe for adding a new login method
