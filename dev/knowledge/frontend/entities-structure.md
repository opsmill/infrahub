# Frontend Entities Structure

Location: `frontend/app/src/entities/`

## Pattern Overview

Each entity represents a domain concept (artifacts, branches, tasks, nodes, etc.). The structure follows a Hexagonal architecture, adapted to frontend constraints:

- **domain/**: is the core and is framework-agnostic
- **api/**: acts as outbound adapters (infrastructure)
- **ui/**: acts as inbound adapters (delivery)
- Dependencies always point inward toward the domain

The goal is to isolate business rules from transport (API) and presentation (UI), while keeping the structure pragmatic for frontend development.

## Folder Structure

```text
entities/<entity-name>/
├── api/       # Raw API calls (REST or GraphQL)
├── domain/    # Business logic, transformations
├── ui/        # React components
├── types.ts   # Domain types & contracts
├── constants.ts
└── stores.ts  # Jotai atoms (if needed)
```

## Layer Responsibilities

### api/

Implements ports required by the domain to communicate with the outside world. Responsibilities:

- Raw HTTP / GraphQL calls
- No business logic
- No UI assumptions
- No transformations beyond transport-level needs
- Can be replaced without touching UI or domain

#### REST Example

`api/generate-artifact-from-api.ts`

```typescript
export function generateArtifactFromApi({ artifactDefinitionId, branchName }) {
  return apiClient.POST("/api/artifact/generate/{artifact_definition_id}", {
    params: { path: { artifact_definition_id: artifactDefinitionId } }
  });
}
```

#### GraphQL Example

Use `gql.tada` for type-safe GraphQL queries and mutations. Import `graphql` to define queries and `VariablesOf` to extract variable types.

`api/create-branch-from-api.ts`

```typescript
import { graphql, type VariablesOf } from "gql.tada";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";

const BRANCH_CREATE = graphql(`
  mutation BRANCH_CREATE($name: String!, $description: String) {
    BranchCreate(data: { name: $name, description: $description }) {
      object {
        id
        name
      }
    }
  }
`);

export type CreateBranchFromApiParams = VariablesOf<typeof BRANCH_CREATE>;

export function createBranchFromApi(params: CreateBranchFromApiParams) {
  return graphqlClient.mutate({
    mutation: BRANCH_CREATE,
    variables: params,
  });
}
```

Key points:
- Define queries/mutations with `graphql()` template literal
- Use `VariablesOf<typeof QUERY>` to get typed parameters
- Use `graphqlClient.query()` for queries, `graphqlClient.mutate()` for mutations

### domain/

Business logic layer. Responsibilities:

- Business rules
- Application use cases
- Data transformation into domain-friendly shapes
- Orchestration of workflows
- React Query hooks (`.query.ts`, `.mutation.ts`)
- Query key factories (`.query-keys.ts`)

Example: `domain/generate-artifact.ts`

```typescript
export const getBranchDetails: GetBranchDetails = async (params) => {
  const { data, errors } = await getBranchDetailsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const branch = data?.InfrahubBranch?.edges[0]?.node;

  if (!branch) throw new Error(`Branch ${params.branchName} not found`);

  return mapToBranchDetail(branch);
};
```

### ui/

This layer adapts user intent into domain interactions. Responsibilities:

- React components
- View-specific logic
- Composition of domain hooks
- Presentation concerns only

Rules:

- Can import from domain/ and types.ts
- Must NEVER call api/ directly

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

## Import Aliases

Use `@/entities/<entity-name>` for imports:

```typescript
import { ArtifactStatusBadge } from "@/entities/artifacts/ui/artifact-status-badge";
import { generateArtifact } from "@/entities/artifacts/domain/generate-artifact";
import type { ArtifactObject } from "@/entities/artifacts/types";
```
