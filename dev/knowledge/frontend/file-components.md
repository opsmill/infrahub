# File Components

Location: `frontend/app/src/`

File handling in Infrahub follows a layered architecture with `DataViewer` as the core rendering component and entity-specific wrappers for different file sources.

## Architecture Overview

```text
Entity Wrappers (fetch data, handle loading/errors)
    ObjectFile        ArtifactFile        GraphqlQueryViewerCard
    (nodeId)          (storageId)         (query)
         \                 |                   /
          \                |                  /
           v               v                 v
                      DataViewer
          (renders content based on MIME type)
```

## Core Component: DataViewer

Location: `shared/components/data-viewer/`

Universal content viewer that renders data based on MIME type. Handles text, images, PDFs, and provides a fallback for unsupported types.

### Files

| File | Purpose |
|------|---------|
| `data-viewer.tsx` | Main component with content type routing |
| `types.ts` | Type definitions and MIME type utilities |
| `data-viewer-action-button.tsx` | Styled button/link components |
| `data-viewer-copy-button.tsx` | Copy to clipboard action (entity wrappers render it only when `isCopyableContentType` returns `true`) |
| `data-viewer-download-button.tsx` | File download action |
| `data-viewer.styles.ts` | Shared styling |

### Supported Content Types

| Category | MIME Types | Rendering |
|----------|------------|-----------|
| Code/Text | `application/json`, `application/yaml`, `application/x-yaml`, `application/hcl`, `application/graphql`, `application/xml`, `application/javascript`, `application/typescript`, `application/x-sh`, `application/x-python`, `application/toml`, `application/x-toml`, `text/plain` | Syntax-highlighted via `CodeViewer` |
| Markdown | `text/markdown` | `MarkdownViewer` with view/raw toggle |
| CSV | `text/csv` | `CsvTable` component |
| SVG | `image/svg+xml` | `Svg` component |
| Images | `image/png`, `image/jpeg`, `image/gif`, `image/webp`, `image/bmp`, `image/x-icon` | Native `<img>` with base64 data URL |
| PDF | `application/pdf` | Embedded `<iframe>` with base64 |
| Other text | Any other `text/*` type | Plain text via `CodeViewer` |
| Other | Unsupported non-`text/*` types | Fallback message |

### Usage

```tsx
import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerCopyButton } from "@/shared/components/data-viewer/data-viewer-copy-button";
import { DataViewerDownloadButton } from "@/shared/components/data-viewer/data-viewer-download-button";

<DataViewer
  data={content}
  contentType="application/json"
  title="Config Preview"
  actions={
    <>
      <DataViewerDownloadButton data={content} fileName="config.json" contentType="application/json" />
      <DataViewerCopyButton data={content} />
    </>
  }
/>
```

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `data` | `string` | Yes | Content to display (base64 for binary) |
| `contentType` | `DataViewerContentType` | No | MIME type (default: `text/plain`) |
| `title` | `string` | No | Header title (default: "Preview") |
| `actions` | `ReactNode` | No | Action buttons slot |
| `className` | `string` | No | Additional CSS classes |

## Entity Wrappers

### ObjectFile

Location: `entities/nodes/object-file/ui/object-file.tsx`

Displays file content for `CoreFileObject` nodes. Handles data fetching, loading states, and binary/text detection.

```tsx
import { ObjectFile } from "@/entities/nodes/object-file/ui/object-file";

<ObjectFile
  nodeId="abc-123"
  fileName="config.yaml"
  contentType="application/yaml"
/>
```

**Data Flow:**
1. `ObjectFile` calls `useGetObjectFile` hook
2. Hook uses `getObjectFile` domain function
3. Domain calls `getObjectFileFromApi` (REST)
4. Binary files → ArrayBuffer → base64 encoding
5. Text files → returned as-is
6. Content passed to `DataViewer`

### ArtifactFile

Location: `entities/artifacts/ui/artifact-file.tsx`

Displays artifact content using storage ID. Same pattern as ObjectFile but uses artifact API endpoints.

```tsx
import { ArtifactFile } from "@/entities/artifacts/ui/artifact-file";

<ArtifactFile
  storageId="storage-abc-123"
  fileName="output.json"
  contentType="application/json"
/>
```

## File Input Components

### FileDropzone

Location: `shared/components/inputs/file-dropzone.tsx`

Drag-and-drop file upload using React Aria. Props extend React Aria `DropZoneProps` with a required `onFileSelect: (file: File) => void`.

```tsx
import { FileDropzone } from "@/shared/components/inputs/file-dropzone";

<FileDropzone onFileSelect={(file) => handleFile(file)} />
```

### FileInfoCard

Location: `shared/components/file/file-info-card.tsx`

Displays file metadata (name, size, type) with appropriate icon. When `onFileSelect` is provided, the card becomes a file-picker button so the user can replace the file.

```tsx
import { FileInfoCard } from "@/shared/components/file/file-info-card";

<FileInfoCard
  fileName="document.pdf"
  fileSize={1024000}
  contentType="application/pdf"
  onFileSelect={(file) => handleFile(file)}
/>
```

### FileField

Location: `shared/components/form/fields/file.field.tsx`

Form field that combines FileDropzone and FileInfoCard for file upload forms.

## Utility Functions

Location: `shared/utils/file.ts`

| Function | Purpose |
|----------|---------|
| `getFileIcon(contentType)` | Returns Lucide icon based on MIME type |
| `isBinaryContentType(contentType)` | Returns `true` for images (except SVG) and PDFs |
| `isCopyableContentType(contentType)` | Returns `true` for non-binary types; gates rendering of the copy button |
| `arrayBufferToBase64(buffer)` | Converts ArrayBuffer to base64 string |

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/storage/files/{node_id}?preview=true` | CoreFileObject content rendered inline (used by the viewer fetch and the raw link) |
| `GET /api/storage/files/{node_id}` | CoreFileObject download |
| `GET /api/storage/object/{identifier}` | Artifact content |

## Related Files

**DataViewer:**
- `shared/components/data-viewer/` - Core viewer components

**Entity Wrappers:**
- `entities/nodes/object-file/` - ObjectFile entity (api/domain/ui)
- `entities/artifacts/` - Artifact entity (api/domain/ui)

**Input Components:**
- `shared/components/inputs/file-dropzone.tsx` - Upload dropzone
- `shared/components/file/file-info-card.tsx` - File metadata card
- `shared/components/form/fields/file.field.tsx` - Form field

**Rendering Dependencies:**
- `shared/components/editor/code/code-viewer.tsx` - Syntax highlighting
- `shared/components/editor/markdown/markdown-viewer.tsx` - Markdown render
- `shared/components/editor/csv-table.tsx` - CSV table
- `shared/components/display/svg.tsx` - SVG display

**Utilities:**
- `shared/utils/file.ts` - File utilities
- `shared/components/download.tsx` - Safe download component
