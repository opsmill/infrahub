# Frontend Entities Structure

Location: `frontend/app/src/entities/`

## Pattern Overview

Each entity represents a domain concept (artifacts, branches, tasks, nodes, etc.) and follows a three-layer architecture:

```
entities/<entity-name>/
├── api/       # Raw API calls (REST or GraphQL)
├── domain/    # Business logic, transformations, React Query hooks
├── ui/        # React components
├── types.ts   # TypeScript types for this entity
├── constants.ts
└── stores.ts  # Jotai atoms (if needed)
```

## Layer Responsibilities

### api/

Raw data fetching. No business logic.

- REST calls using `apiClient` from `@/shared/api/rest/client`
- GraphQL queries using Handlebars templates
- Function naming: `get<Entity>FromApi`, `create<Entity>FromApi`

Example: `api/generate-artifact-from-api.ts`
```typescript
export function generateArtifactFromApi({ artifactDefinitionId, branchName }) {
  return apiClient.POST("/api/artifact/generate/{artifact_definition_id}", {
    params: { path: { artifact_definition_id: artifactDefinitionId } }
  });
}
```

### domain/

Business logic layer. Transforms API data for UI consumption.

- Wraps API calls with error handling
- React Query hooks (`.query.ts`, `.mutation.ts`)
- Query key factories (`.query-keys.ts`)
- Data transformations

Example: `domain/generate-artifact.ts`
```typescript
export const generateArtifact = async (params) => {
  const { error } = await generateArtifactFromApi(params);
  if (error) throw error;
};
```

### ui/

React components. Presentational and container components.

- Component naming: `kebab-case.tsx`
- Tests colocated: `component-name.test.tsx`
- Subdirectories for related components

Example: `ui/artifact-status-badge.tsx`
```typescript
export function ArtifactStatusBadge({ status }) {
  return <Badge variant={getVariant(status)}>{status}</Badge>;
}
```

## File Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| API function | `get-<entity>-from-api.ts` | `get-tasks-from-api.ts` |
| Domain function | `<action>-<entity>.ts` | `generate-artifact.ts` |
| Query hook | `<action>.query.ts` | `get-objects.query.ts` |
| Mutation hook | `<action>.mutation.ts` | `delete-objects.mutation.ts` |
| Query keys | `<entity>.query-keys.ts` | `object.query-keys.ts` |
| Component | `<entity>-<variant>.tsx` | `artifact-status-badge.tsx` |
| Test | `<filename>.test.ts(x)` | `get-objects.test.ts` |

## Current Entities

| Entity | Purpose |
|--------|---------|
| `artifacts` | Generated configuration files |
| `branches` | Git-like branch management |
| `nodes` | Core graph objects (largest entity) |
| `tasks` | Background job tracking |
| `schema` | Schema definitions |
| `proposed-changes` | Change request workflow |
| `diff` | Branch comparison |
| `groups` | Object grouping |
| `generators` | Artifact generators |
| `repository` | Git repository integration |
| `ipam` | IP address management |
| `resource-manager` | Resource allocation |
| `triggers` | Event triggers |
| `navigation` | App navigation state |
| `user-profile` | User settings |
| `config` | App configuration |
| `graphql` | GraphQL utilities |
| `homepage` | Dashboard widgets |
| `role-manager` | RBAC |

## Import Aliases

Use `@/entities/<entity-name>` for imports:

```typescript
import { ArtifactStatusBadge } from "@/entities/artifacts/ui/artifact-status-badge";
import { generateArtifact } from "@/entities/artifacts/domain/generate-artifact";
import type { ArtifactObject } from "@/entities/artifacts/types";
```

## Adding a New Entity

1. Create directory: `entities/<entity-name>/`
2. Add `types.ts` with TypeScript interfaces
3. Add `api/` with raw API calls
4. Add `domain/` with business logic and React Query hooks
5. Add `ui/` with React components
6. Add `constants.ts` if needed
