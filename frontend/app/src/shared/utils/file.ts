import type { LucideIcon } from "lucide-react";
import {
  FileIcon,
  FileImageIcon,
  FileJsonIcon,
  FileSpreadsheetIcon,
  FileTextIcon,
  FileTypeIcon,
} from "lucide-react";

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

export function getFileIcon(contentType: string | undefined): LucideIcon {
  if (!contentType) return FileIcon;
  return FILE_TYPE_ICONS[contentType] ?? FileIcon;
}
