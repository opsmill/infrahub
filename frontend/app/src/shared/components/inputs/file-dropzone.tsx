import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import type { DropEvent, FileDropItem } from "react-aria";
import { DropZone, FileTrigger, Pressable } from "react-aria-components";

import { classNames } from "@/shared/utils/common";

export interface FileDropzoneProps {
  onFileSelect: (file: File) => void;
  accept?: string[];
  maxSize?: number;
  disabled?: boolean;
  className?: string;
}

export function FileDropzone({
  onFileSelect,
  accept,
  disabled,
  className,
}: FileDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDrop = async (e: DropEvent) => {
    const fileItems = e.items.filter((item) => item.kind === "file") as FileDropItem[];
    if (fileItems.length > 0) {
      const file = await fileItems[0].getFile();
      onFileSelect(file);
    }
  };

  const handleSelect = (files: FileList | null) => {
    const file = files?.[0];
    if (file) {
      onFileSelect(file);
    }
  };

  return (
    <DropZone
      onDrop={handleDrop}
      onDropEnter={() => setIsDragOver(true)}
      onDropExit={() => setIsDragOver(false)}
      isDisabled={disabled}
      className={classNames(
        "flex w-full flex-col items-center justify-center rounded-md border p-6 transition-colors",
        isDragOver && "border-custom-blue-500 bg-gray-100",
        !isDragOver && "border-gray-300 hover:border-custom-blue-500",
        disabled && "cursor-not-allowed opacity-50",
        className
      )}
    >
      <FileTrigger onSelect={handleSelect} acceptedFileTypes={accept}>
        <Pressable>
          <div className="flex w-full cursor-pointer flex-col items-center justify-center">
            <Icon
              icon={isDragOver ? "mdi:file-upload" : "mdi:cloud-upload-outline"}
              className={classNames(
                "mb-2 text-4xl",
                isDragOver ? "text-custom-blue-500" : "text-gray-400"
              )}
            />
            <p className="text-gray-600 text-sm">
              {isDragOver ? "Drop the file here..." : "Drag and drop a file here, or click to select"}
            </p>
            <p className={classNames("mt-1 text-xs", isDragOver ? "invisible" : "text-gray-400")}>
              PDF, YAML, JSON, TXT, CSV, images, and more
            </p>
            <p className={classNames("mt-0.5 text-xs", isDragOver ? "invisible" : "text-gray-400")}>
              Max file size: 10MB
            </p>
          </div>
        </Pressable>
      </FileTrigger>
    </DropZone>
  );
}
