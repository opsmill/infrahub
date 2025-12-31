import type { LucideIcon } from "lucide-react";
import {
  FileIcon,
  FileImageIcon,
  FileJsonIcon,
  FileSpreadsheetIcon,
  FileTextIcon,
  FileTypeIcon,
  LockIcon,
} from "lucide-react";

import type { FileRelationshipOneData } from "@/entities/nodes/object/ui/object-details/object-data-display/types/file-types";

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

interface FileCardProps {
  file: FileRelationshipOneData;
  onClick: () => void;
}

export function FileCard({ file, onClick }: FileCardProps) {
  const fileNode = file.node;

  if (!fileNode) {
    return null;
  }

  const fileName = fileNode.file_name?.value ?? fileNode.name?.value ?? "Unnamed file";
  const fileSize = fileNode.file_size?.value;
  const contentType = fileNode.content_type?.value;
  const isProtected = file.properties?.is_protected;
  const IconComponent = getFileIcon(contentType);

  return (
    <div className="flex items-center gap-2 py-1" data-testid={`file-card-${fileNode.id}`}>
      <IconComponent className="size-4 shrink-0 text-gray-500" />

      <button
        type="button"
        onClick={onClick}
        className="truncate text-gray-700 text-sm leading-none underline hover:text-gray-800"
      >
        {fileName}
      </button>

      <span className="text-gray-500 text-xs leading-none">{formatFileSize(fileSize)}</span>

      {isProtected && <LockIcon className="size-3.5 shrink-0 text-gray-500" />}
    </div>
  );
}
