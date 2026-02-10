import { UploadIcon } from "lucide-react";
import { Button, FileTrigger, type FileTriggerProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { Row } from "@/shared/components/container";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames, formatFileSize } from "@/shared/utils/common";
import { getFileIcon } from "@/shared/utils/file";

export interface FileInfoCardProps {
  fileName: string;
  fileSize?: number;
  contentType?: string;
  onFileSelect?: (file: File) => void;
}

export function FileInfoCard({ fileName, fileSize, contentType, onFileSelect }: FileInfoCardProps) {
  const FileIconComponent = getFileIcon(contentType);

  const content = (
    <Row className="overflow-hidden">
      <FileIconComponent className="size-5 shrink-0 text-gray-500" />
      <div className="min-w-0 flex-1 truncate">
        <p className="truncate font-medium text-gray-900 text-sm">{fileName}</p>
        {(fileSize !== undefined || contentType) && (
          <p className="mt-0.5 text-gray-500 text-xs">
            {[fileSize !== undefined && formatFileSize(fileSize), contentType]
              .filter(Boolean)
              .join(" • ")}
          </p>
        )}
      </div>
    </Row>
  );

  if (onFileSelect) {
    const handleSelect: FileTriggerProps["onSelect"] = (files) => {
      const file = files?.[0];
      if (file) {
        onFileSelect(file);
      }
    };

    return (
      <FileTrigger onSelect={handleSelect}>
        <Button
          className={classNames(
            inputStyle,
            focusVisibleStyle,
            "gap-2 bg-gray-50 px-3 text-left",
            "hover:border-gray-300 hover:bg-gray-100"
          )}
        >
          {content}
          <UploadIcon className="ml-auto size-4 shrink-0 text-gray-400" />
        </Button>
      </FileTrigger>
    );
  }

  return <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">{content}</div>;
}
