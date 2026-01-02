import { LockIcon } from "lucide-react";

import { formatFileSize } from "@/shared/utils/common";
import { getFileIcon } from "@/shared/utils/file";

import type { FileRelationshipOneData } from "@/entities/nodes/object/ui/object-details/object-data-display/types/file-types";

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
