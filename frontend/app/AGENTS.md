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

## Code Style

### Components

```typescript
// ✅ Good - Typed props, functional component
interface NodeCardProps {
  node: Node;
  onSelect: (id: string) => void;
}

export function NodeCard({ node, onSelect }: NodeCardProps) {
  return (
    <div className="p-4 rounded-lg" onClick={() => onSelect(node.id)}>
      {node.display_label}
    </div>
  );
}

// ❌ Bad - Untyped, inline styles
export function NodeCard(props) {
  return <div style={{ padding: 16 }}>{props.node.display_label}</div>;
}
```

### GraphQL

```typescript
// ✅ Good - Use generated types
import type { GetNodesQuery } from "@/shared/api/graphql/generated";

const { data } = useQuery<GetNodesQuery>(GET_NODES);
```

### Naming Conventions

- **Components:** `PascalCase.tsx`
- **Hooks:** `useSomething.ts`
- **Utilities:** `camelCase.ts`
- **Constants:** `UPPER_SNAKE_CASE`

### Import Order (Biome enforced)

```typescript
import { useState } from "react";           // React
import { useQuery } from "@apollo/client";  // External packages
import { useConfig } from "@/config";       // Internal aliases
import { NodeCard } from "@/shared/...";    // Shared
import { useNodeData } from "@/entities/..."; // Entities
import "./styles.css";                      // Local
```

## Boundaries

### Always Do

- Run `npm run biome:fix` before committing
- Use TypeScript types for all props and state
- Use Tailwind classes (no inline styles)
- Use generated GraphQL types

### Ask First

- New dependencies
- New page routes
- GraphQL query changes affecting multiple components

### Never Do

- Edit files in `src/shared/api/graphql/generated/`
- Use `console.log` (use `console.error`, `warn`, `info`)
- Use `any` type without justification
