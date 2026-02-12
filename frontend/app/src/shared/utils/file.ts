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

export function isBinaryContentType(contentType?: string): boolean {
  if (!contentType) return false;

  // Images (except SVG which is text-based)
  if (contentType.startsWith("image/") && contentType !== "image/svg+xml") {
    return true;
  }

  // PDF
  if (contentType === "application/pdf") {
    return true;
  }

  return false;
}

export function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const binary = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");
  return btoa(binary);
}

export function isCopyableContentType(contentType?: string): boolean {
  if (!contentType) return true;
  return !isBinaryContentType(contentType);
}
