# AGENTS.md - Frontend

> See [root AGENTS.md](../../AGENTS.md) for project-wide commands and guidelines.

## Overview

React TypeScript frontend built with Vite, using Tailwind CSS for styling.

## File Structure

- `src/` – Main application source
  - `entities/` – Domain entities (api/domain/ui pattern)
  - `features/` – Feature-specific components
  - `shared/` – Shared utilities and components
  - `pages/` – Page-level components
- `tests/` – Test utilities and setup

## Commands

```bash
cd frontend/app && npm install     # Install dependencies
cd frontend/app && npm run dev     # Start dev server
cd frontend/app && npm run build   # Production build
cd frontend/app && npm run test    # Run unit tests
cd frontend/app && npm run test:e2e # Run E2E tests
cd frontend/app && npm run biome:fix # Format and lint
cd frontend/app && npm run codegen # Generate GraphQL types
```

## Coding Standards

See `dev/guidelines/frontend/` for detailed coding standards including:

- TypeScript conventions
- URL and path construction patterns
- Component patterns
- Type safety requirements

## See Also

### Guidelines

- `dev/guidelines/frontend/README.md` - Frontend coding standards index

### Knowledge (How the system works)

- `dev/knowledge/frontend/entities-structure.md` - Entity layer pattern (api/domain/ui)

### Guides (How to do X)

- `dev/guides/frontend/writing-unit-tests.md` - How to write unit tests for TypeScript functions
- `dev/guides/frontend/writing-component-tests.md` - How to write React component tests
