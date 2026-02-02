import { useRef } from "react";
import { useFormContext } from "react-hook-form";

import { FileInfoCard } from "@/shared/components/file/ui/file-info-card";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { FileDropzone } from "@/shared/components/inputs/file-dropzone";

export interface FileFieldProps {
  label?: string;
  required?: boolean;
  selectedFile: File | null;
  existingFile?: {
    fileName: string;
    fileSize?: number;
    contentType?: string;
  } | null;
  onFileSelect: (file: File) => void;
}

export function FileField({
  label = "File",
  required = false,
  selectedFile,
  existingFile,
  onFileSelect,
}: FileFieldProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { formState } = useFormContext();

  const hasFile = selectedFile !== null;
  const hasExistingFile = !!existingFile?.fileName;
  const showFileCard = hasFile || hasExistingFile;
  const showError = formState.submitCount > 0 && required && !hasFile;

  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) onFileSelect(file);
    event.target.value = "";
  };

  return (
    <div className="space-y-2">
      <LabelFormField label={label} required={required} />
      <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileInputChange} />
      {showFileCard ? (
        <FileInfoCard
          fileName={selectedFile?.name ?? existingFile?.fileName ?? ""}
          fileSize={selectedFile?.size ?? existingFile?.fileSize}
          contentType={selectedFile?.type || existingFile?.contentType}
          onReplace={() => fileInputRef.current?.click()}
        />
      ) : (
        <FileDropzone onFileSelect={onFileSelect} hasError={showError} />
      )}
      {showError && (
        <p className="text-red-600 text-sm" data-cy="field-error-message">
          {label} is required
        </p>
      )}
    </div>
  );
}
