# Object file entity — code reference

Implementation of the [entities structure pattern](entities-structure.md). Source: `frontend/app/src/entities/nodes/object-file/`

The layer boundaries (api → domain → ui, context propagation, query-key composition) are the parts to copy. The folder layout is not: this entity keeps its use-case at `domain/get-object-file.ts` (flat `domain/` root), which predates the `domain/use-cases/` and `domain/model/` rule in [entities-structure.md](entities-structure.md) and is pending migration.

## Layout

```text
object-file/
├── api/
│   └── get-object-file-from-api.ts    # Raw REST call
├── domain/
│   └── get-object-file.ts             # Use-case + URL helpers (flat root, pending use-cases/ migration)
└── ui/
    ├── object-file.tsx                # <ObjectFile /> viewer component
    └── queries/
        ├── get-object-file.query.ts   # TanStack Query options + hook
        └── object-file.query-keys.ts  # Query-key factory
```

## api/get-object-file-from-api.ts

Raw REST call to `/api/storage/files/{node_id}` through the typed `apiClient`. Params extend `ContextParams` (`branchName`, `atDate?`) so branch and time context flow into the request:

```typescript
export interface GetObjectFileFromApiParams extends ContextParams {
  nodeId: string;
  parseAs?: "text" | "arrayBuffer";
}
```

Behavior:

- Sends `branch: branchName`, `at: atDate?.toISOString()`, and `preview: true` as query params.
- `parseAs` defaults to `"text"`; the domain layer passes `"arrayBuffer"` for binary content types.

## ui/queries/object-file.query-keys.ts

Query-key factory. Keys are not a standalone root: they compose on the parent `object` entity's context-scoped keys, so invalidating an object context also drops its file caches. Both helpers take a params object, not positional arguments:

```typescript
export const objectFileQueryKeys = {
  all: (context: ContextParams) =>
    [...objectQueryKeys.allWithContext(context), "object-file"] as const,
  file: ({ branchName, atDate, nodeId, contentType }: GetObjectFileParams) =>
    [...objectFileQueryKeys.all({ branchName, atDate }), "file", nodeId, contentType] as const,
} as const;
```

`objectQueryKeys` comes from `entities/nodes/object/ui/queries/object.query-keys.ts`.

## domain/get-object-file.ts

Use-case and URL helpers. `GetObjectFileParams extends ContextParams` and adds `nodeId: string` and `contentType?: string`.

- `getObjectFile(params): Promise<string>`: fetches through `getObjectFileFromApi`. Binary content types (`isBinaryContentType`) are fetched as `arrayBuffer` and returned base64-encoded via `arrayBufferToBase64`; everything else returns the text body. API errors are thrown.
- `getObjectFileDownloadUrl(urlParams)`: builds the direct storage URL from `INFRAHUB_API_SERVER_URL` (not through `apiClient`) with `branch` and, when set, `at` query params.
- `getObjectFileRawUrl(urlParams)`: the download URL plus `&preview=true`, so the browser renders the content instead of downloading it.

```typescript
export type GetObjectFileUrlParams = Pick<GetObjectFileParams, "nodeId" | "branchName" | "atDate">;

export function getObjectFileDownloadUrl({
  nodeId,
  branchName,
  atDate,
}: GetObjectFileUrlParams): string {
  const params = new URLSearchParams({ branch: branchName });
  if (atDate) {
    params.append("at", atDate.toISOString());
  }
  return `${INFRAHUB_API_SERVER_URL}/api/storage/files/${nodeId}?${params}`;
}

export function getObjectFileRawUrl(urlParams: GetObjectFileUrlParams): string {
  return `${getObjectFileDownloadUrl(urlParams)}&preview=true`;
}
```

## ui/queries/get-object-file.query.ts

TanStack Query integration:

- `getObjectFileQueryOptions(params: GetObjectFileParams)`: wraps `getObjectFile(params)` with `objectFileQueryKeys.file(params)`. No `enabled` guard — callers render the component only when a `nodeId` exists.
- `useGetObjectFile(params, config?)`: resolves context internally (`useCurrentBranch()` for the branch, `datetimeAtom` for the time), so consumers pass only the non-context params:

```typescript
export function useGetObjectFile(
  params: Omit<GetObjectFileParams, keyof ContextParams>,
  config?: QueryConfig<typeof getObjectFileQueryOptions>
) {
```

## ui/object-file.tsx

`<ObjectFile />` renders a file inside the shared `DataViewer`. Props: `nodeId`, `fileName`, `contentType?` (`DataViewerContentType`), `className?`. It fetches through the domain use-case via `useGetObjectFile` — never the API layer directly.

Render states:

- Pending: `LoadingIndicator`
- Error: `NoDataFound` with the error message
- Empty data: returns `null`
- Data: `DataViewer` with `title={fileName}` and three actions — a "Raw" link (`getObjectFileRawUrl`), a download button (`getObjectFileDownloadUrl`), and a copy button rendered only for copyable content:

```typescript
{isCopyableContentType(contentType) && <DataViewerCopyButton data={data} />}
```

The URL helpers need the same context the hook resolves internally, so the component also reads `useCurrentBranch()` and `datetimeAtom` to build `{ nodeId, branchName: currentBranch.name, atDate }` for `getObjectFileRawUrl` and `getObjectFileDownloadUrl`.
