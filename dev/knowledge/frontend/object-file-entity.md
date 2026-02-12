# Object File Entity — Full Code Reference

Reference implementation of the [entities structure pattern](entities-structure.md). Source: `frontend/app/src/entities/object-file/`

## api/get-object-file-from-api.ts

Raw REST call. Extends `ContextParams` to accept branch and time context:

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

## domain/object-file.query-keys.ts

Query key factory. Keys include branch and time context for cache isolation:

```typescript
export const objectFileQueryKeys = {
  all: ["object-file"] as const,
  file: (nodeId: string, branchName: string, atDate?: Date | null, contentType?: string) =>
    [...objectFileQueryKeys.all, "file", nodeId, branchName, atDate, contentType] as const,
} as const;
```

## domain/get-object-file.ts

Business logic: URL generation, binary detection, base64 encoding. Extends `ContextParams` to propagate context through the call chain:

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

## domain/get-object-file.query.ts

React Query hook. `useGetObjectFile` resolves branch and time context internally so consumers only pass `nodeId` and `contentType`:

```typescript
import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetObjectFileParams,
  getObjectFile,
} from "@/entities/object-file/domain/get-object-file";
import { objectFileQueryKeys } from "@/entities/object-file/domain/object-file.query-keys";

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

## ui/object-file.tsx

React component. Uses domain hooks only — never calls API directly:

```typescript
import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerLinkButton } from "@/shared/components/data-viewer/data-viewer-action-button";
import { DataViewerCopyButton } from "@/shared/components/data-viewer/data-viewer-copy-button";
import { DataViewerDownloadButton } from "@/shared/components/data-viewer/data-viewer-download-button";
import type { DataViewerContentType } from "@/shared/components/data-viewer/types";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  getObjectFileDownloadUrl,
  getObjectFileRawUrl,
} from "@/entities/object-file/domain/get-object-file";
import { useGetObjectFile } from "@/entities/object-file/domain/get-object-file.query";

export interface ObjectFileProps {
  nodeId: string;
  fileName: string;
  contentType?: DataViewerContentType;
  className?: string;
}

export function ObjectFile({ nodeId, fileName, contentType, className }: ObjectFileProps) {
  const { currentBranch } = useCurrentBranch();
  const { data: content, isPending, error } = useGetObjectFile({ nodeId, contentType });

  if (isPending) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <NoDataFound message={error.message} />;
  }

  if (!content) {
    return <NoDataFound message="File content is empty" />;
  }

  const rawUrl = getObjectFileRawUrl(nodeId, currentBranch.name);
  const downloadUrl = getObjectFileDownloadUrl(nodeId, currentBranch.name);

  return (
    <DataViewer
      data={content}
      contentType={contentType}
      className={className}
      actions={
        <>
          <DataViewerLinkButton href={rawUrl} target="_blank" rel="noopener noreferrer">
            Raw
          </DataViewerLinkButton>
          <DataViewerDownloadButton
            data={content}
            fileName={fileName}
            contentType={contentType}
            downloadUrl={downloadUrl}
          />
          <DataViewerCopyButton value={content} />
        </>
      }
    />
  );
}
```
