import type { LucideIcon } from "lucide-react";
import {
  FileIcon,
  FileImageIcon,
  FileJsonIcon,
  FileSpreadsheetIcon,
  FileTextIcon,
  FileTypeIcon,
} from "lucide-react";

import { FileActionMenu } from "@/shared/components/inputs/file-action-menu";

const FILE_TYPE_ICONS: Record<string, LucideIcon> = {
  "image/png": FileImageIcon,
  "image/jpeg": FileImageIcon,
  "image/gif": FileImageIcon,
  "image/svg+xml": FileImageIcon,
  "application/pdf": FileTypeIcon,
  "application/json": FileJsonIcon,
  "application/yaml": FileTextIcon,
  "text/markdown": FileTextIcon,
  "text/plain": FileTextIcon,
  "text/csv": FileSpreadsheetIcon,
};

function formatFileSize(bytes: number | undefined): string {
  if (bytes === undefined || bytes === null) return "";
  if (bytes === 0) return "0 B";

  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const size = bytes / 1024 ** i;

  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

function getFileIcon(contentType: string | undefined): LucideIcon {
  if (!contentType) return FileIcon;
  return FILE_TYPE_ICONS[contentType] ?? FileIcon;
}

export interface ExistingFileData {
  id: string;
  display_label?: string;
  file_name?: string;
  file_size?: number;
  content_type?: string;
  storage_id?: string;
}

export interface StagedFileData {
  file: File;
}

export type FileData = ExistingFileData | StagedFileData;

export function isStagedFile(data: FileData): data is StagedFileData {
  return "file" in data;
}

export interface FileItemRowProps {
  file: FileData;
  canEdit?: boolean;
  canDelete?: boolean;
  onReplace?: () => void;
  onDelete?: () => void;
}

export function FileItemRow({
  file,
  canEdit = true,
  canDelete = true,
  onReplace,
  onDelete,
}: FileItemRowProps) {
  const isStaged = isStagedFile(file);

  const fileName = isStaged
    ? file.file.name
    : (file.file_name ?? file.display_label ?? "Unnamed file");
  const fileSize = isStaged ? file.file.size : file.file_size;
  const contentType = isStaged ? file.file.type : file.content_type;
  const storageId = isStaged ? undefined : file.storage_id;

  const IconComponent = getFileIcon(contentType);

  return (
    <div
      className="flex items-center gap-2 rounded-md border border-gray-200 bg-white px-3 py-2"
      data-testid={`file-item-row-${isStaged ? "staged" : file.id}`}
    >
      <IconComponent className="size-4 shrink-0 text-gray-500" />

      <span className="flex-1 truncate text-gray-700 text-sm">{fileName}</span>

      {fileSize !== undefined && (
        <span className="text-gray-500 text-xs">{formatFileSize(fileSize)}</span>
      )}

      {isStaged && (
        <span className="rounded bg-yellow-100 px-1.5 py-0.5 text-xs text-yellow-800">Pending</span>
      )}

      <FileActionMenu
        fileName={fileName}
        storageId={storageId}
        canEdit={canEdit}
        canDelete={canDelete}
        onReplace={onReplace}
        onDelete={onDelete}
      />
    </div>
  );
}
