# File Components

Location: `frontend/app/src/shared/components/file/`

Shared components for displaying and uploading files. Used by both artifacts and CoreFileObject nodes.

## Components Overview

| Component | Purpose | Location |
|-----------|---------|----------|
| `FileViewer` | Renders file preview based on content type | `file-viewer.tsx` |
| `FileViewerFallback` | Fallback UI for unsupported file types | `file-viewer.tsx` |
| `FileInfoCard` | Displays file metadata (name, size, type) | `file-info-card.tsx` |
| `FilePreviewCard` | Combines FileInfoCard + FileViewer | `file-preview-card.tsx` |
| `FileDropzone` | Drag-and-drop file upload area | `../inputs/file-dropzone.tsx` |

## FileViewer

Unified file preview component that renders different file types appropriately.

### Supported Content Types

| Category | MIME Types | Rendering |
|----------|-----------|-----------|
| Text-based | `application/json`, `application/yaml`, `application/xml`, `text/plain`, `text/markdown`, `text/csv`, `image/svg+xml` | Syntax-highlighted via `DataViewer` |
| Images | `image/*` (except SVG) | Native `<img>` element |
| PDF | `application/pdf` | Embedded `<iframe>` |
| Other | Any unsupported type | `FileViewerFallback` with download link |

### Usage

```tsx
import { FileViewer } from "@/shared/components/file/file-viewer";
import { CONFIG } from "@/shared/config/config";

// Basic usage
<FileViewer
  url="/api/files/config.json"
  fileName="config.json"
  contentType="application/json"
/>

// With artifact storage
<FileViewer
  url={CONFIG.ARTIFACTS_CONTENT_URL(storageId)}
  fileName="artifact.yaml"
  contentType="application/yaml"
/>
```

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `url` | `string` | Yes | URL to fetch file content |
| `fileName` | `string` | Yes | File name for download/display |
| `contentType` | `string` | No | MIME type for rendering strategy |

## FileInfoCard

Displays file metadata in a compact card format with optional replace action.

### Usage

```tsx
import { FileInfoCard } from "@/shared/components/file/file-info-card";

<FileInfoCard
  fileName="document.pdf"
  fileSize={1024000}
  contentType="application/pdf"
  onReplace={() => handleReplace()}
/>
```

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `fileName` | `string` | Yes | File name to display |
| `fileSize` | `number` | No | File size in bytes (formatted automatically) |
| `contentType` | `string` | No | MIME type (shows icon based on type) |
| `onReplace` | `() => void` | No | Callback for replace action |

## FilePreviewCard

Combines `FileInfoCard` and `FileViewer` for complete file display. Used in object details views.

### Usage

```tsx
import { FilePreviewCard } from "@/entities/nodes/object/ui/object-details/file-preview-card";

<FilePreviewCard
  storageId="abc-123"
  fileName="config.yaml"
  fileSize={2048}
  contentType="application/yaml"
/>
```

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `storageId` | `string` | No | Storage ID for file URL generation |
| `fileName` | `string` | Yes | File name |
| `fileSize` | `number` | No | File size in bytes |
| `contentType` | `string` | No | MIME type |

## FileDropzone

Drag-and-drop file upload component using React Aria.

### Usage

```tsx
import { FileDropzone } from "@/shared/components/inputs/file-dropzone";

<FileDropzone
  onFileSelect={(file) => handleFile(file)}
  accept={["image/*", ".pdf"]}
  hasError={!!validationError}
/>
```

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `onFileSelect` | `(file: File) => void` | Yes | Callback when file is selected |
| `accept` | `string[]` | No | Accepted file types (MIME or extensions) |
| `maxSize` | `number` | No | Max file size in bytes |
| `disabled` | `boolean` | No | Disable the dropzone |
| `hasError` | `boolean` | No | Show error state (red border) |

## Integration Examples

### Artifact Details

```tsx
// entities/artifacts/ui/artifact-details.tsx
import { FileViewer } from "@/shared/components/file/file-viewer";
import { CONFIG } from "@/shared/config/config";

<FileViewer
  url={CONFIG.ARTIFACTS_CONTENT_URL(artifact.storage_id.value)}
  fileName={`${artifactId}.${extension}`}
  contentType={artifact.content_type.value}
/>
```

### CoreFileObject Details

```tsx
// entities/nodes/object/ui/object-details/file-attachment-details.tsx
import { FilePreviewCard } from "./file-preview-card";

<FilePreviewCard
  storageId={objectData.storage_id?.value}
  fileName={objectData.file_name?.value}
  fileSize={objectData.file_size?.value}
  contentType={objectData.file_type?.value}
/>
```

### File Upload Form

```tsx
// shared/components/form/core-file-form.tsx
import { FileDropzone } from "@/shared/components/inputs/file-dropzone";
import { FileInfoCard } from "@/shared/components/file/file-info-card";

{selectedFile ? (
  <FileInfoCard
    fileName={selectedFile.name}
    fileSize={selectedFile.size}
    contentType={selectedFile.type}
    onReplace={handleReplace}
  />
) : (
  <FileDropzone onFileSelect={handleFileSelect} hasError={!!error} />
)}
```

## URL Generation

Use `CONFIG.ARTIFACTS_CONTENT_URL(storageId)` to generate file URLs:

```tsx
import { CONFIG } from "@/shared/config/config";

const fileUrl = CONFIG.ARTIFACTS_CONTENT_URL(storageId);
// Returns: /api/storage/object/{storageId}
```

## Related Files

- `shared/components/file/file-viewer.tsx` - Main viewer component
- `shared/components/file/file-info-card.tsx` - Metadata card
- `shared/components/inputs/file-dropzone.tsx` - Upload dropzone
- `shared/components/data-viewer/data-viewer.tsx` - Text content rendering
- `shared/utils/file.ts` - File utility functions (icons, formatting)
- `entities/nodes/object/ui/object-details/file-preview-card.tsx` - Combined preview
- `entities/nodes/object/ui/object-details/file-attachment-details.tsx` - File object details
- `entities/artifacts/ui/artifact-details.tsx` - Artifact file display
