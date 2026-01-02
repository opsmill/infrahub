import { Icon } from "@iconify-icon/react";
import { useCallback } from "react";
import { useDropzone } from "react-dropzone";

import { classNames } from "@/shared/utils/common";

export interface FileDropzoneProps {
  onFileSelect: (file: File) => void;
  accept?: Record<string, string[]>;
  maxSize?: number;
  disabled?: boolean;
  className?: string;
}

export function FileDropzone({
  onFileSelect,
  accept,
  maxSize,
  disabled,
  className,
}: FileDropzoneProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (file) {
        onFileSelect(file);
      }
    },
    [onFileSelect]
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept,
    maxSize,
    disabled,
    multiple: false,
  });

  return (
    <div
      {...getRootProps()}
      className={classNames(
        "flex cursor-pointer flex-col items-center justify-center rounded-md border p-6 transition-colors",
        isDragActive && !isDragReject && "border-custom-blue-500 bg-gray-100",
        isDragReject && "border-red-500 bg-red-50",
        !isDragActive && !isDragReject && "border-gray-300 hover:border-custom-blue-500",
        disabled && "cursor-not-allowed opacity-50",
        className
      )}
    >
      <input {...getInputProps()} />
      <Icon
        icon={isDragActive ? "mdi:file-upload" : "mdi:cloud-upload-outline"}
        className={classNames(
          "mb-2 text-4xl",
          isDragActive && !isDragReject && "text-custom-blue-500",
          isDragReject && "text-red-500",
          !isDragActive && "text-gray-400"
        )}
      />
      <p className="text-gray-600 text-sm">
        {isDragActive ? "Drop the file here..." : "Drag and drop a file here, or click to select"}
      </p>
      <p className={classNames("mt-1 text-xs", isDragActive ? "invisible" : "text-gray-400")}>
        PDF, YAML, JSON, TXT, CSV, images, and more
      </p>
      <p className={classNames("mt-0.5 text-xs", isDragActive ? "invisible" : "text-gray-400")}>
        Max file size: 10MB
      </p>
    </div>
  );
}
