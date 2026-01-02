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
        "flex flex-col items-center justify-center rounded-md border-2 border-dashed p-6 transition-colors cursor-pointer",
        isDragActive && !isDragReject && "border-custom-blue-500 bg-custom-blue-50",
        isDragReject && "border-red-500 bg-red-50",
        !isDragActive && !isDragReject && "border-gray-300 hover:border-gray-400",
        disabled && "cursor-not-allowed opacity-50",
        className
      )}
    >
      <input {...getInputProps()} />
      <Icon
        icon={isDragActive ? "mdi:file-upload" : "mdi:cloud-upload-outline"}
        className={classNames(
          "text-4xl mb-2",
          isDragActive && !isDragReject && "text-custom-blue-500",
          isDragReject && "text-red-500",
          !isDragActive && "text-gray-400"
        )}
      />
      {isDragActive ? (
        <p className="text-sm text-gray-600">Drop the file here...</p>
      ) : (
        <>
          <p className="text-sm text-gray-600">Drag and drop a file here, or click to select</p>
          <p className="text-xs text-gray-400 mt-1">
            {maxSize ? `Max file size: ${Math.round(maxSize / 1024 / 1024)}MB` : ""}
          </p>
        </>
      )}
    </div>
  );
}
