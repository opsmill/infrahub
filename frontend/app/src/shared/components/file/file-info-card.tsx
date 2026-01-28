import { RefreshCwIcon } from "lucide-react";

import { formatFileSize } from "@/shared/utils/common";
import { getFileIcon } from "@/shared/utils/file";

export interface FileInfoCardProps {
  fileName: string;
  fileSize?: number;
  contentType?: string;
  /** Called when replace is clicked (upload form only) */
  onReplace?: () => void;
}

export function FileInfoCard({ fileName, fileSize, contentType, onReplace }: FileInfoCardProps) {
  const FileIconComponent = getFileIcon(contentType);

  return (
    <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
      <div className="flex items-center gap-2">
        <FileIconComponent className="size-5 shrink-0 text-gray-500" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-gray-900 text-sm">{fileName}</p>
          {(fileSize !== undefined || contentType) && (
            <p className="mt-0.5 text-gray-500 text-xs">
              {[fileSize !== undefined && formatFileSize(fileSize), contentType]
                .filter(Boolean)
                .join(" • ")}
            </p>
          )}
        </div>

        {onReplace && (
          <button
            type="button"
            onClick={onReplace}
            className="rounded p-1 text-gray-400 hover:text-gray-600"
            title="Replace file"
          >
            <RefreshCwIcon className="size-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
