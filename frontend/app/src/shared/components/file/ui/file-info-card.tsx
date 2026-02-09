import { UploadIcon } from "lucide-react";

import { Row } from "@/shared/components/container";
import { formatFileSize } from "@/shared/utils/common";
import { getFileIcon } from "@/shared/utils/file";

export interface FileInfoCardProps {
  fileName: string;
  fileSize?: number;
  contentType?: string;
  /** Called when the card is clicked to replace the file (upload form only) */
  onReplace?: () => void;
}

export function FileInfoCard({ fileName, fileSize, contentType, onReplace }: FileInfoCardProps) {
  const FileIconComponent = getFileIcon(contentType);

  const content = (
    <Row>
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
      {onReplace && <UploadIcon className="size-4 shrink-0 text-gray-400" />}
    </Row>
  );

  if (onReplace) {
    return (
      <button
        type="button"
        onClick={onReplace}
        className="w-full rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-left hover:border-gray-300 hover:bg-gray-100"
        title="Replace file"
      >
        {content}
      </button>
    );
  }

  return <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">{content}</div>;
}
