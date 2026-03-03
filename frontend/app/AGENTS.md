# AGENTS.md - Frontend

> See [root AGENTS.md](../../AGENTS.md) for project-wide commands and guidelines.

## Overview

React TypeScript frontend built with Vite, using Tailwind CSS for styling.

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

## See Also

### Guidelines (How to write code)

- `dev/guidelines/frontend/naming-conventions.md` - File naming patterns
- `dev/guidelines/frontend/typescript.md` - TypeScript and React patterns
- `dev/guidelines/frontend/styling.md` - Tailwind CSS and CVA
- `dev/guidelines/frontend/object-forms.md` - react-hook-form patterns and focus management
- `dev/guidelines/frontend/url-construction.md` - URL building utilities

### Knowledge (How the system works)

- `dev/knowledge/frontend/react.md` - React 19 and React Compiler patterns
- `dev/knowledge/frontend/architecture.md` - Project organization
- `dev/knowledge/frontend/entities-structure.md` - Entity layer pattern (api/domain/ui)
- `dev/knowledge/frontend/file-components.md` - DataViewer and file handling components

### Guides (How to do X)

- `dev/guides/frontend/writing-unit-tests.md` - Unit tests for TypeScript functions
- `dev/guides/frontend/writing-component-tests.md` - React component tests
- `dev/guides/frontend/writing-e2e-tests.md` - Playwright E2E tests
