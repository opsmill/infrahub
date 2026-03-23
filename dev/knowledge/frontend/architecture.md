## Architecture

Feature-Sliced architecture using DDD/Hexagonal principles, where each feature keeps domain logic, data access, and UI strictly separated:

- **app/** - Application core (providers, routing, styles)
- **pages/** - Route-based page components
- **entities/** - Business domain modules (features)
- **shared/** - Shared utilities, components, APIs

Dependency rule: `app → pages → entities → shared` (unidirectional)

## File Structure

```text
src/
├── app/              # App setup: providers, router, styles
├── pages/            # Route handlers (one per page/route)
├── entities/         # Feature modules (DDD/Hexagonal inspired)
│   └── {feature}/    # Each entity follows DDD/Hexagonal principles:
│       ├── api/      # GraphQL/REST calls, data fetching (infrastructure layer)
│       ├── domain/   # Business logic, models, types (no React, no fetch, no external dependencies)
│       ├── ui/       # React components knows domain, not api (presentation layer)
│       ├── utils/    # Feature-specific utilities
│       └── stores.ts # Jotai state atoms
├── shared/
│   ├── api/          # GraphQL/REST clients
│   ├── components/   # Reusable UI components
│   ├── hooks/        # Shared React hooks
│   ├── stores/       # Global state atoms
│   └── utils/        # Utility functions
└── assets/           # Static files
```

## Generated Files (Do Not Edit)

- `src/shared/api/graphql/generated/` - GraphQL types
- `src/shared/api/rest/types.generated.ts` - REST types

Regenerate with `npm run codegen:graphql` or `npm run codegen:openapi`.
