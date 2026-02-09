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

## Branch & Date Context

Most entities need the current branch and optional time-machine date for queries. These are provided via shared types and injected at the query hook layer.

### ContextParams

Defined in `shared/api/types.ts`:

```typescript
export type BranchContextParams = {
  branchName: string;
};

export interface ContextParams extends BranchContextParams {
  atDate?: Date | null;
}
```

### Where context is stored

- **Branch:** `useCurrentBranch()` hook from `@/entities/branches/ui/branches-provider`
- **Date:** `datetimeAtom` Jotai atom from `@/shared/stores/time.atom`

### Where context is injected

The **query hook** (`.query.ts`) is the single injection point. It reads branch and date from global state and passes them down to `queryOptions` and the domain function. The public hook signature stays simple — callers never pass branch or date manually.

```typescript
// domain/get-object-file.query.ts
export function useGetObjectFile(
  params: { nodeId: string; contentType?: string },  // no context params here
  config?: QueryConfig<typeof getObjectFileQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();       // read branch
  const atDate = useAtomValue(datetimeAtom);           // read date

  return useQuery({
    ...getObjectFileQueryOptions({
      ...params,
      branchName: currentBranch.name,                  // inject
      atDate,                                          // inject
    }),
    ...config,
  });
}
```

### How context flows through layers

| Layer | What happens |
|-------|-------------|
| **Query hook** (`.query.ts`) | Reads `useCurrentBranch()` + `datetimeAtom`, injects into `queryOptions` |
| **Query keys** (`.query-keys.ts`) | Includes `branchName` and `atDate` for per-branch/date cache isolation |
| **Domain function** (`.ts`) | Params type extends `ContextParams`, passes them to the API layer |
| **API layer** (`-from-api.ts`) | Params type extends `ContextParams`, serializes to transport (`branch` query param, `at` as ISO string) |

## Complete Example: Object File Entity

The `object-file` entity demonstrates the full pattern including context flow.

### Structure

```text
entities/object-file/
├── api/
│   └── get-object-file-from-api.ts    # REST API call
├── domain/
│   ├── get-object-file.ts             # Business logic & URL helpers
│   ├── get-object-file.query.ts       # React Query hook (context injection point)
│   └── object-file.query-keys.ts      # Query key factory
└── ui/
    └── object-file.tsx                # React component
```

### api/get-object-file-from-api.ts

Raw REST call. Params extend `ContextParams` — context is serialized to query parameters:

```typescript
import { apiClient } from "@/shared/api/rest/client";
import type { ContextParams } from "@/shared/api/types";

export interface GetObjectFileFromApiParams extends ContextParams {
  nodeId: string;
  parseAs?: "text" | "arrayBuffer";
}

export function getObjectFileFromApi({
  nodeId,
  branchName,
  atDate,
  parseAs = "text",
}: GetObjectFileFromApiParams) {
  return apiClient.GET("/api/storage/files/{node_id}", {
    params: {
      path: { node_id: nodeId },
      query: {
        branch: branchName,
        at: atDate?.toISOString() ?? null,
        preview: true,
      },
    },
    parseAs,
  });
}
```

### domain/object-file.query-keys.ts

Query keys include branch and date for cache isolation:

```typescript
export const objectFileQueryKeys = {
  all: ["object-file"] as const,
  file: (nodeId: string, branchName: string, atDate?: Date | null, contentType?: string) =>
    [...objectFileQueryKeys.all, "file", nodeId, branchName, atDate, contentType] as const,
} as const;
```

### domain/get-object-file.ts

Business logic. Params extend `ContextParams` and pass context through to the API:

```typescript
import type { ContextParams } from "@/shared/api/types";
import { CONFIG } from "@/shared/config/config";
import { arrayBufferToBase64, isBinaryContentType } from "@/shared/utils/file";
import { getObjectFileFromApi } from "@/entities/object-file/api/get-object-file-from-api";

export interface GetObjectFileParams extends ContextParams {
  nodeId: string;
  contentType?: string;
}

export function getObjectFileDownloadUrl(nodeId: string, branchName: string): string {
  return CONFIG.FILE_BY_NODE_ID_URL(nodeId, branchName);
}

export function getObjectFileRawUrl(nodeId: string, branchName: string): string {
  return CONFIG.FILE_BY_NODE_ID_URL(nodeId, branchName, true);
}

export async function getObjectFile({
  nodeId,
  contentType,
  branchName,
  atDate,
}: GetObjectFileParams): Promise<string> {
  if (isBinaryContentType(contentType)) {
    const { data, error } = await getObjectFileFromApi({
      nodeId,
      branchName,
      atDate,
      parseAs: "arrayBuffer",
    });

    if (error) throw error;

    return arrayBufferToBase64(data as ArrayBuffer);
  }

  const { data, error } = await getObjectFileFromApi({ nodeId, branchName, atDate });

  if (error) throw error;

  return data as string;
}
```

### domain/get-object-file.query.ts

React Query hook — this is where context is injected from global state:

```typescript
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import type { QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type GetObjectFileParams, getObjectFile } from "./get-object-file";
import { objectFileQueryKeys } from "./object-file.query-keys";

export function getObjectFileQueryOptions({
  nodeId,
  contentType,
  branchName,
  atDate,
}: GetObjectFileParams) {
  return queryOptions({
    queryKey: objectFileQueryKeys.file(nodeId, branchName, atDate, contentType),
    queryFn: () => getObjectFile({ nodeId, contentType, branchName, atDate }),
    enabled: !!nodeId,
  });
}

export function useGetObjectFile(
  params: { nodeId: string; contentType?: string },
  config?: QueryConfig<typeof getObjectFileQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getObjectFileQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate,
    }),
    ...config,
  });
}
```

### Key Patterns Demonstrated

1. **ContextParams**: Domain and API param types extend `ContextParams` for consistent branch/date typing
2. **Context injection**: Query hooks read global state and inject it — callers never pass branch/date
3. **Cache isolation**: Query keys include branch and date so each combination gets its own cache entry
4. **api/**: Pure transport — serializes `branchName` → `branch` query param, `atDate` → ISO string
5. **domain/**: Business rules (URL generation, binary handling), passes context through to API
6. **ui/**: Imports from domain only, never from API directly
7. **Error handling**: Domain throws, UI catches via React Query
