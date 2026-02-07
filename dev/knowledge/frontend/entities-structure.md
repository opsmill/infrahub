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

## Complete Example: Object File Entity

The `object-file` entity demonstrates the full pattern for fetching and displaying file content.

### Structure

```text
entities/object-file/
├── api/
│   └── get-object-file-from-api.ts    # REST API call
├── domain/
│   ├── get-object-file.ts             # Business logic & URL helpers
│   ├── get-object-file.query.ts       # React Query hook
│   └── object-file.query-keys.ts      # Query key factory
└── ui/
    └── object-file.tsx                # React component
```

### api/get-object-file-from-api.ts

Raw REST call with no business logic:

```typescript
import { apiClient } from "@/shared/api/rest/client";

export interface GetObjectFileFromApiParams {
  nodeId: string;
  parseAs?: "text" | "arrayBuffer";
}

export function getObjectFileFromApi({ nodeId, parseAs = "text" }: GetObjectFileFromApiParams) {
  return apiClient.GET("/api/storage/files/{node_id}", {
    params: {
      path: { node_id: nodeId },
      query: { preview: true },
    },
    parseAs,
  });
}
```

### domain/object-file.query-keys.ts

Query key factory for cache management:

```typescript
export const objectFileQueryKeys = {
  all: ["object-file"] as const,
  file: (nodeId: string, contentType?: string) =>
    [...objectFileQueryKeys.all, "file", nodeId, contentType] as const,
} as const;
```

### domain/get-object-file.ts

Business logic: URL generation, binary detection, base64 encoding:

```typescript
import { CONFIG } from "@/shared/config/config";
import { arrayBufferToBase64, isBinaryContentType } from "@/shared/utils/file";
import { getObjectFileFromApi } from "@/entities/object-file/api/get-object-file-from-api";

export interface GetObjectFileParams {
  nodeId: string;
  contentType?: string;
}

export function getObjectFileDownloadUrl(nodeId: string): string {
  return CONFIG.FILE_BY_NODE_ID_URL(nodeId);
}

export function getObjectFileRawUrl(nodeId: string): string {
  return CONFIG.FILE_BY_NODE_ID_URL(nodeId, true);
}

export async function getObjectFile({ nodeId, contentType }: GetObjectFileParams): Promise<string> {
  if (!nodeId) throw new Error("Node ID is required");

  // Binary files need base64 encoding for display
  if (isBinaryContentType(contentType)) {
    const { data, error } = await getObjectFileFromApi({ nodeId, parseAs: "arrayBuffer" });
    if (error) throw error;
    return arrayBufferToBase64(data as ArrayBuffer);
  }

  const { data, error } = await getObjectFileFromApi({ nodeId });
  if (error) throw error;
  return data as string;
}
```

### domain/get-object-file.query.ts

React Query hook wrapping the domain function:

```typescript
import { queryOptions, useQuery } from "@tanstack/react-query";
import type { QueryConfig } from "@/shared/api/types";
import { getObjectFile, type GetObjectFileParams } from "./get-object-file";
import { objectFileQueryKeys } from "./object-file.query-keys";

export function getObjectFileQueryOptions({ nodeId, contentType }: GetObjectFileParams) {
  return queryOptions({
    queryKey: objectFileQueryKeys.file(nodeId, contentType),
    queryFn: () => getObjectFile({ nodeId, contentType }),
    enabled: !!nodeId,
  });
}

export function useGetObjectFile(
  params: GetObjectFileParams,
  config?: QueryConfig<typeof getObjectFileQueryOptions>
) {
  return useQuery({ ...getObjectFileQueryOptions(params), ...config });
}
```

### ui/object-file.tsx

React component using domain hooks (never calls API directly):

```typescript
import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerLinkButton } from "@/shared/components/data-viewer/data-viewer-action-button";
import { DataViewerCopyButton } from "@/shared/components/data-viewer/data-viewer-copy-button";
import { DataViewerDownloadButton } from "@/shared/components/data-viewer/data-viewer-download-button";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { getObjectFileDownloadUrl, getObjectFileRawUrl } from "@/entities/object-file/domain/get-object-file";
import { useGetObjectFile } from "@/entities/object-file/domain/get-object-file.query";

export interface ObjectFileProps {
  nodeId: string;
  fileName: string;
  contentType?: string;
  className?: string;
}

export function ObjectFile({ nodeId, fileName, contentType, className }: ObjectFileProps) {
  const { data: content, isPending, error } = useGetObjectFile({ nodeId, contentType });

  if (isPending) return <LoadingIndicator className="p-4" />;
  if (error) return <NoDataFound message={error.message} />;
  if (!content) return <NoDataFound message="File content is empty" />;

  return (
    <DataViewer
      data={content}
      contentType={contentType}
      className={className}
      actions={
        <>
          <DataViewerLinkButton href={getObjectFileRawUrl(nodeId)} target="_blank">
            Raw
          </DataViewerLinkButton>
          <DataViewerDownloadButton
            value={content}
            fileName={fileName}
            contentType={contentType}
            downloadUrl={getObjectFileDownloadUrl(nodeId)}
          />
          <DataViewerCopyButton value={content} />
        </>
      }
    />
  );
}
```

### Key Patterns Demonstrated

1. **api/**: Pure transport layer - just HTTP calls, no logic
2. **domain/**: Business rules (URL generation, binary handling), React Query hooks
3. **ui/**: Imports from domain only, never from API directly
4. **Query keys**: Factory pattern for consistent cache keys
5. **Error handling**: Domain throws, UI catches via React Query
