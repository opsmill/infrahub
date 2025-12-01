# AGENTS.md - Frontend

> See [root AGENTS.md](../../AGENTS.md) for project-wide commands and guidelines.

## Overview

React SPA with Apollo Client for GraphQL, Jotai for state management, and Tailwind CSS for styling.

## File Structure

- `src/`
  - `app/` – App configuration and providers
  - `pages/` – Route-based page components
  - `entities/` – Feature-specific components
  - `shared/` – Shared utilities and API clients
- `tests/e2e/` – Playwright E2E tests

## Commands

```bash
npm run dev            # Start dev server
npm run build          # Production build
npm run test           # Unit tests (Vitest)
npm run test:e2e       # E2E tests (Playwright)
npm run biome:fix      # Format and lint
npm run codegen        # Regenerate GraphQL types
```
